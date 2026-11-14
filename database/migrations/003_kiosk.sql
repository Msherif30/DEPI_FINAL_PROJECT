-- ============================================================
-- RestoMate AI - Migration 003
-- Anonymous kiosk sessions with server-side carts.
-- The kiosk never receives direct SQL or table access.
-- ============================================================
USE bremer;
SET NAMES utf8mb4;

CREATE TABLE kiosk_sessions (
  session_id    CHAR(36) PRIMARY KEY,
  status        ENUM('active','submitted','expired','abandoned') NOT NULL DEFAULT 'active',
  language      ENUM('ar','en') NOT NULL DEFAULT 'ar',
  customer_name VARCHAR(120) NULL,
  customer_phone VARCHAR(30) NULL,
  table_number  INT NULL,
  started_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  expires_at    DATETIME NOT NULL,
  ended_at      DATETIME NULL,
  order_id      INT NULL,
  last_activity DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  CONSTRAINT fk_kiosk_order FOREIGN KEY (order_id) REFERENCES orders (order_id) ON DELETE SET NULL,
  INDEX idx_kiosk_status (status),
  INDEX idx_kiosk_expires (expires_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE kiosk_cart_items (
  cart_item_id   BIGINT AUTO_INCREMENT PRIMARY KEY,
  session_id     CHAR(36) NOT NULL,
  item_id        INT NOT NULL,
  quantity       INT NOT NULL,
  special_instructions VARCHAR(300) NULL,
  created_at     DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at     DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  CONSTRAINT fk_kiosk_cart_session FOREIGN KEY (session_id)
      REFERENCES kiosk_sessions (session_id) ON DELETE CASCADE,
  CONSTRAINT fk_kiosk_cart_item FOREIGN KEY (item_id)
      REFERENCES menu_items (item_id),
  CONSTRAINT chk_kiosk_cart_qty CHECK (quantity > 0),
  UNIQUE KEY uq_kiosk_cart (session_id, item_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE kiosk_messages (
  message_id BIGINT AUTO_INCREMENT PRIMARY KEY,
  session_id CHAR(36) NOT NULL,
  role       ENUM('user','assistant','system') NOT NULL,
  content    TEXT NOT NULL,
  language   ENUM('ar','en') NOT NULL DEFAULT 'ar',
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_kiosk_msg_session FOREIGN KEY (session_id)
      REFERENCES kiosk_sessions (session_id) ON DELETE CASCADE,
  INDEX idx_kiosk_msg_session (session_id, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
