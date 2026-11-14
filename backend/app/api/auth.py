"""Authentication and profile endpoints."""
from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.rate_limit import login_limiter, request_ip
from app.core.security import (
    CurrentUser,
    create_access_token,
    decode_token,
    hash_password,
    needs_rehash,
    verify_password,
    verify_pin,
)
from app.database.session import get_db
from app.models import Customer, User, UserSession
from app.schemas import (
    CustomerProfileOut,
    LoginRequest,
    MeOut,
    PasswordChange,
    PinLoginRequest,
    ProfileUpdate,
    RegisterRequest,
    TokenResponse,
    UserOut,
)
from app.services import audit
from app.services.orders import ensure_customer_profile

router = APIRouter(prefix="/auth", tags=["Authentication"])


def user_payload(user: User) -> dict:
    return {
        "user_id": user.user_id,
        "username": user.username,
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role,
        "is_active": user.is_active,
        "created_at": user.created_at,
        "last_login_at": user.last_login_at,
        "has_pin": bool(user.pin_hash),
    }


def _issue(db: Session, user: User, request: Request) -> TokenResponse:
    session_id = str(uuid.uuid4())
    token, jti, expires = create_access_token(user, session_id)
    db.add(
        UserSession(
            session_id=session_id,
            user_id=user.user_id,
            jwt_id=jti,
            expires_at=expires,
            ip_address=request_ip(request),
            user_agent=(request.headers.get("user-agent") or "")[:255],
        )
    )
    user.last_login_at = datetime.utcnow()
    db.commit()
    return TokenResponse(
        access_token=token,
        expires_at=expires,
        user=UserOut(**user_payload(user)),
    )


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, request: Request, db: Session = Depends(get_db)):
    login_limiter.check(f"register:{request_ip(request)}")
    if db.scalar(select(User).where(User.username == payload.username)):
        raise HTTPException(status.HTTP_409_CONFLICT, "Username is already taken")
    if payload.email and db.scalar(select(User).where(User.email == payload.email)):
        raise HTTPException(status.HTTP_409_CONFLICT, "Email is already registered")
    if payload.phone and db.scalar(select(Customer).where(Customer.phone == payload.phone)):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "This phone number already belongs to a customer profile. "
            "Please contact the restaurant to link your account securely.",
        )

    user = User(
        username=payload.username,
        email=str(payload.email) if payload.email else None,
        password_hash=hash_password(payload.password),
        password_algo="bcrypt",
        role="customer",
        full_name=payload.full_name,
        is_active=True,
    )
    db.add(user)
    db.flush()
    customer = Customer(
        user_id=user.user_id,
        customer_name=payload.full_name,
        phone=payload.phone,
        address=payload.address,
    )
    db.add(customer)
    audit.log_audit(
        db,
        user_id=user.user_id,
        action="auth.register",
        entity_type="user",
        entity_id=str(user.user_id),
        ip_address=request_ip(request),
    )
    db.commit()
    db.refresh(user)
    return _issue(db, user, request)


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)):
    key = f"login:{request_ip(request)}:{payload.username.lower()}"
    login_limiter.check(key)
    user = db.scalar(
        select(User).where(
            or_(User.username == payload.username, User.email == payload.username)
        )
    )
    if user is None or not verify_password(payload.password, user.password_hash, user.password_algo):
        audit.log_audit(
            db,
            user_id=user.user_id if user else None,
            action="auth.login_failed",
            entity_type="user",
            entity_id=str(user.user_id) if user else None,
            ip_address=request_ip(request),
        )
        db.commit()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid username or password")
    if not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This account is inactive")
    if user.role == "system_ai":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "The system_ai account cannot be used to log in")

    # Transparent legacy upgrade: SHA2 -> bcrypt after a successful login.
    if needs_rehash(user.password_hash, user.password_algo):
        user.password_hash = hash_password(payload.password)
        user.password_algo = "bcrypt"
        user.must_change_password = False if user.password_algo == "bcrypt" else user.must_change_password

    if user.role == "customer":
        ensure_customer_profile(db, user)

    audit.log_audit(
        db,
        user_id=user.user_id,
        action="auth.login",
        entity_type="user",
        entity_id=str(user.user_id),
        ip_address=request_ip(request),
    )
    login_limiter.reset(key)
    return _issue(db, user, request)


@router.post("/pin", response_model=TokenResponse)
def pin_login(payload: PinLoginRequest, request: Request, db: Session = Depends(get_db)):
    key = f"pin:{request_ip(request)}:{payload.username.lower()}"
    login_limiter.check(key)
    user = db.scalar(select(User).where(User.username == payload.username))
    if (
        user is None
        or user.role not in ("chef", "cashier", "manager")
        or not user.is_active
        or not verify_pin(payload.pin, user.pin_hash or "")
    ):
        audit.log_audit(
            db,
            user_id=user.user_id if user else None,
            action="auth.pin_failed",
            entity_type="user",
            entity_id=str(user.user_id) if user else None,
            ip_address=request_ip(request),
        )
        db.commit()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid username or PIN")
    audit.log_audit(
        db,
        user_id=user.user_id,
        action="auth.pin_login",
        entity_type="user",
        entity_id=str(user.user_id),
        ip_address=request_ip(request),
    )
    login_limiter.reset(key)
    return _issue(db, user, request)


@router.post("/logout")
def logout(
    request: Request,
    user: CurrentUser,
    db: Session = Depends(get_db),
):
    auth = request.headers.get("authorization", "")
    token = auth.removeprefix("Bearer ").strip()
    if token:
        payload = decode_token(token)
        session = db.scalar(select(UserSession).where(UserSession.jwt_id == payload.get("jti")))
        if session:
            session.revoked_at = datetime.utcnow()
    audit.log_audit(
        db,
        user_id=user.user_id,
        action="auth.logout",
        entity_type="user",
        entity_id=str(user.user_id),
        ip_address=request_ip(request),
    )
    db.commit()
    return {"message": "Signed out"}


@router.get("/me", response_model=MeOut)
def me(user: CurrentUser, db: Session = Depends(get_db)):
    profile = db.scalar(select(Customer).where(Customer.user_id == user.user_id))
    return MeOut(
        user=UserOut(**user_payload(user)),
        customer=CustomerProfileOut.model_validate(profile) if profile else None,
    )


@router.patch("/me", response_model=MeOut)
def update_me(
    payload: ProfileUpdate,
    request: Request,
    user: CurrentUser,
    db: Session = Depends(get_db),
):
    if payload.email and payload.email != user.email:
        if db.scalar(select(User).where(User.email == payload.email, User.user_id != user.user_id)):
            raise HTTPException(status.HTTP_409_CONFLICT, "Email is already in use")
        user.email = str(payload.email)
    if payload.full_name:
        user.full_name = payload.full_name
    profile = db.scalar(select(Customer).where(Customer.user_id == user.user_id))
    if profile:
        if payload.phone and payload.phone != profile.phone:
            if db.scalar(select(Customer).where(Customer.phone == payload.phone, Customer.customer_id != profile.customer_id)):
                raise HTTPException(status.HTTP_409_CONFLICT, "Phone number is already in use")
            profile.phone = payload.phone
        if payload.address is not None:
            profile.address = payload.address
        if payload.full_name:
            profile.customer_name = payload.full_name
    audit.log_audit(
        db,
        user_id=user.user_id,
        action="profile.update",
        entity_type="user",
        entity_id=str(user.user_id),
        ip_address=request_ip(request),
    )
    db.commit()
    return me(user, db)


@router.post("/me/password")
def change_password(
    payload: PasswordChange,
    request: Request,
    user: CurrentUser,
    db: Session = Depends(get_db),
):
    if not verify_password(payload.current_password, user.password_hash, user.password_algo):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Current password is incorrect")
    if payload.current_password == payload.new_password:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "New password must be different")
    user.password_hash = hash_password(payload.new_password)
    user.password_algo = "bcrypt"
    user.must_change_password = False
    audit.log_audit(
        db,
        user_id=user.user_id,
        action="auth.password_changed",
        entity_type="user",
        entity_id=str(user.user_id),
        ip_address=request_ip(request),
    )
    db.commit()
    return {"message": "Password updated"}
