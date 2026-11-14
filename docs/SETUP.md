# Setup and runbook

## 1. Prerequisites

| Requirement | Verified version | Notes |
| --- | --- | --- |
| MySQL Server | 8.0.46 | Service `MySQL80` on Windows; database `bremer` |
| Python | 3.14.6 (3.11+ works) | Virtual environment recommended |
| Node.js / npm | 26.13.1 / 11.20.0 (Node 18+ works) | Frontend build |
| Git | optional | Workspace is not a git repository |

MySQL client and `mysqldump` are expected at:

```
C:\Program Files\MySQL\MySQL Server 8.0\bin\
```

Add that folder to `PATH` or call the executables with their full path.

---

## 2. Configuration

```powershell
Copy-Item .env.example .env
```

Edit `.env`:

```dotenv
DB_HOST=localhost
DB_PORT=3306
DB_USER=root
DB_PASSWORD=your_mysql_password
DB_NAME=bremer

# python -c "import secrets;print(secrets.token_urlsafe(48))"
SECRET_KEY=replace_with_a_long_random_value
ACCESS_TOKEN_EXPIRE_MINUTES=480
KIOSK_SESSION_MINUTES=45

CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173,http://localhost:4173
RATE_LIMIT_LOGIN_PER_MINUTE=10

# Optional. Leave empty to use the deterministic kiosk engine.
LLM_API_KEY=
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4o-mini
```

- `.env` is git-ignored; never commit real credentials.
- If `SECRET_KEY` is missing or still starts with `change_me`, development falls back to a deterministic
  local key. **Set a real key in production.**
- `UPLOAD_DIR` and `ML_ARTIFACT_DIR` default to `backend/uploads` and `backend/ml_artifacts`.
- The frontend never receives `LLM_API_KEY`; only the backend reads it.

---

## 3. Back up the live database (do this first)

```powershell
$dump = "C:\Program Files\MySQL\MySQL Server 8.0\bin\mysqldump.exe"
$ts = Get-Date -Format "yyyyMMdd_HHmmss"
& $dump -uroot -p --databases bremer --single-transaction --routines --triggers `
  --default-character-set=utf8mb4 --result-file="database\backups\bremer_manual_$ts.sql"
```

Existing backups from this project are in `database/backups/` (git-ignored).

Restore if ever needed:

```powershell
$mysql = "C:\Program Files\MySQL\MySQL Server 8.0\bin\mysql.exe"
& $mysql -uroot -p -e "DROP DATABASE IF EXISTS bremer; CREATE DATABASE bremer CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
& $mysql -uroot -p bremer < database\backups\bremer_pre_cleanup_20261113_025634.sql
```

The restore above is the **only** destructive operation in this project; it is never run by the app or
by the migration runner.

---

## 4. Python environment

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
```

Installed groups: FastAPI/Uvicorn, SQLAlchemy/PyMySQL, Pydantic, PyJWT, bcrypt, pandas/NumPy/scikit-learn/joblib,
httpx (LLM calls), pytest, Alembic (available; the project uses numbered SQL migrations).

---

## 5. Apply database migrations

```powershell
.venv\Scripts\python.exe database\migrate.py
```

What it does:

1. Reads `.env`.
2. Creates a timestamped `mysqldump` backup in `database/backups/` before the first change.
3. Applies only migrations not listed in `schema_migrations`.
4. Converts legacy plaintext PINs to bcrypt and clears `pin_code`.

Expected state after a fresh install of this project: versions `001`–`005` recorded. Re-running is safe.

Optional demo inventory (**not** applied automatically, clearly labelled demo data):

```powershell
$mysql = "C:\Program Files\MySQL\MySQL Server 8.0\bin\mysql.exe"
# Review the file first. It inserts demo suppliers/ingredients/stock only.
& $mysql -uroot -p bremer < database\seeds\demo_inventory.sql
```

Recipes are intentionally not seeded: the source notebook contains no recipe quantities. Configure them
in **Manager → Inventory → Recipes** before expecting automatic consumption.

---

## 6. Run the backend

```powershell
$env:PYTHONPATH="backend"
$env:PYTHONIOENCODING="utf-8"
.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

- API: `http://127.0.0.1:8000/api`
- Swagger: `http://127.0.0.1:8000/api/docs`
- Health: `http://127.0.0.1:8000/api/health`
- Database counts: `http://127.0.0.1:8000/api/health/db`

Startup logs the database name and creates the upload directory. If MySQL is down the API still starts
but `/api/health` returns `503`; fix `.env`/MySQL before using the app.

---

## 7. Run the frontend

```powershell
cd frontend
npm install
npm run dev
```

Open `http://127.0.0.1:5173`.

On Windows, if `node`/`npm` are not on `PATH`:

```powershell
$env:Path = "C:\Program Files\nodejs;$env:Path"
npm.cmd run dev -- --host 127.0.0.1 --port 5173
```

Vite proxies `/api`, `/uploads` and `/ws` to `http://127.0.0.1:8000`, so no CORS changes are needed for
local development.

### Demo logins

| Portal | Username | Password | PIN |
| --- | --- | --- | --- |
| Customer | `ahmed_ali` | `pass123` | — |
| Chef | `chef` | `chef123` | `1234` |
| Cashier | `cashier` | `cashier123` | `5555` |
| Manager | `manager` | `admin123` | `9999` |

The login screen has **Customer** and **Staff** modes; staff can switch to **Use PIN**. The kiosk is
public: `http://127.0.0.1:5173/kiosk`.

Production: change every demo password/PIN and remove unused accounts.

---

## 8. Build for production

```powershell
cd frontend
npm run typecheck
npm run build
```

`frontend/dist` is created. FastAPI detects it at startup and serves the SPA with `index.html` fallback,
so a single Uvicorn process can host the API and the UI:

```powershell
$env:PYTHONPATH="backend"
$env:ENVIRONMENT="production"
.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Put TLS and compression in front of Uvicorn (Nginx/Caddy). Restrict `CORS_ORIGINS` to the real domain,
set `SECRET_KEY`, use a dedicated MySQL user, and keep `.env` out of version control.

---

## 9. Tests

```powershell
$env:PYTHONIOENCODING="utf-8"
.venv\Scripts\python.exe -m pytest
```

Configuration in `pytest.ini` (`testpaths = backend/tests`, `pythonpath = backend`).

- Tests create a dedicated **`bremer_test`** database from SQLAlchemy metadata. `conftest.py` refuses to
  run unless the name ends with `_test`.
- Each test runs in an outer transaction that is rolled back.
- `test_preserved_data.py` performs read-only checks against the live `bremer` database and skips if it
  is unreachable.
- `ML_ARTIFACT_DIR` and `UPLOAD_DIR` point to temporary folders, so tests never overwrite live artifacts.

Latest result: **30 passed, 5 warnings** (~75 s). Warnings come from scikit-learn about feature names and
parallelism; they do not affect results.

Frontend checks:

```powershell
cd frontend
npm run typecheck
npm run build
```

---

## 10. Useful maintenance commands

```sql
-- verify preserved seed counts
SELECT 'categories', COUNT(*) FROM categories
UNION ALL SELECT 'menu_items', COUNT(*) FROM menu_items
UNION ALL SELECT 'customers', COUNT(*) FROM customers
UNION ALL SELECT 'orders', COUNT(*) FROM orders
UNION ALL SELECT 'order_items', COUNT(*) FROM order_items
UNION ALL SELECT 'users', COUNT(*) FROM users;

-- applied migrations
SELECT version, applied_at FROM schema_migrations ORDER BY version;
```

Remove only the acceptance-test artifacts (orders 42-48 and related rows) if they are present again:

```powershell
$mysql = "C:\Program Files\MySQL\MySQL Server 8.0\bin\mysql.exe"
& $mysql -uroot -p bremer < database\maintenance\cleanup_verification_data.sql
```

Re-train the forecast after importing more history:

```powershell
# Manager UI -> Forecasting -> Retrain model
# or:
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/forecast/train `
  -Headers @{ Authorization = "Bearer $token" }
```

Artifacts: `backend/ml_artifacts/demand_model.joblib` + `forecast_meta.json`.

---

## 11. Troubleshooting

| Symptom | Cause / fix |
| --- | --- |
| `Can't connect to MySQL server` | Start the `MySQL80` service; check host/port in `.env` |
| `Access denied for user` | Wrong `DB_USER`/`DB_PASSWORD`; quote passwords containing `#` or spaces |
| Login returns 401 for staff | Use the Staff tab and the correct password/PIN; `system_ai` is blocked by design |
| `403` on staff/manager pages | Correct role required; frontend guards are not the source of truth |
| `409` when confirming an order | One or more items became unavailable, or insufficient stock blocked preparation |
| Kiosk says it cannot reach the kitchen | Backend is down or `/api` proxy target is wrong |
| Kiosk voice button missing | Browser does not expose the Web Speech API; typed input still works |
| Voice permission blocked | Allow microphone for `127.0.0.1:5173` in browser settings |
| Forecast page shows a warning | Expected: ~41 historical orders is a small dataset |
| `npm` not recognized | Prepend `C:\Program Files\nodejs` to `PATH` or use `npm.cmd` |
| Port already in use | Stop the old Uvicorn/Vite process or choose another port |
| Uploaded image 404 | Ensure the backend is running; `/uploads` is served by FastAPI |
| Tests cannot create `bremer_test` | Grant CREATE/DROP on test databases to the MySQL user |

---

## 12. Environment variables reference

| Variable | Default | Purpose |
| --- | --- | --- |
| `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `DB_NAME` | localhost, 3306, root, "", bremer | MySQL connection |
| `DATABASE_URL` | — | Optional full SQLAlchemy URL override |
| `SECRET_KEY` | dev fallback | JWT signing key |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | 480 | Token/session lifetime |
| `KIOSK_SESSION_MINUTES` | 45 | Kiosk session expiry |
| `CORS_ORIGINS` | local origins | Comma-separated allow-list |
| `RATE_LIMIT_LOGIN_PER_MINUTE` | 10 | Login/PIN attempts per IP per minute |
| `LLM_API_KEY`, `LLM_BASE_URL`, `LLM_MODEL` | empty, OpenAI, gpt-4o-mini | Optional kiosk LLM |
| `UPLOAD_DIR` | `backend/uploads` | Menu images |
| `ML_ARTIFACT_DIR` | `backend/ml_artifacts` | Trained model + metadata |
| `LOG_LEVEL` | INFO | Uvicorn/app logging |
| `ENVIRONMENT` | development | Enables HSTS when `production` |
