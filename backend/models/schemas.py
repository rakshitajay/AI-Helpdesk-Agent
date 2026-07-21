"""
schemas.py
----------
Pydantic request/response schemas for all API endpoints.
Keeps API layer decoupled from ORM models.
"""

from datetime import datetime
from typing import Optional, List, Any
from pydantic import BaseModel, EmailStr, Field, field_validator
import re


# ── Auth Schemas ──────────────────────────────────────────────

class UserRegister(BaseModel):
    email: EmailStr
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=8)
    full_name: Optional[str] = None

    @field_validator("username")
    @classmethod
    def username_alphanumeric(cls, v: str) -> str:
        if not re.match(r"^[a-zA-Z0-9_]+$", v):
            raise ValueError("Username must be alphanumeric (underscores allowed)")
        return v

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit")
        return v


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: int
    username: str
    role: str
    expires_in: int  # seconds


class UserResponse(BaseModel):
    id: int
    email: str
    username: str
    full_name: Optional[str]
    role: str
    is_active: bool
    preferred_language: str
    created_at: datetime
    last_login: Optional[datetime]

    class Config:
        from_attributes = True


# ── Chat Schemas ──────────────────────────────────────────────

class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)
    session_id: Optional[str] = None   # UUID; create new if None
    language: str = Field(default="en", max_length=10)
    document_id: Optional[int] = None
    @field_validator("question")
    @classmethod
    def sanitize_question(cls, v: str) -> str:
        return v.strip()


class SourceCitation(BaseModel):
    document_name: str
    page_number: Optional[int] = None
    chunk_text: str
    relevance_score: float


class ChatResponse(BaseModel):
    answer: str
    session_id: str
    message_id: int
    sources: List[SourceCitation]
    confidence_score: float
    suggested_questions: List[str]
    response_time_ms: float
    language: str


class ChatSessionResponse(BaseModel):
    session_id: str
    title: Optional[str]
    created_at: datetime
    updated_at: datetime
    message_count: int

    class Config:
        from_attributes = True


class ChatHistoryResponse(BaseModel):
    session_id: str
    messages: List[dict]


# ── Document Schemas ──────────────────────────────────────────

class DocumentResponse(BaseModel):
    id: int
    filename: str
    original_name: str
    file_type: str
    file_size: int
    chunk_count: int
    is_indexed: bool
    description: Optional[str]
    created_at: datetime
    indexed_at: Optional[datetime]

    class Config:
        from_attributes = True


class DocumentUploadResponse(BaseModel):
    id: int
    original_name: str
    file_type: str
    file_size: int
    message: str
    is_indexed: bool


# ── Analytics Schemas ─────────────────────────────────────────

class AnalyticsSummary(BaseModel):
    total_users: int
    total_documents: int
    total_queries: int
    total_sessions: int
    avg_confidence_score: float
    avg_response_time_ms: float


class TopQuery(BaseModel):
    query: str
    count: int


class AnalyticsResponse(BaseModel):
    summary: AnalyticsSummary
    top_queries: List[TopQuery]
    daily_queries: List[dict]
    recent_users: List[UserResponse]


# ── Generic Schemas ───────────────────────────────────────────

class MessageResponse(BaseModel):
    message: str
    success: bool = True
    data: Optional[Any] = None


class ErrorResponse(BaseModel):
    detail: str
    error_code: Optional[str] = None
