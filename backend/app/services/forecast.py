"""Demand forecasting pipeline (SQL -> pandas -> scikit-learn -> persisted model).

Only completed orders are used. The chronological split prevents leakage.
With the small seed dataset the API reports low-confidence warnings and
compares the model against a simple per-product baseline.
"""
from __future__ import annotations

import json
import math
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional

from fastapi import HTTPException, status as http_status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import MenuItem, Order, OrderItem

MODEL_PATH = Path(settings.ml_artifact_dir) / "demand_model.joblib"
META_PATH = Path(settings.ml_artifact_dir) / "forecast_meta.json"
FEATURES = ["item_id", "day_of_week", "month", "is_weekend", "lag_1", "lag_7", "rolling_7"]


def _load_frame(db: Session):
    import pandas as pd

    rows = db.execute(
        select(
            Order.order_id,
            Order.order_date,
            OrderItem.item_id,
            MenuItem.item_name,
            MenuItem.item_name_ar,
            OrderItem.quantity,
        )
        .join(OrderItem, OrderItem.order_id == Order.order_id)
        .join(MenuItem, MenuItem.item_id == OrderItem.item_id)
        .where(Order.status == "completed")
        .order_by(Order.order_date)
    ).all()
    data = [
        {
            "order_id": r.order_id,
            "order_date": r.order_date,
            "item_id": r.item_id,
            "item_name": r.item_name,
            "item_name_ar": r.item_name_ar,
            "quantity": int(r.quantity),
        }
        for r in rows
    ]
    return pd.DataFrame(data)


def _make_dataset(frame):
    import pandas as pd

    if frame.empty:
        return pd.DataFrame(), [], []
    frame["order_date"] = pd.to_datetime(frame["order_date"]).dt.date
    daily = frame.groupby(["order_date", "item_id"], as_index=False)["quantity"].sum()
    items = sorted(daily["item_id"].unique().tolist())
    all_dates = sorted(daily["order_date"].unique().tolist())
    grid = pd.MultiIndex.from_product([all_dates, items], names=["order_date", "item_id"]).to_frame(
        index=False
    )
    daily = grid.merge(daily, on=["order_date", "item_id"], how="left").fillna({"quantity": 0})
    daily = daily.sort_values(["item_id", "order_date"]).reset_index(drop=True)
    grouped = daily.groupby("item_id")["quantity"]
    daily["lag_1"] = grouped.shift(1)
    daily["lag_7"] = grouped.shift(7)
    daily["rolling_7"] = grouped.transform(
        lambda s: s.shift(1).rolling(7, min_periods=1).mean()
    )
    dates = pd.to_datetime(daily["order_date"])
    daily["day_of_week"] = dates.dt.dayofweek
    daily["month"] = dates.dt.month
    daily["is_weekend"] = (dates.dt.dayofweek >= 5).astype(int)
    daily = daily.dropna(subset=["lag_1", "lag_7", "rolling_7"]).reset_index(drop=True)
    return daily, all_dates, items


def train(db: Session, model_name: str = "auto") -> dict:
    try:
        import joblib
        import numpy as np
        from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor
        from sklearn.metrics import mean_absolute_error, mean_squared_error
    except ImportError as exc:  # pragma: no cover - dependency guard
        raise HTTPException(
            http_status.HTTP_503_SERVICE_UNAVAILABLE,
            "Machine-learning dependencies are not installed. Run: pip install -r backend/requirements.txt",
        ) from exc

    frame = _load_frame(db)
    daily, dates, items = _make_dataset(frame)
    if daily.empty or len(dates) < 10:
        raise HTTPException(
            http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            {
                "message": "Not enough completed historical data to train a model.",
                "completed_order_rows": int(len(frame)),
                "unique_days": len(dates),
                "minimum_days": 10,
            },
        )

    split_idx = max(1, int(len(dates) * 0.8))
    split_date = dates[split_idx - 1] if split_idx - 1 < len(dates) else dates[-1]
    train_df = daily[daily["order_date"] <= split_date]
    test_df = daily[daily["order_date"] > split_date]
    if test_df.empty:
        test_df = train_df.tail(max(1, len(train_df) // 5))
        train_df = train_df.iloc[: -len(test_df)]

    X_train, y_train = train_df[FEATURES], train_df["quantity"]
    X_test, y_test = test_df[FEATURES], test_df["quantity"]

    # Baseline: per-product average daily demand learned only on the train split.
    baseline_map = y_train.groupby(train_df["item_id"]).mean()
    baseline_pred = test_df["item_id"].map(baseline_map).fillna(y_train.mean())
    baseline_mae = float(mean_absolute_error(y_test, baseline_pred))
    baseline_rmse = float(math.sqrt(mean_squared_error(y_test, baseline_pred)))

    candidates = {
        "RandomForestRegressor": RandomForestRegressor(
            n_estimators=250, min_samples_leaf=2, random_state=42, n_jobs=-1
        ),
        "GradientBoostingRegressor": GradientBoostingRegressor(
            n_estimators=150, learning_rate=0.05, max_depth=3, random_state=42
        ),
    }
    results = {}
    best_name, best_model, best_mae = None, None, float("inf")
    for name, model in candidates.items():
        model.fit(X_train, y_train)
        pred = np.clip(model.predict(X_test), 0, None)
        mae = float(mean_absolute_error(y_test, pred))
        rmse = float(math.sqrt(mean_squared_error(y_test, pred)))
        results[name] = {"mae": round(mae, 4), "rmse": round(rmse, 4)}
        if mae < best_mae:
            best_name, best_model, best_mae = name, model, mae

    use_baseline = baseline_mae <= best_mae
    selected_name = "PerProductMeanBaseline" if use_baseline else best_name
    final_model = None if use_baseline else best_model
    metrics = {
        "mae": round(baseline_mae if use_baseline else best_mae, 4),
        "rmse": round(
            baseline_rmse if use_baseline else results[best_name]["rmse"], 4
        ),
        "baseline_mae": round(baseline_mae, 4),
        "baseline_rmse": round(baseline_rmse, 4),
        "model_comparison": results,
    }

    if final_model is not None:
        joblib.dump({"model": final_model, "features": FEATURES}, MODEL_PATH)

    meta = {
        "model_name": selected_name,
        "selected_model": selected_name,
        "trained_at": datetime.utcnow().isoformat(),
        "metrics": metrics,
        "features": FEATURES,
        "train_rows": int(len(train_df)),
        "test_rows": int(len(test_df)),
        "data_start": str(min(dates)),
        "data_end": str(max(dates)),
        "split_date": str(split_date),
        "unique_days": len(dates),
        "products": len(items),
        "completed_order_rows": int(len(frame)),
        "baseline_item_means": {str(k): float(v) for k, v in baseline_map.items()},
        "warnings": [],
        "split_strategy": "Chronological 80/20 split by unique order date (no shuffling).",
    }
    if len(frame) < 200 or len(dates) < 30:
        meta["warnings"].append(
            f"Small dataset: {len(frame)} completed order lines across {len(dates)} days. "
            "Forecast accuracy is limited and must not be presented as production-grade."
        )
    if use_baseline:
        meta["warnings"].append(
            "The simple per-product mean baseline outperformed the ML models on the holdout period, "
            "so the baseline is used for predictions."
        )
    META_PATH.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return meta


def load_meta() -> dict:
    if not META_PATH.exists():
        return {"trained": False, "warnings": ["No forecast model has been trained yet."]}
    meta = json.loads(META_PATH.read_text(encoding="utf-8"))
    meta["trained"] = True
    return meta


def predict(db: Session, horizon_days: int = 7, item_id: Optional[int] = None) -> dict:
    meta = load_meta()
    if not meta.get("trained"):
        return {
            "trained": False,
            "predictions": [],
            "metrics": None,
            "warnings": meta["warnings"],
            "message": "Train a model first from the Forecasting page.",
        }

    frame = _load_frame(db)
    daily, dates, items = _make_dataset(frame)
    if daily.empty:
        return {"trained": True, "predictions": [], "metrics": meta.get("metrics"), "warnings": meta.get("warnings", [])}

    import joblib
    import numpy as np

    artifact = None
    if meta["model_name"] != "PerProductMeanBaseline" and MODEL_PATH.exists():
        artifact = joblib.load(MODEL_PATH)
    means = {int(k): float(v) for k, v in meta.get("baseline_item_means", {}).items()}
    default_mean = float(np.mean(list(means.values()))) if means else 0.0

    selected_items = [item_id] if item_id else sorted(daily["item_id"].unique().tolist())
    names = {
        r[0]: (r[1], r[2])
        for r in db.execute(select(MenuItem.item_id, MenuItem.item_name, MenuItem.item_name_ar)).all()
    }
    next_date = max(dates) + timedelta(days=1)
    predictions = []
    histories = {}
    for current_item in selected_items:
        history = (
            daily[daily["item_id"] == current_item]
            .sort_values("order_date")["quantity"]
            .astype(float)
            .tolist()
        )
        histories[current_item] = history or [0.0] * 14

    # Predict one day at a time for all products, batching the model call.
    # Predicting each product individually is dramatically slower and made
    # the endpoint unusable with a few hundred menu items.
    for step in range(horizon_days):
        forecast_date = next_date + timedelta(days=step)
        feature_rows: list[list[float]] = []
        feature_items: list[int] = []
        for current_item in selected_items:
            history = histories[current_item]
            lag_1 = history[-1] if history else 0.0
            lag_7 = history[-7] if len(history) >= 7 else 0.0
            rolling_7 = float(np.mean(history[-7:])) if history else 0.0
            if artifact:
                feature_rows.append(
                    [
                        current_item,
                        forecast_date.weekday(),
                        forecast_date.month,
                        1 if forecast_date.weekday() >= 5 else 0,
                        lag_1,
                        lag_7,
                        rolling_7,
                    ]
                )
                feature_items.append(current_item)
            else:
                base = means.get(current_item, default_mean)
                weekend_factor = 1.15 if forecast_date.weekday() >= 5 else 1.0
                value = round(max(0.0, base * weekend_factor), 2)
                histories[current_item].append(value)
                predictions.append(
                    {
                        "item_id": current_item,
                        "item_name": names.get(current_item, ("Unknown", None))[0],
                        "item_name_ar": names.get(current_item, ("Unknown", None))[1],
                        "forecast_date": forecast_date.isoformat(),
                        "predicted_quantity": value,
                    }
                )

        if artifact and feature_rows:
            batch = np.asarray(feature_rows, dtype=float)
            batch_values = np.clip(artifact["model"].predict(batch), 0, None)
            for current_item, raw_value in zip(feature_items, batch_values):
                value = round(float(raw_value), 2)
                histories[current_item].append(value)
                predictions.append(
                    {
                        "item_id": current_item,
                        "item_name": names.get(current_item, ("Unknown", None))[0],
                        "item_name_ar": names.get(current_item, ("Unknown", None))[1],
                        "forecast_date": forecast_date.isoformat(),
                        "predicted_quantity": value,
                    }
                )

    return {
        "trained": True,
        "model_name": meta["model_name"],
        "metrics": meta.get("metrics"),
        "predictions": predictions,
        "warnings": meta.get("warnings", []),
        "data_range": {"start": meta.get("data_start"), "end": meta.get("data_end")},
        "trained_at": meta.get("trained_at"),
        "horizon_days": horizon_days,
        "disclaimer": "Predictions are estimates based on historical completed orders, not guarantees.",
    }


def performance(db: Session) -> dict:
    meta = load_meta()
    frame = _load_frame(db)
    days = sorted({row["order_date"].date() for row in frame.to_dict("records")}) if not frame.empty else []
    return {
        "trained": meta.get("trained", False),
        "metrics": meta.get("metrics"),
        "model_name": meta.get("model_name"),
        "trained_at": meta.get("trained_at"),
        "data_range": {"start": meta.get("data_start"), "end": meta.get("data_end")},
        "available_completed_days": len(days),
        "available_completed_order_lines": int(len(frame)),
        "warnings": meta.get("warnings", []),
    }
