"""Order lifecycle, pricing, role transition, payment and stock tests."""
from __future__ import annotations

from sqlalchemy import select

from app.models import InventoryStock, Order, OrderStockApplication, StockMovement


def _create_order(client, headers, lines, **extra):
    payload = {"items": lines, "payment_method": "cash", **extra}
    response = client.post("/api/orders", headers=headers, json=payload)
    assert response.status_code == 201, response.text
    return response.json()["order"]


def _set_status(client, headers, order_id, status):
    return client.patch(
        f"/api/orders/{order_id}/status", headers=headers, json={"status": status}
    )


def _stock(client, headers, ingredient_id):
    response = client.get("/api/inventory", headers=headers)
    assert response.status_code == 200
    return next(row for row in response.json() if row["ingredient_id"] == ingredient_id)


def test_customer_order_pricing_and_full_lifecycle(client, db, login, seeded):
    customer = login("customer1")
    order = _create_order(
        client,
        customer,
        [
            {"item_id": seeded["item_ids"]["burger"], "quantity": 2},
            {"item_id": seeded["item_ids"]["mojito"], "quantity": 1, "special_instructions": "No ice"},
        ],
        order_notes="Test order",
        idempotency_key="lifecycle-1",
    )
    order_id = order["order_id"]
    # 2 * 120 + 1 * 60; prices are computed server-side only.
    assert order["total_amount"] == 300
    assert order["status"] == "pending"
    assert order["order_source"] == "web_app"

    duplicate = _create_order(
        client,
        customer,
        [{"item_id": seeded["item_ids"]["burger"], "quantity": 2}],
        idempotency_key="lifecycle-1",
    )
    assert duplicate["order_id"] == order_id

    cashier = login("cashier1")
    chef = login("chef1")
    manager = login("manager1")

    # Chef cannot confirm a pending order; cashier cannot start preparation.
    assert _set_status(client, chef, order_id, "confirmed").status_code == 403
    assert _set_status(client, cashier, order_id, "preparing").status_code == 403
    # Customers cannot use the staff transition endpoint at all.
    assert _set_status(client, customer, order_id, "confirmed").status_code == 403

    confirmed = _set_status(client, cashier, order_id, "confirmed")
    assert confirmed.status_code == 200
    assert confirmed.json()["order"]["status"] == "confirmed"

    patty_before = _stock(client, manager, seeded["ingredients"]["patty"])["quantity_on_hand"]
    bun_before = _stock(client, manager, seeded["ingredients"]["bun"])["quantity_on_hand"]
    mint_before = _stock(client, manager, seeded["ingredients"]["mint"])["quantity_on_hand"]

    preparing = _set_status(client, chef, order_id, "preparing")
    assert preparing.status_code == 200, preparing.text
    assert preparing.json()["inventory"]["applied"] is True
    assert _stock(client, manager, seeded["ingredients"]["patty"])["quantity_on_hand"] == patty_before - 2
    assert _stock(client, manager, seeded["ingredients"]["bun"])["quantity_on_hand"] == bun_before - 2
    assert _stock(client, manager, seeded["ingredients"]["mint"])["quantity_on_hand"] == mint_before - 10

    completed = _set_status(client, chef, order_id, "completed")
    assert completed.status_code == 200
    assert completed.json()["order"]["status"] == "completed"

    paid = client.patch(
        f"/api/orders/{order_id}/payment",
        headers=cashier,
        json={"payment_status": "paid", "transaction_reference": "TEST-REF-1"},
    )
    assert paid.status_code == 200, paid.text
    assert paid.json()["order"]["payment_status"] == "paid"
    assert paid.json()["order"]["payments"][0]["payment_status"] == "paid"

    detail = client.get(f"/api/orders/{order_id}", headers=customer).json()
    assert [row["new_status"] for row in detail["status_history"]] == [
        "pending",
        "confirmed",
        "preparing",
        "completed",
    ]
    assert detail["items"][0]["line_total"] == 240

    # Completed orders cannot be cancelled.
    assert _set_status(client, manager, order_id, "cancelled").status_code == 409


def test_cancellation_after_consumption_restores_stock(client, db, login, seeded):
    customer = login("customer1")
    cashier = login("cashier1")
    chef = login("chef1")
    manager = login("manager1")
    patty_id = seeded["ingredients"]["patty"]

    order = _create_order(
        client, customer, [{"item_id": seeded["item_ids"]["burger"], "quantity": 3}]
    )
    order_id = order["order_id"]
    assert _set_status(client, cashier, order_id, "confirmed").status_code == 200
    before = _stock(client, manager, patty_id)["quantity_on_hand"]
    assert _set_status(client, chef, order_id, "preparing").status_code == 200
    assert _stock(client, manager, patty_id)["quantity_on_hand"] == before - 3

    cancelled = _set_status(client, manager, order_id, "cancelled")
    assert cancelled.status_code == 200, cancelled.text
    assert cancelled.json()["inventory"]["reversed"] is True
    assert _stock(client, manager, patty_id)["quantity_on_hand"] == before

    application = db.get(OrderStockApplication, order_id)
    assert application is not None
    assert application.status == "reversed"
    returns = db.scalars(
        select(StockMovement).where(
            StockMovement.order_id == order_id, StockMovement.movement_type == "return"
        )
    ).all()
    assert len(returns) == 2  # patty + bun


def test_insufficient_stock_blocks_preparation(client, db, login, seeded):
    customer = login("customer1")
    cashier = login("cashier1")
    chef = login("chef1")
    patty_id = seeded["ingredients"]["patty"]

    stock = db.scalar(
        select(InventoryStock).where(InventoryStock.ingredient_id == patty_id)
    )
    stock.quantity = 0
    db.commit()

    order = _create_order(
        client, customer, [{"item_id": seeded["item_ids"]["burger"], "quantity": 1}]
    )
    order_id = order["order_id"]
    assert _set_status(client, cashier, order_id, "confirmed").status_code == 200

    blocked = _set_status(client, chef, order_id, "preparing")
    assert blocked.status_code == 409
    assert "Insufficient stock" in str(blocked.json()["detail"])
    # The transition is rolled back atomically.
    assert client.get(f"/api/orders/{order_id}", headers=customer).json()["status"] == "confirmed"

    db.expire_all()
    assert db.get(Order, order_id).status == "confirmed"


def test_staff_board_and_analytics_use_real_data(client, login, seeded):
    customer = login("customer1")
    cashier = login("cashier1")
    chef = login("chef1")
    manager = login("manager1")

    board_denied = client.get("/api/staff/orders", headers=customer)
    assert board_denied.status_code == 403

    order = _create_order(
        client, customer, [{"item_id": seeded["item_ids"]["truffle"], "quantity": 1}]
    )
    order_id = order["order_id"]
    assert _set_status(client, cashier, order_id, "confirmed").status_code == 200
    assert _set_status(client, chef, order_id, "preparing").status_code == 200
    assert _set_status(client, chef, order_id, "completed").status_code == 200
    assert client.patch(
        f"/api/orders/{order_id}/payment",
        headers=cashier,
        json={"payment_status": "paid"},
    ).status_code == 200

    board = client.get("/api/staff/orders?status=completed", headers=cashier)
    assert board.status_code == 200
    assert any(row["order_id"] == order_id for row in board.json()["items"])

    overview = client.get("/api/analytics/overview", headers=manager)
    assert overview.status_code == 200
    body = overview.json()
    assert body["completed_orders"] >= 1
    assert body["total_revenue"] >= 190
    assert body["paid_revenue"] >= 190
    assert body["average_order_value"] > 0

    products = client.get("/api/analytics/products?limit=5", headers=manager)
    assert products.status_code == 200
    assert any(row["item_name"] == "Truffle Burger" for row in products.json())
