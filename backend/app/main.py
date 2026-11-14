"""RestoMate AI FastAPI application."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from app.api import ai, analytics, auth, forecast, inventory, menu, orders, users
from app.core.config import settings
from app.database.session import SessionLocal, check_database
from app.models import Order
from app.realtime.manager import authenticate_socket, can_view_order, manager

logging.basicConfig(level=settings.log_level)
logger = logging.getLogger("restomate")


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        check_database()
        logger.info("Connected to MySQL database %s", settings.db_name)
    except Exception as exc:  # noqa: BLE001
        logger.error("Database connection failed: %s", exc)
    Path(settings.upload_dir).mkdir(parents=True, exist_ok=True)
    yield


app = FastAPI(
    title="RestoMate AI API",
    description=(
        "Unified restaurant operating system: customer ordering, staff operations, "
        "manager analytics, inventory, AI kiosk and demand forecasting."
    ),
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Idempotency-Key"],
)


@app.middleware("http")
async def security_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), geolocation=()"
    if settings.environment == "production":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


API_PREFIX = "/api"
app.include_router(auth.router, prefix=API_PREFIX)
app.include_router(menu.router, prefix=API_PREFIX)
app.include_router(menu.admin_router, prefix=API_PREFIX)
app.include_router(orders.router, prefix=API_PREFIX)
app.include_router(orders.staff_router, prefix=API_PREFIX)
app.include_router(analytics.router, prefix=API_PREFIX)
app.include_router(users.router, prefix=API_PREFIX)
app.include_router(inventory.router, prefix=API_PREFIX)
app.include_router(inventory.supplier_router, prefix=API_PREFIX)
app.include_router(inventory.purchase_router, prefix=API_PREFIX)
app.include_router(forecast.router, prefix=API_PREFIX)
app.include_router(ai.router, prefix=API_PREFIX)

app.mount("/uploads", StaticFiles(directory=settings.upload_dir), name="uploads")


@app.get("/api/health", tags=["System"])
def health():
    try:
        check_database()
        db_status = "ok"
    except Exception as exc:  # noqa: BLE001
        return JSONResponse(status_code=503, content={"status": "degraded", "database": str(exc)})
    return {
        "status": "ok",
        "database": db_status,
        "database_name": settings.db_name,
        "environment": settings.environment,
        "llm_configured": bool(settings.llm_api_key),
    }


@app.get("/api/health/db", tags=["System"])
def database_health():
    with SessionLocal() as db:
        counts = {}
        for table in (
            "categories",
            "menu_items",
            "customers",
            "orders",
            "order_items",
            "users",
            "ingredients",
            "payments",
        ):
            counts[table] = db.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar()
    return {"status": "ok", "counts": counts}


# --------------------------------------------------------------------------- #
# WebSockets
# --------------------------------------------------------------------------- #
@app.websocket("/ws/orders")
async def staff_socket(websocket: WebSocket, token: str | None = Query(default=None)):
    db = SessionLocal()
    try:
        user = authenticate_socket(token, db)
        if user.role not in ("chef", "cashier", "manager"):
            await websocket.close(code=1008)
            return
    except Exception:  # noqa: BLE001
        await websocket.close(code=1008)
        db.close()
        return
    finally:
        pass

    await manager.connect_staff(websocket)
    try:
        while True:
            message = await websocket.receive_text()
            if message == "ping":
                await websocket.send_text('{"type":"pong"}')
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    finally:
        manager.disconnect(websocket)
        db.close()


@app.websocket("/ws/orders/{order_id}")
async def order_socket(websocket: WebSocket, order_id: int, token: str | None = Query(default=None)):
    db = SessionLocal()
    try:
        user = authenticate_socket(token, db)
        if not db.get(Order, order_id) or not can_view_order(db, user, order_id):
            await websocket.close(code=1008)
            return
    except Exception:  # noqa: BLE001
        await websocket.close(code=1008)
        db.close()
        return

    await manager.connect_order(websocket, order_id)
    try:
        while True:
            message = await websocket.receive_text()
            if message == "ping":
                await websocket.send_text('{"type":"pong"}')
    except WebSocketDisconnect:
        manager.disconnect(websocket, order_id)
    finally:
        manager.disconnect(websocket, order_id)
        db.close()


# Optional production SPA hosting (when frontend/dist exists).
FRONTEND_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if FRONTEND_DIST.exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="frontend-assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa(full_path: str):
        from fastapi.responses import FileResponse

        candidate = FRONTEND_DIST / full_path
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(FRONTEND_DIST / "index.html")
