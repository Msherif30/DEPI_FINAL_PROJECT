"""SQLAlchemy models for the RestoMate AI database.

The six original tables keep their primary keys and rows. New columns are
nullable or have safe defaults so historical records remain valid.
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

ORDER_STATUSES = ("pending", "confirmed", "preparing", "completed", "cancelled")
ORDER_SOURCES = ("voice", "pos", "web_app", "kiosk")
USER_ROLES = ("customer", "chef", "cashier", "manager", "system_ai")
PAYMENT_STATUSES = ("unpaid", "pending", "paid", "refunded", "partially_refunded")
PAYMENT_RECORD_STATUSES = ("pending", "paid", "failed", "refunded")
MOVEMENT_TYPES = ("initial", "purchase", "consumption", "adjustment", "waste", "return")
PO_STATUSES = ("draft", "ordered", "partially_received", "received", "cancelled")
KIOSK_STATUSES = ("active", "submitted", "expired", "abandoned")


class Base(DeclarativeBase):
    pass


class Category(Base):
    __tablename__ = "categories"

    category_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    category_name: Mapped[str] = mapped_column(String(100), nullable=False)
    category_name_ar: Mapped[Optional[str]] = mapped_column(String(100))
    description: Mapped[Optional[str]] = mapped_column(Text)
    image_url: Mapped[Optional[str]] = mapped_column(String(500))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    items: Mapped[list["MenuItem"]] = relationship(back_populates="category")


class MenuItem(Base):
    __tablename__ = "menu_items"

    item_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.category_id"), nullable=False)
    item_name: Mapped[str] = mapped_column(String(150), nullable=False)
    item_name_ar: Mapped[str] = mapped_column(String(150), nullable=False)
    synonyms: Mapped[Optional[str]] = mapped_column(Text)
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    is_available: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    description: Mapped[Optional[str]] = mapped_column(Text)
    description_ar: Mapped[Optional[str]] = mapped_column(Text)
    image_url: Mapped[Optional[str]] = mapped_column(String(500))
    preparation_time: Mapped[Optional[int]] = mapped_column(Integer)
    is_featured: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    category: Mapped["Category"] = relationship(back_populates="items")
    recipe_lines: Mapped[list["MenuItemIngredient"]] = relationship(
        back_populates="menu_item", cascade="all, delete-orphan"
    )

    @property
    def synonyms_list(self) -> list[str]:
        if not self.synonyms:
            return []
        return [part.strip() for part in self.synonyms.split(",") if part.strip()]


class Customer(Base):
    __tablename__ = "customers"

    customer_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.user_id", ondelete="SET NULL"), unique=True
    )
    customer_name: Mapped[Optional[str]] = mapped_column(String(100))
    phone: Mapped[Optional[str]] = mapped_column(String(20), unique=True)
    address: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    user: Mapped[Optional["User"]] = relationship(back_populates="customer_profile")
    orders: Mapped[list["Order"]] = relationship(back_populates="customer")


class Order(Base):
    __tablename__ = "orders"

    order_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    customer_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("customers.customer_id"), nullable=True
    )
    order_date: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )
    status: Mapped[str] = mapped_column(
        SAEnum(*ORDER_STATUSES, name="order_status"), nullable=False, default="pending"
    )
    payment_status: Mapped[str] = mapped_column(
        SAEnum(*PAYMENT_STATUSES, name="payment_status"), nullable=False, default="unpaid"
    )
    payment_method: Mapped[Optional[str]] = mapped_column(
        ForeignKey("payment_methods.code", onupdate="CASCADE"), nullable=True
    )
    order_notes: Mapped[Optional[str]] = mapped_column(Text)
    idempotency_key: Mapped[Optional[str]] = mapped_column(String(64), unique=True)
    order_source: Mapped[str] = mapped_column(
        SAEnum(*ORDER_SOURCES, name="order_source"), nullable=False, default="web_app"
    )
    raw_transcription: Mapped[Optional[str]] = mapped_column(Text)
    confidence_score: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2))
    total_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False, default=0)

    customer: Mapped[Optional["Customer"]] = relationship(back_populates="orders")
    items: Mapped[list["OrderItem"]] = relationship(
        back_populates="order", cascade="all, delete-orphan"
    )
    status_history: Mapped[list["OrderStatusHistory"]] = relationship(
        back_populates="order", cascade="all, delete-orphan", order_by="OrderStatusHistory.changed_at"
    )
    payments: Mapped[list["Payment"]] = relationship(
        back_populates="order", cascade="all, delete-orphan"
    )


class OrderItem(Base):
    __tablename__ = "order_items"

    order_item_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(
        ForeignKey("orders.order_id", ondelete="CASCADE"), nullable=False
    )
    item_id: Mapped[int] = mapped_column(ForeignKey("menu_items.item_id"), nullable=False)
    item_name_snapshot: Mapped[Optional[str]] = mapped_column(String(150))
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    special_instructions: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    order: Mapped["Order"] = relationship(back_populates="items")
    menu_item: Mapped["MenuItem"] = relationship()


class User(Base):
    __tablename__ = "users"

    user_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    email: Mapped[Optional[str]] = mapped_column(String(255), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    password_algo: Mapped[str] = mapped_column(String(30), nullable=False, default="legacy_sha256")
    role: Mapped[str] = mapped_column(
        SAEnum(*USER_ROLES, name="user_role"), nullable=False, default="customer"
    )
    pin_code: Mapped[Optional[str]] = mapped_column(String(10))
    pin_hash: Mapped[Optional[str]] = mapped_column(String(255))
    must_change_password: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    full_name: Mapped[Optional[str]] = mapped_column(String(100))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

    customer_profile: Mapped[Optional["Customer"]] = relationship(back_populates="user")


class PaymentMethod(Base):
    __tablename__ = "payment_methods"

    code: Mapped[str] = mapped_column(String(50), primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    name_ar: Mapped[str] = mapped_column(String(100), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    requires_reference: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Payment(Base):
    __tablename__ = "payments"

    payment_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(
        ForeignKey("orders.order_id", ondelete="CASCADE"), nullable=False
    )
    payment_method: Mapped[str] = mapped_column(
        ForeignKey("payment_methods.code"), nullable=False
    )
    payment_status: Mapped[str] = mapped_column(
        SAEnum(*PAYMENT_RECORD_STATUSES, name="payment_record_status"),
        nullable=False,
        default="pending",
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    transaction_reference: Mapped[Optional[str]] = mapped_column(String(120))
    paid_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    created_by: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.user_id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    order: Mapped["Order"] = relationship(back_populates="payments")
    method: Mapped["PaymentMethod"] = relationship()


class OrderStatusHistory(Base):
    __tablename__ = "order_status_history"

    history_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(
        ForeignKey("orders.order_id", ondelete="CASCADE"), nullable=False
    )
    previous_status: Mapped[Optional[str]] = mapped_column(
        SAEnum(*ORDER_STATUSES, name="history_prev_status")
    )
    new_status: Mapped[str] = mapped_column(
        SAEnum(*ORDER_STATUSES, name="history_new_status"), nullable=False
    )
    changed_by: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.user_id", ondelete="SET NULL")
    )
    changed_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    notes: Mapped[Optional[str]] = mapped_column(String(500))

    order: Mapped["Order"] = relationship(back_populates="status_history")
    user: Mapped[Optional["User"]] = relationship()


class AuditLog(Base):
    __tablename__ = "audit_logs"

    audit_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.user_id", ondelete="SET NULL")
    )
    action: Mapped[str] = mapped_column(String(80), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(60), nullable=False)
    entity_id: Mapped[Optional[str]] = mapped_column(String(60))
    details: Mapped[Optional[dict]] = mapped_column(JSON)
    ip_address: Mapped[Optional[str]] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    user: Mapped[Optional["User"]] = relationship()


class UserSession(Base):
    __tablename__ = "user_sessions"

    session_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False
    )
    jwt_id: Mapped[str] = mapped_column(String(36), unique=True, nullable=False)
    issued_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    ip_address: Mapped[Optional[str]] = mapped_column(String(64))
    user_agent: Mapped[Optional[str]] = mapped_column(String(255))


class Supplier(Base):
    __tablename__ = "suppliers"

    supplier_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    supplier_name: Mapped[str] = mapped_column(String(150), unique=True, nullable=False)
    contact_name: Mapped[Optional[str]] = mapped_column(String(120))
    phone: Mapped[Optional[str]] = mapped_column(String(30))
    email: Mapped[Optional[str]] = mapped_column(String(255))
    address: Mapped[Optional[str]] = mapped_column(Text)
    notes: Mapped[Optional[str]] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class Ingredient(Base):
    __tablename__ = "ingredients"

    ingredient_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ingredient_name: Mapped[str] = mapped_column(String(150), unique=True, nullable=False)
    ingredient_name_ar: Mapped[Optional[str]] = mapped_column(String(150))
    unit_of_measure: Mapped[str] = mapped_column(String(20), nullable=False)
    minimum_stock: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False, default=0)
    safety_stock: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False, default=0)
    lead_time_days: Mapped[int] = mapped_column(Integer, nullable=False, default=2)
    cost_per_unit: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 4))
    default_supplier_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("suppliers.supplier_id", ondelete="SET NULL")
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    notes: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    stock: Mapped[Optional["InventoryStock"]] = relationship(
        back_populates="ingredient", uselist=False, cascade="all, delete-orphan"
    )
    recipe_lines: Mapped[list["MenuItemIngredient"]] = relationship(back_populates="ingredient")


class InventoryStock(Base):
    __tablename__ = "inventory_stock"

    stock_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    ingredient_id: Mapped[int] = mapped_column(
        ForeignKey("ingredients.ingredient_id", ondelete="CASCADE"), unique=True, nullable=False
    )
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False, default=0)
    last_updated: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )
    updated_by: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.user_id", ondelete="SET NULL")
    )

    ingredient: Mapped["Ingredient"] = relationship(back_populates="stock")


class MenuItemIngredient(Base):
    __tablename__ = "menu_item_ingredients"

    menu_item_ingredient_id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True
    )
    item_id: Mapped[int] = mapped_column(
        ForeignKey("menu_items.item_id", ondelete="CASCADE"), nullable=False
    )
    ingredient_id: Mapped[int] = mapped_column(
        ForeignKey("ingredients.ingredient_id", ondelete="CASCADE"), nullable=False
    )
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    unit_of_measure: Mapped[str] = mapped_column(String(20), nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    menu_item: Mapped["MenuItem"] = relationship(back_populates="recipe_lines")
    ingredient: Mapped["Ingredient"] = relationship(back_populates="recipe_lines")


class StockMovement(Base):
    __tablename__ = "stock_movements"

    movement_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    ingredient_id: Mapped[int] = mapped_column(
        ForeignKey("ingredients.ingredient_id", ondelete="CASCADE"), nullable=False
    )
    movement_type: Mapped[str] = mapped_column(
        SAEnum(*MOVEMENT_TYPES, name="movement_type"), nullable=False
    )
    quantity_change: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    quantity_after: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    reason: Mapped[Optional[str]] = mapped_column(String(255))
    reference_type: Mapped[Optional[str]] = mapped_column(String(40))
    reference_id: Mapped[Optional[str]] = mapped_column(String(60))
    order_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("orders.order_id", ondelete="SET NULL")
    )
    purchase_order_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("purchase_orders.purchase_order_id", ondelete="SET NULL")
    )
    user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.user_id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    ingredient: Mapped["Ingredient"] = relationship()
    user: Mapped[Optional["User"]] = relationship()


class PurchaseOrder(Base):
    __tablename__ = "purchase_orders"

    purchase_order_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    supplier_id: Mapped[int] = mapped_column(ForeignKey("suppliers.supplier_id"), nullable=False)
    status: Mapped[str] = mapped_column(
        SAEnum(*PO_STATUSES, name="po_status"), nullable=False, default="draft"
    )
    order_date: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    expected_date: Mapped[Optional[date]] = mapped_column(Date)
    received_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    notes: Mapped[Optional[str]] = mapped_column(Text)
    created_by: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.user_id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    supplier: Mapped["Supplier"] = relationship()
    items: Mapped[list["PurchaseOrderItem"]] = relationship(
        back_populates="purchase_order", cascade="all, delete-orphan"
    )


class PurchaseOrderItem(Base):
    __tablename__ = "purchase_order_items"

    purchase_order_item_id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True
    )
    purchase_order_id: Mapped[int] = mapped_column(
        ForeignKey("purchase_orders.purchase_order_id", ondelete="CASCADE"), nullable=False
    )
    ingredient_id: Mapped[int] = mapped_column(
        ForeignKey("ingredients.ingredient_id"), nullable=False
    )
    quantity_ordered: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    quantity_received: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False, default=0)
    unit_cost: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 4))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    purchase_order: Mapped["PurchaseOrder"] = relationship(back_populates="items")
    ingredient: Mapped["Ingredient"] = relationship()


class OrderStockApplication(Base):
    __tablename__ = "order_stock_applications"

    order_id: Mapped[int] = mapped_column(
        ForeignKey("orders.order_id", ondelete="CASCADE"), primary_key=True
    )
    status: Mapped[str] = mapped_column(
        SAEnum("applied", "reversed", name="osa_status"), nullable=False, default="applied"
    )
    applied_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    applied_by: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.user_id", ondelete="SET NULL")
    )
    reversed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    reversed_by: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.user_id", ondelete="SET NULL")
    )
    note: Mapped[Optional[str]] = mapped_column(String(255))


class KioskSession(Base):
    __tablename__ = "kiosk_sessions"

    session_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    status: Mapped[str] = mapped_column(
        SAEnum(*KIOSK_STATUSES, name="kiosk_status"), nullable=False, default="active"
    )
    state: Mapped[str] = mapped_column(String(30), nullable=False, default="idle")
    language: Mapped[str] = mapped_column(SAEnum("ar", "en", name="kiosk_lang"), default="ar")
    customer_name: Mapped[Optional[str]] = mapped_column(String(120))
    customer_phone: Mapped[Optional[str]] = mapped_column(String(30))
    table_number: Mapped[Optional[int]] = mapped_column(Integer)
    started_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    ended_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    order_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("orders.order_id", ondelete="SET NULL")
    )
    last_activity: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    cart_items: Mapped[list["KioskCartItem"]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )


class KioskCartItem(Base):
    __tablename__ = "kiosk_cart_items"

    cart_item_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(
        ForeignKey("kiosk_sessions.session_id", ondelete="CASCADE"), nullable=False
    )
    item_id: Mapped[int] = mapped_column(ForeignKey("menu_items.item_id"), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    special_instructions: Mapped[Optional[str]] = mapped_column(String(300))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    session: Mapped["KioskSession"] = relationship(back_populates="cart_items")
    menu_item: Mapped["MenuItem"] = relationship()


class KioskMessage(Base):
    __tablename__ = "kiosk_messages"

    message_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(
        ForeignKey("kiosk_sessions.session_id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(
        SAEnum("user", "assistant", "system", name="kiosk_role"), nullable=False
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    language: Mapped[str] = mapped_column(
        SAEnum("ar", "en", name="kiosk_msg_lang"), nullable=False, default="ar"
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
