"""Inventory, recipe consumption, purchasing and recommendation logic."""
from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

from fastapi import HTTPException, status as http_status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import (
    Ingredient,
    InventoryStock,
    MenuItemIngredient,
    Order,
    OrderItem,
    OrderStockApplication,
    PurchaseOrder,
    PurchaseOrderItem,
    StockMovement,
    Supplier,
    User,
)
from app.services import audit

QTY = Decimal("0.001")


def q(value) -> Decimal:
    return Decimal(str(value)).quantize(QTY, rounding=ROUND_HALF_UP)


def stock_status(quantity: Decimal, minimum: Decimal, safety: Decimal = Decimal("0")) -> str:
    if quantity <= 0:
        return "out"
    if quantity <= minimum:
        return "critical"
    if quantity <= minimum + safety:
        return "low"
    return "ok"


def get_or_create_stock(db: Session, ingredient: Ingredient) -> InventoryStock:
    stock = db.scalar(select(InventoryStock).where(InventoryStock.ingredient_id == ingredient.ingredient_id))
    if stock is None:
        stock = InventoryStock(ingredient_id=ingredient.ingredient_id, quantity=Decimal("0"))
        db.add(stock)
        db.flush()
    return stock


def record_movement(
    db: Session,
    *,
    ingredient: Ingredient,
    movement_type: str,
    quantity_change: Decimal,
    reason: Optional[str],
    user_id: Optional[int],
    reference_type: Optional[str] = None,
    reference_id: Optional[str] = None,
    order_id: Optional[int] = None,
    purchase_order_id: Optional[int] = None,
) -> StockMovement:
    stock = db.scalar(
        select(InventoryStock)
        .where(InventoryStock.ingredient_id == ingredient.ingredient_id)
        .with_for_update()
    )
    if stock is None:
        stock = InventoryStock(ingredient_id=ingredient.ingredient_id, quantity=Decimal("0"))
        db.add(stock)
        db.flush()

    change = q(quantity_change)
    new_quantity = q(stock.quantity) + change
    if new_quantity < 0:
        raise HTTPException(
            http_status.HTTP_409_CONFLICT,
            f"Stock cannot go negative for '{ingredient.ingredient_name}' "
            f"(available {q(stock.quantity)} {ingredient.unit_of_measure})",
        )
    stock.quantity = new_quantity
    stock.updated_by = user_id
    stock.last_updated = datetime.utcnow()
    movement = StockMovement(
        ingredient_id=ingredient.ingredient_id,
        movement_type=movement_type,
        quantity_change=change,
        quantity_after=new_quantity,
        reason=reason,
        reference_type=reference_type,
        reference_id=reference_id,
        order_id=order_id,
        purchase_order_id=purchase_order_id,
        user_id=user_id,
    )
    db.add(movement)
    db.flush()
    return movement


def consume_order_ingredients(db: Session, *, order: Order, user: Optional[User]) -> dict:
    """Consume recipes exactly once per order.

    Only configured recipes are consumed; unconfigured products are reported
    and never guessed.
    """
    existing = db.get(OrderStockApplication, order.order_id)
    if existing and existing.status == "applied":
        return {"applied": False, "reason": "already_applied", "unconfigured_items": []}

    required: dict[int, Decimal] = {}
    unconfigured: set[str] = set()
    for line in order.items:
        rows = db.scalars(
            select(MenuItemIngredient).where(MenuItemIngredient.item_id == line.item_id)
        ).all()
        if not rows:
            unconfigured.add(line.item_name_snapshot or f"item {line.item_id}")
            continue
        for row in rows:
            required[row.ingredient_id] = required.get(row.ingredient_id, Decimal("0")) + q(
                row.quantity
            ) * line.quantity

    if not required:
        return {
            "applied": False,
            "reason": "no_configured_recipes",
            "unconfigured_items": sorted(unconfigured),
        }

    shortages = []
    for ingredient_id, needed in required.items():
        ingredient = db.get(Ingredient, ingredient_id)
        stock = db.scalar(
            select(InventoryStock)
            .where(InventoryStock.ingredient_id == ingredient_id)
            .with_for_update()
        )
        available = q(stock.quantity) if stock else Decimal("0")
        if available < needed:
            shortages.append(
                {
                    "ingredient_id": ingredient_id,
                    "ingredient": ingredient.ingredient_name if ingredient else str(ingredient_id),
                    "required": float(needed),
                    "available": float(available),
                    "unit": ingredient.unit_of_measure if ingredient else "",
                }
            )
    if shortages:
        raise HTTPException(
            http_status.HTTP_409_CONFLICT,
            detail={"message": "Insufficient stock for this order", "shortages": shortages},
        )

    for ingredient_id, needed in required.items():
        ingredient = db.get(Ingredient, ingredient_id)
        record_movement(
            db,
            ingredient=ingredient,
            movement_type="consumption",
            quantity_change=-needed,
            reason=f"Recipe consumption for order #{order.order_id}",
            user_id=user.user_id if user else None,
            reference_type="order",
            reference_id=str(order.order_id),
            order_id=order.order_id,
        )

    app = OrderStockApplication(
        order_id=order.order_id,
        status="applied",
        applied_by=user.user_id if user else None,
        note=(
            "Unconfigured recipes (not consumed): " + ", ".join(sorted(unconfigured))
            if unconfigured
            else "All order items had configured recipes"
        ),
    )
    db.add(app)
    db.flush()
    audit.log_audit(
        db,
        user_id=user.user_id if user else None,
        action="inventory.consume_order",
        entity_type="order",
        entity_id=str(order.order_id),
        details={"ingredients": len(required), "unconfigured_items": sorted(unconfigured)},
    )
    return {
        "applied": True,
        "ingredients_consumed": len(required),
        "unconfigured_items": sorted(unconfigured),
    }


def reverse_order_consumption(db: Session, *, order: Order, user: Optional[User]) -> dict:
    app = db.get(OrderStockApplication, order.order_id)
    if app is None or app.status == "reversed":
        return {"reversed": False, "reason": "nothing_to_reverse"}

    movements = db.scalars(
        select(StockMovement).where(
            StockMovement.order_id == order.order_id,
            StockMovement.movement_type == "consumption",
        )
    ).all()
    totals: dict[int, Decimal] = {}
    for movement in movements:
        totals[movement.ingredient_id] = totals.get(movement.ingredient_id, Decimal("0")) + abs(
            q(movement.quantity_change)
        )
    for ingredient_id, quantity in totals.items():
        ingredient = db.get(Ingredient, ingredient_id)
        record_movement(
            db,
            ingredient=ingredient,
            movement_type="return",
            quantity_change=quantity,
            reason=f"Cancellation reversal for order #{order.order_id}",
            user_id=user.user_id if user else None,
            reference_type="order",
            reference_id=str(order.order_id),
            order_id=order.order_id,
        )
    app.status = "reversed"
    app.reversed_at = datetime.utcnow()
    app.reversed_by = user.user_id if user else None
    db.flush()
    audit.log_audit(
        db,
        user_id=user.user_id if user else None,
        action="inventory.reverse_order",
        entity_type="order",
        entity_id=str(order.order_id),
        details={"ingredients": len(totals)},
    )
    return {"reversed": True, "ingredients_restored": len(totals)}


def receive_purchase_order(
    db: Session, *, purchase: PurchaseOrder, receipts: list, user: User
) -> PurchaseOrder:
    if purchase.status in ("received", "cancelled"):
        raise HTTPException(http_status.HTTP_409_CONFLICT, "This purchase order cannot be received")
    received_map = {r.purchase_order_item_id: q(r.quantity) for r in receipts}
    total_received = Decimal("0")
    total_ordered = Decimal("0")
    for line in purchase.items:
        total_ordered += q(line.quantity_ordered)
        if line.purchase_order_item_id not in received_map:
            total_received += q(line.quantity_received)
            continue
        receive_now = received_map[line.purchase_order_item_id]
        if receive_now <= 0:
            total_received += q(line.quantity_received)
            continue
        if q(line.quantity_received) + receive_now > q(line.quantity_ordered):
            raise HTTPException(
                http_status.HTTP_400_BAD_REQUEST,
                f"Cannot receive more than ordered for ingredient {line.ingredient_id}",
            )
        ingredient = db.get(Ingredient, line.ingredient_id)
        record_movement(
            db,
            ingredient=ingredient,
            movement_type="purchase",
            quantity_change=receive_now,
            reason=f"Received purchase order #{purchase.purchase_order_id}",
            user_id=user.user_id,
            reference_type="purchase_order",
            reference_id=str(purchase.purchase_order_id),
            purchase_order_id=purchase.purchase_order_id,
        )
        line.quantity_received = q(line.quantity_received) + receive_now
        total_received += q(line.quantity_received)
        if line.unit_cost is not None and ingredient is not None:
            ingredient.cost_per_unit = line.unit_cost

    if total_received >= total_ordered:
        purchase.status = "received"
        purchase.received_at = datetime.utcnow()
    elif total_received > 0:
        purchase.status = "partially_received"
    db.flush()
    audit.log_audit(
        db,
        user_id=user.user_id,
        action="purchase.receive",
        entity_type="purchase_order",
        entity_id=str(purchase.purchase_order_id),
        details={"status": purchase.status},
    )
    return purchase


def purchase_recommendations(db: Session, horizon_days: int = 7) -> list[dict]:
    since = datetime.utcnow() - timedelta(days=30)
    usage_rows = db.execute(
        select(
            StockMovement.ingredient_id,
            func.coalesce(func.sum(-StockMovement.quantity_change), 0),
        )
        .where(
            StockMovement.movement_type == "consumption",
            StockMovement.created_at >= since,
        )
        .group_by(StockMovement.ingredient_id)
    ).all()
    usage = {row[0]: q(row[1]) for row in usage_rows}

    ingredients = db.scalars(
        select(Ingredient).where(Ingredient.is_active.is_(True)).order_by(Ingredient.ingredient_name)
    ).all()
    recommendations: list[dict] = []
    for ingredient in ingredients:
        stock = db.scalar(
            select(InventoryStock).where(InventoryStock.ingredient_id == ingredient.ingredient_id)
        )
        current = q(stock.quantity) if stock else Decimal("0")
        consumed_30 = usage.get(ingredient.ingredient_id, Decimal("0"))
        daily = q(consumed_30 / Decimal("30"))
        expected_demand = q(daily * Decimal(horizon_days + ingredient.lead_time_days))
        target = expected_demand + q(ingredient.minimum_stock) + q(ingredient.safety_stock)
        suggested = target - current
        if suggested <= 0:
            continue
        if consumed_30 > 0:
            reason = (
                f"30-day usage {float(consumed_30):g} {ingredient.unit_of_measure}; "
                f"expected demand {float(expected_demand):g} over "
                f"{horizon_days + ingredient.lead_time_days} days "
                f"(lead time {ingredient.lead_time_days}d) + safety/minimum stock."
            )
        else:
            reason = "No consumption history: recommendation is based on configured minimum and safety stock only."
        recommendations.append(
            {
                "ingredient_id": ingredient.ingredient_id,
                "ingredient_name": ingredient.ingredient_name,
                "unit_of_measure": ingredient.unit_of_measure,
                "current_quantity": float(current),
                "minimum_stock": float(ingredient.minimum_stock),
                "safety_stock": float(ingredient.safety_stock),
                "expected_demand": float(expected_demand),
                "suggested_quantity": float(q(suggested)),
                "lead_time_days": ingredient.lead_time_days,
                "reason": reason,
            }
        )
    return recommendations
