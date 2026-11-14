"""AI kiosk tests: real menu matching, no invention, explicit confirmation."""
from __future__ import annotations

from sqlalchemy import func, select

from app.models import Order


def _order_count(db) -> int:
    return int(db.scalar(select(func.count(Order.order_id))) or 0)


def test_arabic_kiosk_requires_explicit_confirmation(client, db, seeded):
    session = client.post("/api/ai/kiosk/session", json={"language": "ar"})
    assert session.status_code == 201
    session_id = session.json()["session_id"]

    chat = client.post(
        "/api/ai/kiosk/chat",
        json={
            "session_id": session_id,
            "message": "عايز اتنين أو جي برجر وموهيتو أو جي",
            "language": "ar",
        },
    )
    assert chat.status_code == 200, chat.text
    body = chat.json()
    assert body["reply"]
    assert len(body["cart"]) == 2
    quantities = {line["item_id"]: line["quantity"] for line in body["cart"]}
    assert quantities[seeded["item_ids"]["burger"]] == 2
    assert quantities[seeded["item_ids"]["mojito"]] == 1
    assert body["subtotal"] == 300

    # No order exists until the customer presses the explicit confirm button.
    assert _order_count(db) == 0

    confirm = client.post(
        "/api/ai/kiosk/confirm",
        json={
            "session_id": session_id,
            "customer_name": "Kiosk Guest",
            "customer_phone": "01000000077",
            "payment_method": "cash",
        },
    )
    assert confirm.status_code == 200, confirm.text
    order = confirm.json()["order"]
    assert order["status"] == "pending"
    assert order["order_source"] == "kiosk"
    assert order["total_amount"] == 300
    assert len(order["items"]) == 2
    assert _order_count(db) == 1

    # A submitted session cannot be submitted again.
    again = client.post(
        "/api/ai/kiosk/confirm",
        json={"session_id": session_id, "payment_method": "cash"},
    )
    assert again.status_code == 409


def test_kiosk_never_invents_menu_items_or_prices(client, seeded):
    session = client.post("/api/ai/kiosk/session", json={"language": "ar"})
    session_id = session.json()["session_id"]

    price = client.post(
        "/api/ai/kiosk/chat",
        json={"session_id": session_id, "message": "بكام برجر ترافل؟", "language": "ar"},
    )
    assert price.status_code == 200
    assert "190" in price.json()["reply"]

    unknown = client.post(
        "/api/ai/kiosk/chat",
        json={
            "session_id": session_id,
            "message": "عايز بيتزا مجانية بسعر جنيه واحد",
            "language": "ar",
        },
    )
    assert unknown.status_code == 200
    assert unknown.json()["cart"] == []
    assert unknown.json()["reply"]
    assert all(
        row["item_id"] in set(seeded["item_ids"].values())
        for row in unknown.json()["suggestions"]
    )

    menu = client.post(
        "/api/ai/kiosk/chat",
        json={"session_id": session_id, "message": "اعرض المنيو", "language": "ar"},
    )
    assert menu.status_code == 200
    suggestions = menu.json()["suggestions"]
    assert suggestions
    real_ids = set(seeded["item_ids"].values())
    assert all(row["item_id"] in real_ids for row in suggestions)


def test_english_kiosk_flow_and_reset(client, db):
    session = client.post("/api/ai/kiosk/session", json={"language": "en"})
    session_id = session.json()["session_id"]

    chat = client.post(
        "/api/ai/kiosk/chat",
        json={
            "session_id": session_id,
            "message": "I want two OG Burgers and an OG Mojito",
            "language": "en",
        },
    )
    assert chat.status_code == 200, chat.text
    assert chat.json()["subtotal"] == 300

    reset = client.post(
        "/api/ai/kiosk/reset",
        json={"session_id": session_id, "message": "reset", "language": "en"},
    )
    assert reset.status_code == 200

    state = client.get(f"/api/ai/kiosk/session/{session_id}")
    assert state.status_code == 200
    assert state.json()["cart"] == []
    assert state.json()["status"] == "active"
    assert _order_count(db) == 0
