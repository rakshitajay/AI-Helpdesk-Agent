#!/bin/bash
# ============================================================
# AI Helpdesk Agent - Local Development Startup Script
# Usage: chmod +x start.sh && ./start.sh
# ============================================================

set -e

echo "╔══════════════════════════════════════════╗"
echo "║       AI Helpdesk Agent Startup          ║"
echo "╚══════════════════════════════════════════╝"

# Check .env exists
if [ ! -f ".env" ]; then
    echo "⚠️  .env not found. Creating from .env.example..."
    cp .env.example .env
    echo "📝 Please edit .env and add your GOOGLE_API_KEY, then run again."
    exit 1
fi

# Check Python version
PYTHON_VERSION=$(python3 --version 2>&1 | cut -d' ' -f2 | cut -d'.' -f1-2)
echo "✅ Python $PYTHON_VERSION detected"

# Check venv
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
fi

source venv/bin/activate
echo "✅ Virtual environment activated"

# Install deps
echo "📦 Installing dependencies..."
pip install -r requirements.txt -q

# Create required directories
mkdir -p backend/documents/uploads backend/vector_db/chroma_store backend/database backend/logs

echo ""
echo "🚀 Starting FastAPI backend on http://localhost:8000"
uvicorn backend.main:app --reload --port 8000 &
BACKEND_PID=$!

sleep 3

echo "🎨 Starting Streamlit frontend on http://localhost:8501"
cd frontend && streamlit run app.py --server.port 8501 &
FRONTEND_PID=$!

echo ""
echo "╔══════════════════════════════════════════╗"
echo "║  ✅ Both services running!               ║"
echo "║  Frontend: http://localhost:8501         ║"
echo "║  API Docs: http://localhost:8000/docs    ║"
echo "║  Press Ctrl+C to stop both              ║"
echo "╚══════════════════════════════════════════╝"

# Wait for both processes
wait $BACKEND_PID $FRONTEND_PID
