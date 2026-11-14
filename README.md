# RestoMate AI

**Unified restaurant operating system** — customer ordering, staff operations, manager business
intelligence, inventory & purchasing, a bilingual AI kiosk and demand forecasting on one FastAPI +
MySQL + React stack.

The project is built on the **existing `bremer` database** shipped with `DataBase.ipynb`. All 17
categories, 142 menu items, 30 historical customers, 41 seeded orders, 150 order items and 5 user
accounts are preserved. No destructive SQL from the notebook was executed.

---

## Portals

| Portal | Route | Who uses it |
| --- | --- | --- |
| Customer web app | `/menu`, `/orders`, `/profile` | Registered customers: browse the real menu, cart, checkout, track orders, reorder |
| Staff operations | `/staff/board` | Chef & cashier: live order board, status transitions, payment records |
| Manager dashboard | `/manager/*` | KPIs, sales analytics, menu/staff management, inventory, suppliers, purchasing, forecasting, audit log |
| AI kiosk | `/kiosk` | Anonymous self-service kiosk: Arabic/English chat, server-side cart, explicit confirmation |

## Feature highlights

- **Real menu only** — every name, Arabic name, synonym, description and price comes from MySQL. Nothing is hardcoded in the frontend.
- **Server-authoritative pricing** — the checkout total is recalculated on the backend from current menu rows; client totals are never trusted.
- **Role-based access control** — enforced in FastAPI dependencies (`customer`, `chef`, `cashier`, `manager`); `system_ai` can never log in.
- **Order lifecycle** — `pending → confirmed → preparing → completed`, cancellation allowed until preparation ends; every transition is written to `order_status_history`.
- **Inventory** — ingredients, recipes, stock, stock movements, suppliers, purchase orders and purchase receiving with idempotent per-order consumption and auditable reversal.
- **AI kiosk** — deterministic Arabic/English matcher by default (works without any API key), optional OpenAI-compatible LLM behind a whitelisted tool layer, explicit confirmation before submission.
- **Demand forecasting** — chronological 80/20 split, per-product mean baseline vs RandomForest/GradientBoosting, MAE/RMSE, persisted model + metadata, honest small-data warnings.
- **Bilingual UI** — English/Modern Standard Arabic/Egyptian Arabic content, RTL layout, EGP currency formatting.
- **Security** — bcrypt passwords, legacy SHA-256 verification with transparent rehash, revocable JWT sessions, login rate limiting, audit log, no secrets in responses.

## Technology

| Layer | Stack |
| --- | --- |
| Frontend | React 18, TypeScript 5.6, Vite 5, Tailwind CSS 3, React Router 6, TanStack Query 5, Recharts 2, lucide-react |
| Backend | Python 3.14, FastAPI, SQLAlchemy 2, Pydantic 2, PyJWT, bcrypt, PyMySQL |
| Database | MySQL 8.0 (`bremer`, utf8mb4) |
| ML | pandas, NumPy, scikit-learn, joblib |
| Tests | pytest + FastAPI TestClient (30 tests) |

---

## Quick start (Windows)

Prerequisites: MySQL 8 running, Python 3.11+, Node 18+.

```powershell
# 1. Configuration
Copy-Item .env.example .env
# edit .env with your MySQL password and a long SECRET_KEY

# 2. Python environment
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r backend\requirements.txt

# 3. Database migrations (backs up automatically, never drops data)
.venv\Scripts\python.exe database\migrate.py

# 4. Backend  ->  http://127.0.0.1:8000  (docs at /api/docs)
$env:PYTHONPATH="backend"; $env:PYTHONIOENCODING="utf-8"
.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload

# 5. Frontend ->  http://127.0.0.1:5173
cd frontend
npm install
npm run dev
```

Full instructions, database restore and troubleshooting: **[docs/SETUP.md](docs/SETUP.md)**.

## Seed accounts (local demo database)

| Username | Role | Password | PIN |
| --- | --- | --- | --- |
| `ahmed_ali` | customer | `pass123` | — |
| `chef` | chef | `chef123` | `1234` |
| `cashier` | cashier | `cashier123` | `5555` |
| `manager` | manager | `admin123` | `9999` |

`kiosk_ai` is a `system_ai` service account and is deliberately blocked from human login.
Change every demo credential before any real deployment.

## Documentation

| Document | Contents |
| --- | --- |
| [docs/SETUP.md](docs/SETUP.md) | Install, migrations, run commands, tests, production build, troubleshooting |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Layers, request flow, RBAC, order/inventory state machines, AI & ML design, security |
| [docs/DATABASE.md](docs/DATABASE.md) | All 25 tables, relationships, migration history, rollback, seed strategy |
| [docs/ER_DIAGRAM.md](docs/ER_DIAGRAM.md) | Mermaid ER diagrams per domain + relationship catalogue |
| [docs/API.md](docs/API.md) | Every endpoint, auth requirements, parameters, examples |
| [docs/ACCEPTANCE_REPORT.md](docs/ACCEPTANCE_REPORT.md) | Verified features, test/build/browser results, limitations |

Database artifacts: [`database/schema.sql`](database/schema.sql) (structure only, no `DROP`),
[`database/migrations/`](database/migrations/), [`database/seeds/demo_inventory.sql`](database/seeds/demo_inventory.sql)
(optional, clearly labelled demo stock — **not** applied to the live database),
[`database/maintenance/cleanup_verification_data.sql`](database/maintenance/cleanup_verification_data.sql).

## Tests

```powershell
$env:PYTHONIOENCODING="utf-8"
.venv\Scripts\python.exe -m pytest
```

Latest run: **30 passed** (dedicated `bremer_test` database, transaction rollback per test, read-only
live-data preservation checks).

```powershell
cd frontend
npm run typecheck
npm run build
```

Both pass; production bundle is written to `frontend/dist`.

## Design rules honoured

- Existing rows are never deleted or overwritten by migrations.
- No fake analytics, fake ML scores or fake payment integrations.
- AI never executes SQL and never invents menu items or prices.
- An order is submitted by the kiosk only after the customer presses **Confirm**.
- Unconfigured recipes never consume stock; managers configure them explicitly.
- Anything not verified end-to-end is listed as a limitation in the acceptance report.

## Known limitations (summary)

- Historical data is small (~41 orders), so forecasts are demonstrative, not production-grade.
- Inventory starts empty by design; a labelled demo seed is provided but not applied.
- Online card payment is a recorded method only — no payment gateway is integrated.
- The optional LLM path is implemented but unverified because no API key is available; the deterministic kiosk is the tested default.
- Browser speech output is implemented; speech input (Web Speech API) is implemented with language
  switching and typed fallback, but actual microphone capture was not verified in this environment
  because it requires device permission.
- WebSocket push is implemented for the staff board; automated tests cover HTTP flows, not socket delivery.
