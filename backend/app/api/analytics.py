"""Manager analytics endpoints (real data only)."""
from __future__ import annotations

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import ManagerUser
from app.database.session import get_db
from app.models import AuditLog, User
from app.services import analytics

router = APIRouter(prefix="/analytics", tags=["Analytics"])


@router.get("/overview")
def overview(
    user: ManagerUser,
    start: Optional[date] = None,
    end: Optional[date] = None,
    db: Session = Depends(get_db),
):
    return analytics.overview(db, start, end)


@router.get("/sales")
def sales(
    user: ManagerUser,
    start: Optional[date] = None,
    end: Optional[date] = None,
    granularity: str = Query(default="day", pattern="^(day|week|month)$"),
    db: Session = Depends(get_db),
):
    return analytics.sales_series(db, start, end, granularity)


@router.get("/products")
def products(
    user: ManagerUser,
    start: Optional[date] = None,
    end: Optional[date] = None,
    limit: int = Query(default=20, ge=1, le=200),
    db: Session = Depends(get_db),
):
    return analytics.product_performance(db, start, end, limit)


@router.get("/categories")
def categories(
    user: ManagerUser,
    start: Optional[date] = None,
    end: Optional[date] = None,
    db: Session = Depends(get_db),
):
    return analytics.category_performance(db, start, end)


@router.get("/peak-hours")
def peak_hours(
    user: ManagerUser,
    start: Optional[date] = None,
    end: Optional[date] = None,
    db: Session = Depends(get_db),
):
    return analytics.peak_hours(db, start, end)


@router.get("/sources")
def sources(
    user: ManagerUser,
    start: Optional[date] = None,
    end: Optional[date] = None,
    db: Session = Depends(get_db),
):
    return analytics.order_sources(db, start, end)


@router.get("/customers")
def customers(
    user: ManagerUser,
    start: Optional[date] = None,
    end: Optional[date] = None,
    limit: int = Query(default=10, ge=1, le=100),
    db: Session = Depends(get_db),
):
    return analytics.customer_patterns(db, start, end, limit)


@router.get("/insights")
def insights(
    user: ManagerUser,
    start: Optional[date] = None,
    end: Optional[date] = None,
    db: Session = Depends(get_db),
):
    return analytics.insights(db, start, end)


@router.get("/audit-logs")
def audit_logs(
    user: ManagerUser,
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    rows = db.execute(
        select(AuditLog, User)
        .outerjoin(User, User.user_id == AuditLog.user_id)
        .order_by(AuditLog.created_at.desc())
        .limit(limit)
    ).all()
    return [
        {
            "audit_id": log.audit_id,
            "user_id": log.user_id,
            "user_name": (usr.full_name or usr.username) if usr else None,
            "action": log.action,
            "entity_type": log.entity_type,
            "entity_id": log.entity_id,
            "details": log.details,
            "ip_address": log.ip_address,
            "created_at": log.created_at,
        }
        for log, usr in rows
    ]
