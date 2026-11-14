# Acceptance report

**Project:** RestoMate AI — unified restaurant operating system
**Delivered:** 2026-11-13/14
**Workspace:** `C:\Users\sys\Desktop\RestoMate.ai`
**Stack:** FastAPI · SQLAlchemy 2 · MySQL 8.0 (`bremer`) · React 18 + TypeScript + Vite · scikit-learn
**Dataset:** the original `DataBase.ipynb` seed data, preserved in place

This report separates what was **executed and observed** from what is **implemented but could not be
verified in this environment**. Nothing below is marked verified on the basis of a plan or a
screenshot alone.

---

## 1. Delivered scope

| Area | Delivered |
| --- | --- |
| Database | 5 additive migrations, 25 tables, structure snapshot, ER diagrams, optional demo seed, cleanup scripts, backups |
| Backend | 66 REST endpoints + 2 WebSocket endpoints, layered services, RBAC, audit, rate limiting, JWT sessions |
| Customer portal | Menu with search/filter/sort, cart, checkout, order history, order detail with live polling, profile |
| Staff portal | Live board for chef/cashier, status transitions, payment recording, WebSocket refresh |
| Manager dashboard | KPIs, sales/category/peak-hour/source analytics, menu & category admin, staff admin, audit log |
| Inventory | Ingredients, stock movements, recipes, low stock, recommendations, suppliers, purchase orders/receiving |
| AI kiosk | Bilingual deterministic assistant, server-side cart, explicit confirmation, TTS, browser STT, optional LLM adapter |
| ML | Chronological 80/20 split, baseline vs RandomForest/GradientBoosting, MAE/RMSE, persisted artifact, warnings |
| Docs | Setup, architecture, database, ER, API, acceptance report, database runbook |
| Tests | 30 pytest tests against an isolated `bremer_test` database + read-only live-data checks |

---

## 2. Database preservation

Verified directly against the live `bremer` database after the final cleanup:

| Table | Rows | Expected | Result |
| --- | --- | --- | --- |
| `categories` | 17 | 17 | ✅ |
| `menu_items` | 142 | 142 | ✅ |
| `customers` | 30 | 30 | ✅ |
| `orders` | 41 | 41 | ✅ |
| `order_items` | 150 | 150 | ✅ |
| `users` | 5 | 5 | ✅ |
| `payments` | 0 | 0 (none existed) | ✅ |
| `order_status_history` | 41 | 41 baseline backfill | ✅ |
| `kiosk_sessions` / `audit_logs` / `user_sessions` | 0 | 0 after cleanup | ✅ |

- No `DROP DATABASE`, `DROP TABLE` or `DELETE` from `DataBase.ipynb` was executed.
- Migrations `001`–`005` are recorded in `schema_migrations` (`001` 2026-11-12 22:07:06 … `005`
  2026-11-12 22:15:55).
- Backups were taken before migration and before the verification-data cleanup; the latest cleanup
  backup is `database/backups/bremer_pre_cleanup_20261113_025634.sql`.
- `test_preserved_data.py` re-checks counts, the 142 menu items / 17 categories, safe staff account
  fields and the presence of the new tables. It is read-only and skips if MySQL is unreachable.

**Expected runtime behaviour:** when the seeded `ahmed_ali` customer account first uses the customer
portal, a `customers` profile is auto-provisioned for it (the 30 historical customers are never
matched by name). That raises the live count to 31 until
`maintenance/cleanup_verification_data.sql` is run again. This is deliberate account linking, not
modification of historical data.

---

## 3. Schema and migration verification

- 25 tables exist in the live database.
- `database/schema.sql` was generated from the live schema: 25 `CREATE TABLE` statements, **no**
  `DROP`, no `USE`, no `CREATE DATABASE`, UTF-8 without BOM.
- New tables: `ingredients`, `inventory_stock`, `menu_item_ingredients`, `stock_movements`,
  `suppliers`, `purchase_orders`, `purchase_order_items`, `payments`, `payment_methods`,
  `order_status_history`, `audit_logs`, `user_sessions`, `kiosk_sessions`, `kiosk_cart_items`,
  `kiosk_messages`, `order_stock_applications`, `schema_migrations` (plus the pre-existing
  `item_aliases` and `restaurant_tables`).
- Constraints verified in the live schema: unique `customers.user_id`, unique
  `orders.idempotency_key`, unique `(session_id, item_id)` kiosk cart lines, `order_id` as the
  primary key of `order_stock_applications`, `CHECK quantity >= 0` on stock and order lines,
  `CHECK price >= 0`, and the documented foreign keys.
- Legacy `SHA2(CONCAT('rm_salt_secure_', password), 256)` hashes are verified and transparently
  upgraded to bcrypt on successful login; plaintext staff PINs were converted to bcrypt and
  `pin_code` was nulled.

---

## 4. Automated test results

Command:

```powershell
$env:PYTHONPATH="backend"; $env:PYTHONIOENCODING="utf-8"
.venv\Scripts\python.exe -m pytest -q
```

Result: **30 passed**, 5 warnings, ~75 s. The suite uses a dedicated `bremer_test` database created
from SQLAlchemy metadata; every test rolls back an outer transaction. Tests do not write to the live
database, the live ML artifacts or `backend/uploads`.

| File | Tests | Coverage |
| --- | --- | --- |
| `test_auth.py` | 9 | Customer login, wrong password, `system_ai` block, PIN login, legacy hash upgrade, register/profile/password, logout revocation, manager-only staff management, cross-customer order isolation |
| `test_orders.py` | 4 | Server-side pricing, idempotency, full lifecycle + payment, role 403s, invalid transition 409, stock consumption, cancellation reversal, insufficient-stock block, real analytics |
| `test_inventory.py` | 4 | Ingredient creation/adjustment, recipes replacement, supplier + purchase order receiving, non-negative stock |
| `test_kiosk.py` | 3 | Arabic flow requires explicit confirmation, no invented items/prices, English flow + reset |
| `test_menu_audit.py` | 3 | Menu create/update/retire, categories/search, audit events |
| `test_forecast.py` | 3 | Honest failure without history, permissions/validation, chronological training + predictions |
| `test_preserved_data.py` | 4 | Live seed counts, menu/category integrity, no secret exposure, new schema present |

Warnings: Starlette `httpx` deprecation, FastAPI `422` constant deprecation and scikit-learn feature-name
warnings. None affect results.

---

## 5. Frontend build

```powershell
cd frontend
npm run typecheck
npm run build
```

- `tsc -b --noEmit`: **passed**.
- `vite build`: **succeeded**, 2,248 modules; production output in `frontend/dist`.
- Only warning: the single JS chunk is larger than 500 kB (~851 kB minified, ~235 kB gzip). This is a
  bundling advisory; it does not affect correctness. Route-level code splitting is a future
  optimisation, not a missing feature.

---

## 6. Browser verification

Verified in Chromium against the Vite dev server and the live API:

| Flow | Observed |
| --- | --- |
| Kiosk load | Session created, bilingual greeting, suggestions rendered, cart panel and confirm button present |
| Kiosk typed order | “I want two OG Burgers and an OG Mojito” produced **2 × OG Burger (270.00 EGP)** + **1 × OG Mojito (95.00 EGP)**, subtotal **635.00 EGP**, 3 items |
| Explicit confirmation | **Confirm order** opened a modal listing the lines, total, optional name/phone and payment method; **Cancel** closed it and **no order was created** (`orders` stayed at 41) |
| Kiosk voice control | Mic button present with `aria-pressed`; Chromium reported `SpeechRecognition`/`webkitSpeechRecognition` support; when the API was simulated as unavailable, the typed fallback toast appeared and input remained usable |
| Kiosk order linkage (earlier run) | A submitted kiosk order (#48) was correctly linked to its `kiosk_sessions` row; removed afterwards by the cleanup script |
| Manager portal | `/manager/inventory`, `/manager/forecast`, `/manager/audit` rendered their headings with **no console errors**; login API succeeded for the manager |
| Staff portal | `/staff/board` rendered the live operations board with no console errors; cashier login succeeded |
| Customer portal | `/menu`, `/orders`, `/profile` rendered with no console errors; customer login succeeded |

A final deeper “data marker” browser pass (waiting for each page's live data to arrive) was interrupted
when the session restarted and the browser tooling became unavailable. Page rendering, console health,
login, kiosk ordering and the confirmation gate were verified; the business rules behind each page are
covered by the 30 API tests.

**Not browser-verified:** actual microphone capture (requires granting device microphone permission),
audible TTS quality, real-time WebSocket delivery across two simultaneous sessions, and the optional
LLM path.

---

## 7. Feature acceptance matrix

| Requirement | Status | Evidence |
| --- | --- | --- |
| Preserve original data | **Verified** | Live counts, backups, `test_preserved_data.py` |
| Additive migrations | **Verified** | `schema_migrations`, live 25-table schema |
| Customer register/login | **Verified** | `test_auth.py`, browser login |
| Staff/manager login + PIN | **Verified** | `test_auth.py`, browser/API login |
| Backend RBAC on every role | **Verified** | Role tests (403/409), dependency audit |
| `system_ai` cannot log in | **Verified** | `test_system_ai_account_cannot_log_in` |
| Browse real menu | **Verified** | Menu/search/category tests, browser menu render |
| Cart + server-side checkout | **Verified** | Order pricing test, kiosk browser flow |
| Order status lifecycle + history | **Verified** | Lifecycle test, state-machine service |
| Payments recorded separately | **Verified** | `/payment` test, dashboard definitions |
| Staff live board | **Verified (render)** | Browser render; API board tests; WebSocket delivery untested |
| Customer order tracking | **Implemented** | Detail page polls while active; socket endpoint authorized; not covered by an automated UI test |
| Manager KPIs / analytics | **Verified** | Real-data analytics test + dashboard render |
| Menu/category admin | **Verified** | `test_menu_audit.py` |
| Staff management | **Verified** | `test_only_managers_can_manage_staff` |
| Inventory / recipes / movements | **Verified** | `test_inventory.py` |
| Idempotent stock consumption + reversal | **Verified** | Order + inventory tests, `order_stock_applications` |
| Suppliers + purchase orders | **Verified** | Receiving test |
| Purchasing recommendations | **Implemented** | API + UI; recommendation math is unit-exercised only through inventory tests |
| Bilingual kiosk, real prices | **Verified** | `test_kiosk.py`, browser order |
| Explicit kiosk confirmation | **Verified** | API test + browser modal/cancel |
| No SQL / no invented menu | **Verified** | Tool whitelist, no submit tool, kiosk tests |
| TTS | **Implemented** | Browser `speechSynthesis` path; acoustic output not verified |
| STT | **Implemented** | Support detection + fallback exercised; real capture not verified |
| Optional LLM adapter | **Implemented, not verified** | No `LLM_API_KEY`; deterministic fallback is the tested runtime |
| Demand forecasting | **Verified** | Chronological split test, MAE/RMSE, persisted artifacts |
| Small-data honesty | **Verified** | Warning emitted and shown in UI |
| Audit log | **Verified** | Audit test + manager audit page |
| Docs / ER / setup / report | **Delivered** | `docs/`, `database/documentation/` |
| Frontend build | **Verified** | typecheck + production build |

---

## 8. AI and ML honesty statement

- The kiosk does **not** call an LLM by default. It uses a deterministic Arabic/English matcher and a
  fixed tool layer (`KioskTools`). This is the path exercised by tests and the browser.
- The optional LLM adapter exposes only eight whitelisted menu/cart functions. There is deliberately
  **no SQL tool and no submit tool**. The order is created only by `POST /api/ai/kiosk/confirm` after
  the customer presses **Confirm**.
- No menu item, Arabic name or price is invented: every value is read from `menu_items`.
- The ML pipeline uses only `status = 'completed'` orders, splits chronologically, builds lag/rolling
  features with shifts, and compares against a per-product mean baseline. With 41 orders (about 15
  active days) the model is **demonstrative**, not production-accurate; the API returns a
  small-dataset warning rather than hiding this.
- No synthetic history, random analytics or fabricated payment records were added.

---

## 9. Remaining limitations

1. **LLM path untested** — no provider key. Interface and fallback exist; only the deterministic engine
   is verified.
2. **Speech-to-text capture untested** — browser and microphone-permission dependent. Support
   detection, language switching and the typed fallback were verified.
3. **WebSocket delivery untested automatically** — sockets are implemented and authorized
   (`/ws/orders`, role/ownership checks), and the UI degrades to query refetches, but no automated
   two-client socket test exists.
4. **Small ML dataset** — ~41 orders / ~15 active days; forecasts are directionally illustrative only.
5. **Inventory starts empty** — recipes and stock are intentionally not invented. The optional
   `database/seeds/demo_inventory.sql` adds 4 demo suppliers and 20 demo ingredients with clear
   “DEMO” labels; it is **not applied** to the delivered database. Recipes must be configured by a
   manager.
6. **No payment gateway** — cash/card-at-counter are recorded states, not online processing.
7. **In-process rate limiter** — suitable for one Uvicorn worker; a shared store (Redis) is required
   for multi-instance production.
8. **Single frontend chunk** — build warning only; no functional impact.
9. **Optional demo account behaviour** — the seeded `ahmed_ali` account gets a profile on first
   customer use; the historical 30 customers remain untouched.
10. **No git repository** — the workspace is delivered as files, not commits.

---

## 10. How to run and re-verify

```powershell
# 1. Database (already migrated; re-running is safe)
.venv\Scripts\python.exe database\migrate.py

# 2. Backend
$env:PYTHONPATH="backend"; $env:PYTHONIOENCODING="utf-8"
.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000

# 3. Frontend (second terminal)
$env:Path="C:\Program Files\nodejs;$env:Path"
cd frontend
npm install
npm run dev -- --host 127.0.0.1 --port 5173

# 4. Tests
$env:PYTHONPATH="backend"; $env:PYTHONIOENCODING="utf-8"
.venv\Scripts\python.exe -m pytest -q

# 5. Production build
cd frontend
npm run typecheck
npm run build
```

URLs: UI `http://127.0.0.1:5173`, API `http://127.0.0.1:8000/api`, Swagger
`http://127.0.0.1:8000/api/docs`, kiosk `http://127.0.0.1:5173/kiosk`.

Demo logins: `ahmed_ali/pass123` (customer), `chef/chef123` PIN `1234`, `cashier/cashier123`
PIN `5555`, `manager/admin123` PIN `9999`. Change all of them before any real deployment.

---

## 11. Sign-off

The delivered system preserves the original data, applies only additive migrations, enforces
authorization on the server, prices orders from MySQL, records auditable stock movements, requires
explicit kiosk confirmation, and produces real (if modest) forecasts from the available history.
The items in section 9 are the exact boundaries of what was verified; they should be read as the
project's honest limitations, not as hidden failures.
