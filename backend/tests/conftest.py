"""Isolated pytest fixtures.

The suite runs against a dedicated `bremer_test` database created from the
SQLAlchemy models. It never touches the live `bremer` database. A separate
read-only check in `test_preserved_data.py` verifies the live seed data.

Each test runs inside an outer transaction that is rolled back afterwards, so
tests can create orders, consume stock and register users without leaking state.
"""
from __future__ import annotations

import hashlib
import os
import tempfile

import pytest

TEST_DB = os.environ.get("TEST_DB_NAME", "bremer_test")
if not TEST_DB.endswith("_test"):
    raise RuntimeError("Refusing to run tests: TEST_DB_NAME must end with '_test'")

# Configure the app before importing any application module.
os.environ["DB_NAME"] = TEST_DB
os.environ["ENVIRONMENT"] = "test"
os.environ["LLM_API_KEY"] = ""
os.environ["RATE_LIMIT_LOGIN_PER_MINUTE"] = "10000"
os.environ["ML_ARTIFACT_DIR"] = tempfile.mkdtemp(prefix="restomate_ml_test_")
os.environ["UPLOAD_DIR"] = tempfile.mkdtemp(prefix="restomate_uploads_test_")

import pymysql  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.core.security import hash_password, hash_pin  # noqa: E402
from app.database.session import get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models import (  # noqa: E402
    Base,
    Category,
    Customer,
    Ingredient,
    InventoryStock,
    MenuItem,
    MenuItemIngredient,
    PaymentMethod,
    User,
)
from app.services.inventory import q  # noqa: E402


def _create_database() -> None:
    connection = pymysql.connect(
        host=settings.db_host,
        port=settings.db_port,
        user=settings.db_user,
        password=settings.db_password,
        charset="utf8mb4",
        autocommit=True,
    )
    try:
        with connection.cursor() as cursor:
            cursor.execute(f"DROP DATABASE IF EXISTS `{TEST_DB}`")
            cursor.execute(
                f"CREATE DATABASE `{TEST_DB}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
    finally:
        connection.close()


@pytest.fixture(scope="session")
def engine():
    _create_database()
    engine = create_engine(settings.sqlalchemy_url, pool_pre_ping=True, future=True)
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture(scope="session")
def seeded(engine):
    """Insert a small, deterministic dataset (IDs start at 1 in the fresh DB)."""
    password = "pass1234"
    session = Session(engine, expire_on_commit=False)
    try:
        session.add_all(
            [
                PaymentMethod(code="cash", name="Cash", name_ar="كاش", sort_order=1),
                PaymentMethod(code="card", name="Card", name_ar="بطاقة", sort_order=2),
                PaymentMethod(
                    code="pay_at_counter", name="Pay at counter", name_ar="الدفع عند الكاشير", sort_order=3
                ),
            ]
        )
        burgers = Category(category_name="Burgers", category_name_ar="برجر")
        drinks = Category(category_name="Drinks", category_name_ar="مشروبات")
        session.add_all([burgers, drinks])
        session.flush()

        burger = MenuItem(
            category_id=burgers.category_id,
            item_name="OG Burger",
            item_name_ar="أو جي برجر",
            synonyms="burger,برجر,og burger",
            price=120,
            is_available=True,
            description="Beef burger",
            description_ar="برجر لحم",
            preparation_time=12,
            is_featured=True,
        )
        truffle = MenuItem(
            category_id=burgers.category_id,
            item_name="Truffle Burger",
            item_name_ar="برجر ترافل",
            synonyms="truffle,ترافل",
            price=190,
            is_available=True,
            preparation_time=15,
            is_featured=True,
        )
        mojito = MenuItem(
            category_id=drinks.category_id,
            item_name="OG Mojito",
            item_name_ar="موهيتو أو جي",
            synonyms="mojito,موهيتو",
            price=60,
            is_available=True,
            preparation_time=5,
        )
        session.add_all([burger, truffle, mojito])
        session.flush()

        users = {}
        for username, role, pin in (
            ("customer1", "customer", None),
            ("chef1", "chef", "2468"),
            ("cashier1", "cashier", "1357"),
            ("manager1", "manager", "9999"),
            ("system_ai", "system_ai", None),
        ):
            user = User(
                username=username,
                email=f"{username}@example.test",
                full_name=username.replace("1", " One").title(),
                password_hash=hash_password(password),
                password_algo="bcrypt",
                role=role,
                pin_hash=hash_pin(pin) if pin else None,
                is_active=True,
            )
            session.add(user)
            users[username] = user
        session.flush()

        legacy = User(
            username="legacy1",
            email="legacy1@example.test",
            full_name="Legacy One",
            password_hash=hashlib.sha256(b"rm_salt_secure_legacy123").hexdigest(),
            password_algo="legacy_sha256",
            role="customer",
            is_active=True,
        )
        session.add(legacy)
        session.flush()

        profile = Customer(
            user_id=users["customer1"].user_id,
            customer_name="Customer One",
            phone="01000000001",
            address="1 Test Street",
        )
        session.add(profile)

        patty = Ingredient(
            ingredient_name="Beef Patty",
            ingredient_name_ar="قطعة لحم",
            unit_of_measure="pcs",
            minimum_stock=10,
            safety_stock=5,
            lead_time_days=2,
            cost_per_unit=30,
        )
        bun = Ingredient(
            ingredient_name="Burger Bun",
            ingredient_name_ar="خبز برجر",
            unit_of_measure="pcs",
            minimum_stock=10,
            safety_stock=5,
            lead_time_days=1,
            cost_per_unit=5,
        )
        mint = Ingredient(
            ingredient_name="Mint",
            ingredient_name_ar="نعناع",
            unit_of_measure="g",
            minimum_stock=100,
            safety_stock=50,
            lead_time_days=1,
        )
        session.add_all([patty, bun, mint])
        session.flush()
        session.add_all(
            [
                InventoryStock(ingredient_id=patty.ingredient_id, quantity=q(100)),
                InventoryStock(ingredient_id=bun.ingredient_id, quantity=q(100)),
                InventoryStock(ingredient_id=mint.ingredient_id, quantity=q(500)),
            ]
        )
        session.add_all(
            [
                MenuItemIngredient(
                    item_id=burger.item_id,
                    ingredient_id=patty.ingredient_id,
                    quantity=q(1),
                    unit_of_measure="pcs",
                ),
                MenuItemIngredient(
                    item_id=burger.item_id,
                    ingredient_id=bun.ingredient_id,
                    quantity=q(1),
                    unit_of_measure="pcs",
                ),
                MenuItemIngredient(
                    item_id=mojito.item_id,
                    ingredient_id=mint.ingredient_id,
                    quantity=q(10),
                    unit_of_measure="g",
                ),
            ]
        )
        session.commit()

        return {
            "password": password,
            "category_ids": {"burgers": burgers.category_id, "drinks": drinks.category_id},
            "item_ids": {
                "burger": burger.item_id,
                "truffle": truffle.item_id,
                "mojito": mojito.item_id,
            },
            "item_names": {
                "burger": "OG Burger",
                "truffle": "Truffle Burger",
                "mojito": "OG Mojito",
            },
            "user_ids": {name: user.user_id for name, user in users.items()},
            "legacy_id": legacy.user_id,
            "customer_id": profile.customer_id,
            "ingredients": {
                "patty": patty.ingredient_id,
                "bun": bun.ingredient_id,
                "mint": mint.ingredient_id,
            },
        }
    finally:
        session.close()


@pytest.fixture()
def db(engine):
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(
        bind=connection,
        join_transaction_mode="create_savepoint",
        expire_on_commit=False,
    )
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture()
def client(db):
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture()
def login(client):
    def _login(username: str, password: str = "pass1234"):
        response = client.post("/api/auth/login", json={"username": username, "password": password})
        assert response.status_code == 200, response.text
        token = response.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}

    return _login


@pytest.fixture()
def live_connection():
    """Read-only connection to the real database, or skip when unavailable."""
    live_db = os.environ.get("LIVE_DB_NAME", "bremer")
    url = settings.sqlalchemy_url.rsplit("/", 1)[0] + f"/{live_db}?charset=utf8mb4"
    try:
        live_engine = create_engine(url, pool_pre_ping=True, future=True)
        connection = live_engine.connect()
        connection.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"Live database not reachable: {exc}")
    try:
        yield connection
    finally:
        connection.close()
        live_engine.dispose()
