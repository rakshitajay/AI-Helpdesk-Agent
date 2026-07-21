"""
api/routes/documents.py
------------------------
Document management endpoints (admin-only uploads/deletes):
  GET    /api/documents              – List all documents
  POST   /api/documents/upload       – Upload + index a document (admin)
  DELETE /api/documents/{id}         – Delete document (admin)
  POST   /api/documents/{id}/reindex – Re-index a document (admin)
  POST   /api/documents/rebuild      – Rebuild full vector store (admin)
  GET    /api/documents/stats        – Vector store statistics
"""

from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.authentication.dependencies import (
    get_current_active_user, get_current_admin_user
)
from backend.database.connection import get_db
from backend.database.models import User
from backend.models.schemas import (
    DocumentResponse, DocumentUploadResponse, SuccessResponse
)
from backend.services.document_service import document_service
from backend.core.rag_pipeline import get_rag_pipeline
from backend.utils.logger import logger

router = APIRouter(prefix="/api/documents", tags=["Documents"])


@router.get("/", response_model=List[DocumentResponse])
async def list_documents(
    _: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    List all uploaded documents (any authenticated user can see the list).
    Full document content is only accessible via the RAG pipeline.
    """
    return await document_service.list_documents(db)


@router.post("/upload", response_model=DocumentUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(...),
    description: Optional[str] = Form(None),
    tags: Optional[str] = Form(None),
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Upload a document and index it into ChromaDB.
    Supports PDF, DOCX, and TXT files up to MAX_FILE_SIZE_MB.
    Admin-only endpoint.
    """
    logger.info(
        f"Upload request: {file.filename} by admin {current_user.email}"
    )
    return await document_service.upload_and_index(
        db=db,
        file=file,
        uploader_id=current_user.id,
        description=description,
        tags=tags,
    )


@router.delete("/{doc_id}", response_model=SuccessResponse)
async def delete_document(
    doc_id: int,
    _: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Permanently delete a document from the filesystem, ChromaDB, and DB.
    Admin-only. This action cannot be undone.
    """
    deleted = await document_service.delete_document(db, doc_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Document {doc_id} not found")
    return SuccessResponse(message=f"Document {doc_id} deleted successfully")


@router.post("/{doc_id}/reindex", response_model=DocumentUploadResponse)
async def reindex_document(
    doc_id: int,
    _: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Re-index a single document that may have failed initial indexing."""
    return await document_service.reindex_document(db, doc_id)


@router.post("/rebuild", response_model=SuccessResponse)
async def rebuild_vector_store(
    _: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """
    WARNING: Wipe and rebuild the entire ChromaDB vector store.
    All documents will be re-ingested from disk.
    This is a long-running operation. Admin-only.
    """
    result = await document_service.rebuild_all(db)
    return SuccessResponse(
        message="Vector store rebuilt successfully",
        data=result,
    )


@router.get("/stats/vector-store")
async def vector_store_stats(
    _: User = Depends(get_current_admin_user),
):
    """Return ChromaDB statistics: total chunks stored."""
    pipeline = get_rag_pipeline()
    return pipeline.vector_store.get_stats()
