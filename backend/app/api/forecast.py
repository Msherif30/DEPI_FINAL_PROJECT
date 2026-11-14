"""Demand forecasting API."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import ManagerUser
from app.database.session import get_db
from app.models import MenuItem, Order, OrderItem
from app.schemas import ForecastRequest
from app.services import forecast

router = APIRouter(prefix="/forecast", tags=["Forecasting"])


@router.post("/train")
def train(user: ManagerUser, db: Session = Depends(get_db)):
    return forecast.train(db)


@router.get("/predictions")
def predictions(
    user: ManagerUser,
    horizon_days: int = Query(default=7, ge=1, le=30),
    item_id: Optional[int] = None,
    db: Session = Depends(get_db),
):
    return forecast.predict(db, horizon_days=horizon_days, item_id=item_id)


@router.get("/performance")
def performance(user: ManagerUser, db: Session = Depends(get_db)):
    return forecast.performance(db)


@router.get("/history")
def history(
    user: ManagerUser,
    item_id: Optional[int] = None,
    days: int = Query(default=60, ge=7, le=365),
    db: Session = Depends(get_db),
):
    query = (
        select(
            Order.order_date,
            OrderItem.item_id,
            MenuItem.item_name,
            OrderItem.quantity,
        )
        .join(OrderItem, OrderItem.order_id == Order.order_id)
        .join(MenuItem, MenuItem.item_id == OrderItem.item_id)
        .where(Order.status == "completed")
    )
    if item_id:
        query = query.where(OrderItem.item_id == item_id)
    rows = db.execute(query.order_by(Order.order_date)).all()
    by_day: dict[str, float] = {}
    for order_date, _item, _name, quantity in rows:
        key = order_date.date().isoformat()
        by_day[key] = by_day.get(key, 0) + int(quantity)
    series = sorted(by_day.items())[-days:]
    return {
        "series": [{"date": key, "quantity": value} for key, value in series],
        "item_id": item_id,
        "source": "completed orders only",
    }
