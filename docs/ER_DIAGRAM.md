# ER diagrams

The database has **25 tables**. Diagrams are split by domain for readability; a combined Mermaid
source is available at [`database/diagrams/er_diagram.mmd`](../database/diagrams/er_diagram.mmd).
A structure-only SQL snapshot is in [`database/schema.sql`](../database/schema.sql).

---

## 1. Core ordering domain

```mermaid
erDiagram
    USERS ||--o| CUSTOMERS : "optional account profile"
    USERS ||--o{ USER_SESSIONS : "login sessions"
    USERS ||--o{ AUDIT_LOGS : "performs"
    USERS ||--o{ ORDER_STATUS_HISTORY : "changes"
    USERS ||--o{ PAYMENTS : "records"

    CATEGORIES ||--o{ MENU_ITEMS : "groups"
    CUSTOMERS ||--o{ ORDERS : "places"
    MENU_ITEMS ||--o{ ORDER_ITEMS : "sold as"

    ORDERS ||--o{ ORDER_ITEMS : "contains"
    ORDERS ||--o{ PAYMENTS : "paid by"
    ORDERS ||--o{ ORDER_STATUS_HISTORY : "audited by"
    ORDERS ||--o| ORDER_STOCK_APPLICATIONS : "consumes stock once"
    ORDERS ||--o| KIOSK_SESSIONS : "submitted from"

    PAYMENT_METHODS ||--o{ ORDERS : "selected method"
    PAYMENT_METHODS ||--o{ PAYMENTS : "method"

    USERS {
        int user_id PK
        varchar username UK
        varchar password_hash
        varchar password_algo
        enum role
        varchar pin_hash
        tinyint is_active
        datetime last_login_at
    }
    CUSTOMERS {
        int customer_id PK
        int user_id FK
        varchar customer_name
        varchar phone UK
        text address
    }
    ORDERS {
        int order_id PK
        int customer_id FK
        datetime order_date
        enum status
        enum payment_status
        varchar payment_method FK
        enum order_source
        decimal total_amount
        varchar idempotency_key UK
    }
    ORDER_ITEMS {
        int order_item_id PK
        int order_id FK
        int item_id FK
        varchar item_name_snapshot
        int quantity
        decimal unit_price
    }
    MENU_ITEMS {
        int item_id PK
        int category_id FK
        varchar item_name
        varchar item_name_ar
        decimal price
        tinyint is_available
        tinyint is_featured
    }
    CATEGORIES {
        int category_id PK
        varchar category_name
        varchar category_name_ar
        tinyint is_active
    }
    PAYMENTS {
        bigint payment_id PK
        int order_id FK
        varchar payment_method FK
        enum payment_status
        decimal amount
        datetime paid_at
    }
    PAYMENT_METHODS {
        varchar code PK
        varchar name
        varchar name_ar
        tinyint is_active
    }
    ORDER_STATUS_HISTORY {
        bigint history_id PK
        int order_id FK
        enum previous_status
        enum new_status
        int changed_by FK
        datetime changed_at
    }
    ORDER_STOCK_APPLICATIONS {
        int order_id PK
        enum status
        datetime applied_at
        datetime reversed_at
    }
    USER_SESSIONS {
        char session_id PK
        int user_id FK
        char jwt_id UK
        datetime expires_at
        datetime revoked_at
    }
    AUDIT_LOGS {
        bigint audit_id PK
        int user_id FK
        varchar action
        varchar entity_type
        varchar entity_id
        json details
        datetime created_at
    }
```

---

## 2. Inventory and purchasing domain

```mermaid
erDiagram
    SUPPLIERS ||--o{ INGREDIENTS : "default supplier"
    SUPPLIERS ||--o{ PURCHASE_ORDERS : "receives"
    INGREDIENTS ||--|| INVENTORY_STOCK : "current balance"
    INGREDIENTS ||--o{ MENU_ITEM_INGREDIENTS : "used in recipes"
    INGREDIENTS ||--o{ STOCK_MOVEMENTS : "ledger"
    INGREDIENTS ||--o{ PURCHASE_ORDER_ITEMS : "purchased as"

    MENU_ITEMS ||--o{ MENU_ITEM_INGREDIENTS : "recipe lines"
    PURCHASE_ORDERS ||--o{ PURCHASE_ORDER_ITEMS : "lines"
    PURCHASE_ORDERS ||--o{ STOCK_MOVEMENTS : "receiving"
    ORDERS ||--o{ STOCK_MOVEMENTS : "consumption/reversal"
    USERS ||--o{ STOCK_MOVEMENTS : "records"
    USERS ||--o{ INVENTORY_STOCK : "updates"

    SUPPLIERS {
        int supplier_id PK
        varchar supplier_name UK
        varchar phone
        varchar email
        tinyint is_active
    }
    INGREDIENTS {
        int ingredient_id PK
        varchar ingredient_name UK
        varchar ingredient_name_ar
        varchar unit_of_measure
        decimal minimum_stock
        decimal safety_stock
        int lead_time_days
        int default_supplier_id FK
    }
    INVENTORY_STOCK {
        bigint stock_id PK
        int ingredient_id FK_UK
        decimal quantity
        datetime last_updated
        int updated_by FK
    }
    MENU_ITEM_INGREDIENTS {
        bigint menu_item_ingredient_id PK
        int item_id FK
        int ingredient_id FK
        decimal quantity
        varchar unit_of_measure
    }
    STOCK_MOVEMENTS {
        bigint movement_id PK
        int ingredient_id FK
        enum movement_type
        decimal quantity_change
        decimal quantity_after
        int order_id FK
        bigint purchase_order_id FK
        int user_id FK
    }
    PURCHASE_ORDERS {
        bigint purchase_order_id PK
        int supplier_id FK
        enum status
        date expected_date
        decimal total_amount
        int created_by FK
    }
    PURCHASE_ORDER_ITEMS {
        bigint purchase_order_item_id PK
        bigint purchase_order_id FK
        int ingredient_id FK
        decimal quantity_ordered
        decimal quantity_received
        decimal unit_cost
    }
```

---

## 3. Kiosk and helper tables

```mermaid
erDiagram
    KIOSK_SESSIONS ||--o{ KIOSK_CART_ITEMS : "holds"
    KIOSK_SESSIONS ||--o{ KIOSK_MESSAGES : "transcript"
    KIOSK_SESSIONS }o--|| ORDERS : "submitted as"
    KIOSK_CART_ITEMS }o--|| MENU_ITEMS : "references"

    KIOSK_SESSIONS {
        char session_id PK
        enum status
        varchar state
        enum language
        datetime expires_at
        int order_id FK
    }
    KIOSK_CART_ITEMS {
        bigint cart_item_id PK
        char session_id FK
        int item_id FK
        int quantity
    }
    KIOSK_MESSAGES {
        bigint message_id PK
        char session_id FK
        enum role
        text content
        enum language
    }
    ITEM_ALIASES {
        int alias_id PK
        int item_id FK
        varchar alias
    }
    RESTAURANT_TABLES {
        int table_id PK
        int table_number UK
        tinyint is_active
    }
    SCHEMA_MIGRATIONS {
        varchar version PK
        datetime applied_at
        char checksum
    }
```

---

## 4. Relationship summary

| Relationship | Cardinality | Delete rule |
| --- | --- | --- |
| `users` → `customers` | one-to-zero-or-one | SET NULL |
| `customers` → `orders` | one-to-many | restrict |
| `categories` → `menu_items` | one-to-many | restrict |
| `orders` → `order_items` | one-to-many | CASCADE |
| `orders` → `payments` | one-to-many | CASCADE |
| `orders` → `order_status_history` | one-to-many | CASCADE |
| `orders` → `order_stock_applications` | one-to-zero-or-one | CASCADE |
| `orders` → `stock_movements` | one-to-many | SET NULL |
| `orders` → `kiosk_sessions` | one-to-zero-or-one | SET NULL |
| `payment_methods` → `orders/payments` | one-to-many | restrict |
| `ingredients` → `inventory_stock` | one-to-one | CASCADE |
| `ingredients` → `menu_item_ingredients` | one-to-many | CASCADE |
| `ingredients` → `stock_movements` | one-to-many | CASCADE |
| `suppliers` → `purchase_orders` | one-to-many | restrict |
| `purchase_orders` → `purchase_order_items` | one-to-many | CASCADE |
| `kiosk_sessions` → `kiosk_cart_items/messages` | one-to-many | CASCADE |
| `users` → `audit_logs`, sessions, history, movements | one-to-many | SET NULL / CASCADE |

`item_aliases`, `restaurant_tables` and `schema_migrations` are standalone helper/metadata tables.
