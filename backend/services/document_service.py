"""
services/document_service.py
-----------------------------
Handles document upload, validation, indexing (RAG ingestion),
deletion, and listing.
"""

import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from fastapi import UploadFile, HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config.settings import settings
from backend.core.rag_pipeline import get_rag_pipeline
from backend.database.models import Document
from backend.models.schemas import DocumentResponse, DocumentUploadResponse
from backend.utils.logger import logger


class DocumentService:
    """All document management operations."""

    def __init__(self):
        # Ensure upload directory exists
        Path(settings.UPLOAD_DIR).mkdir(parents=True, exist_ok=True)

    # ── Validation ────────────────────────────────────────────────────────────

    def _validate_file(self, file: UploadFile) -> str:
        """
        Check file extension and size are within allowed limits.

        Returns:
            Cleaned file extension (e.g. "pdf").

        Raises:
            HTTPException 400 if invalid.
        """
        filename = file.filename or ""
        ext = Path(filename).suffix.lower().lstrip(".")

        if ext not in settings.allowed_extensions_list:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported file type '{ext}'. "
                       f"Allowed: {', '.join(settings.allowed_extensions_list)}",
            )
        return ext

    # ── Upload & Index ────────────────────────────────────────────────────────

    async def upload_and_index(
        self,
        db: AsyncSession,
        file: UploadFile,
        uploader_id: int,
        description: Optional[str] = None,
        tags: Optional[str] = None,
    ) -> DocumentUploadResponse:
        """
        Save uploaded file to disk, persist metadata to DB,
        then run the RAG ingestion pipeline.

        Args:
            db:           Database session.
            file:         FastAPI UploadFile object.
            uploader_id:  User ID of the uploader (must be admin).
            description:  Optional document description.
            tags:         Comma-separated tags.

        Returns:
            DocumentUploadResponse with chunk count and status.
        """
        ext = self._validate_file(file)
        original_name = file.filename or "document"

        # Build unique filename to avoid collisions
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        safe_name = f"{timestamp}_{original_name.replace(' ', '_')}"
        file_path = Path(settings.UPLOAD_DIR) / safe_name

        # Read file contents
        contents = await file.read()
        file_size = len(contents)

        # Enforce size limit
        if file_size > settings.max_file_size_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File exceeds the {settings.MAX_FILE_SIZE_MB} MB limit "
                       f"({file_size / 1024 / 1024:.1f} MB received)",
            )

        # Write to disk
        with open(file_path, "wb") as f:
            f.write(contents)
        logger.info(f"File saved to disk: {file_path}")

        # Persist metadata record
        doc = Document(
            filename=safe_name,
            original_filename=original_name,
            file_type=ext,
            file_size=file_size,
            file_path=str(file_path),
            uploaded_by=uploader_id,
            description=description,
            tags=tags,
        )
        db.add(doc)
        await db.flush()

        # Run RAG ingestion
        try:
            print("=" * 60)
            print("STARTING INDEXING")
            print("File:", file_path)
            print("Document ID:", doc.id)
            pipeline = get_rag_pipeline()
            chunk_count = pipeline.ingest_document(str(file_path), doc.id)
            print("Chunk count:", chunk_count)
            doc.chunk_count = chunk_count
            doc.is_indexed = True
            doc.indexed_at = datetime.utcnow()
            await db.flush()
            print("INDEXING SUCCESS")
            print("=" * 60)
            logger.info(f"Document indexed: id={doc.id} chunks={chunk_count}")
        except Exception as e:
            print("=" * 60)
            print("INDEXING FAILED")
            print(type(e))
            print(e)
            print("=" * 60)
            logger.error(f"Indexing failed for document {doc.id}: {e}")
            # Keep the file in DB as not indexed – admin can retry
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"File uploaded but indexing failed: {str(e)}",
            )

        return DocumentUploadResponse(
             id=doc.id,
             original_name=original_name,
             file_type=ext,
             file_size=file_size,
            message="Document uploaded and indexed successfully",
            is_indexed=True,
           
        )

    # ── Listing ───────────────────────────────────────────────────────────────

    async def list_documents(self, db: AsyncSession) -> List[DocumentResponse]:
        """Return all documents ordered by upload date."""
        result = await db.execute(
            select(Document).order_by(Document.uploaded_at.desc())
        )
        docs = result.scalars().all()
        return [DocumentResponse.model_validate(d) for d in docs]

    async def get_document(self, db: AsyncSession, doc_id: int) -> Optional[Document]:
        """Fetch a single document by ID."""
        result = await db.execute(select(Document).where(Document.id == doc_id))
        return result.scalar_one_or_none()

    # ── Deletion ──────────────────────────────────────────────────────────────

    async def delete_document(self, db: AsyncSession, doc_id: int) -> bool:
        """
        Delete document from:
          1. ChromaDB vector store
          2. Filesystem
          3. SQLite metadata table

        Returns:
            True on success, False if document not found.
        """
        result = await db.execute(select(Document).where(Document.id == doc_id))
        doc = result.scalar_one_or_none()
        if not doc:
            return False

        # Remove from vector store
        pipeline = get_rag_pipeline()
        pipeline.vector_store.delete_document(doc_id)

        # Remove file from disk
        file_path = Path(doc.file_path)
        if file_path.exists():
            file_path.unlink()
            logger.info(f"File deleted from disk: {file_path}")

        # Remove DB record
        await db.delete(doc)
        await db.flush()
        logger.info(f"Document deleted: id={doc_id}")
        return True

    # ── Re-indexing ───────────────────────────────────────────────────────────

    async def reindex_document(self, db: AsyncSession, doc_id: int) -> DocumentUploadResponse:
        """
        Re-run ingestion on an already-uploaded document.
        Useful if the document was uploaded but indexing failed.
        """
        result = await db.execute(select(Document).where(Document.id == doc_id))
        doc = result.scalar_one_or_none()

        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")

        if not Path(doc.file_path).exists():
            raise HTTPException(status_code=404, detail="File not found on disk")

        # Remove old vectors first
        pipeline = get_rag_pipeline()
        pipeline.vector_store.delete_document(doc_id)

        # Re-ingest
        chunk_count = pipeline.ingest_document(doc.file_path, doc.id)
        doc.chunk_count = chunk_count
        doc.is_indexed = True
        doc.indexed_at = datetime.utcnow()
        await db.flush()

        return DocumentUploadResponse(
             id=doc.id,
             original_name=doc.original_filename,
              file_type=doc.file_type,
              file_size=doc.file_size,
            message="Document re-indexed successfully",
             is_indexed=True,
        )

    async def rebuild_all(self, db: AsyncSession) -> dict:
        """
        Rebuild entire vector store from all indexed documents.
        Admin-only nuclear option.
        """
        pipeline = get_rag_pipeline()
        pipeline.vector_store.rebuild_index()

        result = await db.execute(
            select(Document).where(Document.is_indexed == True)
        )
        docs = result.scalars().all()

        total_chunks = 0
        for doc in docs:
            if Path(doc.file_path).exists():
                chunks = pipeline.ingest_document(doc.file_path, doc.id)
                total_chunks += chunks
                doc.chunk_count = chunks
                doc.indexed_at = datetime.utcnow()

        await db.flush()
        logger.info(f"Full rebuild complete: {len(docs)} docs, {total_chunks} chunks")
        return {"documents_reindexed": len(docs), "total_chunks": total_chunks}


# Singleton
document_service = DocumentService()
