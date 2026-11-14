-- ============================================================
-- RestoMate AI - Migration 001
-- Enhance the six existing tables without destroying data.
-- Safe to apply once; tracked by database/migrate.py
-- ============================================================
USE bremer;
SET NAMES utf8mb4;

-- ------------------------------------------------------------
-- categories
-- ------------------------------------------------------------
ALTER TABLE categories
  ADD COLUMN description   TEXT NULL AFTER category_name_ar,
  ADD COLUMN image_url     VARCHAR(500) NULL AFTER description,
  ADD COLUMN is_active     TINYINT(1) NOT NULL DEFAULT 1 AFTER image_url,
  ADD COLUMN created_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP AFTER is_active,
  ADD COLUMN updated_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP AFTER created_at;

CREATE INDEX idx_categories_active ON categories (is_active);

-- ------------------------------------------------------------
-- menu_items
-- ------------------------------------------------------------
ALTER TABLE menu_items
  ADD COLUMN image_url         VARCHAR(500) NULL AFTER description_ar,
  ADD COLUMN preparation_time  INT NULL AFTER image_url,
  ADD COLUMN is_featured       TINYINT(1) NOT NULL DEFAULT 0 AFTER preparation_time,
  ADD COLUMN created_at        DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP AFTER is_featured,
  ADD COLUMN updated_at        DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP AFTER created_at;

CREATE INDEX idx_menu_items_category    ON menu_items (category_id);
CREATE INDEX idx_menu_items_available   ON menu_items (is_available);
CREATE INDEX idx_menu_items_featured    ON menu_items (is_featured);
CREATE INDEX idx_menu_items_name        ON menu_items (item_name);
CREATE INDEX idx_menu_items_name_ar     ON menu_items (item_name_ar);

ALTER TABLE menu_items
  ADD CONSTRAINT chk_menu_items_price CHECK (price >= 0),
  ADD CONSTRAINT chk_menu_items_prep  CHECK (preparation_time IS NULL OR preparation_time >= 0);

-- ------------------------------------------------------------
-- customers  (link optional user account; historical rows stay valid)
-- ------------------------------------------------------------
ALTER TABLE customers
  ADD COLUMN user_id     INT NULL AFTER customer_id,
  ADD COLUMN updated_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP AFTER created_at;

ALTER TABLE customers
  ADD CONSTRAINT uq_customers_user UNIQUE (user_id),
  ADD CONSTRAINT fk_customers_user FOREIGN KEY (user_id)
      REFERENCES users (user_id) ON DELETE SET NULL ON UPDATE CASCADE;

CREATE INDEX idx_customers_phone ON customers (phone);

-- ------------------------------------------------------------
-- orders
-- ------------------------------------------------------------
ALTER TABLE orders
  MODIFY COLUMN order_source ENUM('voice','pos','web_app','kiosk')
      NOT NULL DEFAULT 'voice',
  ADD COLUMN updated_at        DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP AFTER order_date,
  ADD COLUMN payment_status    ENUM('unpaid','pending','paid','refunded','partially_refunded')
      NOT NULL DEFAULT 'unpaid' AFTER status,
  ADD COLUMN payment_method    VARCHAR(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL AFTER payment_status,
  ADD COLUMN order_notes       TEXT NULL AFTER payment_method,
  ADD COLUMN idempotency_key   VARCHAR(64) NULL AFTER order_notes;

ALTER TABLE orders
  ADD CONSTRAINT uq_orders_idempotency UNIQUE (idempotency_key);

CREATE INDEX idx_orders_date        ON orders (order_date);
CREATE INDEX idx_orders_status      ON orders (status);
CREATE INDEX idx_orders_customer    ON orders (customer_id);
CREATE INDEX idx_orders_source      ON orders (order_source);
CREATE INDEX idx_orders_payment     ON orders (payment_status);

ALTER TABLE orders
  ADD CONSTRAINT chk_orders_total CHECK (total_amount >= 0);

-- ------------------------------------------------------------
-- order_items  (freeze product name + price at purchase time)
-- ------------------------------------------------------------
ALTER TABLE order_items
  ADD COLUMN item_name_snapshot VARCHAR(150) NULL AFTER item_id,
  ADD COLUMN created_at         DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP AFTER special_instructions;

UPDATE order_items oi
JOIN menu_items mi ON mi.item_id = oi.item_id
SET oi.item_name_snapshot = mi.item_name
WHERE oi.item_name_snapshot IS NULL;

ALTER TABLE order_items
  ADD CONSTRAINT chk_order_items_quantity CHECK (quantity > 0),
  ADD CONSTRAINT chk_order_items_price    CHECK (unit_price >= 0);

CREATE INDEX idx_order_items_item ON order_items (item_id);

-- ------------------------------------------------------------
-- users  (legacy SHA2 hashes keep working through the auth service)
-- ------------------------------------------------------------
ALTER TABLE users
  ADD COLUMN email                VARCHAR(255) NULL AFTER username,
  ADD COLUMN pin_hash             VARCHAR(255) NULL AFTER pin_code,
  ADD COLUMN password_algo        VARCHAR(30) NOT NULL DEFAULT 'legacy_sha256' AFTER password_hash,
  ADD COLUMN must_change_password TINYINT(1) NOT NULL DEFAULT 0 AFTER pin_hash,
  ADD COLUMN updated_at           DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP AFTER created_at,
  ADD COLUMN last_login_at        DATETIME NULL AFTER updated_at;

ALTER TABLE users
  ADD CONSTRAINT uq_users_email UNIQUE (email);

CREATE INDEX idx_users_role   ON users (role);
CREATE INDEX idx_users_active ON users (is_active);

-- ------------------------------------------------------------
-- Immutable history of every order status transition
-- ------------------------------------------------------------
CREATE TABLE order_status_history (
  history_id      BIGINT AUTO_INCREMENT PRIMARY KEY,
  order_id        INT NOT NULL,
  previous_status ENUM('pending','confirmed','preparing','completed','cancelled') NULL,
  new_status      ENUM('pending','confirmed','preparing','completed','cancelled') NOT NULL,
  changed_by      INT NULL,
  changed_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  notes           VARCHAR(500) NULL,
  CONSTRAINT fk_history_order FOREIGN KEY (order_id) REFERENCES orders (order_id) ON DELETE CASCADE,
  CONSTRAINT fk_history_user  FOREIGN KEY (changed_by) REFERENCES users (user_id) ON DELETE SET NULL,
  INDEX idx_history_order (order_id, changed_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Backfill one baseline row for each pre-existing order.
INSERT INTO order_status_history (order_id, previous_status, new_status, changed_at, notes)
SELECT o.order_id, NULL, o.status, o.order_date, 'Imported from pre-migration order state'
FROM orders o
WHERE NOT EXISTS (SELECT 1 FROM order_status_history h WHERE h.order_id = o.order_id);

-- ------------------------------------------------------------
-- Payment methods are configurable, not hardcoded in the frontend
-- ------------------------------------------------------------
CREATE TABLE payment_methods (
  code               VARCHAR(50) PRIMARY KEY,
  name               VARCHAR(100) NOT NULL,
  name_ar            VARCHAR(100) NOT NULL,
  is_active          TINYINT(1) NOT NULL DEFAULT 1,
  requires_reference TINYINT(1) NOT NULL DEFAULT 0,
  sort_order         INT NOT NULL DEFAULT 0,
  created_at         DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

INSERT INTO payment_methods (code, name, name_ar, is_active, requires_reference, sort_order) VALUES
  ('cash',           'Cash',            'نقدي',            1, 0, 1),
  ('pay_at_counter', 'Pay at counter',  'الدفع عند الكاشير', 1, 0, 2),
  ('card',           'Card (terminal)', 'بطاقة (ماكينة)',    1, 1, 3)
ON DUPLICATE KEY UPDATE name = VALUES(name), name_ar = VALUES(name_ar);

CREATE TABLE payments (
  payment_id            BIGINT AUTO_INCREMENT PRIMARY KEY,
  order_id              INT NOT NULL,
  payment_method        VARCHAR(50) NOT NULL,
  payment_status        ENUM('pending','paid','failed','refunded') NOT NULL DEFAULT 'pending',
  amount                DECIMAL(10,2) NOT NULL,
  transaction_reference VARCHAR(120) NULL,
  paid_at               DATETIME NULL,
  created_by            INT NULL,
  created_at            DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at            DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  CONSTRAINT fk_payments_order  FOREIGN KEY (order_id) REFERENCES orders (order_id) ON DELETE CASCADE,
  CONSTRAINT fk_payments_method FOREIGN KEY (payment_method) REFERENCES payment_methods (code),
  CONSTRAINT fk_payments_user   FOREIGN KEY (created_by) REFERENCES users (user_id) ON DELETE SET NULL,
  CONSTRAINT chk_payments_amount CHECK (amount >= 0),
  INDEX idx_payments_order (order_id),
  INDEX idx_payments_status (payment_status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

ALTER TABLE orders
  ADD CONSTRAINT fk_orders_payment_method
      FOREIGN KEY (payment_method) REFERENCES payment_methods (code) ON UPDATE CASCADE;

-- ------------------------------------------------------------
-- Audit trail (never store secrets / personal sensitive payloads)
-- ------------------------------------------------------------
CREATE TABLE audit_logs (
  audit_id    BIGINT AUTO_INCREMENT PRIMARY KEY,
  user_id     INT NULL,
  action      VARCHAR(80) NOT NULL,
  entity_type VARCHAR(60) NOT NULL,
  entity_id   VARCHAR(60) NULL,
  details     JSON NULL,
  ip_address  VARCHAR(64) NULL,
  created_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_audit_user FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE SET NULL,
  INDEX idx_audit_created (created_at),
  INDEX idx_audit_entity (entity_type, entity_id),
  INDEX idx_audit_user (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ------------------------------------------------------------
-- Server-side sessions (revocable logout) - stores no passwords
-- ------------------------------------------------------------
CREATE TABLE user_sessions (
  session_id CHAR(36) PRIMARY KEY,
  user_id    INT NOT NULL,
  jwt_id     CHAR(36) NOT NULL,
  issued_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  expires_at DATETIME NOT NULL,
  revoked_at DATETIME NULL,
  ip_address VARCHAR(64) NULL,
  user_agent VARCHAR(255) NULL,
  CONSTRAINT fk_sessions_user FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE,
  UNIQUE KEY uq_sessions_jwt (jwt_id),
  INDEX idx_sessions_user (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
