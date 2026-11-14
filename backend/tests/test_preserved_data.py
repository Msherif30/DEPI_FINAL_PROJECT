"""Read-only verification that the live seed data was preserved.

These tests never write to the live database. They are skipped automatically
when the live MySQL server is not reachable.
"""
from __future__ import annotations

from sqlalchemy import text


def test_live_seed_counts_are_preserved(live_connection):
    counts = {}
    for table in (
        "categories",
        "menu_items",
        "customers",
        "orders",
        "order_items",
        "users",
    ):
        counts[table] = int(
            live_connection.execute(text(f"SELECT COUNT(*) FROM `{table}`")).scalar() or 0
        )

    assert counts["categories"] >= 17
    assert counts["menu_items"] >= 142
    assert counts["customers"] >= 30
    assert counts["orders"] >= 41
    assert counts["order_items"] >= 150
    assert counts["users"] >= 5


def test_live_menu_and_categories_are_intact(live_connection):
    first_item = live_connection.execute(
        text("SELECT item_name FROM menu_items WHERE item_id = 1")
    ).scalar()
    assert first_item == "Buffalo Wings"

    hot_coffee = live_connection.execute(
        text("SELECT category_name FROM categories WHERE category_id = 17")
    ).scalar()
    assert hot_coffee == "Hot Coffee"

    lowest_price = live_connection.execute(
        text("SELECT MIN(price) FROM menu_items")
    ).scalar()
    assert float(lowest_price) > 0

    null_prices = live_connection.execute(
        text("SELECT COUNT(*) FROM menu_items WHERE price IS NULL OR price <= 0")
    ).scalar()
    assert int(null_prices) == 0


def test_live_staff_accounts_and_secrets_are_safe(live_connection):
    rows = live_connection.execute(
        text("SELECT username, role, password_hash, password_algo, pin_code FROM users")
    ).all()
    usernames = {row[0] for row in rows}
    roles = {row[0]: row[1] for row in rows}

    assert {"chef", "cashier", "manager"}.issubset(usernames)
    assert roles.get("chef") == "chef"
    assert roles.get("cashier") == "cashier"
    assert roles.get("manager") == "manager"
    assert "kiosk_ai" in usernames
    assert roles.get("kiosk_ai") == "system_ai"

    for _username, _role, password_hash, _algo, pin_code in rows:
        assert password_hash
        assert password_hash not in {"chef123", "cashier123", "admin123", "pass123"}
        assert pin_code is None, "Plaintext PINs must be migrated to pin_hash and nulled out"


def test_live_schema_contains_new_modules(live_connection):
    tables = {
        row[0]
        for row in live_connection.execute(
            text(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = DATABASE()"
            )
        ).all()
    }
    required = {
        "audit_logs",
        "user_sessions",
        "payments",
        "payment_methods",
        "order_status_history",
        "suppliers",
        "ingredients",
        "inventory_stock",
        "menu_item_ingredients",
        "stock_movements",
        "purchase_orders",
        "purchase_order_items",
        "order_stock_applications",
        "kiosk_sessions",
        "kiosk_cart_items",
        "kiosk_messages",
        "schema_migrations",
    }
    assert required.issubset(tables)

    applied = {
        row[0]
        for row in live_connection.execute(text("SELECT version FROM schema_migrations")).all()
    }
    assert {
        "001_enhance_core.sql",
        "002_inventory.sql",
        "003_kiosk.sql",
        "004_kiosk_state.sql",
        "005_repair_core_tables.sql",
    }.issubset(applied)
