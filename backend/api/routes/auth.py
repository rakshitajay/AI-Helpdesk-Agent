"""
api/routes/auth.py
------------------
Authentication endpoints:
  POST /api/auth/register  – Create a new account
  POST /api/auth/login     – Get JWT tokens
  POST /api/auth/refresh   – Refresh access token
  GET  /api/auth/me        – Get current user profile
  PUT  /api/auth/me        – Update profile
"""

from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.authentication.auth_service import (
    authenticate_user, create_access_token, create_refresh_token,
    decode_token, get_user_by_email, hash_password,
)
from backend.authentication.dependencies import get_current_active_user
from backend.config.settings import settings
from backend.database.connection import get_db
from backend.database.models import User
from backend.models.schemas import (
    RefreshTokenRequest, TokenResponse, UserLoginRequest,
    UserRegisterRequest, UserResponse, SuccessResponse,
)
from backend.utils.logger import logger

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    payload: UserRegisterRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Register a new user account.
    Validates email uniqueness and password strength before creating the record.
    """
    # Check email uniqueness
    existing = await get_user_by_email(db, payload.email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists",
        )

    # Check username uniqueness
    from sqlalchemy import select
    result = await db.execute(
        select(User).where(User.username == payload.username.lower())
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username already taken",
        )

    user = User(
        email=payload.email,
        username=payload.username.lower(),
        hashed_password=hash_password(payload.password),
        full_name=payload.full_name,
        is_admin=False,
    )
    db.add(user)
    await db.flush()

    logger.info(f"New user registered: {user.email}")
    return user


@router.post("/login", response_model=TokenResponse)
async def login(
    payload: UserLoginRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Authenticate with email/password.
    Returns JWT access_token (short-lived) and refresh_token (long-lived).
    """
    user = await authenticate_user(db, payload.email, payload.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(
        data={"sub": user.email, "role": "admin" if user.is_admin else "user"}
    )
    refresh_token = create_refresh_token(
        data={"sub": user.email}
    )

    logger.info(f"User logged in: {user.email}")
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    payload: RefreshTokenRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Exchange a valid refresh token for a new access token.
    Allows clients to stay logged in without re-entering credentials.
    """
    decoded = decode_token(payload.refresh_token)
    if not decoded or decoded.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    email = decoded.get("sub")
    user = await get_user_by_email(db, email)
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    new_access = create_access_token(
        data={"sub": user.email, "role": "admin" if user.is_admin else "user"}
    )
    new_refresh = create_refresh_token(data={"sub": user.email})

    return TokenResponse(
        access_token=new_access,
        refresh_token=new_refresh,
        token_type="bearer",
        expires_in=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.get("/me", response_model=UserResponse)
async def get_profile(
    current_user: User = Depends(get_current_active_user),
):
    """Return the authenticated user's profile."""
    return current_user


@router.put("/me/language", response_model=SuccessResponse)
async def update_language(
    language: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Update the user's preferred language setting."""
    current_user.preferred_language = language
    await db.flush()
    return SuccessResponse(message=f"Language updated to '{language}'")
