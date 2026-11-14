"""Audit logging with defensive redaction of secrets."""
from __future__ import annotations

from typing import Any, Optional

from sqlalchemy.orm import Session

from app.models import AuditLog

SENSITIVE_KEYS = {"password", "new_password", "current_password", "pin", "pin_hash", "token", "secret", "api_key"}


def _redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: ("[redacted]" if any(secret in key.lower() for secret in SENSITIVE_KEYS) else _redact(val))
            for key, val in value.items()
        }
    if isinstance(value, list):
        return [_redact(item) for item in value]
    return value


def log_audit(
    db: Session,
    *,
    user_id: Optional[int],
    action: str,
    entity_type: str,
    entity_id: Optional[str] = None,
    details: Optional[dict] = None,
    ip_address: Optional[str] = None,
) -> None:
    db.add(
        AuditLog(
            user_id=user_id,
            action=action,
            entity_type=entity_type,
            entity_id=str(entity_id) if entity_id is not None else None,
            details=_redact(details) if details else None,
            ip_address=ip_address,
        )
    )
    db.flush()
