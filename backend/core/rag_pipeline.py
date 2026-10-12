"""
core/rag_pipeline.py
---------------------
Complete Retrieval-Augmented Generation (RAG) pipeline.

Stages:
  1. Document loading  (PDF / DOCX / TXT)
  2. Text chunking     (RecursiveCharacterTextSplitter)
  3. Embedding         (Google text-embedding-004)
  4. Vector storage    (ChromaDB)
  5. Retrieval         (similarity search, top-k)
  6. Query rewriting   (for better retrieval)
  7. Answer generation (Gemini 2.5 Flash)
  8. Citation building
"""

import json
import time
from pathlib import Path
from typing import List, Optional, Tuple

import chromadb
from chromadb.config import Settings as ChromaSettings
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import (
    PyPDFLoader,
    Docx2txtLoader,
    TextLoader,
)
from langchain.schema import Document
from langchain.prompts import PromptTemplate
from tenacity import retry, stop_after_attempt, wait_exponential

from backend.config.settings import get_settings
settings = get_settings()
from backend.models.schemas import SourceDocument
from backend.utils.logger import logger


# ══════════════════════════════════════════════════════════════════════════════
# PROMPT TEMPLATES
# ══════════════════════════════════════════════════════════════════════════════

RAG_PROMPT_TEMPLATE = """You are an expert AI Helpdesk Assistant. Answer the user's question 
based ONLY on the provided context documents. 

Rules:
- If the context doesn't contain enough information, say "I don't have enough information 
  in the uploaded documents to answer this accurately."
- Always cite which document/section your answer comes from.
- Be concise, accurate, and professional.
- If asked in a language other than English, respond in the same language.
- Do NOT make up information that isn't in the context.

Context Documents:
{context}

Conversation History:
{chat_history}

User Question: {question}

Provide a helpful, accurate answer with source references:"""


QUERY_REWRITE_TEMPLATE = """Rewrite the following user question to make it more effective 
for semantic search in a document database. Make it clearer and more specific.
Only return the rewritten question, nothing else.

Original question: {question}
Rewritten question:"""


SUGGESTED_QUESTIONS_TEMPLATE = """Based on this answer about the topic, generate exactly 3 
short follow-up questions a user might ask. Return them as a JSON array of strings.
Only return the JSON array, nothing else.

Answer: {answer}
Follow-up questions (JSON array):"""


# ══════════════════════════════════════════════════════════════════════════════
# DOCUMENT LOADER
# ══════════════════════════════════════════════════════════════════════════════

class DocumentLoader:
    """Loads PDF, DOCX, and TXT files into LangChain Document objects."""

    @staticmethod
    def load(file_path: str) -> List[Document]:
        """
        Load a document based on its file extension.

        Args:
            file_path: Absolute or relative path to the document.

        Returns:
            List of LangChain Document objects (one per page/chunk from loader).

        Raises:
            ValueError: If the file type is unsupported.
            FileNotFoundError: If the file doesn't exist.
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        ext = path.suffix.lower().lstrip(".")
        logger.info(f"Loading document: {path.name} (type={ext})")

        loaders = {
            "pdf":  lambda: PyPDFLoader(str(path)),
            "docx": lambda: Docx2txtLoader(str(path)),
            "txt":  lambda: TextLoader(str(path), encoding="utf-8"),
        }

        if ext not in loaders:
            raise ValueError(f"Unsupported file type: {ext}")

        loader = loaders[ext]()
        docs = loader.load()

        # Enrich metadata
        for doc in docs:
            doc.metadata["source_file"] = path.name
            doc.metadata["file_type"] = ext

        logger.info(f"Loaded {len(docs)} pages/sections from {path.name}")
        return docs


# ══════════════════════════════════════════════════════════════════════════════
# TEXT SPLITTER
# ══════════════════════════════════════════════════════════════════════════════

class TextChunker:
    """Splits documents into overlapping chunks for embedding."""

    def __init__(self):
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=settings.CHUNK_SIZE,
            chunk_overlap=settings.CHUNK_OVERLAP,
            length_function=len,
            separators=["\n\n", "\n", ". ", " ", ""],
        )

    def split(self, documents: List[Document]) -> List[Document]:
        """
        Split a list of documents into smaller overlapping chunks.

        Returns:
            List of Document chunks with enriched metadata.
        """
        chunks = self.splitter.split_documents(documents)

        # Add chunk index to metadata
        for i, chunk in enumerate(chunks):
            chunk.metadata["chunk_index"] = i

        logger.info(f"Split into {len(chunks)} chunks")
        return chunks


# ══════════════════════════════════════════════════════════════════════════════
# VECTOR STORE MANAGER
# ══════════════════════════════════════════════════════════════════════════════

class VectorStoreManager:
    """Manages ChromaDB vector store operations: add, search, delete."""

    def __init__(self):
        # Ensure persist directory exists
        Path(settings.CHROMA_PERSIST_DIR).mkdir(parents=True, exist_ok=True)

        # Initialise persistent ChromaDB client
        self.client = chromadb.PersistentClient(
            path=settings.CHROMA_PERSIST_DIR,
        )

        # Google embeddings
        self.embeddings = GoogleGenerativeAIEmbeddings(
            model=settings.EMBEDDING_MODEL,
            google_api_key=settings.GOOGLE_API_KEY,
        )

        # Get or create collection
        self.collection = self.client.get_or_create_collection(
            name=settings.CHROMA_COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )

        logger.info(
            f"VectorStore ready | collection={settings.CHROMA_COLLECTION_NAME} "
            f"| docs={self.collection.count()}"
        )

    def add_documents(self, chunks: List[Document], document_id: int) -> int:
        """
        Embed and store document chunks in ChromaDB.

        Args:
            chunks: Text chunks from TextChunker.
            document_id: DB id of the parent document for metadata.

        Returns:
            Number of chunks stored.
        """
        if not chunks:
            return 0

        texts = [chunk.page_content for chunk in chunks]
        metadatas = [
            {
                **chunk.metadata,
                "document_id": str(document_id),
            }
            for chunk in chunks
        ]
        ids = [f"doc_{document_id}_chunk_{i}" for i in range(len(chunks))]

        # Generate embeddings via Google API
        logger.info(f"Generating embeddings for {len(texts)} chunks...")
        embeddings = self.embeddings.embed_documents(texts)

        self.collection.add(
            documents=texts,
            embeddings=embeddings,
            metadatas=metadatas,
            ids=ids,
        )

        logger.info(f"Stored {len(chunks)} chunks for document_id={document_id}")
        return len(chunks)

    def search(
        self,
        query: str,
        top_k: int = None,
        document_id: int = None,
    ):
        """
        Perform semantic similarity search.
        """
        k = top_k or settings.TOP_K_RESULTS

        # Embed the query
        query_embedding = self.embeddings.embed_query(query)

        # Search Chroma
        if document_id is not None:
            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=min(k, max(self.collection.count(), 1)),
                where={"document_id": str(document_id)},
                include=["documents", "metadatas", "distances"],
            )
        else:
            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=min(k, max(self.collection.count(), 1)),
                include=["documents", "metadatas", "distances"],
            )
            print("=" * 60)
            print("REQUESTED DOCUMENT:", document_id)
            print("RETURNED METADATA:", results["metadatas"])
            print("=" * 60)

        docs = []

        if results["documents"]:
            for doc, meta, dist in zip(
                results["documents"][0],
                results["metadatas"][0],
                results["distances"][0],
            ):
                similarity = 1 - dist

                if similarity >= settings.SIMILARITY_THRESHOLD:
                    docs.append(
                        {
                            "content": doc,
                            "metadata": meta,
                            "score": round(similarity, 4),
                        }
                    )

        logger.info(f"Search returned {len(docs)} relevant chunks")
        return docs

    def delete_document(self, document_id: int) -> bool:
        """Remove all chunks belonging to a specific document."""
        try:
            # Find all IDs for this document
            prefix = f"doc_{document_id}_chunk_"
            results = self.collection.get(where={"document_id": str(document_id)})
            ids_to_delete = results.get("ids", [])

            if ids_to_delete:
                self.collection.delete(ids=ids_to_delete)
                logger.info(f"Deleted {len(ids_to_delete)} chunks for document_id={document_id}")

            return True
        except Exception as e:
            logger.error(f"Error deleting document {document_id}: {e}")
            return False

    def rebuild_index(self) -> int:
        """Delete entire collection and recreate it (admin action)."""
        self.client.delete_collection(settings.CHROMA_COLLECTION_NAME)
        self.collection = self.client.get_or_create_collection(
            name=settings.CHROMA_COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
        logger.warning("Vector store index rebuilt from scratch")
        return 0

    def get_stats(self) -> dict:
        """Return stats about the vector store."""
        return {"total_chunks": self.collection.count()}


# ══════════════════════════════════════════════════════════════════════════════
# RAG PIPELINE
# ══════════════════════════════════════════════════════════════════════════════

class RAGPipeline:
    """
    Orchestrates the full RAG workflow:
    Question → Rewrite → Embed → Retrieve → Prompt → Gemini → Answer + Citations
    """

    def __init__(self):
        self.vector_store = VectorStoreManager()
        self.chunker = TextChunker()
        self.loader = DocumentLoader()

        # Gemini LLM
        self.llm = ChatGoogleGenerativeAI(
            model=settings.GEMINI_MODEL,
            google_api_key=settings.GOOGLE_API_KEY,
            temperature=0.1,      # Low temperature = factual, less creative
            max_output_tokens=2048,
        )

        # Prompt templates
        self.rag_prompt = PromptTemplate(
            template=RAG_PROMPT_TEMPLATE,
            input_variables=["context", "chat_history", "question"],
        )
        self.rewrite_prompt = PromptTemplate(
            template=QUERY_REWRITE_TEMPLATE,
            input_variables=["question"],
        )
        self.suggestions_prompt = PromptTemplate(
            template=SUGGESTED_QUESTIONS_TEMPLATE,
            input_variables=["answer"],
        )

    def ingest_document(self, file_path: str, document_id: int) -> int:
        """
        Full ingestion pipeline: load → chunk → embed → store.

        Returns:
            Number of chunks stored.
        """
        print("Loading file:", file_path)
        docs = self.loader.load(file_path)
        print("Pages loaded:", len(docs))
        
        chunks = self.chunker.split(docs)
        print("Chunks:", len(chunks))
        count = self.vector_store.add_documents(chunks, document_id)
        print("Stored chunks:", count)
        return count

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def _rewrite_query(self, question: str) -> str:
        """Use Gemini to rewrite the query for better retrieval."""
        try:
            prompt_text = self.rewrite_prompt.format(question=question)
            response = self.llm.invoke(prompt_text)
            rewritten = response.content.strip()
            logger.debug(f"Query rewritten: '{question}' → '{rewritten}'")
            return rewritten
        except Exception as e:
            logger.warning(f"Query rewrite failed, using original: {e}")
            return question

    def _build_context(self, retrieved_docs: List[dict]) -> str:
        """Format retrieved chunks into a numbered context string for the prompt."""
        context_parts = []
        for i, doc in enumerate(retrieved_docs, 1):
            meta = doc["metadata"]
            source = meta.get("source_file", "Unknown")
            page = meta.get("page", "")
            page_str = f" (page {page})" if page else ""
            score = doc["score"]
            context_parts.append(
                f"[Source {i}: {source}{page_str} | Relevance: {score:.0%}]\n"
                f"{doc['content']}\n"
            )
        return "\n---\n".join(context_parts)

    def _build_sources(self, retrieved_docs: List[dict]) -> List[SourceDocument]:
        """Convert raw search results into SourceDocument response objects."""
        sources = []
        for doc in retrieved_docs:
            meta = doc["metadata"]
            sources.append(SourceDocument(
                filename=meta.get("source_file", "Unknown"),
                page_number=meta.get("page"),
                chunk_index=meta.get("chunk_index", 0),
                content_preview=doc["content"][:200] + "..." if len(doc["content"]) > 200 else doc["content"],
                relevance_score=doc["score"],
            ))
        return sources

    def _calculate_confidence(self, retrieved_docs: List[dict]) -> float:
        """
        Compute an overall confidence score from retrieved chunk scores.
        Uses weighted average with more weight on top results.
        """
        if not retrieved_docs:
            return 0.0
        scores = [d["score"] for d in retrieved_docs]
        # Weights: 40% top, 30% second, 20% third, 10% rest
        weights = [0.4, 0.3, 0.2, 0.05, 0.05]
        weighted = sum(s * w for s, w in zip(scores, weights[:len(scores)]))
        return round(min(weighted, 1.0), 3)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def _get_suggested_questions(self, answer: str) -> List[str]:
        """Generate 3 follow-up questions based on the answer."""
        try:
            prompt_text = self.suggestions_prompt.format(answer=answer[:500])
            response = self.llm.invoke(prompt_text)
            raw = response.content.strip()
            # Strip markdown code fences if present
            raw = raw.replace("```json", "").replace("```", "").strip()
            suggestions = json.loads(raw)
            return suggestions[:3] if isinstance(suggestions, list) else []
        except Exception as e:
            logger.warning(f"Could not generate suggestions: {e}")
            return []

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def answer(
        self,
        question: str,
        chat_history: str = "",
        language: str = "en",
        document_id: int | None = None,
    ) -> Tuple[str, List[SourceDocument], float, List[str], int]:
        """
        Full RAG pipeline execution.

        Args:
            question:     User's raw question.
            chat_history: Last N messages formatted as string for context.
            language:     ISO language code (e.g. "en", "hi", "fr").

        Returns:
            Tuple of (answer, sources, confidence_score, suggested_questions, response_time_ms)
        """
        start_time = time.time()

        # Step 1: Rewrite query for better retrieval
        rewritten_query = self._rewrite_query(question)

        # Step 2: Retrieve relevant chunks
        print("ANSWER() DOCUMENT ID =", document_id)
        retrieved_docs = self.vector_store.search(
            rewritten_query,
            document_id=document_id,
            )

        if not retrieved_docs:
            # No relevant documents found
            answer_text = (
                "I couldn't find relevant information in the uploaded documents "
                "to answer your question. Please try rephrasing, or ask an admin "
                "to upload documents covering this topic."
            )
            elapsed = int((time.time() - start_time) * 1000)
            return answer_text, [], 0.0, [], elapsed

        # Step 3: Build context string
        context = self._build_context(retrieved_docs)

        # Step 4: Add language instruction if not English
        lang_instruction = ""
        if language != "en":
            lang_instruction = f"\nIMPORTANT: Respond in the language with code '{language}'."

        # Step 5: Build the final prompt
        prompt_text = self.rag_prompt.format(
            context=context,
            chat_history=chat_history or "No previous conversation.",
            question=question + lang_instruction,
        )

        # Step 6: Call Gemini
        logger.info(f"Calling Gemini with {len(retrieved_docs)} context chunks...")
        response = self.llm.invoke(prompt_text)
        answer_text = response.content.strip()

        # Step 7: Post-processing
        sources = self._build_sources(retrieved_docs)
        confidence = self._calculate_confidence(retrieved_docs)
        suggestions = self._get_suggested_questions(answer_text)

        elapsed = int((time.time() - start_time) * 1000)
        logger.info(
            f"RAG complete | confidence={confidence} | "
            f"sources={len(sources)} | time={elapsed}ms"
        )

        return answer_text, sources, confidence, suggestions, elapsed


# ── Module-level singleton ─────────────────────────────────────────────────────
# Shared across all FastAPI workers to avoid recreating ChromaDB connections
_rag_pipeline: Optional[RAGPipeline] = None


def get_rag_pipeline() -> RAGPipeline:
    """Return the shared RAGPipeline singleton (lazy init)."""
    global _rag_pipeline
    if _rag_pipeline is None:
        _rag_pipeline = RAGPipeline()
    return _rag_pipeline
