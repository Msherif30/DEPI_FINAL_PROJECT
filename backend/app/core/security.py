"""Password hashing, JWT issuing/verification and authentication dependencies."""
from __future__ import annotations

import hashlib
import hmac
import uuid
from datetime import datetime, timedelta, timezone
from typing import Annotated, Optional

import bcrypt
import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.database.session import get_db
from app.models import User, UserSession

ALGORITHM = "HS256"
LEGACY_SALT = "rm_salt_secure_"
STAFF_ROLES = ("chef", "cashier", "manager")


# --------------------------------------------------------------------------- #
# Password / PIN hashing
# --------------------------------------------------------------------------- #
def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode()


def _legacy_hash(password: str) -> str:
    return hashlib.sha256((LEGACY_SALT + password).encode("utf-8")).hexdigest()


def verify_password(password: str, stored_hash: str, algorithm: str = "bcrypt") -> bool:
    """Verify current bcrypt hashes and the notebook's SHA2 legacy hashes."""
    if not stored_hash:
        return False
    if algorithm == "legacy_sha256" or (len(stored_hash) == 64 and ":" not in stored_hash):
        return hmac.compare_digest(_legacy_hash(password), stored_hash)
    try:
        return bcrypt.checkpw(password.encode("utf-8"), stored_hash.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def needs_rehash(stored_hash: str, algorithm: str) -> bool:
    return algorithm != "bcrypt" or not stored_hash.startswith("$2")


def hash_pin(pin: str) -> str:
    return bcrypt.hashpw(("pin:" + pin).encode("utf-8"), bcrypt.gensalt()).decode()


def verify_pin(pin: str, stored_hash: str) -> bool:
    if not stored_hash:
        return False
    try:
        return bcrypt.checkpw(("pin:" + pin).encode("utf-8"), stored_hash.encode("utf-8"))
    except (ValueError, TypeError):
        return False


# --------------------------------------------------------------------------- #
# JWT
# --------------------------------------------------------------------------- #
def create_access_token(user: User, session_id: str | None = None) -> tuple[str, str, datetime]:
    jti = str(uuid.uuid4())
    expires = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {
        "sub": str(user.user_id),
        "role": user.role,
        "jti": jti,
        "sid": session_id or str(uuid.uuid4()),
        "iat": datetime.now(timezone.utc),
        "exp": expires,
        "typ": "access",
    }
    token = jwt.encode(payload, settings.effective_secret, algorithm=ALGORITHM)
    return token, jti, expires.replace(tzinfo=None)


def decode_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, settings.effective_secret, algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Session expired") from exc
    except jwt.PyJWTError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid session token") from exc
    if payload.get("typ") != "access":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token type")
    return payload


# --------------------------------------------------------------------------- #
# Dependencies
# --------------------------------------------------------------------------- #
_bearer = HTTPBearer(auto_error=False)


def get_current_user(
    creds: Annotated[Optional[HTTPAuthorizationCredentials], Depends(_bearer)],
    db: Annotated[Session, Depends(get_db)],
) -> User:
    unauthorized = HTTPException(
        status.HTTP_401_UNAUTHORIZED,
        "Authentication required",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if creds is None:
        raise unauthorized
    payload = decode_token(creds.credentials)
    try:
        user_id = int(payload["sub"])
        jti = str(payload["jti"])
    except (KeyError, ValueError) as exc:
        raise unauthorized from exc

    session = db.scalar(select(UserSession).where(UserSession.jwt_id == jti))
    if session is None or session.revoked_at is not None or session.expires_at < datetime.now(timezone.utc).replace(tzinfo=None):
        raise unauthorized

    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise unauthorized
    if user.role == "system_ai":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "The system_ai account cannot log in")
    return user


def get_optional_user(
    creds: Annotated[Optional[HTTPAuthorizationCredentials], Depends(_bearer)],
    db: Annotated[Session, Depends(get_db)],
) -> Optional[User]:
    if creds is None:
        return None
    try:
        return get_current_user(creds, db)
    except HTTPException:
        return None


CurrentUser = Annotated[User, Depends(get_current_user)]
OptionalUser = Annotated[Optional[User], Depends(get_optional_user)]


def require_roles(*roles: str):
    def dependency(user: CurrentUser) -> User:
        if user.role not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "You do not have permission for this action")
        return user

    return dependency


require_staff = require_roles("chef", "cashier", "manager")
require_manager = require_roles("manager")
require_customer = require_roles("customer")
require_kitchen = require_roles("chef", "manager")
require_cashier = require_roles("cashier", "manager")
StaffUser = Annotated[User, Depends(require_staff)]
ManagerUser = Annotated[User, Depends(require_manager)]
CustomerUser = Annotated[User, Depends(require_customer)]


def client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"
