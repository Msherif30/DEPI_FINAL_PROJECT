"""Business intelligence queries. Every number comes from MySQL, never random data."""
from __future__ import annotations

from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import Optional

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.models import Category, Customer, MenuItem, Order, OrderItem, Payment


def _range(start: Optional[date], end: Optional[date]) -> tuple[datetime, datetime]:
    today = date.today()
    end_date = end or today
    start_date = start or (end_date - timedelta(days=29))
    if start_date > end_date:
        start_date, end_date = end_date, start_date
    return datetime.combine(start_date, time.min), datetime.combine(end_date, time.max)


def overview(db: Session, start: Optional[date] = None, end: Optional[date] = None) -> dict:
    start_dt, end_dt = _range(start, end)
    base = select(
        func.count(Order.order_id),
        func.coalesce(func.sum(case((Order.status == "completed", Order.total_amount), else_=0)), 0),
        func.coalesce(func.sum(case((Order.status == "completed", 1), else_=0)), 0),
        func.coalesce(func.sum(case((Order.status == "cancelled", 1), else_=0)), 0),
        func.coalesce(func.sum(case((Order.status == "pending", 1), else_=0)), 0),
    ).where(Order.order_date >= start_dt, Order.order_date <= end_dt)
    total_orders, revenue, completed, cancelled, pending = db.execute(base).one()
    revenue = Decimal(revenue or 0)
    aov = (revenue / completed) if completed else Decimal("0")

    paid_revenue = db.scalar(
        select(func.coalesce(func.sum(Payment.amount), 0))
        .join(Order, Order.order_id == Payment.order_id)
        .where(
            Payment.payment_status == "paid",
            Order.order_date >= start_dt,
            Order.order_date <= end_dt,
        )
    ) or Decimal("0")

    best = db.execute(
        select(
            MenuItem.item_id,
            MenuItem.item_name,
            MenuItem.item_name_ar,
            func.sum(OrderItem.quantity).label("qty"),
            func.sum(OrderItem.quantity * OrderItem.unit_price).label("revenue"),
        )
        .join(OrderItem, OrderItem.item_id == MenuItem.item_id)
        .join(Order, Order.order_id == OrderItem.order_id)
        .where(
            Order.status == "completed",
            Order.order_date >= start_dt,
            Order.order_date <= end_dt,
        )
        .group_by(MenuItem.item_id, MenuItem.item_name, MenuItem.item_name_ar)
        .order_by(func.sum(OrderItem.quantity).desc())
        .limit(1)
    ).first()

    return {
        "period": {"start": start_dt.date().isoformat(), "end": end_dt.date().isoformat()},
        "total_revenue": float(revenue),
        "paid_revenue": float(paid_revenue),
        "total_orders": int(total_orders or 0),
        "completed_orders": int(completed or 0),
        "cancelled_orders": int(cancelled or 0),
        "pending_orders": int(pending or 0),
        "average_order_value": float(aov),
        "best_selling_product": (
            {
                "item_id": best.item_id,
                "item_name": best.item_name,
                "item_name_ar": best.item_name_ar,
                "quantity": int(best.qty or 0),
                "revenue": float(best.revenue or 0),
            }
            if best
            else None
        ),
        "revenue_definition": "Completed orders only. Cancelled and pending orders are excluded.",
    }


def sales_series(
    db: Session,
    start: Optional[date] = None,
    end: Optional[date] = None,
    granularity: str = "day",
) -> list[dict]:
    start_dt, end_dt = _range(start, end)
    if granularity == "month":
        bucket = func.date_format(Order.order_date, "%Y-%m")
    elif granularity == "week":
        bucket = func.date_format(Order.order_date, "%x-W%v")
    else:
        bucket = func.date(Order.order_date)
    rows = db.execute(
        select(
            bucket.label("bucket"),
            func.coalesce(
                func.sum(case((Order.status == "completed", Order.total_amount), else_=0)), 0
            ).label("revenue"),
            func.count(Order.order_id).label("orders"),
            func.coalesce(func.sum(case((Order.status == "completed", 1), else_=0)), 0).label(
                "completed"
            ),
        )
        .where(Order.order_date >= start_dt, Order.order_date <= end_dt)
        .group_by(bucket)
        .order_by(bucket)
    ).all()
    return [
        {
            "bucket": str(row.bucket),
            "revenue": float(row.revenue or 0),
            "orders": int(row.orders or 0),
            "completed": int(row.completed or 0),
        }
        for row in rows
    ]


def product_performance(db: Session, start: Optional[date] = None, end: Optional[date] = None, limit: int = 20) -> list[dict]:
    start_dt, end_dt = _range(start, end)
    rows = db.execute(
        select(
            MenuItem.item_id,
            MenuItem.item_name,
            MenuItem.item_name_ar,
            Category.category_name,
            func.coalesce(func.sum(OrderItem.quantity), 0).label("quantity"),
            func.coalesce(func.sum(OrderItem.quantity * OrderItem.unit_price), 0).label("revenue"),
            func.count(func.distinct(Order.order_id)).label("orders"),
        )
        .join(OrderItem, OrderItem.item_id == MenuItem.item_id)
        .join(Order, Order.order_id == OrderItem.order_id)
        .join(Category, Category.category_id == MenuItem.category_id)
        .where(Order.status == "completed", Order.order_date >= start_dt, Order.order_date <= end_dt)
        .group_by(MenuItem.item_id, MenuItem.item_name, MenuItem.item_name_ar, Category.category_name)
        .order_by(func.sum(OrderItem.quantity).desc())
        .limit(limit)
    ).all()
    return [
        {
            "item_id": r.item_id,
            "item_name": r.item_name,
            "item_name_ar": r.item_name_ar,
            "category": r.category_name,
            "quantity": int(r.quantity or 0),
            "revenue": float(r.revenue or 0),
            "orders": int(r.orders or 0),
        }
        for r in rows
    ]


def category_performance(db: Session, start: Optional[date] = None, end: Optional[date] = None) -> list[dict]:
    start_dt, end_dt = _range(start, end)
    rows = db.execute(
        select(
            Category.category_id,
            Category.category_name,
            Category.category_name_ar,
            func.coalesce(func.sum(OrderItem.quantity), 0).label("quantity"),
            func.coalesce(func.sum(OrderItem.quantity * OrderItem.unit_price), 0).label("revenue"),
        )
        .join(MenuItem, MenuItem.category_id == Category.category_id)
        .join(OrderItem, OrderItem.item_id == MenuItem.item_id)
        .join(Order, Order.order_id == OrderItem.order_id)
        .where(Order.status == "completed", Order.order_date >= start_dt, Order.order_date <= end_dt)
        .group_by(Category.category_id, Category.category_name, Category.category_name_ar)
        .order_by(func.sum(OrderItem.quantity * OrderItem.unit_price).desc())
    ).all()
    return [
        {
            "category_id": r.category_id,
            "category_name": r.category_name,
            "category_name_ar": r.category_name_ar,
            "quantity": int(r.quantity or 0),
            "revenue": float(r.revenue or 0),
        }
        for r in rows
    ]


def peak_hours(db: Session, start: Optional[date] = None, end: Optional[date] = None) -> list[dict]:
    start_dt, end_dt = _range(start, end)
    rows = db.execute(
        select(
            func.hour(Order.order_date).label("hour"),
            func.count(Order.order_id).label("orders"),
            func.coalesce(
                func.sum(case((Order.status == "completed", Order.total_amount), else_=0)), 0
            ).label("revenue"),
        )
        .where(Order.order_date >= start_dt, Order.order_date <= end_dt)
        .group_by(func.hour(Order.order_date))
        .order_by(func.hour(Order.order_date))
    ).all()
    by_hour = {int(r.hour): r for r in rows}
    return [
        {
            "hour": hour,
            "label": f"{hour:02d}:00",
            "orders": int(by_hour[hour].orders) if hour in by_hour else 0,
            "revenue": float(by_hour[hour].revenue or 0) if hour in by_hour else 0.0,
        }
        for hour in range(24)
    ]


def order_sources(db: Session, start: Optional[date] = None, end: Optional[date] = None) -> list[dict]:
    start_dt, end_dt = _range(start, end)
    rows = db.execute(
        select(Order.order_source, func.count(Order.order_id))
        .where(Order.order_date >= start_dt, Order.order_date <= end_dt)
        .group_by(Order.order_source)
    ).all()
    return [{"source": source, "orders": int(count)} for source, count in rows]


def customer_patterns(db: Session, start: Optional[date] = None, end: Optional[date] = None, limit: int = 10) -> list[dict]:
    start_dt, end_dt = _range(start, end)
    rows = db.execute(
        select(
            Customer.customer_id,
            Customer.customer_name,
            func.count(Order.order_id).label("orders"),
            func.coalesce(
                func.sum(case((Order.status == "completed", Order.total_amount), else_=0)), 0
            ).label("spend"),
            func.max(Order.order_date).label("last_order"),
        )
        .join(Order, Order.customer_id == Customer.customer_id)
        .where(Order.order_date >= start_dt, Order.order_date <= end_dt)
        .group_by(Customer.customer_id, Customer.customer_name)
        .order_by(func.count(Order.order_id).desc())
        .limit(limit)
    ).all()
    return [
        {
            "customer_id": r.customer_id,
            "customer_name": r.customer_name,
            "orders": int(r.orders or 0),
            "spend": float(r.spend or 0),
            "last_order": r.last_order.isoformat() if r.last_order else None,
        }
        for r in rows
    ]


def insights(db: Session, start: Optional[date] = None, end: Optional[date] = None) -> dict:
    start_dt, end_dt = _range(start, end)
    span = (end_dt.date() - start_dt.date()).days + 1
    prev_end = start_dt - timedelta(seconds=1)
    prev_start = prev_end - timedelta(days=span)
    current = overview(db, start_dt.date(), end_dt.date())
    previous = overview(db, prev_start.date(), prev_end.date())
    change = 0.0
    if previous["total_revenue"] > 0:
        change = (
            (current["total_revenue"] - previous["total_revenue"]) / previous["total_revenue"]
        ) * 100

    hours = peak_hours(db, start_dt.date(), end_dt.date())
    peak = max(hours, key=lambda h: h["orders"]) if hours else None
    products = product_performance(db, start_dt.date(), end_dt.date(), limit=100)
    lowest = min(products, key=lambda p: p["quantity"]) if products else None

    return {
        "period": current["period"],
        "revenue_change_percent": round(change, 2),
        "previous_period_revenue": previous["total_revenue"],
        "peak_hour": peak,
        "top_product": products[0] if products else None,
        "lowest_product": lowest,
        "facts": [
            f"Revenue for the selected period is EGP {current['total_revenue']:,.2f} from completed orders.",
            f"Cancelled orders in the period: {current['cancelled_orders']}.",
            (
                f"Peak ordering hour is {peak['label']} with {peak['orders']} orders."
                if peak and peak["orders"]
                else "No orders were recorded in the selected period."
            ),
            "These are historical facts. Demand predictions are shown separately in Forecasting.",
        ],
        "data_note": (
            "Profit is not calculated because ingredient costs are only known for configured inventory."
        ),
    }

