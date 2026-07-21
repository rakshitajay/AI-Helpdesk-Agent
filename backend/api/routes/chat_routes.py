"""
chat_routes.py
--------------
Chat endpoints:
  POST /api/chat/ask              - Ask a question (main RAG endpoint)
  GET  /api/chat/sessions         - List user's chat sessions
  GET  /api/chat/sessions/{id}    - Get full message history of a session
  DELETE /api/chat/sessions/{id}  - Delete a session
  GET  /api/chat/sessions/{id}/export - Export session as PDF
"""

import json
import uuid
import time
from io import BytesIO
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import func
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch

from backend.database import get_db
from backend.database.models import User, ChatSession, ChatMessage, QueryLog
from backend.authentication.auth import get_current_user
from backend.models.schemas import (
    ChatRequest, ChatResponse, ChatSessionResponse,
    ChatHistoryResponse, SourceCitation, MessageResponse
)
from backend.utils.rag_pipeline import run_rag_pipeline
from backend.config import get_settings
from backend.utils.logger import logger

router = APIRouter(prefix="/api/chat", tags=["Chat"])
settings = get_settings()


@router.post("/ask", response_model=ChatResponse)
def ask_question(
    payload: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Main RAG endpoint. Accepts a question and optional session_id.
    - If session_id is None, creates a new chat session.
    - Retrieves conversation history for context.
    - Runs full RAG pipeline and returns structured answer.
    """
    start = time.time()

    # ── Session handling ──────────────────────────────────────
    if payload.session_id:
        session = db.query(ChatSession).filter(
            ChatSession.session_id == payload.session_id,
            ChatSession.user_id == current_user.id
        ).first()
        if not session:
            raise HTTPException(status_code=404, detail="Session not found.")
    else:
        session = ChatSession(
            session_id=str(uuid.uuid4()),
            user_id=current_user.id,
            title=payload.question[:60] + ("..." if len(payload.question) > 60 else ""),
        )
        db.add(session)
        db.commit()
        db.refresh(session)

    # ── Build chat history for context ────────────────────────
    past_messages = db.query(ChatMessage).filter(
        ChatMessage.session_id == session.id
    ).order_by(ChatMessage.created_at.desc()).limit(10).all()

    chat_history = [
        {"role": msg.role, "content": msg.content}
        for msg in reversed(past_messages)
    ]

    # ── Run RAG Pipeline ──────────────────────────────────────
    try:
        result = run_rag_pipeline(
            question=payload.question,
            chat_history=chat_history,
            document_id=payload.document_id,
            language=payload.language or current_user.preferred_language,
        )
    except Exception as e:
        logger.error(f"RAG pipeline error for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="The AI engine encountered an error. Please try again."
        )

    # ── Persist user message ──────────────────────────────────
    user_msg = ChatMessage(
        session_id=session.id,
        role="user",
        content=payload.question,
        language=payload.language,
    )
    db.add(user_msg)

    # ── Persist assistant message ─────────────────────────────
    sources_json = json.dumps([
        {
            "document_name": s.document_name,
            "page_number": s.page_number,
            "chunk_text": s.chunk_text,
            "relevance_score": s.relevance_score,
        }
        for s in result.sources
    ])
    assistant_msg = ChatMessage(
        session_id=session.id,
        role="assistant",
        content=result.answer,
        sources=sources_json,
        confidence_score=result.confidence_score,
        language=payload.language,
    )
    db.add(assistant_msg)

    # ── Update session timestamp ──────────────────────────────
    session.updated_at = datetime.utcnow()

    # ── Log for analytics ─────────────────────────────────────
    elapsed_ms = (time.time() - start) * 1000
    log_entry = QueryLog(
        user_id=current_user.id,
        query=payload.question,
        response_time_ms=elapsed_ms,
        confidence_score=result.confidence_score,
        sources_count=len(result.sources),
    )
    db.add(log_entry)
    db.commit()
    db.refresh(assistant_msg)

    return ChatResponse(
        answer=result.answer,
        session_id=session.session_id,
        message_id=assistant_msg.id,
        sources=[
            SourceCitation(
                document_name=s.document_name,
                page_number=s.page_number,
                chunk_text=s.chunk_text,
                relevance_score=s.relevance_score,
            )
            for s in result.sources
        ],
        confidence_score=result.confidence_score,
        suggested_questions=result.suggested_questions,
        response_time_ms=result.response_time_ms,
        language=payload.language,
    )


@router.get("/sessions", response_model=List[ChatSessionResponse])
def list_sessions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Return all active chat sessions for the current user."""
    sessions = db.query(ChatSession).filter(
        ChatSession.user_id == current_user.id,
        ChatSession.is_active == True
    ).order_by(ChatSession.updated_at.desc()).all()

    result = []
    for s in sessions:
        count = db.query(func.count(ChatMessage.id)).filter(
            ChatMessage.session_id == s.id
        ).scalar()
        result.append(ChatSessionResponse(
            session_id=s.session_id,
            title=s.title,
            created_at=s.created_at,
            updated_at=s.updated_at,
            message_count=count,
        ))
    return result


@router.get("/sessions/{session_id}", response_model=ChatHistoryResponse)
def get_session_history(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all messages in a specific session."""
    session = db.query(ChatSession).filter(
        ChatSession.session_id == session_id,
        ChatSession.user_id == current_user.id
    ).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")

    messages = db.query(ChatMessage).filter(
        ChatMessage.session_id == session.id
    ).order_by(ChatMessage.created_at).all()

    return ChatHistoryResponse(
        session_id=session_id,
        messages=[
            {
                "id": m.id,
                "role": m.role,
                "content": m.content,
                "sources": json.loads(m.sources) if m.sources else [],
                "confidence_score": m.confidence_score,
                "created_at": m.created_at.isoformat(),
            }
            for m in messages
        ]
    )


@router.delete("/sessions/{session_id}", response_model=MessageResponse)
def delete_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Soft-delete a chat session."""
    session = db.query(ChatSession).filter(
        ChatSession.session_id == session_id,
        ChatSession.user_id == current_user.id
    ).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")

    session.is_active = False
    db.commit()
    return MessageResponse(message="Session deleted.", success=True)


@router.get("/sessions/{session_id}/export")
def export_session_pdf(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Export a chat session as a downloadable PDF."""
    session = db.query(ChatSession).filter(
        ChatSession.session_id == session_id,
        ChatSession.user_id == current_user.id
    ).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")

    messages = db.query(ChatMessage).filter(
        ChatMessage.session_id == session.id
    ).order_by(ChatMessage.created_at).all()

    # Build PDF in memory
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter,
                            leftMargin=inch, rightMargin=inch,
                            topMargin=inch, bottomMargin=inch)
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('Title', parent=styles['Heading1'], fontSize=16)
    user_style = ParagraphStyle('User', parent=styles['Normal'],
                                textColor='#1a73e8', fontSize=11, spaceAfter=4)
    ai_style = ParagraphStyle('AI', parent=styles['Normal'],
                              fontSize=11, spaceAfter=4)

    story = []
    story.append(Paragraph(f"Chat Export: {session.title or 'Conversation'}", title_style))
    story.append(Paragraph(
        f"Exported on {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')} | "
        f"User: {current_user.username}", styles['Normal']
    ))
    story.append(Spacer(1, 0.3 * inch))

    for msg in messages:
        prefix = "You" if msg.role == "user" else "AI Assistant"
        style = user_style if msg.role == "user" else ai_style
        story.append(Paragraph(f"<b>{prefix}:</b>", style))
        # Sanitize text for reportlab
        safe_content = msg.content.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        story.append(Paragraph(safe_content, styles['Normal']))
        story.append(Spacer(1, 0.15 * inch))

    doc.build(story)
    buffer.seek(0)

    filename = f"chat_{session_id[:8]}_{datetime.utcnow().strftime('%Y%m%d')}.pdf"
    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )
