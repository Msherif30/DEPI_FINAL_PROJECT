"""Customer orders, order tracking, staff status workflow and payments."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.rate_limit import request_ip
from app.core.security import CurrentUser, StaffUser, require_roles
from app.database.session import get_db
from app.models import Customer, Order
from app.realtime.manager import manager
from app.schemas import (
    OrderCreate,
    OrderOut,
    PaymentUpdate,
    StatusUpdate,
)
from app.services import audit
from app.services.inventory import consume_order_ingredients, reverse_order_consumption
from app.services.orders import (
    apply_payment,
    change_status,
    create_order,
    ensure_customer_profile,
    load_order,
    order_query,
    serialize_order,
)

router = APIRouter(prefix="/orders", tags=["Orders"])
staff_router = APIRouter(prefix="/staff", tags=["Staff"])

CashierOrManager = require_roles("cashier", "manager")


def _customer_profile(db: Session, user) -> Customer:
    profile = ensure_customer_profile(db, user)
    if profile is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Customer profile required")
    return profile


@router.post("", response_model=dict, status_code=status.HTTP_201_CREATED)
async def place_order(
    payload: OrderCreate,
    request: Request,
    user: CurrentUser,
    db: Session = Depends(get_db),
):
    profile = _customer_profile(db, user)
    if not payload.items:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Cart is empty")
    order = create_order(
        db,
        lines=payload.items,
        customer_id=profile.customer_id,
        order_source="web_app",
        payment_method=payload.payment_method,
        order_notes=payload.order_notes,
        idempotency_key=payload.idempotency_key,
        idempotency_scope=f"user:{user.user_id}",
    )
    audit.log_audit(
        db,
        user_id=user.user_id,
        action="order.create",
        entity_type="order",
        entity_id=str(order.order_id),
        details={"items": len(payload.items), "total": float(order.total_amount)},
        ip_address=request_ip(request),
    )
    db.commit()
    order = load_order(db, order.order_id)
    payload_out = serialize_order(order)
    await manager.broadcast_staff({"type": "order.created", "order": payload_out})
    return {
        "order": payload_out,
        "message": f"Order #{order.order_id} placed successfully",
    }


@router.get("", response_model=dict)
def my_orders(
    user: CurrentUser,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    profile = _customer_profile(db, user)
    base = order_query(db).filter(Order.customer_id == profile.customer_id)
    total = db.scalar(select(func.count()).select_from(base.subquery()))
    orders = (
        base.order_by(Order.order_date.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return {
        "items": [serialize_order(order) for order in orders],
        "total": int(total or 0),
        "page": page,
        "page_size": page_size,
    }


@router.get("/{order_id}", response_model=dict)
def get_order(order_id: int, user: CurrentUser, db: Session = Depends(get_db)):
    order = load_order(db, order_id)
    if user.role == "customer":
        profile = _customer_profile(db, user)
        if order.customer_id != profile.customer_id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Order not found")
    return serialize_order(order)


@router.patch("/{order_id}/status", response_model=dict)
async def update_status(
    order_id: int,
    payload: StatusUpdate,
    request: Request,
    user: StaffUser,
    db: Session = Depends(get_db),
):
    order = load_order(db, order_id)
    inventory_result: Optional[dict] = None
    try:
        change_status(db, order=order, new_status=payload.status, user=user, notes=payload.notes)
        if payload.status == "preparing":
            inventory_result = consume_order_ingredients(db, order=order, user=user)
        if payload.status == "cancelled":
            inventory_result = reverse_order_consumption(db, order=order, user=user)
        audit.log_audit(
            db,
            user_id=user.user_id,
            action="order.status",
            entity_type="order",
            entity_id=str(order_id),
            details={"status": payload.status, "inventory": inventory_result},
            ip_address=request_ip(request),
        )
        db.commit()
    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise
    order = load_order(db, order_id)
    payload_out = serialize_order(order)
    await manager.broadcast_order_event(
        order_id,
        {
            "type": "order.status_changed",
            "status": order.status,
            "order": payload_out,
        },
    )
    return {"order": payload_out, "inventory": inventory_result}


@router.patch("/{order_id}/payment", response_model=dict)
async def update_payment(
    order_id: int,
    payload: PaymentUpdate,
    request: Request,
    user=Depends(CashierOrManager),
    db: Session = Depends(get_db),
):
    order = load_order(db, order_id)
    payment = apply_payment(
        db,
        order=order,
        new_status=payload.payment_status,
        user=user,
        transaction_reference=payload.transaction_reference,
    )
    audit.log_audit(
        db,
        user_id=user.user_id,
        action="payment.update",
        entity_type="order",
        entity_id=str(order_id),
        details={"payment_status": payload.payment_status},
        ip_address=request_ip(request),
    )
    db.commit()
    order = load_order(db, order_id)
    payload_out = serialize_order(order)
    await manager.broadcast_order_event(
        order_id,
        {"type": "order.payment_changed", "payment_status": order.payment_status, "order": payload_out},
    )
    return {"order": payload_out, "payment_id": payment.payment_id}


# --------------------------------------------------------------------------- #
# Staff board
# --------------------------------------------------------------------------- #
@staff_router.get("/orders", response_model=dict)
def staff_orders(
    user: StaffUser,
    status_filter: Optional[str] = Query(default=None, alias="status"),
    source: Optional[str] = Query(default=None),
    date_from: Optional[str] = Query(default=None),
    date_to: Optional[str] = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    query = order_query(db)
    if status_filter:
        statuses = [part.strip() for part in status_filter.split(",") if part.strip()]
        query = query.filter(Order.status.in_(statuses))
    if source:
        query = query.filter(Order.order_source == source)
    if date_from:
        query = query.filter(Order.order_date >= datetime.fromisoformat(date_from))
    if date_to:
        query = query.filter(Order.order_date <= datetime.fromisoformat(date_to))
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    orders = (
        query.order_by(Order.order_date.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return {
        "items": [serialize_order(order) for order in orders],
        "total": int(total or 0),
        "page": page,
        "page_size": page_size,
    }


@staff_router.get("/orders/summary", response_model=dict)
def staff_summary(user: StaffUser, db: Session = Depends(get_db)):
    rows = db.execute(
        select(Order.status, func.count(Order.order_id)).group_by(Order.status)
    ).all()
    counts = {status: int(count) for status, count in rows}
    latest = db.scalar(select(func.max(Order.order_date)))
    return {
        "counts": {
            "pending": counts.get("pending", 0),
            "confirmed": counts.get("confirmed", 0),
            "preparing": counts.get("preparing", 0),
            "completed": counts.get("completed", 0),
            "cancelled": counts.get("cancelled", 0),
        },
        "total": sum(counts.values()),
        "latest_order_at": latest,
        "role": user.role,
    }
