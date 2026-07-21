"""
api/routes/chat.py
------------------
Chat endpoints:
  POST /api/chat/ask                        – Ask a question (RAG)
  GET  /api/chat/sessions                   – List user's sessions
  GET  /api/chat/sessions/{session_id}      – Get messages in a session
  DELETE /api/chat/sessions/{session_id}    – Delete a session
  GET  /api/chat/sessions/{session_id}/export – Export session as JSON
"""

from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.authentication.dependencies import get_current_active_user
from backend.database.connection import get_db
from backend.database.models import User
from backend.models.schemas import (
    ChatRequest, ChatResponse, MessageResponse,
    SessionResponse, SuccessResponse,
)
from backend.services.chat_service import chat_service
from backend.utils.logger import logger

router = APIRouter(prefix="/api/chat", tags=["Chat"])


@router.post("/ask", response_model=ChatResponse)
async def ask_question(
    request: ChatRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Submit a question and receive an AI-generated answer.

    The RAG pipeline:
    1. Rewrites the query for better retrieval
    2. Searches ChromaDB for relevant document chunks
    3. Sends context + question to Gemini
    4. Returns the answer with source citations and confidence score
    """
    logger.info(f"Question from user {current_user.id}: {request.question[:80]}...")
    logger.info(f"Question: {request.question}")
    logger.info(f"Document ID: {request.document_id}")
    return await chat_service.process_question(db, request, current_user.id)


@router.get("/sessions", response_model=List[SessionResponse])
async def list_sessions(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Return all of the current user's chat sessions, newest first."""
    return await chat_service.get_user_sessions(db, current_user.id)


@router.get("/sessions/{session_id}/messages", response_model=List[MessageResponse])
async def get_session_messages(
    session_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Return all messages in a specific chat session.
    Only the session owner can access their messages.
    """
    messages = await chat_service.get_session_messages(db, session_id, current_user.id)
    if messages is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return messages


@router.delete("/sessions/{session_id}", response_model=SuccessResponse)
async def delete_session(
    session_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Soft-delete a chat session (hidden from UI but kept for analytics)."""
    deleted = await chat_service.delete_session(db, session_id, current_user.id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Session not found")
    return SuccessResponse(message="Session deleted successfully")


@router.get("/sessions/{session_id}/export")
async def export_session(
    session_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Export a full chat session as JSON.
    The Streamlit frontend converts this to a downloadable PDF.
    """
    messages = await chat_service.get_session_messages(db, session_id, current_user.id)
    if not messages:
        raise HTTPException(status_code=404, detail="Session not found or empty")

    return {
        "session_id": session_id,
        "user": current_user.username,
        "messages": [m.model_dump() for m in messages],
        "total_messages": len(messages),
    }
