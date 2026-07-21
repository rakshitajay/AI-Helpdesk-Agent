"""
document_processor.py
---------------------
Handles loading and chunking of uploaded documents.

Supports:
  - PDF   : via PyPDFLoader
  - DOCX  : via Docx2txtLoader
  - TXT   : via TextLoader

Each file is split into overlapping chunks using RecursiveCharacterTextSplitter.
Chunk metadata includes: source filename, page number, file type.
"""

import os
from typing import List, Tuple
from langchain.schema import Document
from langchain_community.document_loaders import PyPDFLoader, Docx2txtLoader, TextLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from backend.config import get_settings
from backend.utils.logger import logger

settings = get_settings()


def load_document(file_path: str, file_type: str, original_name: str) -> List[Document]:
    """
    Load a document from disk and return a list of LangChain Document objects.

    Args:
        file_path    : Absolute path to the stored file.
        file_type    : 'pdf', 'docx', or 'txt'.
        original_name: The user-visible filename (for metadata).

    Returns:
        List of raw Document pages (not yet split).
    """
    logger.info(f"Loading document: {original_name} ({file_type})")

    try:
        if file_type == "pdf":
            loader = PyPDFLoader(file_path)
            docs = loader.load()

        elif file_type == "docx":
            loader = Docx2txtLoader(file_path)
            docs = loader.load()

        elif file_type == "txt":
            loader = TextLoader(file_path, encoding="utf-8")
            docs = loader.load()

        else:
            raise ValueError(f"Unsupported file type: {file_type}")

        # Enrich metadata for every page
        for i, doc in enumerate(docs):
            doc.metadata.update({
                "source": original_name,
                "file_type": file_type,
                "page": doc.metadata.get("page", i),
            })

        logger.info(f"Loaded {len(docs)} pages from {original_name}")
        return docs

    except Exception as e:
        logger.error(f"Failed to load document {original_name}: {e}")
        raise


def split_documents(docs: List[Document]) -> List[Document]:
    """
    Split loaded document pages into overlapping text chunks.

    Uses RecursiveCharacterTextSplitter with chunk_size and
    chunk_overlap from settings (defaults: 1000 / 200 chars).

    Returns:
        List of Document chunks ready for embedding.
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
        length_function=len,
        separators=["\n\n", "\n", ". ", " ", ""],
    )

    chunks = splitter.split_documents(docs)
    logger.info(f"Split into {len(chunks)} chunks (size={settings.chunk_size}, overlap={settings.chunk_overlap})")
    return chunks


def process_document(file_path: str, file_type: str, original_name: str) -> Tuple[List[Document], int]:
    """
    Full pipeline: load → split → return chunks.

    Returns:
        Tuple of (chunks list, chunk count).
    """
    docs = load_document(file_path, file_type, original_name)
    chunks = split_documents(docs)
    return chunks, len(chunks)


def validate_file(filename: str, file_size: int) -> Tuple[bool, str]:
    """
    Validate filename extension and file size against settings.

    Returns:
        (is_valid: bool, error_message: str)
    """
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    if ext not in settings.allowed_extensions:
        return False, f"File type '.{ext}' not allowed. Allowed: {settings.allowed_extensions}"

    max_bytes = settings.max_file_size_mb * 1024 * 1024
    if file_size > max_bytes:
        return False, f"File size {file_size / 1024 / 1024:.1f} MB exceeds limit of {settings.max_file_size_mb} MB"

    return True, ""
