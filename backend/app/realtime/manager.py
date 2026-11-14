"""Authorized WebSocket fan-out for order events."""
from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from fastapi import WebSocket
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import decode_token
from app.models import Order, User, UserSession


class ConnectionManager:
    def __init__(self) -> None:
        self.staff: set[WebSocket] = set()
        self.orders: dict[int, set[WebSocket]] = defaultdict(set)

    async def connect_staff(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.staff.add(websocket)

    async def connect_order(self, websocket: WebSocket, order_id: int) -> None:
        await websocket.accept()
        self.orders[order_id].add(websocket)

    def disconnect(self, websocket: WebSocket, order_id: int | None = None) -> None:
        self.staff.discard(websocket)
        if order_id is not None:
            self.orders[order_id].discard(websocket)
            if not self.orders[order_id]:
                self.orders.pop(order_id, None)
        else:
            for key, sockets in list(self.orders.items()):
                sockets.discard(websocket)
                if not sockets:
                    self.orders.pop(key, None)

    async def _send(self, sockets: set[WebSocket], payload: dict[str, Any]) -> None:
        dead: list[WebSocket] = []
        message = json.dumps(payload, ensure_ascii=False, default=str)
        for socket in list(sockets):
            try:
                await socket.send_text(message)
            except Exception:  # noqa: BLE001 - stale connection
                dead.append(socket)
        for socket in dead:
            self.disconnect(socket)

    async def broadcast_staff(self, payload: dict[str, Any]) -> None:
        await self._send(self.staff, payload)

    async def broadcast_order(self, order_id: int, payload: dict[str, Any]) -> None:
        await self._send(self.orders.get(order_id, set()), payload)

    async def broadcast_order_event(self, order_id: int, payload: dict[str, Any]) -> None:
        await self.broadcast_staff({**payload, "order_id": order_id})
        await self.broadcast_order(order_id, {**payload, "order_id": order_id})


manager = ConnectionManager()


def authenticate_socket(token: str | None, db: Session) -> User:
    """Validate a JWT and its server-side session. Raises ValueError."""
    if not token:
        raise ValueError("Missing token")
    payload = decode_token(token)
    session = db.scalar(select(UserSession).where(UserSession.jwt_id == payload.get("jti")))
    if session is None or session.revoked_at is not None:
        raise ValueError("Session revoked")
    if session.expires_at < datetime.now(timezone.utc).replace(tzinfo=None):
        raise ValueError("Session expired")
    user = db.get(User, int(payload["sub"]))
    if user is None or not user.is_active or user.role == "system_ai":
        raise ValueError("Inactive user")
    return user


def can_view_order(db: Session, user: User, order_id: int) -> bool:
    if user.role in ("chef", "cashier", "manager"):
        return True
    order = db.get(Order, order_id)
    if order is None or order.customer_id is None:
        return False
    return order.customer is not None and order.customer.user_id == user.user_id
