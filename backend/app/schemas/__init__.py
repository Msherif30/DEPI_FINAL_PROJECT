"""Pydantic request/response schemas."""
from __future__ import annotations

from datetime import date, datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

Role = Literal["customer", "chef", "cashier", "manager"]
OrderStatus = Literal["pending", "confirmed", "preparing", "completed", "cancelled"]


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# --------------------------------------------------------------------------- #
# Auth / users
# --------------------------------------------------------------------------- #
class LoginRequest(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    password: str = Field(min_length=4, max_length=128)


class PinLoginRequest(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    pin: str = Field(min_length=4, max_length=10)


class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=50, pattern=r"^[A-Za-z0-9_.-]+$")
    email: Optional[EmailStr] = None
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(min_length=2, max_length=100)
    phone: Optional[str] = Field(default=None, max_length=20)
    address: Optional[str] = Field(default=None, max_length=500)

    @field_validator("phone")
    @classmethod
    def clean_phone(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        value = value.strip()
        return value or None


class UserOut(ORMModel):
    user_id: int
    username: str
    email: Optional[str] = None
    full_name: Optional[str] = None
    role: str
    is_active: bool
    created_at: Optional[datetime] = None
    last_login_at: Optional[datetime] = None
    has_pin: bool = False


class CustomerProfileOut(ORMModel):
    customer_id: int
    customer_name: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    created_at: Optional[datetime] = None


class MeOut(BaseModel):
    user: UserOut
    customer: Optional[CustomerProfileOut] = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_at: datetime
    user: UserOut


class ProfileUpdate(BaseModel):
    full_name: Optional[str] = Field(default=None, min_length=2, max_length=100)
    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(default=None, max_length=20)
    address: Optional[str] = Field(default=None, max_length=500)


class PasswordChange(BaseModel):
    current_password: str = Field(min_length=4, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=50, pattern=r"^[A-Za-z0-9_.-]+$")
    email: Optional[EmailStr] = None
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(min_length=2, max_length=100)
    role: Role
    pin: Optional[str] = Field(default=None, min_length=4, max_length=10)


class UserUpdate(BaseModel):
    full_name: Optional[str] = Field(default=None, min_length=2, max_length=100)
    email: Optional[EmailStr] = None
    role: Optional[Role] = None
    is_active: Optional[bool] = None
    pin: Optional[str] = Field(default=None, min_length=4, max_length=10)


class PasswordReset(BaseModel):
    new_password: str = Field(min_length=8, max_length=128)


# --------------------------------------------------------------------------- #
# Menu
# --------------------------------------------------------------------------- #
class CategoryOut(ORMModel):
    category_id: int
    category_name: str
    category_name_ar: Optional[str] = None
    description: Optional[str] = None
    image_url: Optional[str] = None
    is_active: bool
    item_count: int = 0


class CategoryCreate(BaseModel):
    category_name: str = Field(min_length=2, max_length=100)
    category_name_ar: Optional[str] = Field(default=None, max_length=100)
    description: Optional[str] = None
    image_url: Optional[str] = Field(default=None, max_length=500)
    is_active: bool = True


class CategoryUpdate(BaseModel):
    category_name: Optional[str] = Field(default=None, min_length=2, max_length=100)
    category_name_ar: Optional[str] = Field(default=None, max_length=100)
    description: Optional[str] = None
    image_url: Optional[str] = Field(default=None, max_length=500)
    is_active: Optional[bool] = None


class MenuItemOut(ORMModel):
    item_id: int
    category_id: int
    category_name: Optional[str] = None
    category_name_ar: Optional[str] = None
    item_name: str
    item_name_ar: str
    synonyms: Optional[str] = None
    price: float
    is_available: bool
    description: Optional[str] = None
    description_ar: Optional[str] = None
    image_url: Optional[str] = None
    preparation_time: Optional[int] = None
    is_featured: bool
    created_at: Optional[datetime] = None


class MenuItemCreate(BaseModel):
    category_id: int
    item_name: str = Field(min_length=2, max_length=150)
    item_name_ar: str = Field(min_length=1, max_length=150)
    synonyms: Optional[str] = None
    price: float = Field(gt=0, le=100000)
    is_available: bool = True
    description: Optional[str] = None
    description_ar: Optional[str] = None
    image_url: Optional[str] = Field(default=None, max_length=500)
    preparation_time: Optional[int] = Field(default=15, ge=0, le=240)
    is_featured: bool = False


class MenuItemUpdate(BaseModel):
    category_id: Optional[int] = None
    item_name: Optional[str] = Field(default=None, min_length=2, max_length=150)
    item_name_ar: Optional[str] = Field(default=None, min_length=1, max_length=150)
    synonyms: Optional[str] = None
    price: Optional[float] = Field(default=None, gt=0, le=100000)
    is_available: Optional[bool] = None
    description: Optional[str] = None
    description_ar: Optional[str] = None
    image_url: Optional[str] = Field(default=None, max_length=500)
    preparation_time: Optional[int] = Field(default=None, ge=0, le=240)
    is_featured: Optional[bool] = None


# --------------------------------------------------------------------------- #
# Orders
# --------------------------------------------------------------------------- #
class CartLineIn(BaseModel):
    item_id: int
    quantity: int = Field(ge=1, le=99)
    special_instructions: Optional[str] = Field(default=None, max_length=300)


class OrderCreate(BaseModel):
    items: list[CartLineIn] = Field(min_length=1, max_length=50)
    payment_method: str = Field(default="pay_at_counter", max_length=50)
    order_notes: Optional[str] = Field(default=None, max_length=500)
    idempotency_key: Optional[str] = Field(default=None, max_length=64)


class OrderItemOut(ORMModel):
    order_item_id: int
    item_id: int
    item_name_snapshot: Optional[str] = None
    item_name_ar: Optional[str] = None
    quantity: int
    unit_price: float
    line_total: float = 0
    special_instructions: Optional[str] = None


class PaymentOut(ORMModel):
    payment_id: int
    payment_method: str
    payment_status: str
    amount: float
    transaction_reference: Optional[str] = None
    paid_at: Optional[datetime] = None
    created_at: Optional[datetime] = None


class StatusHistoryOut(ORMModel):
    history_id: int
    previous_status: Optional[str] = None
    new_status: str
    changed_by: Optional[int] = None
    changed_by_name: Optional[str] = None
    changed_at: Optional[datetime] = None
    notes: Optional[str] = None


class OrderOut(ORMModel):
    order_id: int
    customer_id: Optional[int] = None
    customer_name: Optional[str] = None
    customer_phone: Optional[str] = None
    order_date: datetime
    updated_at: Optional[datetime] = None
    status: str
    payment_status: str
    payment_method: Optional[str] = None
    order_notes: Optional[str] = None
    order_source: str
    total_amount: float
    items: list[OrderItemOut] = []
    payments: list[PaymentOut] = []
    status_history: list[StatusHistoryOut] = []


class OrderCreatedOut(BaseModel):
    order: OrderOut
    message: str


class StatusUpdate(BaseModel):
    status: OrderStatus
    notes: Optional[str] = Field(default=None, max_length=500)


class PaymentUpdate(BaseModel):
    payment_status: Literal["pending", "paid", "failed", "refunded"]
    transaction_reference: Optional[str] = Field(default=None, max_length=120)


class PaymentMethodOut(ORMModel):
    code: str
    name: str
    name_ar: str


# --------------------------------------------------------------------------- #
# Inventory
# --------------------------------------------------------------------------- #
class IngredientOut(ORMModel):
    ingredient_id: int
    ingredient_name: str
    ingredient_name_ar: Optional[str] = None
    unit_of_measure: str
    minimum_stock: float
    safety_stock: float
    lead_time_days: int
    cost_per_unit: Optional[float] = None
    default_supplier_id: Optional[int] = None
    is_active: bool
    quantity_on_hand: float = 0
    stock_status: str = "unknown"
    has_recipe: bool = False


class IngredientCreate(BaseModel):
    ingredient_name: str = Field(min_length=2, max_length=150)
    ingredient_name_ar: Optional[str] = Field(default=None, max_length=150)
    unit_of_measure: str = Field(min_length=1, max_length=20)
    minimum_stock: float = Field(default=0, ge=0)
    safety_stock: float = Field(default=0, ge=0)
    lead_time_days: int = Field(default=2, ge=0, le=365)
    cost_per_unit: Optional[float] = Field(default=None, ge=0)
    default_supplier_id: Optional[int] = None
    initial_stock: float = Field(default=0, ge=0)
    is_active: bool = True


class IngredientUpdate(BaseModel):
    ingredient_name: Optional[str] = Field(default=None, min_length=2, max_length=150)
    ingredient_name_ar: Optional[str] = Field(default=None, max_length=150)
    unit_of_measure: Optional[str] = Field(default=None, min_length=1, max_length=20)
    minimum_stock: Optional[float] = Field(default=None, ge=0)
    safety_stock: Optional[float] = Field(default=None, ge=0)
    lead_time_days: Optional[int] = Field(default=None, ge=0, le=365)
    cost_per_unit: Optional[float] = Field(default=None, ge=0)
    default_supplier_id: Optional[int] = None
    is_active: Optional[bool] = None


class StockMovementCreate(BaseModel):
    ingredient_id: int
    movement_type: Literal["purchase", "adjustment", "waste", "return"]
    quantity: float = Field(gt=0)
    direction: Literal["increase", "decrease"] = "increase"
    reason: Optional[str] = Field(default=None, max_length=255)


class StockMovementOut(ORMModel):
    movement_id: int
    ingredient_id: int
    ingredient_name: Optional[str] = None
    movement_type: str
    quantity_change: float
    quantity_after: float
    reason: Optional[str] = None
    reference_type: Optional[str] = None
    reference_id: Optional[str] = None
    order_id: Optional[int] = None
    purchase_order_id: Optional[int] = None
    user_id: Optional[int] = None
    user_name: Optional[str] = None
    created_at: datetime


class RecipeLineIn(BaseModel):
    ingredient_id: int
    quantity: float = Field(gt=0)
    unit_of_measure: str = Field(min_length=1, max_length=20)
    notes: Optional[str] = Field(default=None, max_length=255)


class RecipeOut(ORMModel):
    menu_item_ingredient_id: int
    item_id: int
    ingredient_id: int
    ingredient_name: Optional[str] = None
    quantity: float
    unit_of_measure: str
    notes: Optional[str] = None


class SupplierOut(ORMModel):
    supplier_id: int
    supplier_name: str
    contact_name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    notes: Optional[str] = None
    is_active: bool


class SupplierCreate(BaseModel):
    supplier_name: str = Field(min_length=2, max_length=150)
    contact_name: Optional[str] = Field(default=None, max_length=120)
    phone: Optional[str] = Field(default=None, max_length=30)
    email: Optional[EmailStr] = None
    address: Optional[str] = None
    notes: Optional[str] = None
    is_active: bool = True


class SupplierUpdate(BaseModel):
    supplier_name: Optional[str] = Field(default=None, min_length=2, max_length=150)
    contact_name: Optional[str] = Field(default=None, max_length=120)
    phone: Optional[str] = Field(default=None, max_length=30)
    email: Optional[EmailStr] = None
    address: Optional[str] = None
    notes: Optional[str] = None
    is_active: Optional[bool] = None


class PurchaseOrderItemIn(BaseModel):
    ingredient_id: int
    quantity_ordered: float = Field(gt=0)
    unit_cost: Optional[float] = Field(default=None, ge=0)


class PurchaseOrderCreate(BaseModel):
    supplier_id: int
    expected_date: Optional[date] = None
    notes: Optional[str] = Field(default=None, max_length=1000)
    items: list[PurchaseOrderItemIn] = Field(min_length=1, max_length=100)
    submit: bool = False


class PurchaseOrderItemOut(ORMModel):
    purchase_order_item_id: int
    ingredient_id: int
    ingredient_name: Optional[str] = None
    unit_of_measure: Optional[str] = None
    quantity_ordered: float
    quantity_received: float
    unit_cost: Optional[float] = None


class PurchaseOrderOut(ORMModel):
    purchase_order_id: int
    supplier_id: int
    supplier_name: Optional[str] = None
    status: str
    order_date: datetime
    expected_date: Optional[date] = None
    received_at: Optional[datetime] = None
    total_amount: float
    notes: Optional[str] = None
    created_by: Optional[int] = None
    items: list[PurchaseOrderItemOut] = []


class ReceiveItem(BaseModel):
    purchase_order_item_id: int
    quantity: float = Field(ge=0)


class ReceivePurchaseOrder(BaseModel):
    items: list[ReceiveItem] = Field(min_length=1)


class RecommendationOut(BaseModel):
    ingredient_id: int
    ingredient_name: str
    unit_of_measure: str
    current_quantity: float
    minimum_stock: float
    safety_stock: float
    expected_demand: float
    suggested_quantity: float
    lead_time_days: int
    reason: str


# --------------------------------------------------------------------------- #
# Kiosk / AI
# --------------------------------------------------------------------------- #
class KioskSessionCreate(BaseModel):
    language: Literal["ar", "en"] = "ar"


class KioskSessionOut(BaseModel):
    session_id: str
    status: str
    language: str
    expires_at: datetime
    cart: list[dict] = []
    subtotal: float = 0
    order_id: Optional[int] = None


class KioskChatIn(BaseModel):
    session_id: str = Field(min_length=8, max_length=40)
    message: str = Field(min_length=1, max_length=1000)
    language: Literal["ar", "en"] = "ar"


class KioskChatOut(BaseModel):
    reply: str
    state: str = "idle"
    cart: list[dict] = []
    subtotal: float = 0
    order_id: Optional[int] = None
    requires_confirmation: bool = False
    suggestions: list[dict] = []


class KioskConfirmIn(BaseModel):
    session_id: str
    customer_name: Optional[str] = Field(default=None, max_length=120)
    customer_phone: Optional[str] = Field(default=None, max_length=30)
    payment_method: str = Field(default="cash", max_length=50)


class ForecastRequest(BaseModel):
    horizon_days: int = Field(default=7, ge=1, le=30)
    item_id: Optional[int] = None
