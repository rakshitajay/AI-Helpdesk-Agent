"""
main.py
-------
FastAPI application entry point.

Responsibilities:
  - Create the FastAPI app with metadata
  - Configure CORS
  - Add rate limiting middleware
  - Register all API routers
  - Create DB tables and seed admin user on startup
  - Health check endpoint
"""

import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from backend.api.routes.auth_routes import router as auth_router
from backend.api.routes.chat_routes import router as chat_router
from backend.api.routes.document_routes import router as doc_router
from backend.api.routes.admin_routes import router as admin_router
from backend.database import create_tables, get_db, SessionLocal
from backend.database.models import User, UserRole
from backend.authentication.auth import hash_password
from backend.config import get_settings
from backend.utils.logger import logger

settings = get_settings()

# ── Rate Limiter ──────────────────────────────────────────────
limiter = Limiter(key_func=get_remote_address)


# ── Lifespan (startup / shutdown) ─────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Run startup tasks before serving, cleanup on shutdown."""
    logger.info(f"Starting {settings.app_name} v{settings.app_version}")

    # Create DB tables
    create_tables()

    # Seed admin user if not exists
    db = SessionLocal()
    try:
        admin = db.query(User).filter(User.email == settings.admin_email).first()
        if not admin:
            print("ADMIN PASSWORD =", repr(settings.admin_password))
            print("PASSWORD LENGTH =", len(settings.admin_password))
            admin = User(
                email=settings.admin_email,
                username="admin",

               
                hashed_password=hash_password(settings.admin_password),
                full_name="System Administrator",
                role=UserRole.ADMIN,
            )
            db.add(admin)
            db.commit()
            logger.info(f"Admin user seeded: {settings.admin_email}")
        else:
            logger.info("Admin user already exists.")
    finally:
        db.close()

    # Ensure upload directory exists
    os.makedirs(settings.upload_dir, exist_ok=True)

    logger.info("Application startup complete. Ready to serve requests.")
    yield
    logger.info("Application shutdown.")


# ── FastAPI App ───────────────────────────────────────────────
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description=(
        "AI Helpdesk Agent — Intelligent RAG Support Assistant. "
        "Answers questions from uploaded documents using Google Gemini + ChromaDB."
    ),
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# ── Middleware ────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


# ── Routers ───────────────────────────────────────────────────
app.include_router(auth_router)
app.include_router(chat_router)
app.include_router(doc_router)
app.include_router(admin_router)


# ── Health Check ──────────────────────────────────────────────
@app.get("/health", tags=["Health"])
def health_check():
    """Quick liveness probe for Docker / Railway / Render."""
    return {
        "status": "healthy",
        "app": settings.app_name,
        "version": settings.app_version,
    }


@app.get("/", tags=["Root"])
def root():
    return {
        "message": f"Welcome to {settings.app_name} API",
        "docs": "/docs",
        "health": "/health",
    }
