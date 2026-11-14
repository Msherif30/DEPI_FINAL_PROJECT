"""Manager menu management and audit-log tests."""
from __future__ import annotations


def test_manager_can_create_update_and_retire_menu_items(client, login, seeded):
    manager = login("manager1")
    chef = login("chef1")
    category_id = seeded["category_ids"]["burgers"]

    denied = client.post(
        "/api/menu",
        headers=chef,
        json={
            "category_id": category_id,
            "item_name": "Chef Item",
            "item_name_ar": "صنف الشيف",
            "price": 10,
        },
    )
    assert denied.status_code == 403

    created = client.post(
        "/api/menu",
        headers=manager,
        json={
            "category_id": category_id,
            "item_name": "Test Burger",
            "item_name_ar": "برجر اختبار",
            "synonyms": "test,اختبار",
            "price": 99.5,
            "description": "Created by an automated test",
            "preparation_time": 10,
            "is_featured": True,
        },
    )
    assert created.status_code == 201, created.text
    item = created.json()
    item_id = item["item_id"]
    assert item["price"] == 99.5
    assert item["is_featured"] is True
    assert item["category_name"] == "Burgers"

    updated = client.patch(
        f"/api/menu/{item_id}",
        headers=manager,
        json={"price": 109.75, "is_available": False},
    )
    assert updated.status_code == 200
    assert updated.json()["price"] == 109.75
    assert updated.json()["is_available"] is False

    # Unused items can be deleted.
    deleted = client.delete(f"/api/menu/{item_id}", headers=manager)
    assert deleted.status_code == 200
    assert client.get(f"/api/menu/{item_id}").status_code == 404

    # Items referenced by order history are retired, never deleted.
    used = client.post(
        "/api/menu",
        headers=manager,
        json={
            "category_id": category_id,
            "item_name": "Used Burger",
            "item_name_ar": "برجر مستخدم",
            "price": 80,
            "is_available": True,
        },
    ).json()
    customer = login("customer1")
    order = client.post(
        "/api/orders",
        headers=customer,
        json={"items": [{"item_id": used["item_id"], "quantity": 1}], "payment_method": "cash"},
    )
    assert order.status_code == 201

    retired = client.delete(f"/api/menu/{used['item_id']}", headers=manager)
    assert retired.status_code == 200
    assert retired.json()["is_available"] is False
    assert client.get(f"/api/menu/{used['item_id']}").status_code == 200


def test_categories_and_search(client, login, seeded):
    manager = login("manager1")

    category = client.post(
        "/api/menu/categories",
        headers=manager,
        json={"category_name": "Test Category", "category_name_ar": "فئة اختبار"},
    )
    assert category.status_code == 201
    category_id = category.json()["category_id"]

    updated = client.patch(
        f"/api/menu/categories/{category_id}",
        headers=manager,
        json={"description": "Updated description"},
    )
    assert updated.status_code == 200
    assert updated.json()["description"] == "Updated description"

    client.post(
        "/api/menu",
        headers=manager,
        json={
            "category_id": category_id,
            "item_name": "Searchable Wrap",
            "item_name_ar": "راب قابل للبحث",
            "price": 55,
            "synonyms": "wrap,راب",
        },
    )
    search = client.get("/api/menu?q=Searchable")
    assert search.status_code == 200
    assert any(row["item_name"] == "Searchable Wrap" for row in search.json()["items"])

    arabic = client.get("/api/menu?q=راب")
    assert arabic.status_code == 200
    assert any(row["item_name"] == "Searchable Wrap" for row in arabic.json()["items"])


def test_audit_log_records_security_and_operational_events(client, login, seeded):
    chef = login("chef1")
    assert client.get("/api/analytics/audit-logs", headers=chef).status_code == 403

    manager = login("manager1")
    client.post("/api/suppliers", headers=manager, json={"supplier_name": "Audit Supplier"})

    response = client.get("/api/analytics/audit-logs?limit=200", headers=manager)
    assert response.status_code == 200
    rows = response.json()
    actions = [row["action"] for row in rows]

    assert "auth.login" in actions
    assert "supplier.create" in actions
    assert all("password" not in (row["details"] or {}) for row in rows)
    supplier_event = next(row for row in rows if row["action"] == "supplier.create")
    assert supplier_event["entity_type"] == "supplier"
    assert supplier_event["user_name"]
    assert supplier_event["created_at"]
