"""Inventory, recipes, suppliers and purchase order endpoints."""
from __future__ import annotations

import math
from datetime import datetime
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.rate_limit import request_ip
from app.core.security import ManagerUser
from app.database.session import get_db
from app.models import (
    Ingredient,
    InventoryStock,
    MenuItem,
    MenuItemIngredient,
    PurchaseOrder,
    PurchaseOrderItem,
    StockMovement,
    Supplier,
    User,
)
from app.schemas import (
    IngredientCreate,
    IngredientOut,
    IngredientUpdate,
    PurchaseOrderCreate,
    PurchaseOrderOut,
    ReceivePurchaseOrder,
    RecipeLineIn,
    RecipeOut,
    StockMovementCreate,
    SupplierCreate,
    SupplierOut,
    SupplierUpdate,
)
from app.services import audit
from app.services.inventory import (
    get_or_create_stock,
    purchase_recommendations,
    q,
    receive_purchase_order,
    record_movement,
    stock_status,
)

router = APIRouter(prefix="/inventory", tags=["Inventory"])
supplier_router = APIRouter(prefix="/suppliers", tags=["Suppliers"])
purchase_router = APIRouter(prefix="/purchase-orders", tags=["Purchasing"])


def _ingredient_payload(db: Session, ingredient: Ingredient, recipe_ids: set[int]) -> IngredientOut:
    stock = db.scalar(
        select(InventoryStock).where(InventoryStock.ingredient_id == ingredient.ingredient_id)
    )
    quantity = q(stock.quantity) if stock else Decimal("0")
    return IngredientOut(
        ingredient_id=ingredient.ingredient_id,
        ingredient_name=ingredient.ingredient_name,
        ingredient_name_ar=ingredient.ingredient_name_ar,
        unit_of_measure=ingredient.unit_of_measure,
        minimum_stock=float(ingredient.minimum_stock),
        safety_stock=float(ingredient.safety_stock),
        lead_time_days=ingredient.lead_time_days,
        cost_per_unit=float(ingredient.cost_per_unit) if ingredient.cost_per_unit is not None else None,
        default_supplier_id=ingredient.default_supplier_id,
        is_active=bool(ingredient.is_active),
        quantity_on_hand=float(quantity),
        stock_status=stock_status(quantity, ingredient.minimum_stock, ingredient.safety_stock),
        has_recipe=ingredient.ingredient_id in recipe_ids,
    )


@router.get("", response_model=list[IngredientOut])
def list_inventory(
    user: ManagerUser,
    include_inactive: bool = False,
    db: Session = Depends(get_db),
):
    query = select(Ingredient).order_by(Ingredient.ingredient_name)
    if not include_inactive:
        query = query.where(Ingredient.is_active.is_(True))
    ingredients = db.scalars(query).all()
    recipe_ids = {
        row[0] for row in db.execute(select(MenuItemIngredient.ingredient_id).distinct()).all()
    }
    return [_ingredient_payload(db, ingredient, recipe_ids) for ingredient in ingredients]


@router.post("/ingredients", response_model=IngredientOut, status_code=status.HTTP_201_CREATED)
def create_ingredient(
    payload: IngredientCreate,
    request: Request,
    user: ManagerUser,
    db: Session = Depends(get_db),
):
    if db.scalar(select(Ingredient).where(Ingredient.ingredient_name == payload.ingredient_name)):
        raise HTTPException(status.HTTP_409_CONFLICT, "Ingredient name already exists")
    data = payload.model_dump(exclude={"initial_stock"})
    ingredient = Ingredient(**data)
    db.add(ingredient)
    db.flush()
    stock = get_or_create_stock(db, ingredient)
    stock.quantity = q(payload.initial_stock)
    stock.updated_by = user.user_id
    if payload.initial_stock > 0:
        db.add(
            StockMovement(
                ingredient_id=ingredient.ingredient_id,
                movement_type="initial",
                quantity_change=q(payload.initial_stock),
                quantity_after=q(payload.initial_stock),
                reason="Initial stock configured by manager",
                user_id=user.user_id,
            )
        )
    audit.log_audit(
        db,
        user_id=user.user_id,
        action="inventory.ingredient_create",
        entity_type="ingredient",
        entity_id=str(ingredient.ingredient_id),
        details={"name": ingredient.ingredient_name, "initial_stock": payload.initial_stock},
        ip_address=request_ip(request),
    )
    db.commit()
    return _ingredient_payload(db, ingredient, set())


@router.patch("/ingredients/{ingredient_id}", response_model=IngredientOut)
def update_ingredient(
    ingredient_id: int,
    payload: IngredientUpdate,
    request: Request,
    user: ManagerUser,
    db: Session = Depends(get_db),
):
    ingredient = db.get(Ingredient, ingredient_id)
    if ingredient is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ingredient not found")
    data = payload.model_dump(exclude_unset=True)
    for key, value in data.items():
        setattr(ingredient, key, value)
    audit.log_audit(
        db,
        user_id=user.user_id,
        action="inventory.ingredient_update",
        entity_type="ingredient",
        entity_id=str(ingredient_id),
        details={"fields": list(data.keys())},
        ip_address=request_ip(request),
    )
    db.commit()
    recipe_ids = {
        row[0] for row in db.execute(select(MenuItemIngredient.ingredient_id).distinct()).all()
    }
    return _ingredient_payload(db, ingredient, recipe_ids)


@router.get("/low-stock")
def low_stock(user: ManagerUser, db: Session = Depends(get_db)):
    ingredients = db.scalars(select(Ingredient).where(Ingredient.is_active.is_(True))).all()
    result = []
    for ingredient in ingredients:
        stock = db.scalar(
            select(InventoryStock).where(InventoryStock.ingredient_id == ingredient.ingredient_id)
        )
        quantity = q(stock.quantity) if stock else Decimal("0")
        status = stock_status(quantity, ingredient.minimum_stock, ingredient.safety_stock)
        if status != "ok":
            result.append(
                {
                    "ingredient_id": ingredient.ingredient_id,
                    "ingredient_name": ingredient.ingredient_name,
                    "ingredient_name_ar": ingredient.ingredient_name_ar,
                    "unit_of_measure": ingredient.unit_of_measure,
                    "quantity_on_hand": float(quantity),
                    "minimum_stock": float(ingredient.minimum_stock),
                    "safety_stock": float(ingredient.safety_stock),
                    "status": status,
                }
            )
    return sorted(result, key=lambda row: row["quantity_on_hand"])


@router.get("/movements")
def list_movements(
    user: ManagerUser,
    ingredient_id: Optional[int] = None,
    movement_type: Optional[str] = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    query = (
        select(StockMovement)
        .options(selectinload(StockMovement.ingredient), selectinload(StockMovement.user))
        .order_by(StockMovement.created_at.desc())
    )
    if ingredient_id:
        query = query.where(StockMovement.ingredient_id == ingredient_id)
    if movement_type:
        query = query.where(StockMovement.movement_type == movement_type)
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    movements = db.scalars(query.offset((page - 1) * page_size).limit(page_size)).all()
    return {
        "items": [
            {
                "movement_id": m.movement_id,
                "ingredient_id": m.ingredient_id,
                "ingredient_name": m.ingredient.ingredient_name if m.ingredient else None,
                "movement_type": m.movement_type,
                "quantity_change": float(m.quantity_change),
                "quantity_after": float(m.quantity_after),
                "reason": m.reason,
                "reference_type": m.reference_type,
                "reference_id": m.reference_id,
                "order_id": m.order_id,
                "purchase_order_id": m.purchase_order_id,
                "user_id": m.user_id,
                "user_name": (m.user.full_name or m.user.username) if m.user else None,
                "created_at": m.created_at,
            }
            for m in movements
        ],
        "total": int(total or 0),
        "page": page,
        "page_size": page_size,
    }


@router.post("/stock-movements")
def create_stock_movement(
    payload: StockMovementCreate,
    request: Request,
    user: ManagerUser,
    db: Session = Depends(get_db),
):
    ingredient = db.get(Ingredient, payload.ingredient_id)
    if ingredient is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ingredient not found")
    sign = 1
    if payload.movement_type == "waste":
        sign = -1
    elif payload.movement_type == "adjustment" and payload.direction == "decrease":
        sign = -1
    if payload.movement_type == "purchase" and payload.direction == "decrease":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "A purchase must increase stock")
    movement = record_movement(
        db,
        ingredient=ingredient,
        movement_type=payload.movement_type,
        quantity_change=q(payload.quantity) * sign,
        reason=payload.reason or payload.movement_type.capitalize(),
        user_id=user.user_id,
        reference_type="manual",
    )
    audit.log_audit(
        db,
        user_id=user.user_id,
        action=f"inventory.{payload.movement_type}",
        entity_type="ingredient",
        entity_id=str(ingredient.ingredient_id),
        details={
            "quantity": payload.quantity,
            "direction": "decrease" if sign < 0 else "increase",
            "reason": payload.reason,
        },
        ip_address=request_ip(request),
    )
    db.commit()
    return {
        "movement_id": movement.movement_id,
        "ingredient_id": movement.ingredient_id,
        "quantity_change": float(movement.quantity_change),
        "quantity_after": float(movement.quantity_after),
    }


@router.get("/recipes/{item_id}", response_model=list[RecipeOut])
def get_recipe(item_id: int, user: ManagerUser, db: Session = Depends(get_db)):
    if db.get(MenuItem, item_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Menu item not found")
    lines = db.scalars(
        select(MenuItemIngredient)
        .options(selectinload(MenuItemIngredient.ingredient))
        .where(MenuItemIngredient.item_id == item_id)
    ).all()
    return [
        RecipeOut(
            menu_item_ingredient_id=line.menu_item_ingredient_id,
            item_id=line.item_id,
            ingredient_id=line.ingredient_id,
            ingredient_name=line.ingredient.ingredient_name if line.ingredient else None,
            quantity=float(line.quantity),
            unit_of_measure=line.unit_of_measure,
            notes=line.notes,
        )
        for line in lines
    ]


@router.put("/recipes/{item_id}", response_model=list[RecipeOut])
def set_recipe(
    item_id: int,
    lines: list[RecipeLineIn],
    request: Request,
    user: ManagerUser,
    db: Session = Depends(get_db),
):
    item = db.get(MenuItem, item_id)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Menu item not found")
    seen = set()
    for line in lines:
        if line.ingredient_id in seen:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Duplicate ingredient in recipe")
        seen.add(line.ingredient_id)
        if db.get(Ingredient, line.ingredient_id) is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Ingredient {line.ingredient_id} not found")
    existing = db.scalars(
        select(MenuItemIngredient).where(MenuItemIngredient.item_id == item_id)
    ).all()
    for row in existing:
        db.delete(row)
    db.flush()
    for line in lines:
        db.add(
            MenuItemIngredient(
                item_id=item_id,
                ingredient_id=line.ingredient_id,
                quantity=q(line.quantity),
                unit_of_measure=line.unit_of_measure,
                notes=line.notes,
            )
        )
    audit.log_audit(
        db,
        user_id=user.user_id,
        action="inventory.recipe_update",
        entity_type="menu_item",
        entity_id=str(item_id),
        details={"lines": len(lines)},
        ip_address=request_ip(request),
    )
    db.commit()
    return get_recipe(item_id, user, db)


@router.get("/recommendations")
def recommendations(
    user: ManagerUser,
    horizon_days: int = Query(default=7, ge=1, le=60),
    db: Session = Depends(get_db),
):
    return purchase_recommendations(db, horizon_days)


@router.get("/movements/{order_id}", include_in_schema=False)
def order_movements(order_id: int, user: ManagerUser, db: Session = Depends(get_db)):
    predecessor = db.scalar(
        select(StockMovement).where(StockMovement.order_id == order_id).limit(1)
    )
    if predecessor is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No movements for this order")
    return {"order_id": order_id}


# --------------------------------------------------------------------------- #
# Suppliers
# --------------------------------------------------------------------------- #
@supplier_router.get("", response_model=list[SupplierOut])
def list_suppliers(user: ManagerUser, db: Session = Depends(get_db)):
    suppliers = db.scalars(select(Supplier).order_by(Supplier.supplier_name)).all()
    return [SupplierOut.model_validate(s) for s in suppliers]


@supplier_router.post("", response_model=SupplierOut, status_code=status.HTTP_201_CREATED)
def create_supplier(
    payload: SupplierCreate,
    request: Request,
    user: ManagerUser,
    db: Session = Depends(get_db),
):
    if db.scalar(select(Supplier).where(Supplier.supplier_name == payload.supplier_name)):
        raise HTTPException(status.HTTP_409_CONFLICT, "Supplier already exists")
    supplier = Supplier(**payload.model_dump())
    db.add(supplier)
    db.flush()
    audit.log_audit(
        db,
        user_id=user.user_id,
        action="supplier.create",
        entity_type="supplier",
        entity_id=str(supplier.supplier_id),
        details={"name": supplier.supplier_name},
        ip_address=request_ip(request),
    )
    db.commit()
    return SupplierOut.model_validate(supplier)


@supplier_router.patch("/{supplier_id}", response_model=SupplierOut)
def update_supplier(
    supplier_id: int,
    payload: SupplierUpdate,
    request: Request,
    user: ManagerUser,
    db: Session = Depends(get_db),
):
    supplier = db.get(Supplier, supplier_id)
    if supplier is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Supplier not found")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(supplier, key, value)
    audit.log_audit(
        db,
        user_id=user.user_id,
        action="supplier.update",
        entity_type="supplier",
        entity_id=str(supplier_id),
        ip_address=request_ip(request),
    )
    db.commit()
    return SupplierOut.model_validate(supplier)


# --------------------------------------------------------------------------- #
# Purchase orders
# --------------------------------------------------------------------------- #
def _po_payload(purchase: PurchaseOrder) -> PurchaseOrderOut:
    return PurchaseOrderOut(
        purchase_order_id=purchase.purchase_order_id,
        supplier_id=purchase.supplier_id,
        supplier_name=purchase.supplier.supplier_name if purchase.supplier else None,
        status=purchase.status,
        order_date=purchase.order_date,
        expected_date=purchase.expected_date,
        received_at=purchase.received_at,
        total_amount=float(purchase.total_amount),
        notes=purchase.notes,
        created_by=purchase.created_by,
        items=[
            {
                "purchase_order_item_id": line.purchase_order_item_id,
                "ingredient_id": line.ingredient_id,
                "ingredient_name": line.ingredient.ingredient_name if line.ingredient else None,
                "unit_of_measure": line.ingredient.unit_of_measure if line.ingredient else None,
                "quantity_ordered": float(line.quantity_ordered),
                "quantity_received": float(line.quantity_received),
                "unit_cost": float(line.unit_cost) if line.unit_cost is not None else None,
            }
            for line in purchase.items
        ],
    )


def _load_po(db: Session, purchase_id: int) -> PurchaseOrder:
    purchase = db.scalar(
        select(PurchaseOrder)
        .options(
            selectinload(PurchaseOrder.items).selectinload(PurchaseOrderItem.ingredient),
            selectinload(PurchaseOrder.supplier),
        )
        .where(PurchaseOrder.purchase_order_id == purchase_id)
    )
    if purchase is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Purchase order not found")
    return purchase


@purchase_router.get("", response_model=dict)
def list_purchase_orders(
    user: ManagerUser,
    status_filter: Optional[str] = Query(default=None, alias="status"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    query = (
        select(PurchaseOrder)
        .options(
            selectinload(PurchaseOrder.items).selectinload(PurchaseOrderItem.ingredient),
            selectinload(PurchaseOrder.supplier),
        )
        .order_by(PurchaseOrder.order_date.desc())
    )
    if status_filter:
        query = query.where(PurchaseOrder.status == status_filter)
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    rows = db.scalars(query.offset((page - 1) * page_size).limit(page_size)).all()
    return {
        "items": [_po_payload(row) for row in rows],
        "total": int(total or 0),
        "page": page,
        "page_size": page_size,
    }


@purchase_router.post("", response_model=PurchaseOrderOut, status_code=status.HTTP_201_CREATED)
def create_purchase_order(
    payload: PurchaseOrderCreate,
    request: Request,
    user: ManagerUser,
    db: Session = Depends(get_db),
):
    supplier = db.get(Supplier, payload.supplier_id)
    if supplier is None or not supplier.is_active:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Supplier is not available")
    if not payload.items:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "At least one item is required")
    seen = set()
    total = Decimal("0")
    purchase = PurchaseOrder(
        supplier_id=payload.supplier_id,
        status="ordered" if payload.submit else "draft",
        expected_date=payload.expected_date,
        notes=payload.notes,
        created_by=user.user_id,
    )
    db.add(purchase)
    db.flush()
    for line in payload.items:
        if line.ingredient_id in seen:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Duplicate ingredient in purchase order")
        seen.add(line.ingredient_id)
        if db.get(Ingredient, line.ingredient_id) is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Ingredient {line.ingredient_id} not found")
        unit_cost = Decimal(str(line.unit_cost)) if line.unit_cost is not None else None
        if unit_cost is not None:
            total += unit_cost * q(line.quantity_ordered)
        db.add(
            PurchaseOrderItem(
                purchase_order_id=purchase.purchase_order_id,
                ingredient_id=line.ingredient_id,
                quantity_ordered=q(line.quantity_ordered),
                unit_cost=unit_cost,
            )
        )
    purchase.total_amount = total.quantize(Decimal("0.01"))
    audit.log_audit(
        db,
        user_id=user.user_id,
        action="purchase.create",
        entity_type="purchase_order",
        entity_id=str(purchase.purchase_order_id),
        details={"supplier_id": payload.supplier_id, "lines": len(payload.items)},
        ip_address=request_ip(request),
    )
    db.commit()
    return _po_payload(_load_po(db, purchase.purchase_order_id))


@purchase_router.patch("/{purchase_id}", response_model=PurchaseOrderOut)
def receive_purchase(
    purchase_id: int,
    payload: ReceivePurchaseOrder,
    request: Request,
    user: ManagerUser,
    db: Session = Depends(get_db),
):
    purchase = _load_po(db, purchase_id)
    receive_purchase_order(db, purchase=purchase, receipts=payload.items, user=user)
    audit.log_audit(
        db,
        user_id=user.user_id,
        action="purchase.receive",
        entity_type="purchase_order",
        entity_id=str(purchase_id),
        ip_address=request_ip(request),
    )
    db.commit()
    return _po_payload(_load_po(db, purchase_id))
