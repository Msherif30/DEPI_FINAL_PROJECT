"""Controlled AI tools. The model can only call these validated functions.

There is deliberately no raw-SQL tool. Every price, product and availability
check is resolved from MySQL on the server, never from the language model.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional

from fastapi import HTTPException, status as http_status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.models import Customer, KioskCartItem, KioskSession, MenuItem, PaymentMethod
from app.schemas import CartLineIn
from app.services import orders as order_service
from app.services.inventory import q

from .matcher import rank_items


class KioskTools:
    def __init__(self, db: Session, session: KioskSession):
        self.db = db
        self.session = session

    # ------------------------------------------------------------------ #
    # Guard rails
    # ------------------------------------------------------------------ #
    def _assert_active(self) -> None:
        if self.session.status != "active":
            raise HTTPException(http_status.HTTP_409_CONFLICT, "This kiosk session is no longer active")
        if self.session.expires_at < datetime.utcnow():
            self.session.status = "expired"
            self.db.flush()
            raise HTTPException(http_status.HTTP_409_CONFLICT, "This kiosk session has expired")

    def touch(self) -> None:
        self.session.last_activity = datetime.utcnow()
        self.session.expires_at = datetime.utcnow() + timedelta(minutes=settings.kiosk_session_minutes)

    def _menu_item(self, item_id: int) -> MenuItem:
        item = self.db.scalar(
            select(MenuItem).options(selectinload(MenuItem.category)).where(MenuItem.item_id == item_id)
        )
        if item is None:
            raise HTTPException(http_status.HTTP_404_NOT_FOUND, f"Menu item {item_id} does not exist")
        return item

    # ------------------------------------------------------------------ #
    # Read tools
    # ------------------------------------------------------------------ #
    def search_menu(self, query: str, limit: int = 5) -> list[dict]:
        self._assert_active()
        items = self.db.scalars(
            select(MenuItem)
            .options(selectinload(MenuItem.category))
            .where(MenuItem.is_available.is_(True))
        ).all()
        ranked = rank_items(items, query, limit=limit)
        return [
            {
                "item_id": item.item_id,
                "item_name": item.item_name,
                "item_name_ar": item.item_name_ar,
                "price": float(item.price),
                "category": item.category.category_name if item.category else None,
                "is_available": item.is_available,
                "score": score,
            }
            for item, score in ranked
        ]

    def get_menu_item(self, item_id: int) -> dict:
        self._assert_active()
        item = self._menu_item(item_id)
        return {
            "item_id": item.item_id,
            "item_name": item.item_name,
            "item_name_ar": item.item_name_ar,
            "description": item.description,
            "description_ar": item.description_ar,
            "price": float(item.price),
            "is_available": item.is_available,
            "category": item.category.category_name if item.category else None,
            "preparation_time": item.preparation_time,
        }

    def get_item_price(self, item_id: int) -> dict:
        self._assert_active()
        item = self._menu_item(item_id)
        return {"item_id": item.item_id, "item_name": item.item_name, "price": float(item.price), "currency": "EGP"}

    def check_availability(self, item_id: int) -> dict:
        self._assert_active()
        item = self._menu_item(item_id)
        return {
            "item_id": item.item_id,
            "item_name": item.item_name,
            "is_available": bool(item.is_available),
        }

    def suggestions(self, limit: int = 6) -> list[dict]:
        items = self.db.scalars(
            select(MenuItem)
            .where(MenuItem.is_available.is_(True), MenuItem.is_featured.is_(True))
            .order_by(MenuItem.item_name)
            .limit(limit)
        ).all()
        if len(items) < limit:
            extra = self.db.scalars(
                select(MenuItem)
                .where(MenuItem.is_available.is_(True))
                .order_by(MenuItem.price.desc())
                .limit(limit)
            ).all()
            seen = {item.item_id for item in items}
            items.extend(item for item in extra if item.item_id not in seen)
        return [self._serialize_item(item) for item in items[:limit]]

    # ------------------------------------------------------------------ #
    # Cart tools
    # ------------------------------------------------------------------ #
    def add_item_to_cart(self, item_id: int, quantity: int = 1, special_instructions: Optional[str] = None) -> dict:
        self._assert_active()
        if quantity < 1 or quantity > 99:
            raise HTTPException(http_status.HTTP_400_BAD_REQUEST, "Quantity must be between 1 and 99")
        item = self._menu_item(item_id)
        if not item.is_available:
            raise HTTPException(http_status.HTTP_409_CONFLICT, f"{item.item_name} is unavailable")
        line = self.db.scalar(
            select(KioskCartItem).where(
                KioskCartItem.session_id == self.session.session_id,
                KioskCartItem.item_id == item_id,
            )
        )
        if line:
            new_qty = line.quantity + quantity
            if new_qty > 99:
                raise HTTPException(http_status.HTTP_400_BAD_REQUEST, "Maximum quantity is 99")
            line.quantity = new_qty
            if special_instructions:
                line.special_instructions = special_instructions[:300]
        else:
            self.db.add(
                KioskCartItem(
                    session_id=self.session.session_id,
                    item_id=item_id,
                    quantity=quantity,
                    special_instructions=special_instructions[:300] if special_instructions else None,
                )
            )
        self.session.state = "awaiting_confirmation"
        self.touch()
        self.db.flush()
        return self.get_cart_summary()

    def update_cart_item(self, item_id: int, quantity: int) -> dict:
        self._assert_active()
        if quantity < 1 or quantity > 99:
            raise HTTPException(http_status.HTTP_400_BAD_REQUEST, "Quantity must be between 1 and 99")
        line = self.db.scalar(
            select(KioskCartItem).where(
                KioskCartItem.session_id == self.session.session_id,
                KioskCartItem.item_id == item_id,
            )
        )
        if line is None:
            raise HTTPException(http_status.HTTP_404_NOT_FOUND, "Item is not in the kiosk cart")
        line.quantity = quantity
        self.touch()
        self.db.flush()
        return self.get_cart_summary()

    def remove_cart_item(self, item_id: int) -> dict:
        self._assert_active()
        line = self.db.scalar(
            select(KioskCartItem).where(
                KioskCartItem.session_id == self.session.session_id,
                KioskCartItem.item_id == item_id,
            )
        )
        if line is None:
            raise HTTPException(http_status.HTTP_404_NOT_FOUND, "Item is not in the kiosk cart")
        self.db.delete(line)
        self.touch()
        self.db.flush()
        return self.get_cart_summary()

    def get_cart_summary(self) -> dict:
        rows = self.db.scalars(
            select(KioskCartItem)
            .options(
                selectinload(KioskCartItem.menu_item).selectinload(MenuItem.category)
            )
            .where(KioskCartItem.session_id == self.session.session_id)
            .order_by(KioskCartItem.created_at)
        ).all()
        cart = []
        total = Decimal("0")
        for line in rows:
            item = line.menu_item
            line_total = q(item.price) * line.quantity
            total += line_total
            cart.append(
                {
                    "cart_item_id": line.cart_item_id,
                    "item_id": item.item_id,
                    "item_name": item.item_name,
                    "item_name_ar": item.item_name_ar,
                    "quantity": line.quantity,
                    "unit_price": float(item.price),
                    "line_total": float(line_total),
                    "is_available": bool(item.is_available),
                    "special_instructions": line.special_instructions,
                }
            )
        return {"cart": cart, "subtotal": float(total), "currency": "EGP"}

    # ------------------------------------------------------------------ #
    # Order submission (requires explicit confirmation upstream)
    # ------------------------------------------------------------------ #
    def submit_confirmed_order(
        self,
        *,
        payment_method: str = "cash",
        customer_name: Optional[str] = None,
        customer_phone: Optional[str] = None,
    ) -> dict:
        self._assert_active()
        summary = self.get_cart_summary()
        if not summary["cart"]:
            raise HTTPException(http_status.HTTP_400_BAD_REQUEST, "The cart is empty")
        if any(not line["is_available"] for line in summary["cart"]):
            raise HTTPException(http_status.HTTP_409_CONFLICT, "One or more items became unavailable")

        method = self.db.get(PaymentMethod, payment_method)
        if method is None or not method.is_active:
            raise HTTPException(http_status.HTTP_400_BAD_REQUEST, "Unsupported payment method")

        customer_id = None
        if customer_phone:
            customer = self.db.scalar(select(Customer).where(Customer.phone == customer_phone))
            if customer is None:
                customer = Customer(customer_name=customer_name or "Kiosk guest", phone=customer_phone)
                self.db.add(customer)
                self.db.flush()
            customer_id = customer.customer_id

        lines = [
            CartLineIn(
                item_id=line["item_id"],
                quantity=line["quantity"],
                special_instructions=line["special_instructions"],
            )
            for line in summary["cart"]
        ]
        order = order_service.create_order(
            self.db,
            lines=lines,
            customer_id=customer_id,
            order_source="kiosk",
            payment_method=payment_method,
            order_notes="Created from AI kiosk",
            raw_transcription="Kiosk session conversation",
        )
        self.session.status = "submitted"
        self.session.state = "submitted"
        self.session.order_id = order.order_id
        self.session.ended_at = datetime.utcnow()
        if customer_name:
            self.session.customer_name = customer_name
        if customer_phone:
            self.session.customer_phone = customer_phone
        self.db.flush()
        return {
            "order_id": order.order_id,
            "total_amount": float(order.total_amount),
            "status": order.status,
            "payment_status": order.payment_status,
            "payment_method": order.payment_method,
            "items": summary["cart"],
        }

    def _serialize_item(self, item: MenuItem) -> dict:
        return {
            "item_id": item.item_id,
            "item_name": item.item_name,
            "item_name_ar": item.item_name_ar,
            "price": float(item.price),
            "category": item.category.category_name if item.category else None,
            "is_available": bool(item.is_available),
            "image_url": item.image_url,
        }
