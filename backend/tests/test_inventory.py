"""Inventory, recipe, supplier and purchasing tests."""
from __future__ import annotations

from sqlalchemy import select

from app.models import InventoryStock


def test_manager_can_create_and_adjust_inventory(client, login, seeded):
    manager = login("manager1")
    chef = login("chef1")

    assert client.get("/api/inventory", headers=chef).status_code == 403

    created = client.post(
        "/api/inventory/ingredients",
        headers=manager,
        json={
            "ingredient_name": "Tomato",
            "ingredient_name_ar": "طماطم",
            "unit_of_measure": "kg",
            "minimum_stock": 30,
            "safety_stock": 5,
            "lead_time_days": 2,
            "cost_per_unit": 12.5,
            "initial_stock": 20,
        },
    )
    assert created.status_code == 201, created.text
    ingredient_id = created.json()["ingredient_id"]
    assert created.json()["quantity_on_hand"] == 20

    purchase = client.post(
        "/api/inventory/stock-movements",
        headers=manager,
        json={
            "ingredient_id": ingredient_id,
            "movement_type": "purchase",
            "quantity": 10,
            "reason": "Test delivery",
        },
    )
    assert purchase.status_code == 200
    assert purchase.json()["quantity_after"] == 30

    waste = client.post(
        "/api/inventory/stock-movements",
        headers=manager,
        json={
            "ingredient_id": ingredient_id,
            "movement_type": "waste",
            "quantity": 2.5,
            "reason": "Spoiled",
        },
    )
    assert waste.status_code == 200
    assert waste.json()["quantity_after"] == 27.5

    negative = client.post(
        "/api/inventory/stock-movements",
        headers=manager,
        json={
            "ingredient_id": ingredient_id,
            "movement_type": "waste",
            "quantity": 100,
            "reason": "Impossible",
        },
    )
    assert negative.status_code == 409

    movements = client.get(
        f"/api/inventory/movements?ingredient_id={ingredient_id}", headers=manager
    )
    assert movements.status_code == 200
    types = [row["movement_type"] for row in movements.json()["items"]]
    assert "initial" in types and "purchase" in types and "waste" in types

    low = client.get("/api/inventory/low-stock", headers=manager)
    assert low.status_code == 200
    assert any(row["ingredient_id"] == ingredient_id for row in low.json())

    recommendations = client.get("/api/inventory/recommendations", headers=manager)
    assert recommendations.status_code == 200
    assert any(row["ingredient_id"] == ingredient_id for row in recommendations.json())


def test_recipes_are_read_and_replaced(client, db, login, seeded):
    manager = login("manager1")
    burger_id = seeded["item_ids"]["burger"]
    truffle_id = seeded["item_ids"]["truffle"]
    patty = seeded["ingredients"]["patty"]
    bun = seeded["ingredients"]["bun"]

    recipe = client.get(f"/api/inventory/recipes/{burger_id}", headers=manager)
    assert recipe.status_code == 200
    assert len(recipe.json()) == 2

    replacement = client.put(
        f"/api/inventory/recipes/{truffle_id}",
        headers=manager,
        json=[
            {"ingredient_id": patty, "quantity": 1.5, "unit_of_measure": "pcs"},
            {"ingredient_id": bun, "quantity": 1, "unit_of_measure": "pcs"},
        ],
    )
    assert replacement.status_code == 200, replacement.text
    rows = replacement.json()
    assert len(rows) == 2
    assert {row["ingredient_id"] for row in rows} == {patty, bun}

    # Unconfigured recipes are reported, never guessed.
    empty = client.get(f"/api/inventory/recipes/{seeded['item_ids']['mojito']}", headers=manager)
    assert empty.status_code == 200
    assert len(empty.json()) == 1


def test_supplier_and_purchase_order_receiving(client, login, seeded):
    manager = login("manager1")
    chef = login("chef1")

    assert client.get("/api/suppliers", headers=chef).status_code == 403

    supplier = client.post(
        "/api/suppliers",
        headers=manager,
        json={
            "supplier_name": "Test Supplier",
            "contact_name": "Sam Supplier",
            "phone": "01000000002",
            "email": "supplier@example.com",
        },
    )
    assert supplier.status_code == 201, supplier.text
    supplier_id = supplier.json()["supplier_id"]

    duplicate = client.post(
        "/api/suppliers",
        headers=manager,
        json={"supplier_name": "Test Supplier"},
    )
    assert duplicate.status_code == 409

    ingredient = client.post(
        "/api/inventory/ingredients",
        headers=manager,
        json={
            "ingredient_name": "Lettuce",
            "unit_of_measure": "kg",
            "minimum_stock": 2,
            "initial_stock": 5,
        },
    )
    assert ingredient.status_code == 201
    ingredient_id = ingredient.json()["ingredient_id"]

    purchase = client.post(
        "/api/purchase-orders",
        headers=manager,
        json={
            "supplier_id": supplier_id,
            "notes": "Weekly restock",
            "submit": True,
            "items": [{"ingredient_id": ingredient_id, "quantity_ordered": 20, "unit_cost": 3.5}],
        },
    )
    assert purchase.status_code == 201, purchase.text
    po = purchase.json()
    assert po["status"] == "ordered"
    assert po["total_amount"] == 70
    line_id = po["items"][0]["purchase_order_item_id"]

    received = client.patch(
        f"/api/purchase-orders/{po['purchase_order_id']}",
        headers=manager,
        json={"items": [{"purchase_order_item_id": line_id, "quantity": 20}]},
    )
    assert received.status_code == 200, received.text
    assert received.json()["status"] == "received"

    stock = client.get("/api/inventory", headers=manager).json()
    row = next(item for item in stock if item["ingredient_id"] == ingredient_id)
    assert row["quantity_on_hand"] == 25

    history = client.get("/api/purchase-orders", headers=manager)
    assert history.status_code == 200
    assert any(item["purchase_order_id"] == po["purchase_order_id"] for item in history.json()["items"])

    # Receiving the same PO twice is rejected.
    again = client.patch(
        f"/api/purchase-orders/{po['purchase_order_id']}",
        headers=manager,
        json={"items": [{"purchase_order_item_id": line_id, "quantity": 1}]},
    )
    assert again.status_code == 409


def test_stock_movement_never_goes_negative(client, db, login, seeded):
    manager = login("manager1")
    stock = db.scalar(
        select(InventoryStock).where(
            InventoryStock.ingredient_id == seeded["ingredients"]["bun"]
        )
    )
    stock.quantity = 1
    db.commit()

    response = client.post(
        "/api/inventory/stock-movements",
        headers=manager,
        json={
            "ingredient_id": seeded["ingredients"]["bun"],
            "movement_type": "adjustment",
            "direction": "decrease",
            "quantity": 5,
        },
    )
    assert response.status_code == 409

