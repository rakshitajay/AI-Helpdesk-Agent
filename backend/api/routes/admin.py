"""
api/routes/admin.py
--------------------
Admin-only management endpoints:
  GET  /api/admin/users            – List all users
  PUT  /api/admin/users/{id}       – Update user (activate/deactivate/promote)
  DELETE /api/admin/users/{id}     – Delete a user
  GET  /api/admin/analytics        – Dashboard stats
"""

from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.authentication.dependencies import get_current_admin_user
from backend.database.connection import get_db
from backend.database.models import User
from backend.models.schemas import (
    AnalyticsResponse, SuccessResponse,
    UserAdminView, UserUpdateRequest
)
from backend.services.analytics_service import analytics_service
from backend.utils.logger import logger

router = APIRouter(prefix="/api/admin", tags=["Admin"])


@router.get("/users", response_model=List[UserAdminView])
async def list_users(
    _: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """List all registered users with management metadata."""
    result = await db.execute(select(User).order_by(User.created_at.desc()))
    return result.scalars().all()


@router.put("/users/{user_id}", response_model=UserAdminView)
async def update_user(
    user_id: int,
    payload: UserUpdateRequest,
    current_admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Update user status or permissions.
    Admins cannot demote themselves to prevent lockout.
    """
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Prevent admin self-demotion
    if user_id == current_admin.id and payload.is_admin is False:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot remove your own admin privileges",
        )

    if payload.is_active is not None:
        user.is_active = payload.is_active
    if payload.is_admin is not None:
        user.is_admin = payload.is_admin
    if payload.full_name is not None:
        user.full_name = payload.full_name

    await db.flush()
    logger.info(f"Admin {current_admin.email} updated user {user.email}")
    return user


@router.delete("/users/{user_id}", response_model=SuccessResponse)
async def delete_user(
    user_id: int,
    current_admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Permanently delete a user account. Admins cannot delete themselves."""
    if user_id == current_admin.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot delete your own account",
        )

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    await db.delete(user)
    await db.flush()
    logger.info(f"Admin {current_admin.email} deleted user {user.email}")
    return SuccessResponse(message=f"User {user.email} deleted")


@router.get("/analytics", response_model=AnalyticsResponse)
async def get_analytics(
    _: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Return aggregated analytics for the admin dashboard."""
    return await analytics_service.get_dashboard_stats(db)
