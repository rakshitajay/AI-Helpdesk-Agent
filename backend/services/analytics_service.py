"""
services/analytics_service.py
------------------------------
Powers the admin dashboard with real-time statistics:
  - Total users, documents, and queries
  - Average confidence and response time
  - Top questions
  - Daily query volume (last 30 days)
"""

import json
from datetime import datetime, timedelta
from typing import List

from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.models import User, Document, ChatMessage, QuestionLog
from backend.models.schemas import AnalyticsResponse
from backend.utils.logger import logger


class AnalyticsService:

    async def get_dashboard_stats(self, db: AsyncSession) -> AnalyticsResponse:
        """Aggregate all stats needed for the admin dashboard."""

        # Total users
        users_result = await db.execute(select(func.count(User.id)))
        total_users = users_result.scalar_one()

        # Total documents
        docs_result = await db.execute(select(func.count(Document.id)))
        total_docs = docs_result.scalar_one()

        # Total queries (user messages only)
        queries_result = await db.execute(
            select(func.count(ChatMessage.id)).where(ChatMessage.role == "user")
        )
        total_queries = queries_result.scalar_one()

        # Average confidence from assistant messages
        conf_result = await db.execute(
            select(func.avg(ChatMessage.confidence_score))
            .where(ChatMessage.role == "assistant", ChatMessage.confidence_score.isnot(None))
        )
        avg_confidence = round(float(conf_result.scalar_one() or 0), 3)

        # Average response time
        rt_result = await db.execute(
            select(func.avg(ChatMessage.response_time_ms))
            .where(ChatMessage.role == "assistant", ChatMessage.response_time_ms.isnot(None))
        )
        avg_rt = round(float(rt_result.scalar_one() or 0), 1)

        # Top 10 most asked questions
        top_q_result = await db.execute(
            select(QuestionLog.question, func.count(QuestionLog.id).label("count"))
            .group_by(QuestionLog.question)
            .order_by(desc("count"))
            .limit(10)
        )
        top_questions = [
            {"question": row.question[:100], "count": row.count}
            for row in top_q_result.fetchall()
        ]

        # Daily query volume (last 30 days)
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        daily_result = await db.execute(
            select(
                func.date(ChatMessage.created_at).label("date"),
                func.count(ChatMessage.id).label("count"),
            )
            .where(
                ChatMessage.role == "user",
                ChatMessage.created_at >= thirty_days_ago,
            )
            .group_by(func.date(ChatMessage.created_at))
            .order_by("date")
        )
        daily_queries = [
            {"date": str(row.date), "count": row.count}
            for row in daily_result.fetchall()
        ]

        return AnalyticsResponse(
            total_users=total_users,
            total_documents=total_docs,
            total_queries=total_queries,
            avg_confidence=avg_confidence,
            avg_response_time_ms=avg_rt,
            top_questions=top_questions,
            daily_queries=daily_queries,
        )


analytics_service = AnalyticsService()
