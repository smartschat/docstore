# DocStore

![Python](https://img.shields.io/badge/python-3.11+-blue)
![Svelte](https://img.shields.io/badge/svelte-5-orange)
[![Tests](https://github.com/smartschat/docstore/actions/workflows/test.yml/badge.svg)](https://github.com/smartschat/docstore/actions/workflows/test.yml)
[![Lint](https://github.com/smartschat/docstore/actions/workflows/lint.yml/badge.svg)](https://github.com/smartschat/docstore/actions/workflows/lint.yml)

A self-hosted document management system with OCR, semantic search, and LLM-powered data extraction. Designed to run on a Raspberry Pi with local embeddings and Ollama for LLM features.

## Features

- **Document Ingestion**: Upload PDFs and images via web UI, scan with camera, or drop files in the inbox folder
- **OCR Processing**: Automatic text extraction using ocrmypdf with German + English support
- **AI Classification**: Automatic document categorization via Ollama LLM
- **Structured Extraction**: Extract title, counterparty, dates, and amounts from documents (supports vision models for visual analysis)
- **Semantic Search**: Find documents by meaning using local ONNX embeddings (ARM compatible)
- **Q&A Interface**: Ask questions about your documents using RAG
- **Tag Management**: Organize documents with custom tags
- **Extraction Queue**: Documents arriving when Ollama is offline are queued for later processing

## Quick Start

### Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) (Python package manager)
- Node.js 20+
- ocrmypdf (`apt install ocrmypdf tesseract-ocr tesseract-ocr-deu`)
- poppler-utils (`apt install poppler-utils`)

### Installation

```bash
# Install uv if not already installed
curl -LsSf https://astral.sh/uv/install.sh | sh

# Clone the repository
cd docstore

# Install dependencies
make install

# Create .env file
cp .env.example backend/.env
# Edit backend/.env with your password and Ollama server address

# Start development servers
make dev
```

The application will be available at:
- Frontend: http://localhost:5173
- Backend API: http://localhost:8000

### Configuration

Create a `.env` file in the `backend/` directory:

```env
# Authentication
AUTH_PASSWORD=your-secure-password
SECRET_KEY=your-secret-key-for-sessions

# Ollama (for LLM extraction and Q&A)
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen3:1.7b

# Optional
DEBUG=false
OCR_LANGUAGE=deu+eng

# Vision model (optional - for visual document analysis)
# OLLAMA_MODEL=qwen3-vl:2b
# OLLAMA_USE_VISION=true
```

### Ollama Setup

The LLM features (extraction, Q&A) require an Ollama server running on your network:

```bash
# On a Mac or other machine with more RAM
brew install ollama
ollama pull qwen3:1.7b
OLLAMA_HOST=0.0.0.0 ollama serve  # Listen on network
```

Documents uploaded when Ollama is unavailable will have their extraction queued and processed automatically when Ollama comes back online.

### Vision Model (Optional)

For improved accuracy on complex document layouts, you can use a vision language model that analyzes PDF pages as images:

```bash
# Pull a vision model
ollama pull qwen3-vl:2b

# Enable in backend/.env
OLLAMA_MODEL=qwen3-vl:2b
OLLAMA_USE_VISION=true
```

Vision mode is slower (~40-65s vs ~15-20s per document) but can better handle forms, certificates, and documents with complex layouts. OCR still runs for full-text search and embeddings.

## Usage

### Web Interface

1. Open http://localhost:5173
2. Log in with your configured password
3. Upload documents via the Upload button
4. Documents are automatically processed (OCR, classification, extraction)
5. Use the search bar to find documents
6. Click on a document to view details and PDF

### Folder Watch

Drop files into the `data/inbox/` folder and they will be automatically processed.

### API

See the API documentation at http://localhost:8000/docs

## Docker Deployment

```bash
# Build the image
docker build -t docstore .

# Run with a volume for data persistence
docker run -d \
  --name docstore \
  -p 8000:8000 \
  -v docstore-data:/app/data \
  -e AUTH_PASSWORD=your-password \
  -e OLLAMA_BASE_URL=http://your-ollama-host:11434 \
  docstore

# View logs
docker logs -f docstore
```

## Architecture

```
docstore/
├── backend/          # FastAPI Python backend
│   ├── app/
│   │   ├── main.py           # FastAPI app
│   │   ├── config.py         # Settings
│   │   ├── auth.py           # Authentication
│   │   ├── database.py       # SQLite setup
│   │   ├── models.py         # Pydantic models
│   │   ├── services/         # Business logic
│   │   │   ├── ocr.py        # OCR processing
│   │   │   ├── extraction.py # LLM extraction (Ollama)
│   │   │   ├── embeddings.py # Vector search (ONNX)
│   │   │   ├── queue.py      # Extraction queue processor
│   │   │   ├── watcher.py    # Folder watcher
│   │   │   └── qa.py         # Q&A service
│   │   └── routers/          # API endpoints
│   ├── tests/                # Unit and integration tests
│   └── pyproject.toml
├── frontend/         # SvelteKit frontend
│   ├── src/
│   │   ├── routes/           # Pages
│   │   └── lib/
│   │       ├── components/   # UI components
│   │       ├── stores/       # State management
│   │       └── api.ts        # API client
│   └── package.json
├── data/             # Data directory
│   ├── inbox/        # Drop files here
│   ├── archive/      # Processed files
│   └── docstore.db   # SQLite database
└── Dockerfile        # Production build
```

## Database Schema

- `documents`: Core document metadata, OCR text, and extracted fields (title, counterparty, category, etc.)
- `tags` / `document_tags`: Tag system
- `document_embeddings`: Vector embeddings for semantic search (384-dim)
- `documents_fts`: Full-text search index
- `sessions`: Authentication sessions

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /api/health | Health check |
| POST | /api/auth/login | Login |
| POST | /api/auth/logout | Logout |
| GET | /api/documents | List documents |
| POST | /api/documents/upload | Upload document |
| GET | /api/documents/:id | Get document |
| DELETE | /api/documents/:id | Delete document |
| POST | /api/search | Search documents |
| POST | /api/ask | Ask question (RAG) |
| GET | /api/stats | Dashboard statistics |

## Development

```bash
# Run backend only
make backend

# Run frontend only
make frontend

# Build frontend for production
make build

# Run linters
make lint

# Run all tests
make test

# Run unit tests only
make test-unit

# Run integration tests only
make test-integration

# Run tests with coverage report
make test-coverage

# Clean build artifacts
make clean

# Add a Python dependency
make add pkg=some-package

# Update all Python dependencies
make update

# Run with uv directly
cd backend && uv run python -m uvicorn app.main:app --reload
```

## Raspberry Pi Deployment

For Raspberry Pi 4 (4GB+), Docker is recommended:

```bash
# Install Docker
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
# Log out and back in

# Deploy
docker build -t docstore .
docker run -d \
  --name docstore \
  -p 8000:8000 \
  -v docstore-data:/app/data \
  -e AUTH_PASSWORD=your-password \
  -e OLLAMA_BASE_URL=http://your-mac-ip:11434 \
  --restart unless-stopped \
  docstore
```

Note: Embeddings use ONNX Runtime which runs natively on ARM. The Ollama server should run on a separate machine (e.g., Mac) as it requires more resources.

## License

MIT
