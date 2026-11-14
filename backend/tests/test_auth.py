"""Authentication, session and role-boundary tests."""
from __future__ import annotations

from sqlalchemy import select

from app.core.security import verify_password
from app.models import User


def test_customer_login_returns_user_without_secrets(client, seeded):
    response = client.post(
        "/api/auth/login", json={"username": "customer1", "password": seeded["password"]}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["user"]["role"] == "customer"
    assert "password_hash" not in body["user"]
    assert "pin_hash" not in body["user"]
    assert "pin_code" not in body["user"]


def test_wrong_password_is_rejected(client):
    response = client.post("/api/auth/login", json={"username": "customer1", "password": "wrong-pass"})
    assert response.status_code == 401


def test_system_ai_account_cannot_log_in(client):
    response = client.post("/api/auth/login", json={"username": "system_ai", "password": "pass1234"})
    assert response.status_code == 403
    assert "system_ai" in response.json()["detail"]


def test_staff_pin_login(client, seeded):
    response = client.post("/api/auth/pin", json={"username": "chef1", "pin": "2468"})
    assert response.status_code == 200
    assert response.json()["user"]["role"] == "chef"

    bad = client.post("/api/auth/pin", json={"username": "chef1", "pin": "0000"})
    assert bad.status_code == 401

    customer = client.post("/api/auth/pin", json={"username": "customer1", "pin": "2468"})
    assert customer.status_code == 401


def test_legacy_sha256_login_is_upgraded_to_bcrypt(client, db, seeded):
    response = client.post(
        "/api/auth/login", json={"username": "legacy1", "password": "legacy123"}
    )
    assert response.status_code == 200

    db.expire_all()
    user = db.get(User, seeded["legacy_id"])
    assert user is not None
    assert user.password_algo == "bcrypt"
    assert user.password_hash.startswith("$2")
    assert verify_password("legacy123", user.password_hash, user.password_algo)


def test_register_profile_update_and_password_change(client):
    register = client.post(
        "/api/auth/register",
        json={
            "username": "new_customer",
            "email": "new_customer@example.com",
            "password": "initial123",
            "full_name": "New Customer",
            "phone": "01000000099",
            "address": "2 Test Street",
        },
    )
    assert register.status_code == 201, register.text
    token = register.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    me = client.get("/api/auth/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["customer"]["phone"] == "01000000099"

    update = client.patch(
        "/api/auth/me",
        headers=headers,
        json={"full_name": "Updated Customer", "address": "3 Test Street"},
    )
    assert update.status_code == 200
    assert update.json()["user"]["full_name"] == "Updated Customer"

    changed = client.post(
        "/api/auth/me/password",
        headers=headers,
        json={"current_password": "initial123", "new_password": "updated123"},
    )
    assert changed.status_code == 200

    old = client.post("/api/auth/login", json={"username": "new_customer", "password": "initial123"})
    assert old.status_code == 401
    new = client.post("/api/auth/login", json={"username": "new_customer", "password": "updated123"})
    assert new.status_code == 200


def test_logout_revokes_token(client):
    response = client.post("/api/auth/login", json={"username": "customer1", "password": "pass1234"})
    headers = {"Authorization": f"Bearer {response.json()['access_token']}"}
    assert client.get("/api/auth/me", headers=headers).status_code == 200

    logout = client.post("/api/auth/logout", headers=headers)
    assert logout.status_code == 200
    assert client.get("/api/auth/me", headers=headers).status_code == 401


def test_only_managers_can_manage_staff(client, login, seeded):
    chef_headers = login("chef1")
    denied = client.get("/api/users", headers=chef_headers)
    assert denied.status_code == 403

    manager_headers = login("manager1")
    users = client.get("/api/users", headers=manager_headers)
    assert users.status_code == 200
    rows = users.json()
    assert any(row["username"] == "chef1" and row["has_pin"] for row in rows)
    assert all("password_hash" not in row and "pin_hash" not in row for row in rows)
    assert all(row["role"] != "system_ai" for row in rows)

    created = client.post(
        "/api/users",
        headers=manager_headers,
        json={
            "username": "chef2",
            "full_name": "Chef Two",
            "password": "chefpass123",
            "role": "chef",
            "pin": "4321",
        },
    )
    assert created.status_code == 201, created.text
    assert created.json()["has_pin"] is True

    deactivate_self = client.patch(
        f"/api/users/{seeded['user_ids']['manager1']}",
        headers=manager_headers,
        json={"is_active": False},
    )
    assert deactivate_self.status_code == 400


def test_customer_cannot_read_another_customers_order(client, login):
    customer_headers = login("customer1")
    second = client.post(
        "/api/auth/register",
        json={
            "username": "other_customer",
            "password": "otherpass123",
            "full_name": "Other Customer",
            "phone": "01000000098",
        },
    )
    assert second.status_code == 201
    other_headers = {"Authorization": f"Bearer {second.json()['access_token']}"}

    order = client.post(
        "/api/orders",
        headers=customer_headers,
        json={"items": [{"item_id": 1, "quantity": 1}], "payment_method": "cash"},
    )
    assert order.status_code == 201
    order_id = order.json()["order"]["order_id"]

    assert client.get(f"/api/orders/{order_id}", headers=customer_headers).status_code == 200
    assert client.get(f"/api/orders/{order_id}", headers=other_headers).status_code == 404

