"""Public menu browsing and manager menu management."""
from __future__ import annotations

import re
import uuid
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.core.security import ManagerUser
from app.database.session import get_db
from app.models import Category, MenuItem, OrderItem, PaymentMethod
from app.schemas import (
    CategoryCreate,
    CategoryOut,
    CategoryUpdate,
    MenuItemCreate,
    MenuItemOut,
    MenuItemUpdate,
    PaymentMethodOut,
)
from app.services import audit
from app.core.rate_limit import request_ip

router = APIRouter(prefix="/menu", tags=["Menu"])
admin_router = APIRouter(prefix="/menu", tags=["Menu management"])

ALLOWED_IMAGE_TYPES = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp", "image/gif": ".gif"}


def _serialize_item(item: MenuItem) -> dict:
    return {
        "item_id": item.item_id,
        "category_id": item.category_id,
        "category_name": item.category.category_name if item.category else None,
        "category_name_ar": item.category.category_name_ar if item.category else None,
        "item_name": item.item_name,
        "item_name_ar": item.item_name_ar,
        "synonyms": item.synonyms,
        "price": float(item.price),
        "is_available": bool(item.is_available),
        "description": item.description,
        "description_ar": item.description_ar,
        "image_url": item.image_url,
        "preparation_time": item.preparation_time,
        "is_featured": bool(item.is_featured),
        "created_at": item.created_at,
    }


@router.get("/categories", response_model=list[CategoryOut])
def list_categories(
    include_inactive: bool = Query(default=False),
    db: Session = Depends(get_db),
):
    counts = dict(
        db.execute(
            select(MenuItem.category_id, func.count(MenuItem.item_id)).group_by(MenuItem.category_id)
        ).all()
    )
    query = select(Category).order_by(Category.category_id)
    if not include_inactive:
        query = query.where(Category.is_active.is_(True))
    categories = db.scalars(query).all()
    return [
        CategoryOut(
            category_id=c.category_id,
            category_name=c.category_name,
            category_name_ar=c.category_name_ar,
            description=c.description,
            image_url=c.image_url,
            is_active=bool(c.is_active),
            item_count=int(counts.get(c.category_id, 0)),
        )
        for c in categories
    ]


@router.get("/payment-methods", response_model=list[PaymentMethodOut])
def payment_methods(db: Session = Depends(get_db)):
    methods = db.scalars(
        select(PaymentMethod).where(PaymentMethod.is_active.is_(True)).order_by(PaymentMethod.sort_order)
    ).all()
    return [PaymentMethodOut.model_validate(m) for m in methods]


@router.get("", response_model=dict)
def list_menu(
    q: Optional[str] = Query(default=None, max_length=120),
    category_id: Optional[int] = None,
    featured: Optional[bool] = None,
    available_only: bool = False,
    sort: str = Query(default="name", pattern="^(name|price_asc|price_desc|newest)$"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=24, ge=1, le=100),
    db: Session = Depends(get_db),
):
    query = select(MenuItem).options(selectinload(MenuItem.category)).join(
        Category, Category.category_id == MenuItem.category_id
    )
    if q:
        term = f"%{q.strip()}%"
        query = query.where(
            or_(
                MenuItem.item_name.ilike(term),
                MenuItem.item_name_ar.ilike(term),
                MenuItem.synonyms.ilike(term),
                MenuItem.description.ilike(term),
                MenuItem.description_ar.ilike(term),
                Category.category_name.ilike(term),
                Category.category_name_ar.ilike(term),
            )
        )
    if category_id:
        query = query.where(MenuItem.category_id == category_id)
    if featured is not None:
        query = query.where(MenuItem.is_featured.is_(featured))
    if available_only:
        query = query.where(MenuItem.is_available.is_(True))

    total = db.scalar(select(func.count()).select_from(query.subquery()))
    if sort == "price_asc":
        query = query.order_by(MenuItem.price.asc())
    elif sort == "price_desc":
        query = query.order_by(MenuItem.price.desc())
    elif sort == "newest":
        query = query.order_by(MenuItem.created_at.desc(), MenuItem.item_id.desc())
    else:
        query = query.order_by(MenuItem.item_name.asc())
    items = db.scalars(query.offset((page - 1) * page_size).limit(page_size)).all()
    return {
        "items": [_serialize_item(item) for item in items],
        "total": int(total or 0),
        "page": page,
        "page_size": page_size,
        "pages": max(1, ((total or 0) + page_size - 1) // page_size),
    }


@router.get("/{item_id}", response_model=MenuItemOut)
def get_item(item_id: int, db: Session = Depends(get_db)):
    item = db.scalar(
        select(MenuItem).options(selectinload(MenuItem.category)).where(MenuItem.item_id == item_id)
    )
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Menu item not found")
    return MenuItemOut(**_serialize_item(item))


# --------------------------------------------------------------------------- #
# Manager-only management
# --------------------------------------------------------------------------- #
@admin_router.post("", response_model=MenuItemOut, status_code=status.HTTP_201_CREATED)
def create_item(payload: MenuItemCreate, request: Request, user: ManagerUser, db: Session = Depends(get_db)):
    if db.get(Category, payload.category_id) is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Category does not exist")
    item = MenuItem(**payload.model_dump())
    db.add(item)
    db.flush()
    audit.log_audit(
        db,
        user_id=user.user_id,
        action="menu.create",
        entity_type="menu_item",
        entity_id=str(item.item_id),
        details={"name": item.item_name, "price": float(item.price)},
        ip_address=request_ip(request),
    )
    db.commit()
    return get_item(item.item_id, db)


@admin_router.patch("/{item_id}", response_model=MenuItemOut)
def update_item(
    item_id: int,
    payload: MenuItemUpdate,
    request: Request,
    user: ManagerUser,
    db: Session = Depends(get_db),
):
    item = db.get(MenuItem, item_id)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Menu item not found")
    data = payload.model_dump(exclude_unset=True)
    if "category_id" in data and db.get(Category, data["category_id"]) is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Category does not exist")
    for key, value in data.items():
        setattr(item, key, value)
    audit.log_audit(
        db,
        user_id=user.user_id,
        action="menu.update",
        entity_type="menu_item",
        entity_id=str(item_id),
        details={"fields": list(data.keys())},
        ip_address=request_ip(request),
    )
    db.commit()
    return get_item(item_id, db)


@admin_router.delete("/{item_id}")
def retire_item(item_id: int, request: Request, user: ManagerUser, db: Session = Depends(get_db)):
    """Menu items with historical order lines are retired, never deleted."""
    item = db.get(MenuItem, item_id)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Menu item not found")
    used = db.scalar(select(func.count()).select_from(OrderItem).where(OrderItem.item_id == item_id))
    if used:
        item.is_available = False
        action = "menu.retire"
    else:
        db.delete(item)
        action = "menu.delete"
    audit.log_audit(
        db,
        user_id=user.user_id,
        action=action,
        entity_type="menu_item",
        entity_id=str(item_id),
        ip_address=request_ip(request),
    )
    db.commit()
    if used:
        return get_item(item_id, db)
    return {"item_id": item_id, "item_name": "deleted"}


@admin_router.post("/categories", response_model=CategoryOut, status_code=status.HTTP_201_CREATED)
def create_category(payload: CategoryCreate, request: Request, user: ManagerUser, db: Session = Depends(get_db)):
    category = Category(**payload.model_dump())
    db.add(category)
    db.flush()
    audit.log_audit(
        db,
        user_id=user.user_id,
        action="category.create",
        entity_type="category",
        entity_id=str(category.category_id),
        details={"name": category.category_name},
        ip_address=request_ip(request),
    )
    db.commit()
    return CategoryOut(
        category_id=category.category_id,
        category_name=category.category_name,
        category_name_ar=category.category_name_ar,
        description=category.description,
        image_url=category.image_url,
        is_active=bool(category.is_active),
        item_count=0,
    )


@admin_router.patch("/categories/{category_id}", response_model=CategoryOut)
def update_category(
    category_id: int,
    payload: CategoryUpdate,
    request: Request,
    user: ManagerUser,
    db: Session = Depends(get_db),
):
    category = db.get(Category, category_id)
    if category is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Category not found")
    data = payload.model_dump(exclude_unset=True)
    for key, value in data.items():
        setattr(category, key, value)
    audit.log_audit(
        db,
        user_id=user.user_id,
        action="category.update",
        entity_type="category",
        entity_id=str(category_id),
        details={"fields": list(data.keys())},
        ip_address=request_ip(request),
    )
    db.commit()
    count = db.scalar(
        select(func.count()).select_from(MenuItem).where(MenuItem.category_id == category_id)
    )
    return CategoryOut(
        category_id=category.category_id,
        category_name=category.category_name,
        category_name_ar=category.category_name_ar,
        description=category.description,
        image_url=category.image_url,
        is_active=bool(category.is_active),
        item_count=int(count or 0),
    )


@admin_router.post("/upload-image")
async def upload_image(
    request: Request,
    user: ManagerUser,
    file: UploadFile = File(...),
):
    if file.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Allowed formats: JPEG, PNG, WEBP, GIF")
    content = await file.read()
    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "Image must be under 5 MB")
    extension = ALLOWED_IMAGE_TYPES[file.content_type]
    safe_stem = re.sub(r"[^A-Za-z0-9_-]", "", Path(file.filename or "image").stem)[:40] or "image"
    filename = f"{uuid.uuid4().hex}_{safe_stem}{extension}"
    target = Path(settings.upload_dir) / filename
    target.write_bytes(content)
    return {"url": f"/uploads/{filename}"}
