"""Order lifecycle: creation, pricing, status transitions, payments, serialization."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Iterable, Optional

from fastapi import HTTPException, status as http_status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import (
    Customer,
    MenuItem,
    Order,
    OrderItem,
    OrderStatusHistory,
    Payment,
    PaymentMethod,
    User,
)
from app.schemas import CartLineIn
from app.services import audit

MONEY = Decimal("0.01")

# Allowed status graph. Cancellation is possible until preparation finishes.
TRANSITIONS: dict[str, set[str]] = {
    "pending": {"confirmed", "cancelled"},
    "confirmed": {"preparing", "cancelled"},
    "preparing": {"completed", "cancelled"},
    "completed": set(),
    "cancelled": set(),
}

# Which statuses a role may set at all. Graph validity is checked separately so
# an authorised role attempting an impossible move (e.g. cancelling a completed
# order) receives 409, while an unauthorised role always receives 403.
ROLE_TARGETS: dict[str, set[str]] = {
    "manager": set(TRANSITIONS),
    "cashier": {"confirmed", "cancelled"},
    "chef": {"preparing", "completed"},
}


def money(value: Decimal | float | int) -> Decimal:
    return Decimal(str(value)).quantize(MONEY, rounding=ROUND_HALF_UP)


def _assert_staff_transition(user: User, previous: str, new: str) -> None:
    if new not in ROLE_TARGETS.get(user.role, set()):
        raise HTTPException(
            http_status.HTTP_403_FORBIDDEN,
            f"Role '{user.role}' cannot move an order from {previous} to {new}",
        )


def get_payment_method(db: Session, code: str) -> PaymentMethod:
    method = db.get(PaymentMethod, code)
    if not method or not method.is_active:
        raise HTTPException(http_status.HTTP_400_BAD_REQUEST, "Unsupported or inactive payment method")
    return method


def build_order_items(db: Session, lines: Iterable[CartLineIn], *, enforce_available: bool = True) -> tuple[list[tuple[MenuItem, CartLineIn]], Decimal]:
    """Validate every product server-side and compute the authoritative total."""
    seen: set[int] = set()
    resolved: list[tuple[MenuItem, CartLineIn]] = []
    total = Decimal("0")
    for line in lines:
        if line.item_id in seen:
            raise HTTPException(http_status.HTTP_400_BAD_REQUEST, "Duplicate menu item in cart")
        seen.add(line.item_id)
        item = db.get(MenuItem, line.item_id)
        if item is None:
            raise HTTPException(http_status.HTTP_400_BAD_REQUEST, f"Menu item {line.item_id} does not exist")
        if enforce_available and not item.is_available:
            raise HTTPException(
                http_status.HTTP_409_CONFLICT,
                f"'{item.item_name}' is currently unavailable",
            )
        if line.quantity < 1 or line.quantity > 99:
            raise HTTPException(http_status.HTTP_400_BAD_REQUEST, "Quantity must be between 1 and 99")
        total += money(item.price) * line.quantity
        resolved.append((item, line))
    return resolved, money(total)


def create_order(
    db: Session,
    *,
    lines: list[CartLineIn],
    customer_id: Optional[int],
    order_source: str,
    payment_method: str,
    order_notes: Optional[str] = None,
    raw_transcription: Optional[str] = None,
    confidence_score: Optional[Decimal] = None,
    idempotency_key: Optional[str] = None,
    idempotency_scope: Optional[str] = None,
) -> Order:
    if idempotency_key and idempotency_scope:
        idempotency_key = f"{idempotency_scope}:{idempotency_key}"
    if idempotency_key:
        existing = db.scalar(select(Order).where(Order.idempotency_key == idempotency_key))
        if existing:
            return existing

    method = get_payment_method(db, payment_method)
    resolved, total = build_order_items(db, lines)

    order = Order(
        customer_id=customer_id,
        status="pending",
        payment_status="pending" if method.code in ("cash", "pay_at_counter", "card") else "unpaid",
        payment_method=method.code,
        order_notes=order_notes,
        order_source=order_source,
        raw_transcription=raw_transcription,
        confidence_score=confidence_score,
        total_amount=total,
        idempotency_key=idempotency_key,
    )
    db.add(order)
    db.flush()

    for item, line in resolved:
        db.add(
            OrderItem(
                order_id=order.order_id,
                item_id=item.item_id,
                item_name_snapshot=item.item_name,
                quantity=line.quantity,
                unit_price=money(item.price),
                special_instructions=line.special_instructions,
            )
        )

    db.add(
        Payment(
            order_id=order.order_id,
            payment_method=method.code,
            payment_status="pending",
            amount=total,
        )
    )
    db.add(
        OrderStatusHistory(
            order_id=order.order_id,
            previous_status=None,
            new_status="pending",
            changed_by=None,
            notes="Order created",
        )
    )
    db.flush()
    db.refresh(order)
    return order


def change_status(
    db: Session,
    *,
    order: Order,
    new_status: str,
    user: Optional[User],
    notes: Optional[str] = None,
) -> Order:
    previous = order.status
    if previous == new_status:
        raise HTTPException(http_status.HTTP_400_BAD_REQUEST, "Order already has this status")
    # Role checks run before graph checks so that an unauthorised role always
    # receives 403 instead of leaking whether a transition would otherwise be valid.
    if user is not None:
        _assert_staff_transition(user, previous, new_status)
    if new_status not in TRANSITIONS.get(previous, set()):
        raise HTTPException(
            http_status.HTTP_409_CONFLICT,
            f"Invalid status transition: {previous} -> {new_status}",
        )

    order.status = new_status
    order.updated_at = datetime.utcnow()
    db.add(
        OrderStatusHistory(
            order_id=order.order_id,
            previous_status=previous,
            new_status=new_status,
            changed_by=user.user_id if user else None,
            notes=notes,
        )
    )
    db.flush()
    return order


def apply_payment(
    db: Session,
    *,
    order: Order,
    new_status: str,
    user: User,
    transaction_reference: Optional[str] = None,
) -> Payment:
    payment = db.scalar(
        select(Payment).where(Payment.order_id == order.order_id).order_by(Payment.payment_id.desc())
    )
    if payment is None:
        method = order.payment_method or "pay_at_counter"
        payment = Payment(
            order_id=order.order_id,
            payment_method=method,
            payment_status="pending",
            amount=order.total_amount,
        )
        db.add(payment)
        db.flush()

    payment.payment_status = new_status
    payment.transaction_reference = transaction_reference
    if new_status == "paid":
        payment.paid_at = datetime.utcnow()
        payment.amount = order.total_amount
        order.payment_status = "paid"
    elif new_status == "refunded":
        order.payment_status = "refunded"
    elif new_status == "failed":
        order.payment_status = "pending"
    else:
        order.payment_status = "pending"
    db.flush()
    return payment


def serialize_order(order: Order, *, include_history: bool = True) -> dict:
    items = []
    for line in order.items:
        items.append(
            {
                "order_item_id": line.order_item_id,
                "item_id": line.item_id,
                "item_name_snapshot": line.item_name_snapshot
                or (line.menu_item.item_name if line.menu_item else None),
                "item_name_ar": line.menu_item.item_name_ar if line.menu_item else None,
                "quantity": line.quantity,
                "unit_price": float(line.unit_price),
                "line_total": float(money(line.unit_price) * line.quantity),
                "special_instructions": line.special_instructions,
            }
        )
    customer = order.customer
    payload = {
        "order_id": order.order_id,
        "customer_id": order.customer_id,
        "customer_name": customer.customer_name if customer else None,
        "customer_phone": customer.phone if customer else None,
        "order_date": order.order_date,
        "updated_at": order.updated_at,
        "status": order.status,
        "payment_status": order.payment_status,
        "payment_method": order.payment_method,
        "order_notes": order.order_notes,
        "order_source": order.order_source,
        "total_amount": float(order.total_amount),
        "items": items,
        "payments": [
            {
                "payment_id": p.payment_id,
                "payment_method": p.payment_method,
                "payment_status": p.payment_status,
                "amount": float(p.amount),
                "transaction_reference": p.transaction_reference,
                "paid_at": p.paid_at,
                "created_at": p.created_at,
            }
            for p in order.payments
        ],
    }
    if include_history:
        payload["status_history"] = [
            {
                "history_id": h.history_id,
                "previous_status": h.previous_status,
                "new_status": h.new_status,
                "changed_by": h.changed_by,
                "changed_by_name": h.user.full_name or h.user.username if h.user else None,
                "changed_at": h.changed_at,
                "notes": h.notes,
            }
            for h in order.status_history
        ]
    else:
        payload["status_history"] = []
    return payload


def order_query(db: Session):
    return db.query(Order).options(
        selectinload(Order.items).selectinload(OrderItem.menu_item),
        selectinload(Order.customer),
        selectinload(Order.payments),
        selectinload(Order.status_history).selectinload(OrderStatusHistory.user),
    )


def load_order(db: Session, order_id: int) -> Order:
    order = order_query(db).filter(Order.order_id == order_id).first()
    if order is None:
        raise HTTPException(http_status.HTTP_404_NOT_FOUND, "Order not found")
    return order


def ensure_customer_profile(db: Session, user: User) -> Optional[Customer]:
    if user.role != "customer":
        return None
    profile = db.scalar(select(Customer).where(Customer.user_id == user.user_id))
    if profile is None:
        # Never auto-link to a historical customer by name. A new profile is
        # created without a phone, which managers can reconcile manually.
        profile = Customer(customer_name=user.full_name or user.username, user_id=user.user_id)
        db.add(profile)
        db.flush()
    return profile
