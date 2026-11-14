-- ============================================================
-- RestoMate AI - Migration 005
-- Repair tables that could be missing if an earlier migration
-- aborted on a foreign-key/collation error before reaching them.
-- Idempotent: safe to run on a fresh install and on a patched DB.
-- ============================================================
USE bremer;
SET NAMES utf8mb4;

-- ------------------------------------------------------------
-- Audit trail (never store secrets / personal sensitive payloads)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS audit_logs (
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
CREATE TABLE IF NOT EXISTS user_sessions (
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
