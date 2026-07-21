"""
chroma_store.py
---------------
ChromaDB vector store manager.
Provides:
  - get_vector_store()  : Load/create persistent ChromaDB collection
  - add_documents()     : Index document chunks
  - similarity_search() : Retrieve top-k relevant chunks
  - delete_document()   : Remove a document's chunks by metadata filter
  - rebuild_index()     : Drop and recreate the entire collection
"""

import os
from typing import List, Optional
import chromadb
from langchain_chroma import Chroma
from langchain.schema import Document
from backend.vector_db.embeddings import get_embeddings
from backend.config import get_settings
from backend.utils.logger import logger

settings = get_settings()


def get_vector_store() -> Chroma:
    """
    Load the persistent ChromaDB vector store.
    Creates the directory and collection if they don't exist.
    """
    os.makedirs(settings.chroma_persist_dir, exist_ok=True)
    embeddings = get_embeddings()

    logger.debug(f"Loading ChromaDB from: {settings.chroma_persist_dir}")
    return Chroma(
        collection_name=settings.chroma_collection_name,
        embedding_function=embeddings,
        persist_directory=settings.chroma_persist_dir,
    )


def add_documents(chunks: List[Document], document_id: int) -> int:
    """
    Add chunked document pages to ChromaDB.

    Each chunk gets metadata: document_id, source filename, page number.
    Returns the number of chunks indexed.
    """
    if not chunks:
        logger.warning("No chunks to index.")
        return 0

    # Attach document_id to every chunk's metadata
    for chunk in chunks:
        chunk.metadata["document_id"] = str(document_id)

    vector_store = get_vector_store()
    vector_store.add_documents(chunks)
    logger.info(f"Indexed {len(chunks)} chunks for document_id={document_id}")
    return len(chunks)


def similarity_search(
        query: str, 
        document_id: Optional[int] = None,
        k: int = None
        ) -> List[Document]:
    """
    Semantic similarity search against all indexed documents.

    Args:
        query: The user's question (raw text — will be embedded internally).
        k    : Number of chunks to retrieve (default from settings).

    Returns:
        List of Document objects with content + metadata + relevance scores.
    """
    k = k or settings.top_k_results
    vector_store = get_vector_store()

    try:
        if document_id is not None:
            results = vector_store.similarity_search_with_relevance_scores(
                query, 
                k=k, 
                filter={"document_id": str(document_id)}
            )
        else:
            results = vector_store.similarity_search_with_relevance_scores(
             query,
             k=k)
        # results: list of (Document, score) tuples
        docs = []
        for doc, score in results:
            doc.metadata["relevance_score"] = round(float(score), 4)
            docs.append(doc)
        logger.debug(f"Retrieved {len(docs)} chunks for query: '{query[:60]}...'")
        return docs
    except Exception as e:
        logger.error(f"Similarity search failed: {e}")
        return []


def delete_document_chunks(document_id: int) -> bool:
    """
    Delete all chunks belonging to a given document from ChromaDB.
    Uses metadata filter on 'document_id'.
    """
    try:
        client = chromadb.PersistentClient(path=settings.chroma_persist_dir)
        collection = client.get_collection(settings.chroma_collection_name)
        collection.delete(where={"document_id": str(document_id)})
        logger.info(f"Deleted chunks for document_id={document_id}")
        return True
    except Exception as e:
        logger.error(f"Failed to delete document chunks: {e}")
        return False


def rebuild_vector_index(all_chunks: List[Document]) -> int:
    """
    Drop the existing collection and re-index from scratch.
    Used by admin 'Rebuild Index' action.
    """
    try:
        client = chromadb.PersistentClient(path=settings.chroma_persist_dir)
        client.delete_collection(settings.chroma_collection_name)
        logger.info("Existing ChromaDB collection deleted.")
    except Exception as e:
        logger.warning(f"Could not delete collection (may not exist): {e}")

    if all_chunks:
        return add_documents(all_chunks, document_id=-1)
    return 0


def get_collection_stats() -> dict:
    """Return count of indexed vectors in the collection."""
    try:
        client = chromadb.PersistentClient(path=settings.chroma_persist_dir)
        collection = client.get_collection(settings.chroma_collection_name)
        return {"total_chunks": collection.count()}
    except Exception:
        return {"total_chunks": 0}
