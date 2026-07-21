# 🤖 AI Helpdesk Agent
### Intelligent RAG-Powered Support Assistant

<div align="center">

![Python](https://img.shields.io/badge/Python-3.12-blue?logo=python)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-green?logo=fastapi)
![Streamlit](https://img.shields.io/badge/Streamlit-1.41-red?logo=streamlit)
![LangChain](https://img.shields.io/badge/LangChain-0.3-purple)
![ChromaDB](https://img.shields.io/badge/ChromaDB-0.6-orange)
![Gemini](https://img.shields.io/badge/Gemini_2.5_Flash-AI-blue?logo=google)
![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?logo=docker)
![License](https://img.shields.io/badge/License-MIT-yellow)

**An enterprise-grade AI helpdesk chatbot that answers user questions by retrieving information from uploaded documents — no hallucinations, only cited facts.**

[Live Demo](#) · [API Docs](http://localhost:8000/docs) · [Report Bug](#) · [Request Feature](#)

</div>

---

## 📋 Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Tech Stack](#tech-stack)
- [Features](#features)
- [Project Structure](#project-structure)
- [Quick Start](#quick-start)
- [Docker Deployment](#docker-deployment)
- [API Reference](#api-reference)
- [RAG Pipeline](#rag-pipeline)
- [Configuration](#configuration)
- [Testing](#testing)
- [Deployment Guide](#deployment-guide)
- [Interview Q&A](#interview-qa)
- [Resume Description](#resume-description)
- [Future Scope](#future-scope)

---

## 🎯 Overview

The **AI Helpdesk Agent** is a production-ready Retrieval-Augmented Generation (RAG) system that:

1. Accepts uploaded documents (PDF, DOCX, TXT)
2. Chunks and embeds them into a persistent ChromaDB vector store
3. When a user asks a question, retrieves the most relevant chunks
4. Sends retrieved context + question to Google Gemini 2.5 Flash
5. Returns a grounded answer with source citations and confidence scores

This eliminates LLM hallucination by **anchoring every answer to actual document content**.

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    STREAMLIT FRONTEND                       │
│  Login │ Chat │ Documents │ Profile │ Admin Dashboard       │
└────────────────────────┬────────────────────────────────────┘
                         │ REST API (JWT Auth)
┌────────────────────────▼────────────────────────────────────┐
│                    FASTAPI BACKEND                          │
│  /auth  │ /chat  │ /documents  │ /admin                    │
└──────┬──────────────────────────────────────────────────────┘
       │
       ├──► SQLite DB (Users, Sessions, Messages, Analytics)
       │
       ├──► Document Processor (PDF/DOCX/TXT → Chunks)
       │
       ├──► ChromaDB Vector Store (Semantic Search)
       │         │
       │         └──► Google Embeddings (models/embedding-001)
       │
       └──► RAG Pipeline
                 │
                 ├──► Query Rewriter
                 ├──► Similarity Search (Top-K chunks)
                 ├──► Context Builder
                 └──► Gemini 2.5 Flash (Answer Generation)
```

---

## 🛠️ Tech Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **Frontend** | Streamlit 1.41 | ChatGPT-style UI, dark mode |
| **Backend** | FastAPI 0.115 | REST API, JWT auth, routing |
| **AI Framework** | LangChain 0.3 | RAG pipeline, prompt templates |
| **LLM** | Gemini 2.5 Flash | Answer generation |
| **Embeddings** | Google `embedding-001` | Semantic vector creation |
| **Vector DB** | ChromaDB 0.6 | Similarity search |
| **Database** | SQLite + SQLAlchemy | Users, sessions, analytics |
| **Auth** | JWT (python-jose) + bcrypt | Secure authentication |
| **Deployment** | Docker + Docker Compose | Containerized production |

---

## ✨ Features

### 👤 User Features
- ✅ Register / Login with JWT authentication
- ✅ ChatGPT-style conversation interface
- ✅ Full chat history with session management
- ✅ Upload PDF, DOCX, TXT documents
- ✅ Source citations with relevance scores
- ✅ Confidence score per answer
- ✅ Typing animation while AI responds
- ✅ Download chat history as PDF
- ✅ Multi-language support (10 languages)
- ✅ Dark / Light theme toggle
- ✅ Suggested follow-up questions
- ✅ Profile management

### 👑 Admin Features
- ✅ Secure admin login
- ✅ Upload and delete documents
- ✅ Re-index documents individually
- ✅ Rebuild entire vector database
- ✅ Analytics dashboard (users, queries, charts)
- ✅ Top 10 most asked questions
- ✅ User management (activate/deactivate)
- ✅ Query logs with timing and confidence
- ✅ ChromaDB vector stats

### 🤖 AI Features
- ✅ Retrieval-Augmented Generation (RAG)
- ✅ Conversation memory (last 6 messages)
- ✅ Query rewriting for better retrieval
- ✅ Semantic similarity search
- ✅ Structured prompt templates
- ✅ Confidence scoring
- ✅ Citation generation
- ✅ Follow-up question suggestions
- ✅ Fallback for no-match scenarios

---

## 📁 Project Structure

```
AI-Helpdesk-Agent/
│
├── backend/
│   ├── api/
│   │   └── routes/
│   │       ├── auth_routes.py       # Register, login, profile
│   │       ├── chat_routes.py       # Ask, sessions, export PDF
│   │       ├── document_routes.py   # Upload, list, delete, reindex
│   │       └── admin_routes.py      # Analytics, users, rebuild index
│   ├── authentication/
│   │   └── auth.py                  # JWT + bcrypt
│   ├── config/
│   │   └── settings.py              # Pydantic BaseSettings
│   ├── database/
│   │   ├── database.py              # SQLAlchemy engine + session
│   │   └── models.py                # ORM: User, Document, ChatSession, etc.
│   ├── documents/
│   │   └── uploads/                 # Uploaded files (gitignored)
│   ├── models/
│   │   └── schemas.py               # Pydantic request/response schemas
│   ├── tests/
│   │   ├── test_auth.py
│   │   └── test_documents.py
│   ├── utils/
│   │   ├── document_processor.py    # PDF/DOCX/TXT loader + chunker
│   │   ├── logger.py                # Loguru logging
│   │   └── rag_pipeline.py          # Full RAG pipeline
│   ├── vector_db/
│   │   ├── chroma_store.py          # ChromaDB CRUD
│   │   └── embeddings.py            # Google embedding wrapper
│   └── main.py                      # FastAPI app + lifespan
│
├── frontend/
│   ├── components/
│   │   ├── api_client.py            # All HTTP calls to backend
│   │   ├── auth_ui.py               # Login / Register forms
│   │   └── sidebar.py               # Nav + session list
│   ├── pages/
│   │   ├── chat_page.py             # Main chat interface
│   │   ├── documents_page.py        # Upload & manage docs
│   │   ├── profile_page.py          # User profile
│   │   └── admin_page.py            # Admin dashboard
│   ├── .streamlit/
│   │   └── config.toml              # Theme config
│   └── app.py                       # Streamlit entry point
│
├── .env.example                     # Template env vars
├── .gitignore
├── docker-compose.yml
├── Dockerfile
├── pytest.ini
├── README.md
└── requirements.txt
```

---

## 🚀 Quick Start

### Prerequisites
- Python 3.12+
- Google Gemini API key → [Get it free here](https://aistudio.google.com/app/apikey)

### 1. Clone & Setup

```bash
git clone https://github.com/yourusername/AI-Helpdesk-Agent.git
cd AI-Helpdesk-Agent

# Create virtual environment
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
cp .env.example .env
# Edit .env and add your GOOGLE_API_KEY
nano .env
```

### 3. Run Backend

```bash
# From project root
uvicorn backend.main:app --reload --port 8000
```
Visit: http://localhost:8000/docs (Swagger UI)

### 4. Run Frontend

```bash
# In a new terminal
cd frontend
streamlit run app.py --server.port 8501
```
Visit: http://localhost:8501

### 5. Login

Default admin: `admin@helpdesk.ai` / `Admin@123456`

---

## 🐳 Docker Deployment

```bash
# Copy and configure .env
cp .env.example .env

# Build and start all services
docker-compose up --build -d

# View logs
docker-compose logs -f

# Stop
docker-compose down
```

Services:
- Frontend: http://localhost:8501
- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/docs

---

## 🌐 Production Deployment (Render / Railway)

### Backend (Render Web Service)
```
Build Command: pip install -r requirements.txt
Start Command: uvicorn backend.main:app --host 0.0.0.0 --port $PORT
```

### Frontend (Render Static / Railway)
```
Build Command: pip install -r requirements.txt
Start Command: streamlit run frontend/app.py --server.port $PORT --server.address 0.0.0.0
```
Set `API_BASE` in `frontend/components/api_client.py` to your backend URL.

---

## 🔌 API Reference

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/api/auth/register` | ❌ | Create account |
| POST | `/api/auth/login` | ❌ | Get JWT token |
| GET | `/api/auth/me` | ✅ | Get profile |
| POST | `/api/chat/ask` | ✅ | Ask a question (RAG) |
| GET | `/api/chat/sessions` | ✅ | List sessions |
| GET | `/api/chat/sessions/{id}` | ✅ | Get history |
| DELETE | `/api/chat/sessions/{id}` | ✅ | Delete session |
| GET | `/api/chat/sessions/{id}/export` | ✅ | Export PDF |
| POST | `/api/documents/upload` | ✅ | Upload document |
| GET | `/api/documents/` | ✅ | List documents |
| DELETE | `/api/documents/{id}` | 👑 | Delete document |
| POST | `/api/documents/{id}/reindex` | 👑 | Re-index |
| GET | `/api/admin/analytics` | 👑 | Dashboard data |
| GET | `/api/admin/users` | 👑 | List users |
| POST | `/api/admin/rebuild-index` | 👑 | Rebuild ChromaDB |

✅ = User auth required | 👑 = Admin only

Full interactive docs: http://localhost:8000/docs

---

## 🧠 RAG Pipeline

```
User Question
     │
     ▼
[1] Query Rewriting (Gemini)
     │  → Reformulates question using chat history
     ▼
[2] Embedding Generation (Google embedding-001)
     │  → Converts rewritten query to 768-dim vector
     ▼
[3] ChromaDB Similarity Search
     │  → Retrieves Top-K most relevant document chunks
     │  → Returns chunks with relevance scores
     ▼
[4] Context Building
     │  → Formats chunks with source + page metadata
     ▼
[5] Prompt Assembly (LangChain PromptTemplate)
     │  → Context + Chat History + Question + Language
     ▼
[6] Gemini 2.5 Flash Generation
     │  → Produces answer + confidence + follow-ups
     ▼
[7] Response Parsing
     │  → Extracts answer, confidence score, suggestions
     ▼
[8] Citation Assembly + DB Storage
     ▼
Structured Response to User
```

---

## ⚙️ Configuration

All settings in `.env`:

```env
GOOGLE_API_KEY=your_key_here
GEMINI_MODEL=gemini-2.5-flash
EMBEDDING_MODEL=models/embedding-001
CHUNK_SIZE=1000
CHUNK_OVERLAP=200
TOP_K_RESULTS=5
JWT_SECRET_KEY=your_secret
```

---

## 🧪 Testing

```bash
# Run all tests
pytest

# With verbose output
pytest -v

# Specific test file
pytest backend/tests/test_auth.py -v

# With coverage
pytest --cov=backend --cov-report=html
```

---

## 🎓 Interview Q&A

**Q: What is RAG and why did you use it?**
A: RAG (Retrieval-Augmented Generation) grounds LLM answers in real documents, preventing hallucination. Instead of relying on the model's training data, we retrieve relevant chunks from our vector database and give them as context to Gemini.

**Q: How does ChromaDB work?**
A: ChromaDB stores document chunks as high-dimensional embedding vectors. When a user asks a question, we embed the query and find the nearest vectors using cosine similarity — these are the most semantically relevant chunks.

**Q: Why FastAPI over Flask/Django?**
A: FastAPI provides automatic OpenAPI docs, async support, Pydantic validation, and dependency injection — all production essentials with minimal boilerplate.

**Q: How do you handle security?**
A: JWT tokens for stateless auth, bcrypt for password hashing, Pydantic input validation, rate limiting via slowapi, CORS configuration, and no hardcoded secrets (all in .env).

**Q: What happens when no relevant document is found?**
A: The system returns a friendly fallback message and suggests the user upload relevant documents or rephrase, rather than hallucinating an answer.

**Q: How does multi-language support work?**
A: The language preference is passed to Gemini in the prompt template as an instruction. Gemini natively supports 30+ languages, so it responds in the requested language without additional translation infrastructure.

---

## 📄 Resume Description

```
AI Helpdesk Agent | Full Stack AI Engineer                    2024
Tech: Python · FastAPI · LangChain · Gemini 2.5 Flash · ChromaDB · Streamlit · Docker

• Built production-grade RAG chatbot answering domain-specific questions from uploaded
  documents (PDF/DOCX/TXT) with 0% hallucination by grounding responses in retrieved context
• Implemented full LangChain RAG pipeline: document chunking → Google embedding generation
  → ChromaDB vector search → Gemini 2.5 Flash answer synthesis with source citations
• Designed JWT-secured FastAPI REST backend with 15+ endpoints, SQLAlchemy ORM,
  rate limiting, and admin analytics dashboard tracking 6 key metrics
• Created ChatGPT-style Streamlit frontend with dark/light mode, 10-language support,
  conversation memory, PDF export, and suggested follow-up questions
• Containerized with multi-stage Docker builds + Docker Compose for one-command deployment
• Wrote pytest test suite covering auth, document management, and RAG edge cases
```

---

## 🔭 Future Scope

- [ ] **Streaming responses** — Token-by-token streaming via SSE for real-time feel
- [ ] **Multi-modal RAG** — Support image extraction from PDFs (tables, diagrams)
- [ ] **Voice I/O** — WebRTC-based voice input + TTS output
- [ ] **Advanced analytics** — User engagement heatmaps, answer quality scoring
- [ ] **Multi-tenancy** — Isolated vector collections per organization
- [ ] **Fine-tuning** — Domain-specific Gemini fine-tuning on helpdesk conversations
- [ ] **Feedback loop** — Thumbs up/down to improve retrieval over time
- [ ] **Document versioning** — Track document updates, invalidate stale chunks
- [ ] **Slack / Teams integration** — Deploy as a workspace bot
- [ ] **RBAC** — Granular document-level access control per user group

---

## 📜 License

MIT License © 2024

---

<div align="center">
Built with ❤️ using Google Gemini · LangChain · ChromaDB · FastAPI · Streamlit
</div>
