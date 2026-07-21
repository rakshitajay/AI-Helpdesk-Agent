"""
services/chat_service.py
------------------------
Business logic for:
  - Creating/managing chat sessions
  - Processing questions through RAG
  - Saving messages to the DB
  - Building conversation history for context
"""

import json
import uuid
from datetime import datetime
from typing import List, Optional, Tuple

from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.rag_pipeline import get_rag_pipeline
from backend.database.models import ChatSession, ChatMessage, QuestionLog
from backend.models.schemas import (
    ChatRequest, ChatResponse, MessageResponse, SessionResponse, SourceDocument
)
from backend.utils.logger import logger


HISTORY_MESSAGE_LIMIT = 6  # Last N messages sent as context to Gemini


class ChatService:
    """Encapsulates all chat-related database and AI operations."""

    # ── Session Management ────────────────────────────────────────────────────

    async def get_or_create_session(
        self, db: AsyncSession, user_id: int, session_id: Optional[str]
    ) -> str:
        """
        Return existing session_id or create a new chat session.

        Args:
            db:         Database session.
            user_id:    ID of the requesting user.
            session_id: Optional existing session ID from client.

        Returns:
            Valid session_id string.
        """
        if session_id:
            # Verify session belongs to this user
            result = await db.execute(
                select(ChatSession).where(
                    ChatSession.session_id == session_id,
                    ChatSession.user_id == user_id,
                    ChatSession.is_active == True,
                )
            )
            existing = result.scalar_one_or_none()
            if existing:
                return session_id

        # Create new session
        new_session_id = str(uuid.uuid4())
        session = ChatSession(
            session_id=new_session_id,
            user_id=user_id,
            title="New Chat",
        )
        db.add(session)
        await db.flush()
        logger.info(f"New chat session created: {new_session_id} for user {user_id}")
        return new_session_id

    async def get_user_sessions(
        self, db: AsyncSession, user_id: int
    ) -> List[SessionResponse]:
        """Return all active chat sessions for a user, newest first."""
        result = await db.execute(
            select(ChatSession)
            .where(ChatSession.user_id == user_id, ChatSession.is_active == True)
            .order_by(desc(ChatSession.updated_at))
        )
        sessions = result.scalars().all()

        responses = []
        for s in sessions:
            # Count messages in this session
            count_result = await db.execute(
                select(func.count(ChatMessage.id)).where(ChatMessage.session_id == s.session_id)
            )
            msg_count = count_result.scalar_one()
            responses.append(SessionResponse(
                session_id=s.session_id,
                title=s.title,
                created_at=s.created_at,
                updated_at=s.updated_at,
                message_count=msg_count,
            ))
        return responses

    async def delete_session(
        self, db: AsyncSession, session_id: str, user_id: int
    ) -> bool:
        """Soft-delete a session (marks is_active=False)."""
        result = await db.execute(
            select(ChatSession).where(
                ChatSession.session_id == session_id,
                ChatSession.user_id == user_id,
            )
        )
        session = result.scalar_one_or_none()
        if not session:
            return False
        session.is_active = False
        await db.flush()
        return True

    # ── Message Handling ──────────────────────────────────────────────────────

    async def get_session_messages(
        self, db: AsyncSession, session_id: str, user_id: int
    ) -> List[MessageResponse]:
        """Return all messages in a session, ordered by time."""
        # Verify ownership
        sess_result = await db.execute(
            select(ChatSession).where(
                ChatSession.session_id == session_id,
                ChatSession.user_id == user_id,
            )
        )
        if not sess_result.scalar_one_or_none():
            return []

        result = await db.execute(
            select(ChatMessage)
            .where(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.created_at)
        )
        messages = result.scalars().all()

        responses = []
        for msg in messages:
            sources = None
            if msg.sources:
                try:
                    raw = json.loads(msg.sources)
                    sources = [SourceDocument(**s) for s in raw]
                except Exception:
                    sources = None

            responses.append(MessageResponse(
                id=msg.id,
                role=msg.role,
                content=msg.content,
                sources=sources,
                confidence_score=msg.confidence_score,
                created_at=msg.created_at,
            ))
        return responses

    async def _build_chat_history(
        self, db: AsyncSession, session_id: str
    ) -> str:
        """
        Fetch last N messages and format as a string for RAG context.
        This gives Gemini conversation memory.
        """
        result = await db.execute(
            select(ChatMessage)
            .where(ChatMessage.session_id == session_id)
            .order_by(desc(ChatMessage.created_at))
            .limit(HISTORY_MESSAGE_LIMIT)
        )
        messages = list(reversed(result.scalars().all()))

        if not messages:
            return ""

        history_lines = []
        for msg in messages:
            role_label = "User" if msg.role == "user" else "Assistant"
            history_lines.append(f"{role_label}: {msg.content[:300]}")

        return "\n".join(history_lines)

    async def _update_session_title(
        self, db: AsyncSession, session_id: str, question: str
    ) -> None:
        """Set session title to first question (truncated) if still 'New Chat'."""
        result = await db.execute(
            select(ChatSession).where(ChatSession.session_id == session_id)
        )
        session = result.scalar_one_or_none()
        if session and session.title == "New Chat":
            title = question[:60] + ("..." if len(question) > 60 else "")
            session.title = title
            session.updated_at = datetime.utcnow()
            await db.flush()

    # ── Main Q&A Entry Point ─────────────────────────────────────────────────

    async def process_question(
        self, db: AsyncSession, request: ChatRequest, user_id: int
    ) -> ChatResponse:
        logger.info("========== process_question STARTED ==========")
        """
        Full pipeline: receive question → RAG → save to DB → return response.

        Args:
            db:       Database session.
            request:  ChatRequest (question, session_id, language).
            user_id:  Authenticated user's DB id.

        Returns:
            ChatResponse with answer, sources, confidence, and suggestions.
        """
        # 1. Ensure we have a valid session
        session_id = await self.get_or_create_session(db, user_id, request.session_id)
        logger.info("Step 1: Session created")

        # 2. Build conversation history for context
        chat_history = await self._build_chat_history(db, session_id)
        logger.info("Step 2: Chat history loaded")

        # 3. Save user's question to DB
        user_msg = ChatMessage(
            session_id=session_id,
            role="user",
            content=request.question,
            language=request.language,
        )
        db.add(user_msg)
        await db.flush()
        logger.info("Step 3: User message saved")

        # 4. Log question for analytics
        q_log = QuestionLog(
            question=request.question,
            user_id=user_id,
            session_id=session_id,
        )
        db.add(q_log)

        # 5. Run RAG pipeline
        logger.info("Step 4: Starting RAG pipeline")
        pipeline = get_rag_pipeline()
        print("=" * 50)
        print("DOCUMENT ID RECEIVED:", request.document_id)
        print("=" * 50)
        
        answer, sources, confidence, suggestions, elapsed = pipeline.answer(
            question=request.question,
            chat_history=chat_history,
            language=request.language,
            document_id=request.document_id,
        )
        logger.info("Step 5: RAG pipeline finished")

        # 6. Update question log
        q_log.answer_found = confidence > 0
        q_log.confidence_score = confidence

        # 7. Serialise sources to JSON for storage
        sources_json = json.dumps([s.model_dump() for s in sources])

        # 8. Save AI response to DB
        ai_msg = ChatMessage(
            session_id=session_id,
            role="assistant",
            content=answer,
            sources=sources_json,
            confidence_score=confidence,
            response_time_ms=elapsed,
            language=request.language,
        )
        db.add(ai_msg)
        await db.flush()

        # 9. Update session title if first message
        await self._update_session_title(db, session_id, request.question)

        logger.info(
            f"Question answered | session={session_id} | user={user_id} "
            f"| confidence={confidence} | time={elapsed}ms"
        )

        return ChatResponse(
            answer=answer,
            session_id=session_id,
            message_id=ai_msg.id,
            sources=sources,
            confidence_score=confidence,
            suggested_questions=suggestions,
            response_time_ms=elapsed,
            language=request.language,
        )


# ── Singleton ─────────────────────────────────────────────────────────────────
chat_service = ChatService()
