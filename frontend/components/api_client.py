"""
api_client.py
-------------
HTTP client for all FastAPI backend calls.
Centralizes base URL, auth headers, error handling.
All methods return (data, error_message) tuples.
"""
import os
import streamlit as st
import requests
from typing import Optional, Tuple, Any



API_BASE = os.getenv(
    "API_BASE",
    os.getenv("API_BASE_URL", "http://127.0.0.1:8000")
).rstrip("/")


def _headers() -> dict:
    """Return auth headers with JWT token from session state."""
    token = st.session_state.get("token")
    return {"Authorization": f"Bearer {token}"} if token else {}


def _handle_response(response: requests.Response) -> Tuple[Any, Optional[str]]:
    """Parse response: return (data, None) on success or (None, error_str) on failure."""
    try:
        data = response.json()
    except Exception:
        data = {}

    if response.status_code in (200, 201):
        return data, None
    else:
        detail = data.get("detail", f"HTTP {response.status_code} error")
        return None, str(detail)


# ── Auth ──────────────────────────────────────────────────────

def register_user(email: str, username: str, password: str, full_name: str = "") -> Tuple[Any, Optional[str]]:
    try:
        r = requests.post(f"{API_BASE}/api/auth/register", json={
            "email": email, "username": username,
            "password": password, "full_name": full_name
        }, timeout=15)
        return _handle_response(r)
    except requests.ConnectionError:
        return None, "Cannot connect to backend. Is the server running?"


def login_user(email: str, password: str) -> Tuple[Any, Optional[str]]:
    try:
        r = requests.post(f"{API_BASE}/api/auth/login", json={
            "email": email, "password": password
        }, timeout=15)
        return _handle_response(r)
    except requests.ConnectionError:
        return None, "Cannot connect to backend. Is the server running?"


def get_profile() -> Tuple[Any, Optional[str]]:
    try:
        r = requests.get(f"{API_BASE}/api/auth/me", headers=_headers(), timeout=10)
        return _handle_response(r)
    except requests.ConnectionError:
        return None, "Connection error"


def update_profile(full_name: str = None, language: str = None) -> Tuple[Any, Optional[str]]:
    params = {}
    if full_name:
        params["full_name"] = full_name
    if language:
        params["preferred_language"] = language
    try:
        r = requests.put(f"{API_BASE}/api/auth/me", params=params, headers=_headers(), timeout=10)
        return _handle_response(r)
    except requests.ConnectionError:
        return None, "Connection error"


# ── Chat ──────────────────────────────────────────────────────

def ask_question(
        question: str, 
        session_id: Optional[str] = None, 
        language: str = "en",
        document_id: Optional[int] = None,
        ) -> Tuple[Any, Optional[str]]:
    try:
        r = requests.post(f"{API_BASE}/api/chat/ask", json={
            "question": question,
            "session_id": session_id,
            "language": language,
            "document_id": document_id, 
        }, headers=_headers(), timeout=60)
        return _handle_response(r)
    except requests.ConnectionError:
        return None, "Cannot connect to backend."
    except requests.Timeout:
        return None, "Request timed out. The AI is taking longer than expected."


def get_sessions() -> Tuple[Any, Optional[str]]:
    try:
        r = requests.get(f"{API_BASE}/api/chat/sessions", headers=_headers(), timeout=10)
        return _handle_response(r)
    except requests.ConnectionError:
        return None, "Connection error"


def get_session_history(session_id: str) -> Tuple[Any, Optional[str]]:
    try:
        r = requests.get(f"{API_BASE}/api/chat/sessions/{session_id}", headers=_headers(), timeout=10)
        return _handle_response(r)
    except requests.ConnectionError:
        return None, "Connection error"


def delete_session(session_id: str) -> Tuple[Any, Optional[str]]:
    try:
        r = requests.delete(f"{API_BASE}/api/chat/sessions/{session_id}", headers=_headers(), timeout=10)
        return _handle_response(r)
    except requests.ConnectionError:
        return None, "Connection error"


def export_chat_pdf(session_id: str) -> Optional[bytes]:
    """Download chat PDF; returns raw bytes or None."""
    try:
        r = requests.get(
            f"{API_BASE}/api/chat/sessions/{session_id}/export",
            headers=_headers(), timeout=30
        )
        if r.status_code == 200:
            return r.content
        return None
    except Exception:
        return None


# ── Documents ─────────────────────────────────────────────────

def upload_document(file_bytes: bytes, filename: str, description: str = "") -> Tuple[Any, Optional[str]]:
    try:
        files = {"file": (filename, file_bytes, "application/octet-stream")}
        data = {"description": description}
        r = requests.post(
            f"{API_BASE}/api/documents/upload",
            files=files, data=data,
            headers=_headers(), timeout=120
        )
        return _handle_response(r)
    except requests.ConnectionError:
        return None, "Cannot connect to backend."


def list_documents() -> Tuple[Any, Optional[str]]:
    try:
        r = requests.get(f"{API_BASE}/api/documents/", headers=_headers(), timeout=10)
        return _handle_response(r)
    except requests.ConnectionError:
        return None, "Connection error"


def delete_document(doc_id: int) -> Tuple[Any, Optional[str]]:
    try:
        r = requests.delete(f"{API_BASE}/api/documents/{doc_id}", headers=_headers(), timeout=15)
        return _handle_response(r)
    except requests.ConnectionError:
        return None, "Connection error"


def reindex_document(doc_id: int) -> Tuple[Any, Optional[str]]:
    try:
        r = requests.post(f"{API_BASE}/api/documents/{doc_id}/reindex", headers=_headers(), timeout=120)
        return _handle_response(r)
    except requests.ConnectionError:
        return None, "Connection error"


# ── Admin ─────────────────────────────────────────────────────

def get_analytics() -> Tuple[Any, Optional[str]]:
    try:
        r = requests.get(f"{API_BASE}/api/admin/analytics", headers=_headers(), timeout=15)
        return _handle_response(r)
    except requests.ConnectionError:
        return None, "Connection error"


def get_users() -> Tuple[Any, Optional[str]]:
    try:
        r = requests.get(f"{API_BASE}/api/admin/users", headers=_headers(), timeout=10)
        return _handle_response(r)
    except requests.ConnectionError:
        return None, "Connection error"


def toggle_user(user_id: int) -> Tuple[Any, Optional[str]]:
    try:
        r = requests.put(f"{API_BASE}/api/admin/users/{user_id}/toggle-active", headers=_headers(), timeout=10)
        return _handle_response(r)
    except requests.ConnectionError:
        return None, "Connection error"


def rebuild_index() -> Tuple[Any, Optional[str]]:
    try:
        r = requests.post(f"{API_BASE}/api/admin/rebuild-index", headers=_headers(), timeout=300)
        return _handle_response(r)
    except requests.ConnectionError:
        return None, "Connection error"


def get_vector_stats() -> Tuple[Any, Optional[str]]:
    try:
        r = requests.get(f"{API_BASE}/api/admin/vector-stats", headers=_headers(), timeout=10)
        return _handle_response(r)
    except requests.ConnectionError:
        return None, "Connection error"


def get_query_logs() -> Tuple[Any, Optional[str]]:
    try:
        r = requests.get(f"{API_BASE}/api/admin/query-logs", headers=_headers(), timeout=10)
        return _handle_response(r)
    except requests.ConnectionError:
        return None, "Connection error"
