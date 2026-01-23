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
- `app/main.py` - FastAPI app with lifespan management, starts folder watcher on startup
- `app/database.py` - SQLite schema with FTS5 full-text search and sqlite-vec for vector embeddings
- `app/services/ocr.py` - OCR processing using ocrmypdf
- `app/services/extraction.py` - LLM-powered structured data extraction (title, counterparty, category, amounts, dates)
- `app/services/embeddings.py` - OpenAI embeddings with sqlite-vec for semantic search, includes Python fallback
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

**Database**: SQLite with three search mechanisms:
- `documents` table with extracted fields
- `documents_fts` FTS5 virtual table for keyword search
- `document_embeddings` vec0 table for semantic search (1536-dim OpenAI embeddings)

## Key Configuration

Environment variables in `backend/.env`:
- `AUTH_PASSWORD` - Single password for web authentication
- `OPENAI_API_KEY` - Required for extraction, embeddings, and Q&A
- `OCR_LANGUAGE` - Tesseract languages (default: deu+eng)

Document categories: utilities, insurance, tax, medical, banking, salary, contract, legal, correspondence, receipt, invoice, other
