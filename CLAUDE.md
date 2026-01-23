# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build and Development Commands

```bash
# Install all dependencies (backend + frontend)
make install

# Run both backend and frontend in development mode
make dev

# Run backend only (FastAPI on port 8000)
make backend

# Run frontend only (Vite on port 5173)
make frontend

# Build frontend for production
make build

# Initialize database manually
make db-init

# Process existing files in inbox folder
make process-inbox

# Add a Python dependency
make add pkg=package-name

# Update all Python dependencies
make update

# Run backend directly with uv
cd backend && uv run uvicorn app.main:app --reload
```

## Architecture

**Backend** (FastAPI + Python):
- `app/main.py` - FastAPI app with lifespan management, starts folder watcher and queue processor on startup
- `app/database.py` - SQLite schema with FTS5 full-text search
- `app/services/ocr.py` - OCR processing using ocrmypdf
- `app/services/extraction.py` - LLM-powered structured data extraction via Ollama (title, counterparty, category, amounts, dates)
- `app/services/embeddings.py` - Local embeddings using ONNX Runtime (all-MiniLM-L6-v2, 384 dims), ARM compatible
- `app/services/queue.py` - Background processor for documents queued when Ollama was unavailable
- `app/services/qa.py` - RAG-based Q&A using semantic search to find relevant documents
- `app/services/watcher.py` - Watchdog-based folder monitor for auto-ingestion from `data/inbox/`
- `app/routers/` - API endpoint modules (documents, search, qa)

**Frontend** (SvelteKit + Tailwind):
- `src/lib/api.ts` - Typed API client, all backend calls go through this
- `src/lib/stores/documents.ts` - Svelte stores for document state
- `src/lib/components/` - Reusable UI components (DocumentCard, PdfViewer, ChatPanel, etc.)
- `src/routes/` - File-based routing (documents, ask, login pages)

**Data Flow**:
1. Documents enter via upload or `data/inbox/` folder watch
2. OCR extracts text (ocrmypdf with deu+eng language support)
3. LLM extraction pulls structured fields (counterparty, amounts, dates, category)
4. Embeddings generated and stored for semantic search
5. FTS5 index updated for keyword search

**Database**: SQLite with multiple search mechanisms:
- `documents` table with extracted fields and `extraction_status` for queue tracking
- `documents_fts` FTS5 virtual table for keyword search
- `document_embeddings` table for semantic search (384-dim MiniLM embeddings via ONNX, with Python fallback for cosine similarity)

## Key Configuration

Environment variables in `backend/.env`:
- `AUTH_PASSWORD` - Single password for web authentication
- `OLLAMA_BASE_URL` - Ollama server URL (default: http://localhost:11434)
- `OLLAMA_MODEL` - Model for extraction/Q&A (default: qwen3:1.7b)
- `OCR_LANGUAGE` - Tesseract languages (default: deu+eng)

**Ollama Setup** (for LLM features):
```bash
# On Mac (serves LLM for extraction and Q&A)
brew install ollama
ollama pull qwen3:1.7b
OLLAMA_HOST=0.0.0.0 ollama serve  # Listen on network
```

**Extraction Queue**: Documents arriving when Ollama is unavailable get `extraction_status='pending'`. A background processor (`queue.py`) checks every 60s and processes pending extractions when Ollama comes back online.

Document categories: utilities, insurance, tax, medical, banking, salary, contract, legal, correspondence, receipt, invoice, other
