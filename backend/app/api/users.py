"""Manager-only staff account management. Hashes and PINs are never returned."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.rate_limit import request_ip
from app.core.security import ManagerUser, hash_password, hash_pin
from app.database.session import get_db
from app.models import User
from app.schemas import PasswordReset, UserCreate, UserOut, UserUpdate
from app.services import audit

router = APIRouter(prefix="/users", tags=["Staff management"])


def _payload(user: User) -> UserOut:
    return UserOut(
        user_id=user.user_id,
        username=user.username,
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        is_active=bool(user.is_active),
        created_at=user.created_at,
        last_login_at=user.last_login_at,
        has_pin=bool(user.pin_hash),
    )


@router.get("", response_model=list[UserOut])
def list_users(user: ManagerUser, db: Session = Depends(get_db)):
    users = db.scalars(
        select(User).where(User.role != "system_ai").order_by(User.role, User.username)
    ).all()
    return [_payload(u) for u in users]


@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: UserCreate,
    request: Request,
    manager: ManagerUser,
    db: Session = Depends(get_db),
):
    if db.scalar(select(User).where(User.username == payload.username)):
        raise HTTPException(status.HTTP_409_CONFLICT, "Username already exists")
    if payload.email and db.scalar(select(User).where(User.email == payload.email)):
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already exists")
    staff = User(
        username=payload.username,
        email=str(payload.email) if payload.email else None,
        password_hash=hash_password(payload.password),
        password_algo="bcrypt",
        role=payload.role,
        full_name=payload.full_name,
        pin_hash=hash_pin(payload.pin) if payload.pin else None,
        is_active=True,
    )
    db.add(staff)
    db.flush()
    audit.log_audit(
        db,
        user_id=manager.user_id,
        action="user.create",
        entity_type="user",
        entity_id=str(staff.user_id),
        details={"username": staff.username, "role": staff.role},
        ip_address=request_ip(request),
    )
    db.commit()
    return _payload(staff)


@router.patch("/{user_id}", response_model=UserOut)
def update_user(
    user_id: int,
    payload: UserUpdate,
    request: Request,
    manager: ManagerUser,
    db: Session = Depends(get_db),
):
    target = db.get(User, user_id)
    if target is None or target.role == "system_ai":
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    if target.user_id == manager.user_id and payload.is_active is False:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "You cannot deactivate your own account")
    data = payload.model_dump(exclude_unset=True)
    pin = data.pop("pin", None)
    if "email" in data and data["email"]:
        data["email"] = str(data["email"])
        clash = db.scalar(select(User).where(User.email == data["email"], User.user_id != user_id))
        if clash:
            raise HTTPException(status.HTTP_409_CONFLICT, "Email is already in use")
    for key, value in data.items():
        setattr(target, key, value)
    if pin:
        target.pin_hash = hash_pin(pin)
        target.pin_code = None
    audit.log_audit(
        db,
        user_id=manager.user_id,
        action="user.update",
        entity_type="user",
        entity_id=str(user_id),
        details={"fields": list(data.keys()), "pin_changed": bool(pin)},
        ip_address=request_ip(request),
    )
    db.commit()
    return _payload(target)


@router.post("/{user_id}/reset-password")
def reset_password(
    user_id: int,
    payload: PasswordReset,
    request: Request,
    manager: ManagerUser,
    db: Session = Depends(get_db),
):
    target = db.get(User, user_id)
    if target is None or target.role == "system_ai":
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    target.password_hash = hash_password(payload.new_password)
    target.password_algo = "bcrypt"
    target.must_change_password = True
    audit.log_audit(
        db,
        user_id=manager.user_id,
        action="user.password_reset",
        entity_type="user",
        entity_id=str(user_id),
        ip_address=request_ip(request),
    )
    db.commit()
    return {"message": "Password reset. The user must set a new password at next login."}
