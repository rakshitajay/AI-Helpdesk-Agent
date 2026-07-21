"""
authentication/auth_service.py
-------------------------------
Handles:
  - Password hashing & verification (bcrypt via passlib)
  - JWT access & refresh token creation
  - Token decoding & validation
  - User lookup from token
"""

from datetime import datetime, timedelta, timezone
from typing import Optional

from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.config.settings import settings
from backend.database.models import User
from backend.utils.logger import logger


# ── Password hashing ──────────────────────────────────────────────────────────
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain_password: str) -> str:
    """Return bcrypt hash of the given password."""
    return pwd_context.hash(plain_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Return True if plain_password matches the stored bcrypt hash."""
    return pwd_context.verify(plain_password, hashed_password)


# ── Token creation ────────────────────────────────────────────────────────────
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Create a signed JWT access token.

    Args:
        data: Payload dict (typically {"sub": user_email, "role": "admin"|"user"})
        expires_delta: Custom TTL; defaults to settings value.

    Returns:
        Encoded JWT string.
    """
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire, "type": "access"})
    return jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_refresh_token(data: dict) -> str:
    """
    Create a longer-lived JWT refresh token.

    Returns:
        Encoded JWT refresh token string.
    """
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "type": "refresh"})
    return jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


# ── Token decoding ────────────────────────────────────────────────────────────
def decode_token(token: str) -> Optional[dict]:
    """
    Decode and validate a JWT token.

    Returns:
        Decoded payload dict, or None if invalid/expired.
    """
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
        return payload
    except JWTError as e:
        logger.warning(f"JWT decode error: {e}")
        return None


# ── User helpers ──────────────────────────────────────────────────────────────
async def get_user_by_email(db: AsyncSession, email: str) -> Optional[User]:
    """Fetch a User record by email address."""
    result = await db.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()


async def authenticate_user(
    db: AsyncSession, email: str, password: str
) -> Optional[User]:
    """
    Verify credentials and return the User on success, None on failure.
    Also updates last_login timestamp.
    """
    user = await get_user_by_email(db, email)
    if not user:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    if not user.is_active:
        logger.warning(f"Inactive user attempted login: {email}")
        return None

    # Update last login time
    user.last_login = datetime.now(timezone.utc)
    await db.commit()

    return user


async def get_current_user(token: str, db: AsyncSession) -> Optional[User]:
    """
    Extract user from a Bearer token string.
    Used by FastAPI dependencies and Streamlit session validation.

    Returns:
        User ORM object, or None if token is invalid.
    """
    payload = decode_token(token)
    if not payload or payload.get("type") != "access":
        return None

    email: str = payload.get("sub")
    if not email:
        return None

    return await get_user_by_email(db, email)
