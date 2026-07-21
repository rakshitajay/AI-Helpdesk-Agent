"""
embeddings.py
-------------
Google Generative AI embedding wrapper for LangChain.
Used by both the document indexer and the RAG retriever.
"""

from langchain_google_genai import GoogleGenerativeAIEmbeddings
from backend.config import get_settings
from backend.utils.logger import logger

settings = get_settings()


def get_embeddings() -> GoogleGenerativeAIEmbeddings:
    """
    Return a configured Google embedding model instance.
    Uses the model specified in settings (default: models/embedding-001).
    """
    if not settings.google_api_key:
        raise ValueError(
            "GOOGLE_API_KEY is not set. "
            "Get your key at https://aistudio.google.com/app/apikey"
        )

    logger.debug(f"Initializing embedding model: {settings.embedding_model}")
    return GoogleGenerativeAIEmbeddings(
        model=settings.embedding_model,
        google_api_key=settings.google_api_key,
    )
