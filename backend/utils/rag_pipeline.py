"""
rag_pipeline.py
---------------
Core RAG (Retrieval-Augmented Generation) pipeline.

Full flow:
  1. Rewrite query for better retrieval
  2. Embed query and search ChromaDB
  3. Build context from top-k chunks
  4. Send context + question to Gemini 2.5 Flash
  5. Parse answer, confidence score, suggested follow-ups
  6. Return structured RAGResult

Uses LangChain prompt templates + Google Gemini via langchain-google-genai.
"""

import time
from dataclasses import dataclass, field
from typing import List, Optional
from langchain_groq import ChatGroq
from langchain.prompts import PromptTemplate
from langchain.schema import Document
from backend.vector_db.chroma_store import similarity_search
from backend.config import get_settings
from backend.utils.logger import logger

settings = get_settings()


# ── Data Classes ──────────────────────────────────────────────

@dataclass
class SourceCitation:
    document_name: str
    page_number: Optional[int]
    chunk_text: str
    relevance_score: float


@dataclass
class RAGResult:
    answer: str
    sources: List[SourceCitation]
    confidence_score: float
    suggested_questions: List[str]
    response_time_ms: float
    query_used: str   # possibly rewritten query


# ── Prompt Templates ──────────────────────────────────────────

QUERY_REWRITE_TEMPLATE = PromptTemplate(
    input_variables=["question", "chat_history"],
    template="""You are a query optimization assistant. Your task is to rewrite the user's
question to be more specific and retrieval-friendly for a document search system.

Chat history (last 3 exchanges):
{chat_history}

Original question: {question}

Rewrite the question to be standalone, specific, and optimized for semantic search.
Return ONLY the rewritten question, nothing else."""
)

RAG_ANSWER_TEMPLATE = PromptTemplate(
    input_variables=["context", "question", "chat_history", "language"],
    template="""You are a professional AI Helpdesk Assistant. Answer the user's question
using ONLY the information provided in the context below.

CRITICAL RULES:
- Base your answer strictly on the provided context
- If the context doesn't contain enough information, say so clearly
- Never make up information not present in the context
- Cite the source document when referencing specific information
- Be concise but comprehensive
- Format the answer clearly using markdown if helpful
- Respond in the language: {language}

=== CONTEXT ===
{context}

=== CHAT HISTORY ===
{chat_history}

=== USER QUESTION ===
{question}

=== YOUR ANSWER ===
Provide a helpful, accurate answer based strictly on the context above.

After your answer, on a new line, output exactly:
CONFIDENCE: [number between 0.0 and 1.0 reflecting how well the context answers the question]
SUGGESTED_QUESTIONS:
- [follow-up question 1]
- [follow-up question 2]
- [follow-up question 3]"""
)


# ── LLM Factory ───────────────────────────────────────────────

import os
from langchain_groq import ChatGroq

def get_llm():
    api_key = os.getenv("GROQ_API_KEY")

    if not api_key:
        raise ValueError("GROQ_API_KEY is not configured")

    return ChatGroq(
        model=os.getenv("GROQ_MODEL", "openai/gpt-oss-20b"),
        api_key=api_key,
        temperature=0.2,
        max_tokens=2048,
    )


# ── Query Rewriter ────────────────────────────────────────────

def rewrite_query(question: str, chat_history: str) -> str:
    """
    Use Gemini to rewrite the user's question for better retrieval.
    Falls back to the original question on any error.
    """
    if not chat_history.strip():
        return question  # No history → no rewrite needed

    try:
        llm = get_llm()
        prompt = QUERY_REWRITE_TEMPLATE.format(
            question=question,
            chat_history=chat_history
        )
        response = llm.invoke(prompt)
        rewritten = response.content.strip()
        logger.debug(f"Query rewritten: '{question}' → '{rewritten}'")
        return rewritten
    except Exception as e:
        logger.warning(f"Query rewrite failed, using original: {e}")
        return question


# ── Context Builder ───────────────────────────────────────────

def build_context(docs: List[Document]) -> str:
    """Format retrieved document chunks into a numbered context block."""
    context_parts = []
    for i, doc in enumerate(docs, 1):
        source = doc.metadata.get("source", "Unknown")
        page = doc.metadata.get("page", "N/A")
        score = doc.metadata.get("relevance_score", 0.0)
        context_parts.append(
            f"[Source {i}: {source} | Page: {page} | Relevance: {score:.2f}]\n{doc.page_content}"
        )
    return "\n\n---\n\n".join(context_parts)


# ── Response Parser ───────────────────────────────────────────

def parse_llm_response(raw_response: str) -> tuple[str, float, List[str]]:
    """
    Parse LLM output into (answer, confidence_score, suggested_questions).

    Expected format:
        <answer text>
        CONFIDENCE: 0.85
        SUGGESTED_QUESTIONS:
        - question 1
        - question 2
        - question 3
    """
    answer = raw_response
    confidence = 0.7
    suggested = []

    try:
        if "CONFIDENCE:" in raw_response:
            parts = raw_response.split("CONFIDENCE:")
            answer = parts[0].strip()
            remainder = parts[1].strip()

            # Extract confidence score
            conf_line = remainder.split("\n")[0].strip()
            try:
                confidence = float(conf_line)
                confidence = max(0.0, min(1.0, confidence))
            except ValueError:
                pass

            # Extract suggested questions
            if "SUGGESTED_QUESTIONS:" in remainder:
                sq_part = remainder.split("SUGGESTED_QUESTIONS:")[1]
                for line in sq_part.strip().split("\n"):
                    line = line.strip().lstrip("-").strip()
                    if line:
                        suggested.append(line)

    except Exception as e:
        logger.warning(f"Response parsing error: {e}")

    return answer, confidence, suggested[:3]


# ── Main RAG Pipeline ─────────────────────────────────────────

def run_rag_pipeline(
    question: str,
    chat_history: List[dict] = None,
    language: str = "en",
    document_id: int | None = None,
) -> RAGResult:
    """
    Execute the full RAG pipeline:
      1. Rewrite query using chat history
      2. Retrieve top-k document chunks from ChromaDB
      3. Build context string
      4. Send to Gemini with prompt template
      5. Parse response into structured RAGResult

    Args:
        question    : Raw user question.
        chat_history: List of {"role": ..., "content": ...} dicts.
        language    : Target language code for the response.

    Returns:
        RAGResult dataclass with all fields populated.
    """
    start_time = time.time()
    chat_history = chat_history or []

    # Format chat history for prompts (last 6 messages = 3 exchanges)
    history_str = "\n".join([
        f"{msg['role'].upper()}: {msg['content']}"
        for msg in chat_history[-6:]
    ])

    # Step 1: Query rewriting
    rewritten_query = rewrite_query(question, history_str)

    # Step 2: Retrieval
    retrieved_docs = similarity_search(rewritten_query,
                                 document_id=document_id,
                                 k=settings.top_k_results,
                                 )

    if not retrieved_docs:
        logger.warning(f"No documents retrieved for query: {rewritten_query}")
        elapsed = (time.time() - start_time) * 1000
        return RAGResult(
            answer=(
                "I couldn't find relevant information in the uploaded documents to answer your question. "
                "Please ensure the relevant documents have been uploaded and indexed, "
                "or try rephrasing your question."
            ),
            sources=[],
            confidence_score=0.0,
            suggested_questions=[
                "What topics are covered in the uploaded documents?",
                "Can you upload more relevant documents?",
                "Could you rephrase your question?"
            ],
            response_time_ms=elapsed,
            query_used=rewritten_query,
        )

    # Step 3: Build context
    context = build_context(retrieved_docs)

    # Step 4: Generate answer via Gemini
    llm = get_llm()
    prompt = RAG_ANSWER_TEMPLATE.format(
        context=context,
        question=question,
        chat_history=history_str,
        language=language
    )

    try:
        response = llm.invoke(prompt)
        raw_answer = response.content
    except Exception as e:
        logger.error(f"LLM generation failed: {e}")
        raise

    # Step 5: Parse response
    answer, confidence, suggested_questions = parse_llm_response(raw_answer)

    # Step 6: Build source citations
    sources = []
    for doc in retrieved_docs:
        sources.append(SourceCitation(
            document_name=doc.metadata.get("source", "Unknown"),
            page_number=doc.metadata.get("page"),
            chunk_text=doc.page_content[:300] + "..." if len(doc.page_content) > 300 else doc.page_content,
            relevance_score=doc.metadata.get("relevance_score", 0.0),
        ))

    elapsed = (time.time() - start_time) * 1000
    logger.info(f"RAG pipeline completed in {elapsed:.0f}ms | confidence={confidence:.2f}")

    return RAGResult(
        answer=answer,
        sources=sources,
        confidence_score=confidence,
        suggested_questions=suggested_questions,
        response_time_ms=elapsed,
        query_used=rewritten_query,
    )
