"""
admin_routes.py
---------------
Admin-only endpoints:
  GET  /api/admin/analytics        - Dashboard stats
  GET  /api/admin/users            - List all users
  PUT  /api/admin/users/{id}       - Activate/deactivate user
  GET  /api/admin/query-logs       - Recent queries log
  POST /api/admin/rebuild-index    - Rebuild entire ChromaDB index
  GET  /api/admin/vector-stats     - ChromaDB collection stats
"""

from typing import List, Optional
from datetime import datetime, timedelta
from collections import Counter

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, desc

from backend.database import get_db
from backend.database.models import User, Document, ChatSession, ChatMessage, QueryLog
from backend.authentication.auth import require_admin
from backend.models.schemas import (
    UserResponse, AnalyticsResponse, AnalyticsSummary,
    TopQuery, MessageResponse
)
from backend.vector_db.chroma_store import rebuild_vector_index, get_collection_stats
from backend.utils.document_processor import process_document
from backend.utils.logger import logger

router = APIRouter(prefix="/api/admin", tags=["Admin"])


@router.get("/analytics", response_model=AnalyticsResponse)
def get_analytics(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Full dashboard analytics for admin panel."""
    total_users = db.query(func.count(User.id)).scalar()
    total_docs = db.query(func.count(Document.id)).scalar()
    total_queries = db.query(func.count(QueryLog.id)).scalar()
    total_sessions = db.query(func.count(ChatSession.id)).scalar()

    avg_conf = db.query(func.avg(QueryLog.confidence_score)).scalar() or 0.0
    avg_resp = db.query(func.avg(QueryLog.response_time_ms)).scalar() or 0.0

    # Top 10 most asked queries
    query_counts = db.query(
        QueryLog.query, func.count(QueryLog.id).label("count")
    ).group_by(QueryLog.query).order_by(desc("count")).limit(10).all()

    top_queries = [TopQuery(query=q, count=c) for q, c in query_counts]

    # Daily query counts (last 7 days)
    daily_queries = []
    for i in range(6, -1, -1):
        day = datetime.utcnow() - timedelta(days=i)
        day_start = day.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day.replace(hour=23, minute=59, second=59)
        count = db.query(func.count(QueryLog.id)).filter(
            QueryLog.created_at >= day_start,
            QueryLog.created_at <= day_end
        ).scalar()
        daily_queries.append({"date": day.strftime("%Y-%m-%d"), "count": count})

    # Recent users (last 5)
    recent_users = db.query(User).order_by(desc(User.created_at)).limit(5).all()

    return AnalyticsResponse(
        summary=AnalyticsSummary(
            total_users=total_users,
            total_documents=total_docs,
            total_queries=total_queries,
            total_sessions=total_sessions,
            avg_confidence_score=round(avg_conf, 3),
            avg_response_time_ms=round(avg_resp, 1),
        ),
        top_queries=top_queries,
        daily_queries=daily_queries,
        recent_users=recent_users,
    )


@router.get("/users", response_model=List[UserResponse])
def list_users(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, le=200),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Return paginated list of all registered users."""
    users = db.query(User).order_by(desc(User.created_at)).offset(skip).limit(limit).all()
    return users


@router.put("/users/{user_id}/toggle-active", response_model=MessageResponse)
def toggle_user_active(
    user_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Activate or deactivate a user account."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
    if user.id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot deactivate your own account.")

    user.is_active = not user.is_active
    db.commit()
    status_str = "activated" if user.is_active else "deactivated"
    logger.info(f"Admin {current_user.email} {status_str} user {user.email}")
    return MessageResponse(message=f"User '{user.username}' has been {status_str}.", success=True)


@router.get("/query-logs")
def get_query_logs(
    limit: int = Query(default=100, le=500),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Return recent query logs for monitoring."""
    logs = db.query(QueryLog).order_by(desc(QueryLog.created_at)).limit(limit).all()
    return [
        {
            "id": log.id,
            "user_id": log.user_id,
            "query": log.query,
            "confidence_score": log.confidence_score,
            "response_time_ms": log.response_time_ms,
            "sources_count": log.sources_count,
            "created_at": log.created_at.isoformat(),
        }
        for log in logs
    ]


@router.post("/rebuild-index", response_model=MessageResponse)
def rebuild_index(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Admin: Drop and rebuild the entire ChromaDB vector index
    from all currently stored documents.
    """
    from backend.utils.document_processor import process_document

    documents = db.query(Document).filter(Document.is_indexed == True).all()
    if not documents:
        return MessageResponse(message="No indexed documents found.", success=False)

    all_chunks = []
    for doc in documents:
        try:
            chunks, _ = process_document(doc.file_path, doc.file_type, doc.original_name)
            for chunk in chunks:
                chunk.metadata["document_id"] = str(doc.id)
            all_chunks.extend(chunks)
        except Exception as e:
            logger.warning(f"Skipping document {doc.original_name} during rebuild: {e}")

    total = rebuild_vector_index(all_chunks)
    logger.info(f"Index rebuilt by admin {current_user.email}: {total} chunks")
    return MessageResponse(
        message=f"Vector index rebuilt successfully with {total} chunks from {len(documents)} documents.",
        success=True
    )


@router.get("/vector-stats")
def vector_stats(current_user: User = Depends(require_admin)):
    """Return ChromaDB collection statistics."""
    return get_collection_stats()
