"""
settings.py
-----------
Central configuration module using Pydantic BaseSettings.
All values are loaded from environment variables / .env file.
No secrets are hardcoded here.
"""

from functools import lru_cache
from typing import List
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Application-wide settings loaded from environment variables."""

    # App
    app_name: str = Field(default="AI Helpdesk Agent", env="APP_NAME")
    app_version: str = Field(default="1.0.0", env="APP_VERSION")
    debug: bool = Field(default=False, env="DEBUG")

    # Google Gemini
    google_api_key: str = Field(default="", env="GOOGLE_API_KEY")
    gemini_model: str = Field(default="gemini-2.5-flash", env="GEMINI_MODEL")
    embedding_model: str = Field(default="models/embedding-001", env="EMBEDDING_MODEL")

    # JWT
    jwt_secret_key: str = Field(default="changeme", env="JWT_SECRET_KEY")
    jwt_algorithm: str = Field(default="HS256", env="JWT_ALGORITHM")
    jwt_access_token_expire_minutes: int = Field(default=60, env="JWT_ACCESS_TOKEN_EXPIRE_MINUTES")

    # Database
    database_url: str = Field(default="sqlite:///./backend/database/helpdesk.db", env="DATABASE_URL")

    # ChromaDB
    chroma_persist_dir: str = Field(default="./backend/vector_db/chroma_store", env="CHROMA_PERSIST_DIR")
    chroma_collection_name: str = Field(default="helpdesk_docs", env="CHROMA_COLLECTION_NAME")

    # FastAPI
    api_host: str = Field(default="0.0.0.0", env="API_HOST")
    api_port: int = Field(default=8000, env="API_PORT")
    cors_origins: List[str] = Field(
        default=["http://localhost:8501", "http://localhost:3000"],
        env="CORS_ORIGINS"
    )

    # File Upload
    upload_dir: str = Field(default="./backend/documents/uploads", env="UPLOAD_DIR")
    max_file_size_mb: int = Field(default=50, env="MAX_FILE_SIZE_MB")
    allowed_extensions: List[str] = Field(default=["pdf", "docx", "txt"], env="ALLOWED_EXTENSIONS")

    # RAG
    chunk_size: int = Field(default=1000, env="CHUNK_SIZE")
    chunk_overlap: int = Field(default=200, env="CHUNK_OVERLAP")
    top_k_results: int = Field(default=5, env="TOP_K_RESULTS")

    # Rate Limiting
    rate_limit_per_minute: int = Field(default=30, env="RATE_LIMIT_PER_MINUTE")

    # Admin
    admin_email: str = Field(default="admin@helpdesk.ai", env="ADMIN_EMAIL")
    admin_password: str = Field(default="Admin@123456", env="ADMIN_PASSWORD")

    # Logging
    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    log_file: str = Field(default="./backend/logs/app.log", env="LOG_FILE")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    """Return cached settings instance (singleton pattern)."""
    return Settings()
