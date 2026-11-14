"""Forecasting tests: honest empty-data failure and a chronological ML run."""
from __future__ import annotations

from datetime import datetime, timedelta

from app.models import Order, OrderItem
from app.services import forecast


def _clear_artifacts() -> None:
    forecast.MODEL_PATH.unlink(missing_ok=True)
    forecast.META_PATH.unlink(missing_ok=True)


def _seed_completed_history(db, seeded, days: int = 12) -> None:
    start = datetime.utcnow().replace(hour=12, minute=0, second=0, microsecond=0) - timedelta(
        days=days - 1
    )
    for offset in range(days):
        burger_qty = 2 + (offset % 3)
        mojito_qty = 1 + (offset % 2)
        order = Order(
            order_date=start + timedelta(days=offset),
            status="completed",
            payment_status="paid",
            payment_method="cash",
            order_source="pos",
            total_amount=burger_qty * 120 + mojito_qty * 60,
        )
        db.add(order)
        db.flush()
        db.add_all(
            [
                OrderItem(
                    order_id=order.order_id,
                    item_id=seeded["item_ids"]["burger"],
                    item_name_snapshot="OG Burger",
                    quantity=burger_qty,
                    unit_price=120,
                ),
                OrderItem(
                    order_id=order.order_id,
                    item_id=seeded["item_ids"]["mojito"],
                    item_name_snapshot="OG Mojito",
                    quantity=mojito_qty,
                    unit_price=60,
                ),
            ]
        )
    db.commit()


def test_train_fails_honestly_without_history(client, login):
    _clear_artifacts()
    manager = login("manager1")

    response = client.post("/api/forecast/train", headers=manager)
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert "Not enough completed historical data" in detail["message"]
    assert detail["minimum_days"] == 10

    predictions = client.get("/api/forecast/predictions", headers=manager)
    assert predictions.status_code == 200
    assert predictions.json()["trained"] is False
    assert predictions.json()["predictions"] == []


def test_forecast_permissions_and_query_validation(client, login):
    _clear_artifacts()
    chef = login("chef1")
    manager = login("manager1")

    assert client.post("/api/forecast/train", headers=chef).status_code == 403
    assert client.get("/api/forecast/performance", headers=chef).status_code == 403
    assert client.get("/api/forecast/predictions?horizon_days=0", headers=manager).status_code == 422
    assert client.get("/api/forecast/predictions?horizon_days=31", headers=manager).status_code == 422
    assert client.get("/api/forecast/history?days=3", headers=manager).status_code == 422


def test_chronological_training_and_predictions(client, db, login, seeded):
    _clear_artifacts()
    manager = login("manager1")
    _seed_completed_history(db, seeded, days=12)

    history = client.get("/api/forecast/history?days=60", headers=manager)
    assert history.status_code == 200
    assert len(history.json()["series"]) == 12
    assert history.json()["source"] == "completed orders only"

    training = client.post("/api/forecast/train", headers=manager)
    assert training.status_code == 200, training.text
    meta = training.json()
    assert meta["model_name"] in {
        "PerProductMeanBaseline",
        "RandomForestRegressor",
        "GradientBoostingRegressor",
    }
    assert meta["unique_days"] == 12
    assert meta["completed_order_rows"] == 24
    assert "mae" in meta["metrics"]
    assert "baseline_mae" in meta["metrics"]
    assert meta["split_strategy"].startswith("Chronological")
    assert meta["warnings"], "small-data warnings must be explicit"

    predictions = client.get("/api/forecast/predictions?horizon_days=3", headers=manager)
    assert predictions.status_code == 200
    body = predictions.json()
    assert body["trained"] is True
    assert body["horizon_days"] == 3
    assert len(body["predictions"]) == 6  # 2 products x 3 days
    assert all(row["predicted_quantity"] >= 0 for row in body["predictions"])
    assert body["disclaimer"]

    performance = client.get("/api/forecast/performance", headers=manager)
    assert performance.status_code == 200
    assert performance.json()["available_completed_days"] == 12
    assert performance.json()["model_name"] == meta["model_name"]
