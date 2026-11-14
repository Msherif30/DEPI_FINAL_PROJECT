# Database guide

- **Server**: MySQL 8.0.46, database `bremer`, charset `utf8mb4`, collation `utf8mb4_unicode_ci`
  (two pre-existing helper tables use `utf8mb4_0900_ai_ci`).
- **Access**: SQLAlchemy 2 + PyMySQL from the backend; `database/migrate.py` for schema changes.
- **Schema snapshot**: [`database/schema.sql`](../database/schema.sql) — structure only, **no `DROP`**.
- **Backups**: [`database/backups/`](../database/backups) (git-ignored because they contain real data).

---

## 1. Preserved seed data

The delivered database still contains the original notebook data:

| Table | Rows |
| --- | --- |
| `categories` | 17 |
| `menu_items` | 142 |
| `customers` | 30 |
| `orders` | 41 |
| `order_items` | 150 |
| `users` | 5 |

Verification data created during acceptance testing (orders 42-48, test kiosk sessions, test payments,
test audit/login rows and one auto-created customer profile) was removed with
[`database/maintenance/cleanup_verification_data.sql`](../database/maintenance/cleanup_verification_data.sql).
A backup was taken immediately before cleanup. The read-only test `test_preserved_data.py` asserts these
counts and the live schema.

---

## 2. Table catalogue

### 2.1 Original tables (extended in place)

| Table | Purpose | Added columns |
| --- | --- | --- |
| `categories` | Menu categories (AR/EN) | `description`, `image_url`, `is_active`, `created_at`, `updated_at` |
| `menu_items` | Products, AR/EN names, synonyms, descriptions | `image_url`, `preparation_time`, `is_featured`, `created_at`, `updated_at` |
| `customers` | Historical customer profiles | `user_id` (nullable, unique FK to `users`), `updated_at` |
| `orders` | Order header and lifecycle | `updated_at`, `payment_status`, `payment_method` (FK), `order_notes`, `idempotency_key` (unique); `order_source` extended with `kiosk` |
| `order_items` | Order lines | `item_name_snapshot`, `created_at` |
| `users` | Accounts | `email` (unique), `password_algo`, `pin_hash`, `must_change_password`, `updated_at`, `last_login_at` |

Key constraints added:

- `CHECK price >= 0`, `CHECK preparation_time >= 0`
- `CHECK total_amount >= 0`, `CHECK quantity > 0`, `CHECK unit_price >= 0`
- `customers.user_id → users.user_id` (`ON DELETE SET NULL`)
- `orders.payment_method → payment_methods.code`
- Indexes on dates, statuses, sources, availability, featured flag, names, phone and email.

`orders.status` and `orders.order_source` remain enums so invalid values are rejected by MySQL.
Historical `unit_price` values are never recalculated.

### 2.2 Ordering, payment and audit

| Table | Purpose | Notes |
| --- | --- | --- |
| `order_status_history` | Append-only transition log | `previous_status`, `new_status`, `changed_by`, `changed_at`, `notes`; one baseline row per pre-existing order was backfilled by migration 001 |
| `payments` | Payment records | `payment_method` FK, `payment_status` (`pending/paid/failed/refunded`), `amount`, `transaction_reference`, `paid_at`, `created_by` |
| `payment_methods` | Configurable methods | seeded `cash`, `pay_at_counter`, `card`; frontend loads them from the API |
| `audit_logs` | Operational/security audit | actor, action, entity type/id, JSON details, IP; never stores secrets |
| `user_sessions` | Revocable login sessions | `session_id` UUID PK, `jwt_id` unique, issued/expires/revoked, IP, user agent |

### 2.3 Inventory and purchasing

| Table | Purpose | Key rules |
| --- | --- | --- |
| `ingredients` | Stock items | unique name, unit, `minimum_stock`, `safety_stock`, `lead_time_days`, optional default supplier, active flag |
| `inventory_stock` | Current balance | one row per ingredient (`UNIQUE ingredient_id`), `CHECK quantity >= 0`, `updated_by` |
| `menu_item_ingredients` | Recipe lines | unique `(item_id, ingredient_id)`, `quantity > 0`, unit |
| `stock_movements` | Stock ledger | types `initial/purchase/consumption/adjustment/waste/return`, signed `quantity_change`, `quantity_after`, order/purchase/user references |
| `order_stock_applications` | Idempotency guard | `order_id` is the primary key; `status = applied/reversed` |
| `suppliers` | Vendor records | unique name, contact fields, active flag |
| `purchase_orders` | Purchase header | `draft/ordered/partially_received/received/cancelled`, supplier, dates, total |
| `purchase_order_items` | Purchase lines | unique `(purchase_order_id, ingredient_id)`, ordered/received quantities, unit cost |

### 2.4 Kiosk

| Table | Purpose |
| --- | --- |
| `kiosk_sessions` | UUID session, status (`active/submitted/expired/abandoned`), state, language, expiry, optional order link |
| `kiosk_cart_items` | Server-side cart, unique `(session_id, item_id)`, `quantity > 0` |
| `kiosk_messages` | Conversation transcript (`user/assistant/system`) |

### 2.5 Helpers and metadata

| Table | Purpose |
| --- | --- |
| `item_aliases` | Extra search aliases for menu items (pre-existing helper table, currently empty) |
| `restaurant_tables` | Physical table numbers (pre-existing helper table, currently empty) |
| `schema_migrations` | Applied migration version, timestamp and optional checksum |

---

## 3. Relationship catalogue

| Parent | Child | Cardinality | On delete |
| --- | --- | --- | --- |
| `users` | `customers` | 1 → 0..1 | SET NULL |
| `users` | `user_sessions` | 1 → N | CASCADE |
| `users` | `audit_logs` | 1 → N | SET NULL |
| `users` | `order_status_history` (changed_by) | 1 → N | SET NULL |
| `users` | `payments` (created_by) | 1 → N | SET NULL |
| `users` | `stock_movements` (user_id) | 1 → N | SET NULL |
| `users` | `inventory_stock` (updated_by) | 1 → N | SET NULL |
| `categories` | `menu_items` | 1 → N | (restrict) |
| `menu_items` | `order_items` | 1 → N | (restrict) |
| `menu_items` | `menu_item_ingredients` | 1 → N | CASCADE |
| `menu_items` | `kiosk_cart_items` | 1 → N | (restrict) |
| `menu_items` | `item_aliases` | 1 → N | CASCADE |
| `customers` | `orders` | 1 → N | (restrict) |
| `orders` | `order_items` | 1 → N | CASCADE |
| `orders` | `payments` | 1 → N | CASCADE |
| `orders` | `order_status_history` | 1 → N | CASCADE |
| `orders` | `order_stock_applications` | 1 → 0..1 | CASCADE |
| `orders` | `stock_movements` | 1 → N | SET NULL |
| `orders` | `kiosk_sessions` | 1 → 0..1 | SET NULL |
| `payment_methods` | `orders`, `payments` | 1 → N | (restrict) |
| `ingredients` | `inventory_stock` | 1 → 1 | CASCADE |
| `ingredients` | `menu_item_ingredients` | 1 → N | CASCADE |
| `ingredients` | `stock_movements` | 1 → N | CASCADE |
| `ingredients` | `purchase_order_items` | 1 → N | (restrict) |
| `suppliers` | `ingredients` (default) | 1 → N | SET NULL |
| `suppliers` | `purchase_orders` | 1 → N | (restrict) |
| `purchase_orders` | `purchase_order_items` | 1 → N | CASCADE |
| `purchase_orders` | `stock_movements` | 1 → N | SET NULL |
| `kiosk_sessions` | `kiosk_cart_items` | 1 → N | CASCADE |
| `kiosk_sessions` | `kiosk_messages` | 1 → N | CASCADE |

Full visual model: [ER_DIAGRAM.md](ER_DIAGRAM.md).

---

## 4. Migration history

All migrations are additive and idempotent where noted. They are applied once and recorded in
`schema_migrations` by `database/migrate.py`.

| Version | Applied (live DB) | Contents |
| --- | --- | --- |
| `001_enhance_core.sql` | 2026-11-12 22:07:06 | Extends the six original tables, adds history/payments/audit/sessions, backfills status history, seeds payment methods |
| `002_inventory.sql` | 2026-11-12 22:07:29 | Suppliers, ingredients, stock, recipes, stock movements, purchase orders/items, `order_stock_applications` |
| `003_kiosk.sql` | 2026-11-12 22:07:31 | Kiosk sessions, server-side cart, messages |
| `004_kiosk_state.sql` | 2026-11-12 22:13:48 | Adds conversational `state` + index |
| `005_repair_core_tables.sql` | 2026-11-12 22:15:55 | Idempotently recreates `audit_logs` and `user_sessions` if an earlier run aborted before reaching them |

The migration runner:

1. Loads `.env`.
2. Creates `database/backups/bremer_pre_migration_<timestamp>.sql` with `mysqldump` before the first change.
3. Skips versions already present in `schema_migrations`.
4. Splits SQL safely (quotes/comments aware), executes in order.
5. Converts legacy plaintext PINs to bcrypt and nulls `pin_code`.

### Rollback

Migrations are **forward-only by design**. The safe rollback is restore from the pre-migration dump:

```powershell
mysql -uroot -p -e "DROP DATABASE IF EXISTS bremer; CREATE DATABASE bremer CHARACTER SET utf8mb4;"
mysql -uroot -p bremer < database/backups/bremer_pre_migration_20261112_215042.sql
```

Do not hand-drop columns/tables on the live database unless you have a verified backup and have checked
every foreign key that references them. For development, re-running `database/migrate.py` against an
empty `bremer` database rebuilds the whole schema from the migrations.

---

## 5. Seed strategy

| Dataset | How it is provided | Applied to live DB? |
| --- | --- | --- |
| Original menu/categories/customers/orders/users | Already in `bremer`, preserved by additive migrations | Yes (unchanged) |
| Payment methods | Migration 001 (`cash`, `pay_at_counter`, `card`) | Yes |
| Order status baseline rows | Migration 001 backfill (`Imported from pre-migration order state`) | Yes |
| Demo inventory | [`database/seeds/demo_inventory.sql`](../database/seeds/demo_inventory.sql) — suppliers, 20 ingredients, initial stock/movements | **No** — optional, clearly labelled demo data |
| Recipes | Not provided | **No** — recipe quantities are not present in the source notebook and must be configured by the manager |
| Test fixtures | `backend/tests/conftest.py` creates `bremer_test` from SQLAlchemy metadata | Separate database only |

No historical row was invented to make dashboards or the ML model look better.

---

## 6. Legacy password/PIN handling

The notebook hashes passwords with:

```sql
SHA2(CONCAT('rm_salt_secure_', password), 256)
```

These are **not** bcrypt/Argon2 hashes. `app/core/security.py`:

- verifies `password_algo = 'legacy_sha256'` using the same salt formula;
- on success, immediately rehashes to bcrypt and sets `password_algo = 'bcrypt'`;
- new registrations/password changes always use bcrypt;
- PIN login verifies `pin_hash`; plaintext `pin_code` was migrated to bcrypt and then set to `NULL`;
- `system_ai` is rejected by `get_current_user`.

API responses never include `password_hash`, `password_algo`, `pin_hash` or `pin_code`.

---

## 7. Operational queries

```sql
-- current stock and status inputs
SELECT i.ingredient_name, s.quantity, i.minimum_stock, i.safety_stock, i.unit_of_measure
FROM ingredients i JOIN inventory_stock s USING (ingredient_id)
ORDER BY i.ingredient_name;

-- recent stock ledger
SELECT movement_id, ingredient_id, movement_type, quantity_change, quantity_after,
       reference_type, reference_id, created_at
FROM stock_movements ORDER BY movement_id DESC LIMIT 50;

-- orders that consumed stock
SELECT order_id, status, applied_at, reversed_at FROM order_stock_applications;

-- applied migrations
SELECT version, applied_at FROM schema_migrations ORDER BY version;
```

Health check: `GET /api/health/db` returns live counts for the core and inventory tables.
