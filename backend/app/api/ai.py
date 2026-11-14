"""Public AI kiosk endpoints and the manager analytics assistant."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.ai.kiosk import process_message
from app.ai.llm import run_llm
from app.ai.tools import KioskTools
from app.core.config import settings
from app.core.rate_limit import SlidingWindowLimiter, request_ip
from app.core.security import ManagerUser
from app.database.session import get_db
from app.models import KioskCartItem, KioskSession, MenuItem
from app.realtime.manager import manager
from app.schemas import KioskChatIn, KioskConfirmIn, KioskSessionCreate, KioskSessionOut
from app.services import analytics
from app.services.orders import load_order, serialize_order

router = APIRouter(prefix="/ai", tags=["AI kiosk"])
kiosk_limiter = SlidingWindowLimiter(30, 60)


def _get_session(db: Session, session_id: str) -> KioskSession:
    session = db.scalar(
        select(KioskSession)
        .options(
            selectinload(KioskSession.cart_items)
            .selectinload(KioskCartItem.menu_item)
        )
        .where(KioskSession.session_id == session_id)
    )
    if session is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Kiosk session not found")
    if session.expires_at < datetime.utcnow() and session.status == "active":
        session.status = "expired"
        db.commit()
    if session.status == "expired":
        raise HTTPException(status.HTTP_410_GONE, "Kiosk session expired")
    return session


def _cart(db: Session, session: KioskSession) -> dict:
    return KioskTools(db, session).get_cart_summary()


@router.post("/kiosk/session", response_model=KioskSessionOut, status_code=status.HTTP_201_CREATED)
def create_session(payload: KioskSessionCreate, request: Request, db: Session = Depends(get_db)):
    kiosk_limiter.check(f"kiosk-session:{request_ip(request)}")
    session = KioskSession(
        session_id=str(uuid.uuid4()),
        status="active",
        language=payload.language,
        expires_at=datetime.utcnow() + timedelta(minutes=settings.kiosk_session_minutes),
    )
    db.add(session)
    db.commit()
    return KioskSessionOut(
        session_id=session.session_id,
        status=session.status,
        language=session.language,
        expires_at=session.expires_at,
        cart=[],
        subtotal=0,
    )


@router.get("/kiosk/session/{session_id}", response_model=KioskSessionOut)
def get_session(session_id: str, db: Session = Depends(get_db)):
    session = _get_session(db, session_id)
    cart = _cart(db, session) if session.status == "active" else {"cart": [], "subtotal": 0}
    return KioskSessionOut(
        session_id=session.session_id,
        status=session.status,
        language=session.language,
        expires_at=session.expires_at,
        cart=cart["cart"],
        subtotal=cart["subtotal"],
        order_id=session.order_id,
    )


@router.post("/kiosk/chat")
def chat(payload: KioskChatIn, request: Request, db: Session = Depends(get_db)):
    kiosk_limiter.check(f"kiosk-chat:{request_ip(request)}:{payload.session_id[:8]}")
    session = _get_session(db, payload.session_id)
    if session.status != "active":
        raise HTTPException(status.HTTP_409_CONFLICT, "This kiosk session has already been submitted")
    llm_result = None
    if settings.llm_api_key:
        llm_result = run_llm(db, session=session, message=payload.message, language=payload.language)
    result = llm_result or process_message(
        db, session=session, message=payload.message, language=payload.language
    )
    db.commit()
    return result


@router.post("/kiosk/confirm")
async def confirm_order(payload: KioskConfirmIn, request: Request, db: Session = Depends(get_db)):
    session = _get_session(db, payload.session_id)
    if session.status != "active":
        raise HTTPException(status.HTTP_409_CONFLICT, "This kiosk session is not active")
    tools = KioskTools(db, session)
    result = tools.submit_confirmed_order(
        payment_method=payload.payment_method,
        customer_name=payload.customer_name,
        customer_phone=payload.customer_phone,
    )
    db.commit()
    order = load_order(db, result["order_id"])
    order_payload = serialize_order(order)
    await manager.broadcast_staff({"type": "order.created", "order": order_payload})
    return {
        "message": "Order confirmed",
        "order": order_payload,
        "summary": result,
    }


@router.post("/kiosk/reset")
def reset_session(payload: KioskChatIn, db: Session = Depends(get_db)):
    session = _get_session(db, payload.session_id)
    if session.status != "active":
        raise HTTPException(status.HTTP_409_CONFLICT, "This kiosk session is not active")
    for line in list(session.cart_items):
        db.delete(line)
    session.state = "idle"
    db.commit()
    return {"message": "Cart cleared", "session_id": session.session_id}


@router.get("/kiosk/suggestions")
def kiosk_suggestions(db: Session = Depends(get_db)):
    items = db.scalars(
        select(MenuItem)
        .where(MenuItem.is_available.is_(True))
        .order_by(MenuItem.is_featured.desc(), MenuItem.item_name)
        .limit(8)
    ).all()
    return [
        {
            "item_id": item.item_id,
            "item_name": item.item_name,
            "item_name_ar": item.item_name_ar,
            "price": float(item.price),
            "description": item.description,
            "description_ar": item.description_ar,
            "image_url": item.image_url,
            "is_featured": bool(item.is_featured),
        }
        for item in items
    ]


# --------------------------------------------------------------------------- #
# Manager analytics assistant (controlled tools, no raw SQL)
# --------------------------------------------------------------------------- #
@router.post("/analyst")
def business_analyst(
    payload: dict,
    user: ManagerUser,
    db: Session = Depends(get_db),
):
    question = str(payload.get("question", "")).strip()
    if not question:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "A question is required")
    overview = analytics.overview(db)
    products = analytics.product_performance(db, limit=5)
    hours = analytics.peak_hours(db)
    peak = max(hours, key=lambda h: h["orders"]) if hours else None
    sources = analytics.order_sources(db)
    insights = analytics.insights(db)

    lines = [
        f"Selected period: {overview['period']['start']} to {overview['period']['end']}.",
        f"Completed-order revenue: EGP {overview['total_revenue']:,.2f} from "
        f"{overview['completed_orders']} completed orders.",
        f"Paid revenue recorded in payments: EGP {overview['paid_revenue']:,.2f}.",
        f"Average order value: EGP {overview['average_order_value']:,.2f}.",
        f"Cancelled orders: {overview['cancelled_orders']}.",
    ]
    if overview["best_selling_product"]:
        best = overview["best_selling_product"]
        lines.append(f"Best seller: {best['item_name']} ({best['quantity']} units).")
    if peak and peak["orders"]:
        lines.append(f"Peak hour: {peak['label']} with {peak['orders']} orders.")
    if products:
        lines.append(
            "Top products by quantity: "
            + ", ".join(f"{p['item_name']} ({p['quantity']})" for p in products[:3])
            + "."
        )
    if sources:
        lines.append(
            "Order sources: " + ", ".join(f"{s['source']} ({s['orders']})" for s in sources) + "."
        )
    lines.append(
        "These are historical facts from MySQL. I do not invent statistics; "
        "for predictions use the Forecasting module."
    )
    return {"answer": "\n".join(lines), "facts": insights["facts"], "data_note": insights["data_note"]}
