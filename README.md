# DocStore

A self-hosted document management system with OCR, semantic search, and LLM-powered data extraction. Designed to run on a Raspberry Pi (4-8GB) with cloud API calls for AI features.

## Features

- **Document Ingestion**: Upload PDFs and images via web UI or drop files in the inbox folder
- **OCR Processing**: Automatic text extraction using ocrmypdf with German + English support
- **AI Classification**: Automatic document type detection (invoices, receipts, bank statements, tax documents)
- **Structured Extraction**: Extract vendor, amounts, dates, and line items from documents
- **Semantic Search**: Find documents by meaning, not just keywords
- **Q&A Interface**: Ask questions about your documents using RAG
- **Tag Management**: Organize documents with custom tags
- **Spending Analytics**: Track spending from invoices and receipts

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
# Edit backend/.env and set your password and OpenAI API key

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

# OpenAI (required for AI features)
OPENAI_API_KEY=sk-...

# Optional
DEBUG=false
OCR_LANGUAGE=deu+eng
```

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
# Build and start containers
docker-compose up -d

# View logs
docker-compose logs -f

# Stop containers
docker-compose down
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
│   │   │   ├── extraction.py # LLM extraction
│   │   │   ├── embeddings.py # Vector search
│   │   │   ├── watcher.py    # Folder watcher
│   │   │   └── qa.py         # Q&A service
│   │   └── routers/          # API endpoints
│   └── requirements.txt
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
└── docker-compose.yml
```

## Database Schema

- `documents`: Core document metadata and OCR text
- `invoices`: Extracted invoice data
- `receipts`: Extracted receipt data
- `bank_statements`: Extracted bank statement data
- `tax_documents`: Extracted tax document data
- `tags` / `document_tags`: Tag system
- `document_embeddings`: Vector embeddings for semantic search
- `documents_fts`: Full-text search index

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

# Clean build artifacts
make clean

# Add a Python dependency
make add pkg=some-package

# Update all Python dependencies
make update

# Run with uv directly
cd backend && uv run uvicorn app.main:app --reload
```

## Raspberry Pi Deployment

For Raspberry Pi 4 (4GB+):

1. Install system dependencies:
   ```bash
   sudo apt update
   sudo apt install python3.11 nodejs npm
   sudo apt install ocrmypdf tesseract-ocr tesseract-ocr-deu poppler-utils libmagic1
   ```

2. Install uv:
   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   source ~/.bashrc  # or restart your shell
   ```

3. Clone and install:
   ```bash
   git clone <repo> docstore
   cd docstore
   make install
   cp .env.example backend/.env
   # Edit backend/.env with your settings
   ```

4. Create systemd service:
   ```bash
   sudo cp docstore.service /etc/systemd/system/
   sudo systemctl daemon-reload
   sudo systemctl enable docstore
   sudo systemctl start docstore
   ```

5. Check status:
   ```bash
   sudo systemctl status docstore
   sudo journalctl -u docstore -f  # View logs
   ```

## License

MIT
