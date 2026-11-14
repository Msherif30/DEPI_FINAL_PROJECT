# API reference

- **Base URL**: `http://127.0.0.1:8000/api`
- **Interactive docs**: `/api/docs` (Swagger UI), `/api/redoc`, schema at `/api/openapi.json`
- **Auth**: `Authorization: Bearer <access_token>` for every endpoint marked *auth*.
- **Content type**: `application/json` except image upload (`multipart/form-data`).
- **Errors**: FastAPI shape `{"detail": "message"}` with `400`, `401`, `403`, `404`, `409`, `422`, `429` or `503`.
- **Rate limits**: login/PIN and kiosk chat are limited per IP; `429` includes `Retry-After`.

Roles: `C` customer, `Ch` chef, `Ca` cashier, `M` manager, `P` public, `A` any authenticated role.

---

## 1. Authentication

| Method | Path | Access | Description |
| --- | --- | --- | --- |
| POST | `/auth/register` | P | Create a customer account and profile; returns token |
| POST | `/auth/login` | P | Username + password (legacy SHA-256 is upgraded to bcrypt on success) |
| POST | `/auth/pin` | P | Staff username + PIN |
| POST | `/auth/logout` | A | Revokes the current `user_sessions` row |
| GET | `/auth/me` | A | Current user + optional customer profile |
| PATCH | `/auth/me` | A | Update full name, email, phone, address |
| POST | `/auth/me/password` | A | Change password (current + new) |

`POST /auth/login`

```json
{ "username": "manager", "password": "admin123" }
```

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer",
  "expires_at": "2026-11-13T10:00:00",
  "user": {
    "user_id": 3,
    "username": "manager",
    "email": null,
    "full_name": "Restaurant Manager",
    "role": "manager",
    "is_active": true,
    "created_at": "2026-10-30T02:23:42",
    "last_login_at": "2026-11-13T02:47:00",
    "has_pin": true
  }
}
```

`system_ai` accounts receive `403`. Password hashes, PIN hashes and plaintext PINs are never returned.

---

## 2. Menu (public + manager)

| Method | Path | Access | Description |
| --- | --- | --- | --- |
| GET | `/menu` | P | Paginated menu; `q`, `category_id`, `featured`, `available_only`, `sort=name\|price_asc\|price_desc\|newest`, `page`, `page_size` |
| GET | `/menu/categories` | P | Categories with item counts and `include_inactive` |
| GET | `/menu/payment-methods` | P | Active payment methods |
| GET | `/menu/{item_id}` | P | One item |
| POST | `/menu` | M | Create item |
| PATCH | `/menu/{item_id}` | M | Update item (price, names, description, availability, image…) |
| DELETE | `/menu/{item_id}` | M | Retire item (soft: marks unavailable) |
| POST | `/menu/categories` | M | Create category |
| PATCH | `/menu/categories/{category_id}` | M | Update category |
| POST | `/menu/upload-image` | M | Multipart image upload; returns `/uploads/<file>` |

`GET /menu?q=burger&page=1&page_size=24`

```json
{
  "items": [
    {
      "item_id": 44,
      "category_id": 9,
      "category_name": "Sandwiches",
      "category_name_ar": "ساندويتشات",
      "item_name": "OG Burger",
      "item_name_ar": "أو جي برجر",
      "synonyms": "burger,برجر",
      "price": 270.0,
      "is_available": true,
      "description": "…",
      "description_ar": "…",
      "image_url": null,
      "preparation_time": 15,
      "is_featured": true,
      "created_at": "2026-10-11T18:22:00"
    }
  ],
  "total": 142,
  "page": 1,
  "page_size": 24,
  "pages": 6
}
```

Search matches English name, Arabic name and synonyms. The frontend never filters a hardcoded list.

---

## 3. Customer orders

| Method | Path | Access | Description |
| --- | --- | --- | --- |
| POST | `/orders` | A (customer flow) | Create an order; server re-prices every line |
| GET | `/orders?page=&page_size=` | A | Customer's own orders; staff receive their permitted list |
| GET | `/orders/{order_id}` | A | Order detail; customers can only read their own (`404` otherwise) |
| PATCH | `/orders/{order_id}/status` | Staff | Transition status (role + graph validated) |
| PATCH | `/orders/{order_id}/payment` | Cashier/Manager | Update payment record/status |

`POST /orders`

```json
{
  "items": [
    { "item_id": 44, "quantity": 2, "special_instructions": "No pickles" },
    { "item_id": 91, "quantity": 1 }
  ],
  "payment_method": "pay_at_counter",
  "order_notes": "Table 4",
  "idempotency_key": "b0f1c2d3-…"
}
```

Response `201`:

```json
{
  "order": {
    "order_id": 45,
    "customer_id": 31,
    "customer_name": "Ahmed Ali",
    "customer_phone": null,
    "order_date": "2026-11-13T02:39:43",
    "updated_at": "2026-11-13T02:39:43",
    "status": "pending",
    "payment_status": "pending",
    "payment_method": "pay_at_counter",
    "order_notes": "Table 4",
    "order_source": "web_app",
    "total_amount": 635.0,
    "items": [
      {
        "order_item_id": 151,
        "item_id": 44,
        "item_name_snapshot": "OG Burger",
        "item_name_ar": "أو جي برجر",
        "quantity": 2,
        "unit_price": 270.0,
        "line_total": 540.0,
        "special_instructions": "No pickles"
      }
    ],
    "payments": [],
    "status_history": []
  },
  "message": "Order #45 placed successfully"
}
```

Rules: items must exist, be available, quantity `1..99`; total is computed with `Decimal`; an invalid or
unavailable item returns `400/409`; a repeated `Idempotency-Key` returns the original order instead of a
duplicate.

`PATCH /orders/{id}/status`

```json
{ "status": "confirmed", "notes": "Verified by cashier" }
```

| Actor | Allowed targets |
| --- | --- |
| cashier | `confirmed`, `cancelled` |
| chef | `preparing`, `completed` |
| manager | any valid target in the state graph |

Graph: `pending → confirmed/cancelled`, `confirmed → preparing/cancelled`,
`preparing → completed/cancelled`, `completed/cancelled` are terminal. Unauthorized role → `403`;
invalid move for an authorized role → `409`.

`PATCH /orders/{id}/payment`

```json
{ "payment_status": "paid", "transaction_reference": "CASH-1042" }
```

---

## 4. Staff board

| Method | Path | Access | Description |
| --- | --- | --- | --- |
| GET | `/staff/orders?status=&source=&date_from=&date_to=&page=&page_size=` | Ch/Ca/M | All orders with items, payments, history |
| GET | `/staff/orders/summary` | Ch/Ca/M | Counts per status for the board columns |

WebSockets (not under `/api`):

| URL | Access | Description |
| --- | --- | --- |
| `ws://host/ws/orders?token=<jwt>` | Ch/Ca/M | New/updated order events for the board |
| `ws://host/ws/orders/{order_id}?token=<jwt>` | owner or staff | Updates for one order |

Invalid/unauthorized sockets close with code `1008`.

---

## 5. Manager analytics

All endpoints accept optional `start=YYYY-MM-DD` and `end=YYYY-MM-DD`; `sales` also accepts
`granularity=day|week|month`.

| Method | Path | Description |
| --- | --- | --- |
| GET | `/analytics/overview` | Revenue (completed only), paid revenue, order counts, AOV, best seller, definitions |
| GET | `/analytics/sales` | Time series of completed revenue and order counts |
| GET | `/analytics/products` | Product quantity/revenue ranking (`limit`) |
| GET | `/analytics/categories` | Revenue and units by category |
| GET | `/analytics/peak-hours` | Orders/revenue by hour |
| GET | `/analytics/sources` | Orders by source (`web_app`, `kiosk`, `voice`, `pos`) |
| GET | `/analytics/customers` | Customer frequency and spend (`limit`) |
| GET | `/analytics/insights` | Deterministic textual insights + period comparison |
| GET | `/analytics/audit-logs?action=&limit=` | Audit entries joined with actor names |

Business definitions (also returned by `/overview`):

- **Revenue** = sum of `total_amount` for `status = 'completed'` only.
- **Paid revenue** = sum of `payments.amount` where `payment_status = 'paid'` — reported separately, never mixed into revenue.
- **Average order value** = completed revenue ÷ completed order count.
- Cancelled and pending orders are excluded from revenue and AOV.

---

## 6. Staff management (manager only)

| Method | Path | Description |
| --- | --- | --- |
| GET | `/users` | List accounts (no hashes/PINs, `has_pin` only) |
| POST | `/users` | Create staff/customer account; optional PIN |
| PATCH | `/users/{user_id}` | Update name, email, role, active flag, PIN |
| POST | `/users/{user_id}/reset-password` | Set a new password securely |

`POST /users` body: `{username, email?, password, full_name, role, pin?}`. Role must be
`customer`, `chef`, `cashier` or `manager`; `system_ai` cannot be assigned.

---

## 7. Inventory

Manager only.

| Method | Path | Description |
| --- | --- | --- |
| GET | `/inventory?include_inactive=` | Ingredients with on-hand quantity, status and recipe flag |
| POST | `/inventory/ingredients` | Create ingredient (optional `initial_stock`) |
| PATCH | `/inventory/ingredients/{ingredient_id}` | Update thresholds/units/supplier |
| GET | `/inventory/low-stock` | Ingredients at/below minimum or safety stock |
| GET | `/inventory/movements?ingredient_id=&movement_type=&page=&page_size=` | Stock ledger |
| POST | `/inventory/stock-movements` | Purchase/adjustment/waste/return increase or decrease |
| GET | `/inventory/recipes/{item_id}` | Recipe lines for a menu item |
| PUT | `/inventory/recipes/{item_id}` | Replace the whole recipe |
| GET | `/inventory/recommendations?horizon_days=7` | Purchase suggestions with reason |

`POST /inventory/stock-movements`

```json
{
  "ingredient_id": 3,
  "movement_type": "purchase",
  "quantity": 25,
  "direction": "increase",
  "reason": "Delivery from supplier"
}
```

Quantity may not go below zero (`409`). Every change writes a `stock_movements` row with the resulting
balance.

`PUT /inventory/recipes/{item_id}` — body is a JSON array of lines

```json
[
  { "ingredient_id": 1, "quantity": 0.15, "unit_of_measure": "kg", "notes": "Per burger" }
]
```

Recipes are manager-configured; the API never invents ingredient quantities.

---

## 8. Suppliers and purchasing

| Method | Path | Description |
| --- | --- | --- |
| GET | `/suppliers` | List suppliers |
| POST | `/suppliers` | Create supplier |
| PATCH | `/suppliers/{supplier_id}` | Update supplier |
| GET | `/purchase-orders?status=&page=&page_size=` | Purchase order history |
| POST | `/purchase-orders` | Create draft or submitted order (`submit: true`) |
| PATCH | `/purchase-orders/{purchase_id}` | Receive quantities (whole or partial) |

`POST /purchase-orders`

```json
{
  "supplier_id": 1,
  "expected_date": "2026-11-20",
  "notes": "Weekly restock",
  "submit": true,
  "items": [
    { "ingredient_id": 1, "quantity_ordered": 40, "unit_cost": 220.5 }
  ]
}
```

`PATCH /purchase-orders/{id}`

```json
{ "items": [ { "purchase_order_item_id": 1, "quantity": 40 } ] }
```

Receiving writes `purchase` stock movements and flips the order to `partially_received`/`received`.
The database enum also models `draft`/`ordered`/`cancelled`; the UI exposes draft vs ordered creation and
receiving, not a cancellation action.

---

## 9. Forecasting

Manager only.

| Method | Path | Description |
| --- | --- | --- |
| POST | `/forecast/train` | Train baseline + RandomForest/GradientBoosting, persist best model |
| GET | `/forecast/predictions?horizon_days=1..30&item_id=` | Predictions for the horizon (all or one item) |
| GET | `/forecast/performance` | MAE/RMSE, baseline metrics, model name, warnings |
| GET | `/forecast/history` | Daily completed demand history |

```json
{
  "trained": true,
  "model_name": "RandomForestRegressor",
  "trained_at": "2026-11-12T20:17:00",
  "metrics": { "mae": 0.1485, "rmse": 0.396, "baseline_mae": 0.1846, "baseline_rmse": 0.396 },
  "warnings": [
    "Small dataset: 136 completed order lines across 14 days. Forecast accuracy is limited…"
  ],
  "predictions": [
    {
      "item_id": 44,
      "item_name": "OG Burger",
      "item_name_ar": "أو جي برجر",
      "forecast_date": "2026-11-13",
      "predicted_quantity": 0.7
    }
  ]
}
```

If no model exists, the response is `trained: false` with a message instead of fake predictions.

---

## 10. AI kiosk (anonymous)

| Method | Path | Access | Description |
| --- | --- | --- | --- |
| POST | `/ai/kiosk/session` | P | Create session `{language: "ar"\|"en"}` |
| GET | `/ai/kiosk/session/{session_id}` | P | Session, cart and subtotal |
| POST | `/ai/kiosk/chat` | P | `{session_id, message, language}` → reply, cart, suggestions |
| POST | `/ai/kiosk/confirm` | P | Create the order after explicit confirmation |
| POST | `/ai/kiosk/reset` | P | Clear cart and start a new conversation |
| GET | `/ai/kiosk/suggestions` | P | Featured/popular menu suggestions |
| POST | `/ai/analyst` | M | Manager analytics Q&A over aggregated metrics |

Conversation example:

```json
POST /ai/kiosk/chat
{ "session_id": "434d3ce0-…", "message": "عايز اتنين برجر دبل وبيبسي", "language": "ar" }
```

```json
{
  "reply": "تمت الإضافة:\n• 2 × دبل برجر\n…\nالإجمالي: 635.00 EGP\nتحب أأكد الطلب؟",
  "state": "awaiting_confirmation",
  "cart": [ { "item_id": 44, "item_name": "OG Burger", "quantity": 2, "line_total": 540.0 } ],
  "subtotal": 635.0,
  "requires_confirmation": true,
  "suggestions": []
}
```

`POST /ai/kiosk/confirm` body `{session_id, customer_name?, customer_phone?, payment_method}`.
It fails with `400` for an empty cart or `409` if an item became unavailable. Chat alone can never
submit an order. There is no LLM tool for submission and no SQL endpoint.

---

## 11. System

| Method | Path | Access | Description |
| --- | --- | --- | --- |
| GET | `/health` | P | App + DB status, environment, whether an LLM key is configured |
| GET | `/health/db` | P | Row counts for core tables |

Static files are served from `/uploads/<filename>`. In production the built SPA is served from `/`
with fallback to `index.html`.

---

## 12. Status codes used

| Code | Meaning in this API |
| --- | --- |
| 200 / 201 | Success / created |
| 400 | Bad request, empty cart, invalid business input |
| 401 | Missing/expired/revoked token |
| 403 | Authenticated but wrong role, inactive user, `system_ai` login |
| 404 | Unknown item/order or an order belonging to another customer |
| 409 | Invalid transition, insufficient stock, duplicate name, unavailable item |
| 422 | Pydantic validation failure |
| 429 | Rate limited |
| 503 | Database unavailable (health endpoint) |
