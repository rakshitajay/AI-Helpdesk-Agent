"""
auth_routes.py
--------------
Authentication endpoints:
  POST /api/auth/register  - Create new user account
  POST /api/auth/login     - Login and receive JWT token
  GET  /api/auth/me        - Get current user profile
  PUT  /api/auth/me        - Update profile / language preference
  POST /api/auth/logout    - Invalidate session (client-side token drop)
"""

from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.database.models import User, UserRole
from backend.authentication.auth import (
    hash_password, verify_password,
    create_access_token, get_current_user
)
from backend.models.schemas import (
    UserRegister, UserLogin, TokenResponse,
    UserResponse, MessageResponse
)
from backend.config import get_settings
from backend.utils.logger import logger

router = APIRouter(prefix="/api/auth", tags=["Authentication"])
settings = get_settings()


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(payload: UserRegister, db: Session = Depends(get_db)):
    """Register a new user account."""
    # Check duplicate email
    if db.query(User).filter(User.email == payload.email).first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists."
        )
    # Check duplicate username
    if db.query(User).filter(User.username == payload.username).first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This username is already taken."
        )

    user = User(
        email=payload.email,
        username=payload.username,
        hashed_password=hash_password(payload.password),
        full_name=payload.full_name,
        role=UserRole.USER,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    logger.info(f"New user registered: {user.email}")
    return user


@router.post("/login", response_model=TokenResponse)
def login(payload: UserLogin, db: Session = Depends(get_db)):
    """Authenticate user and return a JWT access token."""
    user = db.query(User).filter(User.email == payload.email).first()

    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account has been deactivated. Contact support."
        )

    token = create_access_token(data={"sub": user.email, "role": user.role.value})

    # Update last login timestamp
    user.last_login = datetime.utcnow()
    db.commit()

    logger.info(f"User logged in: {user.email}")
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        user_id=user.id,
        username=user.username,
        role=user.role.value,
        expires_in=settings.jwt_access_token_expire_minutes * 60,
    )


@router.get("/me", response_model=UserResponse)
def get_profile(current_user: User = Depends(get_current_user)):
    """Return the authenticated user's profile."""
    return current_user


@router.put("/me", response_model=UserResponse)
def update_profile(
    full_name: str = None,
    preferred_language: str = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update user's full name or preferred language."""
    if full_name:
        current_user.full_name = full_name
    if preferred_language:
        current_user.preferred_language = preferred_language
    db.commit()
    db.refresh(current_user)
    return current_user


@router.post("/logout", response_model=MessageResponse)
def logout(current_user: User = Depends(get_current_user)):
    """
    Logout endpoint. JWT is stateless — the client must discard the token.
    Server-side, we just log the event.
    """
    logger.info(f"User logged out: {current_user.email}")
    return MessageResponse(message="Logged out successfully.", success=True)
