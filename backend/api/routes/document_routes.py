"""
document_routes.py
------------------
Document management endpoints:
  POST   /api/documents/upload     - Upload and index a document
  GET    /api/documents/           - List all documents
  GET    /api/documents/{id}       - Get document metadata
  DELETE /api/documents/{id}       - Delete document + ChromaDB chunks
  POST   /api/documents/{id}/reindex - Re-index a specific document
"""

import os
import uuid
from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.database.models import User, Document
from backend.authentication.auth import get_current_user, require_admin
from backend.models.schemas import DocumentResponse, DocumentUploadResponse, MessageResponse
from backend.utils.document_processor import process_document, validate_file
from backend.vector_db.chroma_store import add_documents, delete_document_chunks
from backend.config import get_settings
from backend.utils.logger import logger

router = APIRouter(prefix="/api/documents", tags=["Documents"])
settings = get_settings()


@router.post("/upload", response_model=DocumentUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(...),
    description: str = Form(default=""),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Upload a PDF, DOCX, or TXT file.
    Automatically processes and indexes it into ChromaDB.
    Both regular users and admins can upload.
    """
    # Read file bytes for size check
    file_bytes = await file.read()
    file_size = len(file_bytes)

    # Validate
    is_valid, error_msg = validate_file(file.filename, file_size)
    if not is_valid:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error_msg)

    # Determine file extension
    ext = file.filename.rsplit(".", 1)[-1].lower()

    # Generate unique filename to avoid collisions
    unique_name = f"{uuid.uuid4().hex}_{file.filename}"
    os.makedirs(settings.upload_dir, exist_ok=True)
    file_path = os.path.join(settings.upload_dir, unique_name)

    # Save to disk
    with open(file_path, "wb") as f:
        f.write(file_bytes)
    logger.info(f"File saved: {file_path}")

    # Create DB record first (get document ID for ChromaDB metadata)
    doc = Document(
        filename=unique_name,
        original_name=file.filename,
        file_type=ext,
        file_size=file_size,
        file_path=file_path,
        uploaded_by=current_user.id,
        description=description,
        is_indexed=False,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    # Process and index
    try:
        chunks, chunk_count = process_document(file_path, ext, file.filename)
        indexed_count = add_documents(chunks, doc.id)

        doc.chunk_count = indexed_count
        doc.is_indexed = True
        doc.indexed_at = datetime.utcnow()
        db.commit()

        logger.info(f"Document indexed: {file.filename} → {indexed_count} chunks")
        return DocumentUploadResponse(
            id=doc.id,
            original_name=doc.original_name,
            file_type=doc.file_type,
            file_size=doc.file_size,
            message=f"Successfully uploaded and indexed {indexed_count} chunks.",
            is_indexed=True,
        )

    except Exception as e:
        logger.error(f"Indexing failed for {file.filename}: {e}")
        doc.is_indexed = False
        db.commit()
        return DocumentUploadResponse(
            id=doc.id,
            original_name=doc.original_name,
            file_type=doc.file_type,
            file_size=doc.file_size,
            message=f"File uploaded but indexing failed: {str(e)}",
            is_indexed=False,
        )


@router.get("/", response_model=List[DocumentResponse])
def list_documents(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Return all uploaded documents (visible to all authenticated users)."""
    docs = db.query(Document).order_by(Document.created_at.desc()).all()
    return docs


@router.get("/{document_id}", response_model=DocumentResponse)
def get_document(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get metadata for a specific document."""
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")
    return doc


@router.delete("/{document_id}", response_model=MessageResponse)
def delete_document(
    document_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Admin only: Delete a document from disk, ChromaDB, and the database.
    """
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")

    # Delete ChromaDB chunks
    delete_document_chunks(document_id)

    # Delete file from disk
    if os.path.exists(doc.file_path):
        os.remove(doc.file_path)
        logger.info(f"File deleted from disk: {doc.file_path}")

    # Delete DB record
    db.delete(doc)
    db.commit()
    logger.info(f"Document deleted: {doc.original_name} (id={document_id})")
    return MessageResponse(message=f"Document '{doc.original_name}' deleted successfully.", success=True)


@router.post("/{document_id}/reindex", response_model=MessageResponse)
def reindex_document(
    document_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Admin only: Re-process and re-index an existing document.
    Useful after changing chunk_size / chunk_overlap settings.
    """
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")

    if not os.path.exists(doc.file_path):
        raise HTTPException(status_code=404, detail="Source file not found on disk.")

    # Remove old chunks
    delete_document_chunks(document_id)

    # Re-process and index
    try:
        chunks, chunk_count = process_document(doc.file_path, doc.file_type, doc.original_name)
        indexed_count = add_documents(chunks, doc.id)
        doc.chunk_count = indexed_count
        doc.is_indexed = True
        doc.indexed_at = datetime.utcnow()
        db.commit()
        return MessageResponse(
            message=f"Re-indexed '{doc.original_name}' with {indexed_count} chunks.",
            success=True
        )
    except Exception as e:
        logger.error(f"Re-indexing failed for document {document_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Re-indexing failed: {str(e)}")
