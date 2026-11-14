-- ============================================================
-- RestoMate AI - Migration 004
-- Conversational kiosk state (explicit confirmation tracking)
-- ============================================================
USE bremer;
SET NAMES utf8mb4;

ALTER TABLE kiosk_sessions
  ADD COLUMN state VARCHAR(30) NOT NULL DEFAULT 'idle' AFTER status;

CREATE INDEX idx_kiosk_state ON kiosk_sessions (state);
