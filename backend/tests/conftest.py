"""Shared test fixtures for DocStore tests."""

import json
import os
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import aiosqlite
import pytest
import pytest_asyncio

# Add app to path
sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture(autouse=True)
def test_settings(tmp_path, monkeypatch):
    """Override settings to use temp directories for each test."""
    test_data_dir = tmp_path / "data"
    test_data_dir.mkdir()
    (test_data_dir / "inbox").mkdir()
    (test_data_dir / "archive").mkdir()

    db_path = test_data_dir / "test.db"

    # Clear cached settings FIRST before setting env vars
    from app.config import get_settings
    get_settings.cache_clear()

    # Set environment variables
    monkeypatch.setenv("DATA_DIR", str(test_data_dir))
    monkeypatch.setenv("INBOX_DIR", str(test_data_dir / "inbox"))
    monkeypatch.setenv("ARCHIVE_DIR", str(test_data_dir / "archive"))
    monkeypatch.setenv("DATABASE_PATH", str(db_path))
    monkeypatch.setenv("AUTH_PASSWORD", "testpassword")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://localhost:11434")

    # Clear again after setting env vars to get fresh settings
    get_settings.cache_clear()

    # Get the fresh settings
    settings = get_settings()

    # Patch settings in all modules that import it at module level
    import app.main
    import app.database
    import app.auth
    import app.services.embeddings
    import app.services.watcher
    import app.services.queue
    import app.services.qa
    import app.services.ocr
    import app.services.extraction
    import app.routers.search
    import app.routers.documents
    import app.routers.qa
    import app.services.entities

    monkeypatch.setattr(app.main, "settings", settings)
    monkeypatch.setattr(app.database, "settings", settings)
    monkeypatch.setattr(app.auth, "settings", settings)
    monkeypatch.setattr(app.services.embeddings, "settings", settings)
    monkeypatch.setattr(app.services.watcher, "settings", settings)
    monkeypatch.setattr(app.services.queue, "settings", settings)
    monkeypatch.setattr(app.services.qa, "settings", settings)
    monkeypatch.setattr(app.services.ocr, "settings", settings)
    monkeypatch.setattr(app.services.extraction, "settings", settings)
    monkeypatch.setattr(app.services.entities, "settings", settings)
    monkeypatch.setattr(app.routers.search, "settings", settings)
    monkeypatch.setattr(app.routers.documents, "settings", settings)
    monkeypatch.setattr(app.routers.qa, "settings", settings)

    yield settings

    # Clear again after test
    get_settings.cache_clear()


@pytest_asyncio.fixture
async def test_db(test_settings) -> AsyncGenerator[str, None]:
    """Create isolated SQLite database for each test."""
    db_path = str(test_settings.database_path)

    # Initialize database schema
    from app.database import init_database
    await init_database()

    yield db_path


@pytest_asyncio.fixture
async def db_connection(test_db) -> AsyncGenerator[aiosqlite.Connection, None]:
    """Get a database connection for testing."""
    async with aiosqlite.connect(test_db) as db:
        db.row_factory = aiosqlite.Row
        yield db


# Seed data for tests
SEED_DOCUMENTS = [
    {
        "id": "doc-001",
        "filename": "invoice_2024.pdf",
        "file_path": "/data/archive/invoice_2024.pdf",
        "file_hash": "abc123hash001",
        "file_size": 1024,
        "mime_type": "application/pdf",
        "raw_text": "Invoice from Power Company Inc. Total: $150.00 Date: January 15, 2024",
        "page_count": 1,
        "summary": "Electric bill for January 2024",
        "title": "Electric Bill January 2024",
        "category": "utilities",
        "counterparty": "Power Company Inc",
        "document_date": "2024-01-15",
        "status": "completed",
        "extraction_status": "completed",
    },
    {
        "id": "doc-002",
        "filename": "insurance_policy.pdf",
        "file_path": "/data/archive/insurance_policy.pdf",
        "file_hash": "def456hash002",
        "file_size": 2048,
        "mime_type": "application/pdf",
        "raw_text": "Insurance Policy from Allianz. Policy Number: POL-12345",
        "page_count": 3,
        "summary": "Home insurance policy",
        "title": "Allianz Home Insurance",
        "category": "insurance",
        "counterparty": "Allianz",
        "document_date": "2024-02-01",
        "status": "completed",
        "extraction_status": "completed",
    },
    {
        "id": "doc-003",
        "filename": "pending_doc.pdf",
        "file_path": "/data/archive/pending_doc.pdf",
        "file_hash": "ghi789hash003",
        "file_size": 512,
        "mime_type": "application/pdf",
        "raw_text": "Some document text",
        "page_count": 1,
        "summary": None,
        "title": None,
        "category": None,
        "counterparty": None,
        "document_date": None,
        "status": "processing",
        "extraction_status": "pending",
    },
]


@pytest_asyncio.fixture
async def seeded_db(test_db) -> str:
    """Database pre-populated with test documents."""
    async with aiosqlite.connect(test_db) as db:
        for doc in SEED_DOCUMENTS:
            await db.execute("""
                INSERT INTO documents (
                    id, filename, file_path, file_hash, file_size, mime_type,
                    raw_text, page_count, summary, title, category, counterparty,
                    document_date, status, extraction_status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                doc["id"], doc["filename"], doc["file_path"], doc["file_hash"],
                doc["file_size"], doc["mime_type"], doc["raw_text"], doc["page_count"],
                doc["summary"], doc["title"], doc["category"], doc["counterparty"],
                doc["document_date"], doc["status"], doc["extraction_status"],
                datetime.utcnow().isoformat()
            ))
        await db.commit()
    return test_db


@pytest.fixture
def sample_pdf(tmp_path) -> Path:
    """Create a minimal valid PDF for testing."""
    # Minimal valid PDF structure
    pdf_content = b"""%PDF-1.4
1 0 obj
<< /Type /Catalog /Pages 2 0 R >>
endobj
2 0 obj
<< /Type /Pages /Kids [3 0 R] /Count 1 >>
endobj
3 0 obj
<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R >>
endobj
4 0 obj
<< /Length 44 >>
stream
BT
/F1 12 Tf
100 700 Td
(Test PDF) Tj
ET
endstream
endobj
xref
0 5
0000000000 65535 f
0000000009 00000 n
0000000058 00000 n
0000000115 00000 n
0000000206 00000 n
trailer
<< /Size 5 /Root 1 0 R >>
startxref
300
%%EOF
"""
    pdf_path = tmp_path / "sample.pdf"
    pdf_path.write_bytes(pdf_content)
    return pdf_path


@pytest.fixture
def sample_image(tmp_path) -> Path:
    """Create a test image."""
    from PIL import Image
    img = Image.new('RGB', (100, 100), color='white')
    img_path = tmp_path / "sample.jpg"
    img.save(img_path)
    return img_path


@pytest.fixture
def mock_ollama_response():
    """Factory for creating mock Ollama responses."""
    def _create_response(content: str | dict, status_code: int = 200):
        if isinstance(content, dict):
            content = json.dumps(content)

        mock_response = MagicMock()
        mock_response.status_code = status_code
        mock_response.json.return_value = {"response": content}
        mock_response.raise_for_status = MagicMock()
        if status_code >= 400:
            from httpx import HTTPStatusError
            mock_response.raise_for_status.side_effect = HTTPStatusError(
                "Error", request=MagicMock(), response=mock_response
            )
        return mock_response

    return _create_response


@pytest.fixture
def mock_ollama_available():
    """Mock Ollama being available."""
    async def mock_get(*args, **kwargs):
        mock_response = MagicMock()
        mock_response.status_code = 200
        return mock_response

    return mock_get


@pytest.fixture
def mock_ollama_unavailable():
    """Mock Ollama being unavailable."""
    import httpx

    async def mock_get(*args, **kwargs):
        raise httpx.ConnectError("Connection refused")

    return mock_get


@pytest.fixture
def mock_embedding():
    """Create a mock embedding vector."""
    import numpy as np
    # 384-dimensional vector (MiniLM dimension)
    return np.random.randn(384).tolist()


# pytest configuration
def pytest_configure(config):
    """Configure pytest markers."""
    config.addinivalue_line(
        "markers", "performance: marks tests as performance tests (deselect with '-m \"not performance\"')"
    )
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests"
    )
