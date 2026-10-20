import time
from collections import defaultdict
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.db.models import User
from app.core.security import verify_password, create_access_token, hash_password
from app.schemas.models import LoginRequest, TokenResponse, UserResponse
from app.api.deps import get_current_user, log_audit

router = APIRouter(prefix="/auth", tags=["auth"])

# Rate-limiting store: key = ip:email, value = list of failure timestamps
RATE_LIMIT_WINDOW_SECONDS = 300
MAX_FAILED_ATTEMPTS = 5
failed_attempts_store = defaultdict(list)

# Dummy hash calculated once at import to ensure constant-time response for nonexistent users
DUMMY_HASH = hash_password("dummy_constant_time_comparison_string")

@router.post("/login", response_model=TokenResponse)
def login(req: LoginRequest, request: Request, db: Session = Depends(get_db)):
    client_ip = request.client.host if request.client else "unknown"
    now = time.time()
    clean_email = req.email.strip().lower()
    rate_key = f"{client_ip}:{clean_email}"

    # Clean expired failure timestamps
    failed_attempts_store[rate_key] = [
        t for t in failed_attempts_store[rate_key] if now - t < RATE_LIMIT_WINDOW_SECONDS
    ]

    # Check if rate-limited
    if len(failed_attempts_store[rate_key]) >= MAX_FAILED_ATTEMPTS:
        retry_after = int(RATE_LIMIT_WINDOW_SECONDS - (now - failed_attempts_store[rate_key][0]))
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Too many failed login attempts. Please wait {max(retry_after, 1)} seconds before trying again.",
            headers={"Retry-After": str(max(retry_after, 1))}
        )

    user = db.query(User).filter(User.email == clean_email).first()

    # Constant-time comparison: use user password if found, otherwise dummy hash
    target_hash = user.hashed_password if user else DUMMY_HASH
    password_ok = verify_password(req.password, target_hash)

    if not user or not password_ok:
        failed_attempts_store[rate_key].append(now)
        remaining = MAX_FAILED_ATTEMPTS - len(failed_attempts_store[rate_key])
        log_audit(
            db,
            user_id=user.id if user else None,
            action="failed_login_attempt",
            entity_type="auth",
            details={"email": clean_email, "remaining_attempts": max(remaining, 0)},
            ip_address=client_ip
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password. Please check your credentials and try again.",
        )

    if not user.is_active:
        log_audit(
            db,
            user_id=user.id,
            action="inactive_user_login_blocked",
            entity_type="user",
            entity_id=str(user.id),
            ip_address=client_ip
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated. Please contact the motel administrator.",
        )

    # Success: reset rate limit attempts
    failed_attempts_store.pop(rate_key, None)

    token = create_access_token(subject=user.id)
    log_audit(
        db,
        user_id=user.id,
        action="login",
        entity_type="user",
        entity_id=str(user.id),
        ip_address=client_ip
    )

    return TokenResponse(
        access_token=token,
        token_type="bearer",
        user={
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role,
            "is_active": user.is_active
        }
    )

@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        full_name=current_user.full_name,
        role=current_user.role,
        is_active=current_user.is_active
    )
