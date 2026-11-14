# Database documentation and operational scripts

Everything that changes the `bremer` MySQL database lives in this folder. No migration or seed in
this project drops a table, truncates a table, or deletes seeded rows from `DataBase.ipynb`.

```
database/
├── migrate.py                  # migration runner (backup, tracking, PIN hashing)
├── schema.sql                  # structure-only snapshot of the live DB (no DROP)
├── migrations/                 # 001..005 additive SQL migrations
├── seeds/demo_inventory.sql    # OPTIONAL demo stock, NOT applied
├── maintenance/
│   ├── cleanup_verification_data.sql
│   └── cleanup_demo_inventory.sql
├── backups/                    # mysqldump files (git-ignored, contains real data)
└── diagrams/er_diagram.mmd     # combined Mermaid ER diagram
```

---

## 1. Preserved source data

The delivered database keeps the original notebook rows:

| Table | Rows |
| --- | --- |
| `categories` | 17 |
| `menu_items` | 142 |
| `customers` | 30 |
| `orders` | 41 |
| `order_items` | 150 |
| `users` | 5 |

Migrations are additive (`ALTER TABLE ... ADD COLUMN`, `CREATE TABLE`, `CREATE INDEX`), and the only
data writes are:

- `payment_methods` reference rows (`cash`, `pay_at_counter`, `card`);
- one `order_status_history` baseline row per pre-existing order (41 rows), labelled
  `Imported from pre-migration order state`;
- bcrypt conversion of legacy PINs (plaintext `pin_code` is set to `NULL`).

Nothing else in the original tables is rewritten. Historical `order_items.unit_price` values are never
recalculated.

---

## 2. Running migrations

```powershell
.venv\Scripts\python.exe database\migrate.py
```

The runner (`migrate.py`) does the following, in order:

1. Loads `.env` (host, port, user, password, database).
2. Connects and creates `schema_migrations` if needed.
3. Takes `database/backups/bremer_pre_migration_<timestamp>.sql` with `mysqldump` (single
   transaction, routines, triggers, `utf8mb4`) **before** applying anything.
4. Reads `migrations/*.sql` in lexical order and skips versions already recorded.
5. Splits each file on statement boundaries (quote/comment aware) and executes statements in order.
6. Records the version in `schema_migrations` only after the file succeeds.
7. Converts any legacy plaintext `users.pin_code` value to bcrypt in `pin_hash` and nulls the column.

Re-running is safe: applied versions are skipped. Migration 005 is additionally idempotent
(`CREATE TABLE IF NOT EXISTS`) so a partially applied earlier run can be repaired.

### Applied versions (live database)

| Version | Applied at | Purpose |
| --- | --- | --- |
| `001_enhance_core.sql` | 2026-11-12 22:07:06 | Extend the six original tables; history, payments, audit, sessions, payment methods |
| `002_inventory.sql` | 2026-11-12 22:07:29 | Suppliers, ingredients, stock, recipes, movements, purchase orders, idempotency guard |
| `003_kiosk.sql` | 2026-11-12 22:07:31 | Kiosk sessions, server-side cart, transcript |
| `004_kiosk_state.sql` | 2026-11-12 22:13:48 | Conversational `state` column + index |
| `005_repair_core_tables.sql` | 2026-11-12 22:15:55 | Idempotent repair of `audit_logs` / `user_sessions` |

Check the live state:

```sql
SELECT version, applied_at FROM schema_migrations ORDER BY version;
```

### Rollback

There is no down-migration. Restore the dump that `migrate.py` wrote before the change:

```powershell
$mysql = "C:\Program Files\MySQL\MySQL Server 8.0\bin\mysql.exe"
& $mysql -uroot -p -e "DROP DATABASE IF EXISTS bremer; CREATE DATABASE bremer CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
& $mysql -uroot -p bremer < database\backups\bremer_pre_migration_<timestamp>.sql
```

This restore is the only destructive operation in the repository, and it is never executed by the
application or by `migrate.py`.

---

## 3. Backups

Dumps are written to `database/backups/` and excluded from version control because they contain real
customer data. Manual backup:

```powershell
$dump = "C:\Program Files\MySQL\MySQL Server 8.0\bin\mysqldump.exe"
$ts = Get-Date -Format "yyyyMMdd_HHmmss"
& $dump -uroot -p --databases bremer --single-transaction --routines --triggers `
  --default-character-set=utf8mb4 --result-file="database\backups\bremer_manual_$ts.sql"
```

Recommended policy: before every migration, seed import, cleanup script or data fix, and keep at least
one dump that predates the current release.

---

## 4. Seeds

| File | Contents | Applied? |
| --- | --- | --- |
| `seeds/demo_inventory.sql` | 4 fictional suppliers, 20 ingredients with Arabic names, opening balances and matching `initial` stock movements | **No** — optional demo data |
| Recipes | not seeded | Recipe quantities are absent from the source notebook and must be configured by a manager |
| Menu/customers/orders/users | already in `bremer` | Yes (original data) |

Apply or remove demo stock:

```powershell
$mysql = "C:\Program Files\MySQL\MySQL Server 8.0\bin\mysql.exe"
& $mysql -uroot -p bremer < database\seeds\demo_inventory.sql
& $mysql -uroot -p bremer < database\maintenance\cleanup_demo_inventory.sql
```

The seed is idempotent (`INSERT IGNORE`, guarded ledger insert) and never overwrites a quantity that a
manager has already adjusted. The cleanup only removes rows created by the seed that are still
unreferenced.

---

## 5. Maintenance scripts

| Script | Purpose | Safety |
| --- | --- | --- |
| `maintenance/cleanup_verification_data.sql` | Remove the orders/kiosk sessions/payments/audit rows created by manual acceptance testing (orders 42-48) | Scoped `WHERE` clauses, wrapped in a transaction; never touches ids 1-41 or the seeded 30 customers |
| `maintenance/cleanup_demo_inventory.sql` | Remove the optional demo stock | Only rows tagged by the demo seed or still unreferenced; keeps recipes, purchases and manager edits |

Take a dump immediately before running either script and verify the counts afterwards:

```sql
SELECT 'orders', COUNT(*) FROM orders
UNION ALL SELECT 'order_items', COUNT(*) FROM order_items
UNION ALL SELECT 'customers', COUNT(*) FROM customers
UNION ALL SELECT 'categories', COUNT(*) FROM categories
UNION ALL SELECT 'menu_items', COUNT(*) FROM menu_items
UNION ALL SELECT 'users', COUNT(*) FROM users;
```

Expected after cleanup: 41 / 150 / 30 / 17 / 142 / 5.

---

## 6. `schema.sql`

`schema.sql` is generated from the migrated live database with:

```powershell
& $dump -uroot -p --no-data --skip-add-drop-table --skip-comments --no-tablespaces `
  --default-character-set=utf8mb4 bremer > database\schema.sql
```

It is a **reference snapshot** — 25 `CREATE TABLE` statements, no `DROP DATABASE`, no `DROP TABLE`,
no `USE`, no data. To build a fresh environment, use the migrations (or a backup), not this file.

---

## 7. Test database

`backend/tests/conftest.py` creates a separate `bremer_test` database from SQLAlchemy metadata and
refuses to run unless `TEST_DB_NAME` ends with `_test`. Each test runs inside an outer transaction
that is rolled back. `test_preserved_data.py` performs **read-only** checks against the live `bremer`
database and skips when it is unreachable.

Tests never write to `database/backups`, `backend/ml_artifacts` or `backend/uploads`: temporary
directories are used for artifacts and uploads.

---

## 8. Related documentation

- [../../docs/DATABASE.md](../../docs/DATABASE.md) — every table, column and relationship
- [../../docs/ER_DIAGRAM.md](../../docs/ER_DIAGRAM.md) — Mermaid diagrams per domain
- [../../docs/SETUP.md](../../docs/SETUP.md) — install, run, restore and troubleshooting
- [../../docs/ACCEPTANCE_REPORT.md](../../docs/ACCEPTANCE_REPORT.md) — what was actually verified
