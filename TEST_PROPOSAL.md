# Test Proposal for DocStore

This document outlines a comprehensive testing strategy for the DocStore application, covering unit tests, integration tests, end-to-end tests, and specialized test categories.

## Implementation Progress

| Phase | Status | Tests Implemented |
|-------|--------|-------------------|
| Phase 1: Test Infrastructure | :white_check_mark: Complete | conftest.py, fixtures, pytest config |
| Phase 2: Critical Unit Tests | :white_check_mark: Complete | 117 tests passing |
| Phase 3: Remaining Unit Tests | :white_check_mark: Complete | 219 tests passing |
| Phase 4: Integration Tests | :white_check_mark: Complete | 51 tests passing |
| Phase 5: Specialized Tests | :x: Not Started | |
| Phase 6: E2E + Performance | :x: Not Started | |

### Completed Unit Tests

- [x] **Extraction Service** (`test_extraction.py`) - 36 tests
  - parse_json_response, strip_thinking, check_ollama_available
  - extract_metadata, generate_title, generate_summary
  - call_ollama, get_empty_extraction, extract_document_data
- [x] **Embeddings Service** (`test_embeddings.py`) - 25 tests
  - _mean_pooling, _normalize, generate_embedding
  - search_similar_fallback, store_embedding, semantic_search
- [x] **Search Router** (`test_search.py`) - 20 tests
  - normalize_scores, keyword_search, hybrid_search
  - search_suggestions, row_to_document
- [x] **Auth Service** (`test_auth.py`) - 20 tests
  - verify_password, generate_session_token
  - create_session, validate_session, cleanup_expired_sessions
- [x] **Database** (`test_database.py`) - 16 tests
  - init_database, init_sqlite_vec, FTS triggers
  - Schema creation, migrations, foreign keys
- [x] **Watcher Service** (`test_watcher.py`) - 29 tests
  - get_file_hash, get_mime_type, check_duplicate
  - create_document_record, update_document_status
  - InboxHandler, FolderWatcher, process_document, process_existing_inbox
- [x] **Queue Service** (`test_queue.py`) - 13 tests
  - get_pending_extractions, get_queue_stats
  - process_pending_extraction, queue_processor_loop
  - start_queue_processor, stop_queue_processor
- [x] **OCR Service** (`test_ocr.py`) - 19 tests
  - OCRResult, process_pdf, process_image
  - extract_text_with_pdftotext, get_pdf_page_count, extract_text_from_file
- [x] **Q&A Service** (`test_qa.py`) - 19 tests
  - check_ollama_available, get_document_context
  - build_context_prompt, answer_with_ollama
  - answer_question, get_document_qa
- [x] **Documents Router** (`test_documents.py`) - 22 tests
  - get_document_by_id, get_document_tags, row_to_document
  - list_documents, get_document, upload_document
  - update_document, delete_document, add_tags, remove_tag

### Completed Integration Tests

- [x] **Auth Flow** (`test_auth_flow.py`) - 8 tests
  - Login creates session and sets cookie
  - Invalid password returns 401
  - Authenticated user can access protected routes
  - Logout clears session and cookie
  - Protected route without auth returns 401
  - Invalid session token returns 401
  - Expired session returns 401
- [x] **Document Pipeline** (`test_document_pipeline.py`) - 7 tests
  - Upload PDF processes complete pipeline
  - Upload queues extraction when Ollama unavailable
  - Upload same filename different content creates separate documents
  - Upload unsupported file type rejected
  - Reprocess reruns full pipeline
  - Reprocess nonexistent document returns 404
  - Queue processes pending extractions
- [x] **Search Pipeline** (`test_search_pipeline.py`) - 10 tests
  - Keyword search returns FTS matches
  - Keyword search with category filter
  - Keyword search escapes special characters
  - Keyword search no results returns empty
  - Semantic search returns similar documents
  - Semantic search respects category filter
  - Hybrid search combines scores
  - Hybrid search keyword only matches
  - Suggestions returns matching data
  - Suggestions minimum query length
- [x] **Q&A Pipeline** (`test_qa_pipeline.py`) - 5 tests
  - Question returns answer with sources
  - Question about specific document
  - Question no relevant documents
  - Question Ollama unavailable returns error
  - Context includes relevant document text
- [x] **Document Lifecycle** (`test_document_lifecycle.py`) - 14 tests
  - List documents returns paginated results
  - List documents filter by category
  - List documents filter by status
  - Get document by ID
  - Get nonexistent document returns 404
  - Update document metadata
  - Delete document removes all data
  - Delete nonexistent document returns 404
  - Add tags to document
  - Remove tag from document
  - List all tags
  - Download document file
  - Download missing file returns 404
  - Download with download header
- [x] **Watcher Pipeline** (`test_watcher_pipeline.py`) - 7 tests
  - File in inbox gets processed
  - Process existing inbox on startup
  - Invalid file type ignored
  - Hidden files ignored by process_existing_inbox
  - Duplicate file detected by hash
  - Handler on_created processes file
  - Handler ignores temp files

**Total:** 270 tests (219 unit + 51 integration) all passing.

---

## Table of Contents

1. [Overview](#overview)
2. [Test Infrastructure](#test-infrastructure)
3. [Unit Tests](#unit-tests)
4. [Integration Tests](#integration-tests)
5. [End-to-End Tests](#end-to-end-tests)
6. [Smoke Tests](#smoke-tests)
7. [Security Tests](#security-tests)
8. [Performance Tests](#performance-tests)
9. [Resilience Tests](#resilience-tests)
10. [Migration Tests](#migration-tests)
11. [API Contract Tests](#api-contract-tests)
12. [Test Directory Structure](#test-directory-structure)
13. [Implementation Plan](#implementation-plan)

---

## Overview

### Current State

- `pytest` and `pytest-asyncio` are listed as dependencies but no tests exist
- No frontend testing infrastructure

### Goals

- Achieve comprehensive coverage of critical business logic
- Ensure pipeline correctness through integration tests
- Validate user workflows with E2E tests
- Protect against regressions and security vulnerabilities

### Scope Summary

| Test Type       | Count | Priority | When to Run            |
|-----------------|-------|----------|------------------------|
| Unit            | ~86   | High     | Every commit           |
| Integration     | ~30   | High     | Every commit           |
| Smoke           | ~8    | Critical | After deploy, CI gate  |
| Security        | ~10   | High     | Weekly + before release|
| E2E             | ~10   | Medium   | Before release         |
| Performance     | ~6    | Medium   | Weekly / on-demand     |
| Migration       | ~4    | Medium   | When schema changes    |
| Resilience      | ~8    | Medium   | Before release         |
| **Total**       | **~162** |       |                        |

---

## Test Infrastructure

### Shared Fixtures (`conftest.py`)

#### Test Database

```python
import pytest
import aiosqlite
from pathlib import Path
from app.database import init_database

@pytest.fixture
async def test_db(tmp_path):
    """Create isolated SQLite database for each test."""
    db_path = tmp_path / "test.db"
    await init_database(str(db_path))
    yield str(db_path)
    # Cleanup automatic with tmp_path
```

#### Mock Ollama Server

```python
import pytest
import json
import re

@pytest.fixture
def mock_ollama(httpx_mock):
    """Controllable Ollama responses for tests."""
    def configure(response_content: str | dict, status_code: int = 200):
        if isinstance(response_content, dict):
            response_content = json.dumps(response_content)
        httpx_mock.add_response(
            url=re.compile(r".*/api/generate"),
            json={"response": response_content},
            status_code=status_code
        )
    return configure

@pytest.fixture
def mock_ollama_unavailable(httpx_mock):
    """Simulate Ollama being down."""
    httpx_mock.add_exception(
        httpx.ConnectError("Connection refused"),
        url=re.compile(r".*/api/.*")
    )
```

#### FastAPI Test Client

```python
from fastapi.testclient import TestClient
from app.main import app
from app.database import get_session

@pytest.fixture
def client(test_db, mock_ollama):
    """FastAPI TestClient with test dependencies."""
    async def override_get_session():
        async with aiosqlite.connect(test_db) as db:
            db.row_factory = aiosqlite.Row
            yield db

    app.dependency_overrides[get_session] = override_get_session
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()
```

#### Seeded Test Data

```python
SEED_DOCUMENTS = [
    {
        "id": "doc-001",
        "filename": "invoice_2024.pdf",
        "title": "Electric Bill January 2024",
        "category": "utilities",
        "counterparty": "Power Company Inc",
        "total_amount": 150.00,
        "document_date": "2024-01-15",
    },
    # ... more seed documents
]

@pytest.fixture
async def seeded_db(test_db):
    """Database pre-populated with test documents."""
    async with aiosqlite.connect(test_db) as db:
        for doc in SEED_DOCUMENTS:
            await db.execute("""
                INSERT INTO documents (id, filename, title, category, counterparty, total_amount, document_date, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'completed')
            """, (doc["id"], doc["filename"], doc["title"], doc["category"],
                  doc["counterparty"], doc["total_amount"], doc["document_date"]))
        await db.commit()
    yield test_db
```

#### Test Files

```python
@pytest.fixture
def sample_pdf(tmp_path):
    """Create a minimal valid PDF for testing."""
    pdf_content = b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n..."
    pdf_path = tmp_path / "sample.pdf"
    pdf_path.write_bytes(pdf_content)
    return pdf_path

@pytest.fixture
def sample_image(tmp_path):
    """Create a test image."""
    from PIL import Image
    img = Image.new('RGB', (100, 100), color='white')
    img_path = tmp_path / "sample.jpg"
    img.save(img_path)
    return img_path
```

### Mocking Strategy

| Dependency | Mock Approach |
|------------|---------------|
| Ollama API | `pytest-httpx` with preset responses |
| Database | In-memory SQLite via `tmp_path` |
| File system | `tmp_path` fixture + mock `Path` operations |
| Subprocesses (ocrmypdf) | `unittest.mock.patch` on `asyncio.create_subprocess_exec` |
| ONNX Runtime | Mock `InferenceSession` return values |
| Datetime | `freezegun` or manual patching |

---

## Unit Tests

Unit tests validate individual functions and classes in isolation.

### Priority 1: Critical Business Logic

#### 1.1 Extraction Service (`app/services/extraction.py`)

**~12 tests**

| Function | Test Cases |
|----------|------------|
| `parse_json_response()` | Valid JSON, JSON in markdown code block, JSON with ```json prefix, malformed JSON, empty response |
| `strip_thinking()` | Text with `<think>` tags, nested tags, no tags present, tags at start/end |
| `check_ollama_available()` | Successful response, timeout, connection refused |
| `extract_metadata()` | All fields extracted, partial fields, invalid date formats, amount parsing |
| `generate_title()` | Valid title, title too short (<3 chars), title too long (>100 chars) |
| `call_ollama()` | Successful call, timeout handling, error response |

```python
# Example test cases
class TestParseJsonResponse:
    def test_parses_plain_json(self):
        response = '{"title": "Invoice", "category": "utilities"}'
        result = parse_json_response(response)
        assert result == {"title": "Invoice", "category": "utilities"}

    def test_parses_json_in_markdown_block(self):
        response = '```json\n{"title": "Invoice"}\n```'
        result = parse_json_response(response)
        assert result == {"title": "Invoice"}

    def test_handles_malformed_json(self):
        response = '{"title": broken}'
        result = parse_json_response(response)
        assert result == {}

class TestStripThinking:
    def test_removes_think_tags(self):
        text = "<think>internal reasoning</think>Final answer"
        result = strip_thinking(text)
        assert result == "Final answer"

    def test_handles_no_tags(self):
        text = "Just a normal response"
        result = strip_thinking(text)
        assert result == "Just a normal response"
```

#### 1.2 Search Scoring (`app/routers/search.py`)

**~8 tests**

| Function | Test Cases |
|----------|------------|
| `normalize_scores()` | Normal range, all same score, single result, empty list |
| `hybrid_search()` | Keyword-only matches, semantic-only matches, overlapping results, score weighting (0.3/0.7) |
| `keyword_search()` | FTS5 match, special characters escaped, no matches |

```python
class TestNormalizeScores:
    def test_normalizes_to_0_1_range(self):
        scores = [10, 20, 30]
        normalized = normalize_scores(scores)
        assert normalized == [0.0, 0.5, 1.0]

    def test_handles_single_value(self):
        scores = [5]
        normalized = normalize_scores(scores)
        assert normalized == [1.0]

    def test_handles_empty_list(self):
        scores = []
        normalized = normalize_scores(scores)
        assert normalized == []
```

#### 1.3 Embeddings Service (`app/services/embeddings.py`)

**~10 tests**

| Function | Test Cases |
|----------|------------|
| `_mean_pooling()` | Standard pooling, varying attention masks |
| `_normalize()` | Normal vectors, zero vector edge case |
| `generate_embedding()` | Valid text, empty text, text exceeding max length (8000 chars) |
| `search_similar()` | With sqlite-vec, fallback to Python cosine similarity |
| `_cosine_similarity()` | Identical vectors (=1), orthogonal vectors (=0), opposite vectors (=-1) |

```python
class TestNormalize:
    def test_l2_normalizes_vector(self):
        vector = np.array([3.0, 4.0])
        normalized = _normalize(vector)
        assert np.allclose(normalized, [0.6, 0.8])
        assert np.isclose(np.linalg.norm(normalized), 1.0)

    def test_handles_zero_vector(self):
        vector = np.array([0.0, 0.0])
        normalized = _normalize(vector)
        assert np.allclose(normalized, [0.0, 0.0])
```

### Priority 2: Data Integrity

#### 1.4 Watcher Service (`app/services/watcher.py`)

**~12 tests**

| Function | Test Cases |
|----------|------------|
| `get_file_hash()` | Small file, large file, consistent results |
| `get_mime_type()` | PDF, JPEG, PNG, TIFF, unknown extension |
| `check_duplicate()` | Duplicate found, no duplicate |
| `process_document()` | Success path, OCR failure, Ollama unavailable |
| `update_document_status()` | Valid transitions (pending→processing→completed) |
| `InboxHandler.on_created()` | Valid file, hidden file (ignored), temp file (ignored) |

```python
class TestGetFileHash:
    def test_computes_sha256(self, tmp_path):
        file = tmp_path / "test.txt"
        file.write_text("hello world")
        hash1 = get_file_hash(file)
        hash2 = get_file_hash(file)
        assert hash1 == hash2
        assert len(hash1) == 64  # SHA256 hex length

class TestCheckDuplicate:
    async def test_finds_existing_document(self, test_db):
        # Insert document with known hash
        await insert_document(test_db, file_hash="abc123")
        result = await check_duplicate(test_db, "abc123")
        assert result is not None

    async def test_returns_none_for_new_hash(self, test_db):
        result = await check_duplicate(test_db, "newhash")
        assert result is None
```

#### 1.5 Auth Service (`app/auth.py`)

**~8 tests**

| Function | Test Cases |
|----------|------------|
| `verify_password()` | Correct password, incorrect password, timing-safe comparison |
| `generate_session_token()` | Sufficient length, randomness |
| `create_session()` | Session stored with expiration |
| `validate_session()` | Valid token, expired token, non-existent token |
| `cleanup_expired_sessions()` | Removes only expired, keeps valid |

```python
class TestVerifyPassword:
    def test_accepts_correct_password(self):
        assert verify_password("secret123", "secret123") is True

    def test_rejects_incorrect_password(self):
        assert verify_password("wrong", "secret123") is False

class TestValidateSession:
    async def test_valid_session_returns_true(self, test_db):
        token = await create_session(test_db)
        assert await validate_session(test_db, token) is True

    async def test_expired_session_returns_false(self, test_db, freezer):
        token = await create_session(test_db)
        freezer.move_to(timedelta(hours=25))  # Past expiration
        assert await validate_session(test_db, token) is False
```

#### 1.6 Database (`app/database.py`)

**~6 tests**

| Function | Test Cases |
|----------|------------|
| `init_database()` | Creates all tables, creates FTS5 table, creates triggers |
| `init_sqlite_vec()` | Loads extension when available, graceful fallback |
| Migration | Adds `extraction_status` column to existing DB |

### Priority 3: API Layer

#### 1.7 Documents Router (`app/routers/documents.py`)

**~10 tests**

| Endpoint | Test Cases |
|----------|------------|
| `GET /documents` | Pagination (offset, limit), filtering by category, filtering by status, multiple filters |
| `GET /documents/{id}` | Document found, document not found (404) |
| `POST /documents` | Valid upload, unsupported file type, duplicate filename handling |
| `PATCH /documents/{id}` | Update title, update category, update date fields |
| `DELETE /documents/{id}` | Deletes document, file, embeddings, and tags |

#### 1.8 Q&A Service (`app/services/qa.py`)

**~6 tests**

| Function | Test Cases |
|----------|------------|
| `build_context_prompt()` | Under limit, exceeds limit (truncation), empty context |
| `get_document_context()` | Single document, multiple documents |
| `answer_question()` | With relevant documents, no relevant documents |

### Priority 4: Background Processing

#### 1.9 Queue Service (`app/services/queue.py`)

**~6 tests**

| Function | Test Cases |
|----------|------------|
| `get_pending_extractions()` | Returns pending documents, respects limit |
| `get_queue_stats()` | Counts by status |
| `process_pending_extraction()` | Success updates status, failure keeps pending |
| `queue_processor_loop()` | Processes batch, handles stop signal |

#### 1.10 OCR Service (`app/services/ocr.py`)

**~8 tests**

| Function | Test Cases |
|----------|------------|
| `process_pdf()` | Successful OCR (return code 0), already has text (code 6), failure |
| `extract_text_with_pdftotext()` | Successful extraction, tool not found |
| `get_pdf_page_count()` | Via pdfinfo, via pikepdf fallback |
| `process_image()` | JPG conversion, PNG conversion, RGBA to RGB |

---

## Integration Tests

Integration tests verify that components work together correctly.

### 2.1 Document Ingestion Pipeline

**~6 tests**

Test the full flow from file upload to searchable document.

| Test Case | Components |
|-----------|------------|
| Upload PDF → OCR → extraction → embeddings stored | Upload, OCR, Extraction, Embeddings, Database |
| Upload image → converted to PDF → processed | Upload, OCR (image path), full pipeline |
| Upload duplicate file → detected and rejected | Watcher, Database |
| Upload when Ollama unavailable → queued | Upload, OCR, Queue, Database |
| Queue processor completes pending extraction | Queue, Extraction, Database |
| Reprocess document → re-runs full pipeline | Documents router, all services |

```python
class TestDocumentIngestionPipeline:
    async def test_full_upload_pipeline(self, client, mock_ollama, sample_pdf):
        # Configure mock Ollama response
        mock_ollama({
            "counterparty": "Test Company",
            "category": "invoice",
            "total_amount": 100.00
        })

        # Upload document
        with open(sample_pdf, "rb") as f:
            response = client.post("/api/documents", files={"file": f})

        assert response.status_code == 201
        doc_id = response.json()["id"]

        # Verify document fully processed
        doc = client.get(f"/api/documents/{doc_id}").json()
        assert doc["status"] == "completed"
        assert doc["counterparty"] == "Test Company"
        assert doc["category"] == "invoice"

        # Verify embeddings created
        async with aiosqlite.connect(test_db) as db:
            cursor = await db.execute(
                "SELECT COUNT(*) FROM document_embeddings WHERE document_id = ?",
                (doc_id,)
            )
            count = (await cursor.fetchone())[0]
            assert count == 1
```

### 2.2 Search Pipeline

**~6 tests**

| Test Case | Components |
|-----------|------------|
| Keyword search returns FTS5 matches | Search router, Database FTS5 |
| Semantic search returns similar documents | Search router, Embeddings |
| Hybrid search combines scores correctly | Search router, both paths |
| Filters applied to both search types | Search router, Database |
| Search with special characters | Search router, FTS5 escaping |
| Empty results handled gracefully | Search router |

```python
class TestSearchPipeline:
    async def test_hybrid_search_combines_results(self, client, seeded_db_with_embeddings):
        response = client.get("/api/search?q=electric+bill")

        assert response.status_code == 200
        results = response.json()["results"]

        # Should find the utility bill document
        assert len(results) > 0
        assert any(r["category"] == "utilities" for r in results)

        # Scores should be normalized 0-1
        for r in results:
            assert 0 <= r["score"] <= 1
```

### 2.3 Q&A (RAG) Pipeline

**~5 tests**

| Test Case | Components |
|-----------|------------|
| Question → finds docs → builds context → returns answer | Q&A router, Embeddings, Q&A service, Ollama |
| Question about specific document | Q&A router, Database, Q&A service |
| No relevant documents | Q&A router, Embeddings, Q&A service |
| Context exceeds limit → truncated | Q&A service |
| Ollama unavailable → error response | Q&A router, Q&A service |

### 2.4 Authentication Flow

**~5 tests**

| Test Case | Components |
|-----------|------------|
| Login → session created → cookie set → access protected routes | Auth router, Auth service, Database |
| Invalid password → 401 | Auth router, Auth service |
| Expired session → 401 | Auth middleware, Auth service |
| Logout → session deleted → cookie cleared | Auth router, Auth service |
| Protected route without auth → 401 | Auth middleware |

```python
class TestAuthFlow:
    def test_login_creates_session(self, client, test_db):
        response = client.post("/api/auth/login", json={"password": "testpass"})

        assert response.status_code == 200
        assert "session" in response.cookies

        # Verify can access protected route
        protected = client.get("/api/documents")
        assert protected.status_code == 200

    def test_logout_clears_session(self, client, authenticated_client):
        response = authenticated_client.post("/api/auth/logout")

        assert response.status_code == 200

        # Verify cannot access protected route
        protected = client.get("/api/documents")
        assert protected.status_code == 401
```

### 2.5 Document Lifecycle

**~5 tests**

| Test Case | Components |
|-----------|------------|
| Create → Read → Update → Delete | Documents router, Database |
| Delete removes file, embeddings, tags, FTS | Documents router, Database, File system |
| Update metadata re-indexes FTS | Documents router, Database |
| Add/remove tags persist | Documents router, Database |
| Thumbnail generation and caching | Documents router, File system |

### 2.6 Folder Watcher Pipeline

**~4 tests**

| Test Case | Components |
|-----------|------------|
| File in inbox → detected → processed → archived | Watcher, full pipeline |
| Invalid file type → ignored | Watcher |
| Process existing inbox on startup | Watcher, Main startup |
| File too large → rejected | Watcher |

---

## End-to-End Tests

E2E tests validate complete user workflows through the UI.

**Tools:** Playwright

### 3.1 Test Cases

**~10 tests**

| Workflow | Steps |
|----------|-------|
| Login flow | Navigate to login → Enter password → Redirected to documents |
| Document upload | Login → Click upload → Select file → See in list → View details |
| Document search | Login → Enter search query → See results → Click result → View document |
| Q&A interaction | Login → Go to Ask → Enter question → See answer with sources → Click source |
| Filter documents | Login → Select category filter → See filtered results → Clear filter |
| Edit document | Login → Open document → Edit title → Save → Verify change persisted |
| Delete document | Login → Open document → Delete → Confirm → Document removed from list |
| Pagination | Login → Navigate pages → Verify correct documents shown |
| Tag management | Login → Open document → Add tag → Remove tag |
| Logout | Login → Click logout → Redirected to login → Cannot access documents |

### 3.2 Test Structure

```typescript
// frontend/tests/e2e/auth.spec.ts
import { test, expect } from '@playwright/test';

test.describe('Authentication', () => {
  test('successful login redirects to documents', async ({ page }) => {
    await page.goto('/login');
    await page.fill('input[type="password"]', 'testpassword');
    await page.click('button[type="submit"]');

    await expect(page).toHaveURL('/documents');
    await expect(page.locator('h1')).toContainText('Documents');
  });

  test('invalid password shows error', async ({ page }) => {
    await page.goto('/login');
    await page.fill('input[type="password"]', 'wrongpassword');
    await page.click('button[type="submit"]');

    await expect(page.locator('.error')).toBeVisible();
    await expect(page).toHaveURL('/login');
  });
});
```

```typescript
// frontend/tests/e2e/documents.spec.ts
test.describe('Document Management', () => {
  test.beforeEach(async ({ page }) => {
    // Login before each test
    await login(page);
  });

  test('upload document appears in list', async ({ page }) => {
    await page.goto('/documents');
    await page.setInputFiles('input[type="file"]', 'tests/fixtures/sample.pdf');

    await expect(page.locator('.document-card')).toContainText('sample.pdf');
  });

  test('search filters documents', async ({ page }) => {
    await page.goto('/documents');
    await page.fill('input[placeholder="Search..."]', 'invoice');
    await page.press('input[placeholder="Search..."]', 'Enter');

    const cards = page.locator('.document-card');
    await expect(cards).toHaveCount(await cards.count());
    // Verify all visible cards match search
  });
});
```

---

## Smoke Tests

Quick sanity checks that core functionality works.

**~8 tests**

| Test | What It Validates |
|------|-------------------|
| App starts without errors | Startup health |
| `/health` returns 200 | Basic availability |
| Database connection works | Infrastructure |
| Can authenticate | Auth system |
| Can list documents | Core route |
| Can upload document | Upload pipeline |
| Can search | Search system |
| Ollama check (graceful if unavailable) | External dependency |

```python
# backend/tests/smoke/test_smoke.py
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

class TestSmoke:
    def test_health_endpoint(self):
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"

    def test_can_list_documents(self, authenticated_client):
        response = authenticated_client.get("/api/documents")
        assert response.status_code == 200
        assert "documents" in response.json()

    def test_can_search(self, authenticated_client):
        response = authenticated_client.get("/api/search?q=test")
        assert response.status_code == 200

    def test_ollama_check_graceful(self):
        """App should work even if Ollama is unavailable."""
        response = client.get("/health")
        assert response.status_code == 200
        # Ollama status may be false, but app is healthy
```

---

## Security Tests

Tests for common vulnerabilities.

**~10 tests**

| Vulnerability | Test Case |
|---------------|-----------|
| SQL Injection | Search query with SQL payload |
| Path Traversal | File download with `../` sequences |
| Auth Bypass | Access protected routes without token |
| Session Fixation | Reuse session token after logout |
| XSS | Document title with script tags (verify escaped in API) |
| CSRF | Mutation without proper origin |
| Timing Attack | Password comparison timing |
| File Type Validation | Upload executable disguised as PDF |
| Size Limits | Upload file exceeding max size |
| Rate Limiting | Brute force login attempts |

```python
# backend/tests/security/test_security.py
class TestSQLInjection:
    def test_search_query_escaped(self, authenticated_client):
        # Attempt SQL injection in search
        response = authenticated_client.get(
            "/api/search?q='; DROP TABLE documents;--"
        )
        assert response.status_code == 200

        # Verify documents table still exists
        response = authenticated_client.get("/api/documents")
        assert response.status_code == 200

class TestPathTraversal:
    def test_file_download_blocked(self, authenticated_client):
        response = authenticated_client.get(
            "/api/documents/file/..%2F..%2F..%2Fetc%2Fpasswd"
        )
        assert response.status_code in (400, 404)

    def test_thumbnail_path_blocked(self, authenticated_client):
        response = authenticated_client.get(
            "/api/documents/thumbnail/..%2F..%2F..%2Fetc%2Fpasswd"
        )
        assert response.status_code in (400, 404)

class TestAuthSecurity:
    def test_protected_route_without_auth(self, client):
        response = client.get("/api/documents")
        assert response.status_code == 401

    def test_invalid_session_token(self, client):
        client.cookies.set("session", "invalid-token")
        response = client.get("/api/documents")
        assert response.status_code == 401

    def test_expired_session_rejected(self, client, expired_session_token):
        client.cookies.set("session", expired_session_token)
        response = client.get("/api/documents")
        assert response.status_code == 401

class TestFileUploadSecurity:
    def test_rejects_executable(self, authenticated_client, tmp_path):
        # Create file with PDF extension but executable content
        fake_pdf = tmp_path / "malware.pdf"
        fake_pdf.write_bytes(b"MZ\x90\x00")  # PE header

        with open(fake_pdf, "rb") as f:
            response = authenticated_client.post(
                "/api/documents",
                files={"file": ("malware.pdf", f, "application/pdf")}
            )

        # Should reject based on content, not just extension
        assert response.status_code in (400, 415)
```

---

## Performance Tests

Verify system performance under load.

**Tools:** `pytest-benchmark`, `locust`

**~6 tests**

| Test | Target |
|------|--------|
| Search latency (1k documents) | < 200ms |
| Search latency (10k documents) | < 500ms |
| Upload throughput | > 5 docs/minute |
| Embedding generation | < 1s per document |
| Concurrent searches (10 parallel) | No errors, < 1s each |
| Memory usage during batch processing | Stable, no leaks |

```python
# backend/tests/performance/test_performance.py
import pytest

class TestSearchPerformance:
    @pytest.mark.performance
    def test_search_latency_1k_docs(self, benchmark, seeded_db_1k):
        def search():
            return client.get("/api/search?q=invoice")

        result = benchmark(search)
        assert result.elapsed < 0.2  # 200ms

    @pytest.mark.performance
    def test_search_latency_10k_docs(self, benchmark, seeded_db_10k):
        def search():
            return client.get("/api/search?q=invoice")

        result = benchmark(search)
        assert result.elapsed < 0.5  # 500ms

class TestConcurrency:
    @pytest.mark.performance
    async def test_concurrent_searches(self, authenticated_client, seeded_db):
        import asyncio

        async def search():
            return authenticated_client.get("/api/search?q=test")

        # Run 10 concurrent searches
        results = await asyncio.gather(*[search() for _ in range(10)])

        assert all(r.status_code == 200 for r in results)
```

### Locust Load Test

```python
# backend/tests/performance/locustfile.py
from locust import HttpUser, task, between

class DocStoreUser(HttpUser):
    wait_time = between(1, 3)

    def on_start(self):
        # Login
        self.client.post("/api/auth/login", json={"password": "testpass"})

    @task(3)
    def search_documents(self):
        self.client.get("/api/search?q=invoice")

    @task(2)
    def list_documents(self):
        self.client.get("/api/documents?limit=20")

    @task(1)
    def ask_question(self):
        self.client.post("/api/qa", json={"question": "What invoices are due?"})
```

---

## Resilience Tests

Verify graceful degradation when components fail.

**~8 tests**

| Scenario | Expected Behavior |
|----------|-------------------|
| Ollama unavailable during upload | Document processed, extraction queued |
| Ollama unavailable during Q&A | Returns error message, doesn't crash |
| Database locked | Returns 503, retries |
| OCR tool missing | Returns clear error |
| Embedding model fails to load | App starts, search degraded |
| File missing from disk | Returns 404, doesn't crash |
| Disk full during upload | Returns 507, cleans up partial |
| Queue processor crash | Restarts, resumes processing |

```python
# backend/tests/resilience/test_error_handling.py
class TestOllamaUnavailable:
    async def test_upload_queues_extraction(self, client, mock_ollama_unavailable, sample_pdf):
        with open(sample_pdf, "rb") as f:
            response = client.post("/api/documents", files={"file": f})

        assert response.status_code == 201
        doc_id = response.json()["id"]

        # Document should be queued, not failed
        doc = client.get(f"/api/documents/{doc_id}").json()
        assert doc["extraction_status"] == "pending"
        assert doc["status"] == "processing"  # Not failed

    async def test_qa_returns_error_gracefully(self, authenticated_client, mock_ollama_unavailable):
        response = authenticated_client.post(
            "/api/qa",
            json={"question": "What is this?"}
        )

        assert response.status_code == 503
        assert "unavailable" in response.json()["detail"].lower()

class TestFileMissing:
    async def test_download_missing_file(self, authenticated_client, test_db):
        # Insert document record without actual file
        doc_id = await insert_document_record(test_db, filename="missing.pdf")

        response = authenticated_client.get(f"/api/documents/{doc_id}/file")
        assert response.status_code == 404

class TestDatabaseErrors:
    async def test_handles_locked_database(self, client, locked_db):
        response = client.get("/api/documents")
        assert response.status_code in (503, 500)
        assert "database" in response.json()["detail"].lower()
```

---

## Migration Tests

Verify schema changes work correctly.

**~4 tests**

| Test | What It Validates |
|------|-------------------|
| Fresh install creates schema | Clean setup works |
| Migration adds new columns | Upgrade path works |
| Migration preserves data | No data loss |
| App works with migrated DB | Compatibility |

```python
# backend/tests/migration/test_migrations.py
class TestMigrations:
    async def test_fresh_install_creates_schema(self, tmp_path):
        db_path = tmp_path / "fresh.db"
        await init_database(str(db_path))

        async with aiosqlite.connect(db_path) as db:
            # Verify all tables exist
            cursor = await db.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
            tables = {row[0] for row in await cursor.fetchall()}

            assert "documents" in tables
            assert "documents_fts" in tables
            assert "document_embeddings" in tables
            assert "sessions" in tables

    async def test_migration_adds_extraction_status(self, tmp_path):
        db_path = tmp_path / "old.db"

        # Create old schema without extraction_status
        async with aiosqlite.connect(db_path) as db:
            await db.execute("""
                CREATE TABLE documents (
                    id TEXT PRIMARY KEY,
                    filename TEXT,
                    title TEXT,
                    status TEXT
                )
            """)
            await db.execute(
                "INSERT INTO documents VALUES ('doc1', 'test.pdf', 'Test', 'completed')"
            )
            await db.commit()

        # Run migration
        await init_database(str(db_path))

        # Verify column added and data preserved
        async with aiosqlite.connect(db_path) as db:
            cursor = await db.execute("SELECT * FROM documents WHERE id = 'doc1'")
            row = await cursor.fetchone()
            assert row is not None

            # Verify new column exists
            cursor = await db.execute("PRAGMA table_info(documents)")
            columns = {row[1] for row in await cursor.fetchall()}
            assert "extraction_status" in columns
```

---

## API Contract Tests

Ensure API responses match expected schemas.

**Tools:** Pydantic validation

```python
# backend/tests/contract/test_contracts.py
from pydantic import BaseModel, ValidationError
from typing import List, Optional

class DocumentResponse(BaseModel):
    id: str
    filename: str
    title: Optional[str]
    category: Optional[str]
    status: str
    created_at: str

class DocumentListResponse(BaseModel):
    documents: List[DocumentResponse]
    total: int
    offset: int
    limit: int

class TestDocumentContracts:
    def test_list_documents_schema(self, authenticated_client, seeded_db):
        response = authenticated_client.get("/api/documents")

        # Should not raise ValidationError
        data = DocumentListResponse.model_validate(response.json())
        assert data.total >= 0

    def test_get_document_schema(self, authenticated_client, seeded_db):
        response = authenticated_client.get("/api/documents/doc-001")

        data = DocumentResponse.model_validate(response.json())
        assert data.id == "doc-001"

    def test_error_response_schema(self, authenticated_client):
        response = authenticated_client.get("/api/documents/nonexistent")

        assert response.status_code == 404
        assert "detail" in response.json()
```

---

## Test Directory Structure

```
backend/
├── tests/
│   ├── __init__.py
│   ├── conftest.py                     # Shared fixtures
│   ├── fixtures/
│   │   ├── sample.pdf                  # Test PDF with text
│   │   ├── scanned.pdf                 # Scanned PDF (needs OCR)
│   │   ├── sample.jpg                  # Test image
│   │   └── seed_data.py                # Document seed data
│   ├── unit/
│   │   ├── __init__.py
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── test_extraction.py      # ~12 tests
│   │   │   ├── test_embeddings.py      # ~10 tests
│   │   │   ├── test_watcher.py         # ~12 tests
│   │   │   ├── test_qa.py              # ~6 tests
│   │   │   ├── test_queue.py           # ~6 tests
│   │   │   └── test_ocr.py             # ~8 tests
│   │   ├── routers/
│   │   │   ├── __init__.py
│   │   │   ├── test_documents.py       # ~10 tests
│   │   │   └── test_search.py          # ~8 tests
│   │   ├── test_auth.py                # ~8 tests
│   │   └── test_database.py            # ~6 tests
│   ├── integration/
│   │   ├── __init__.py
│   │   ├── test_document_pipeline.py   # ~6 tests
│   │   ├── test_search_pipeline.py     # ~6 tests
│   │   ├── test_qa_pipeline.py         # ~5 tests
│   │   ├── test_auth_flow.py           # ~5 tests
│   │   ├── test_document_lifecycle.py  # ~5 tests
│   │   └── test_watcher_pipeline.py    # ~4 tests
│   ├── smoke/
│   │   ├── __init__.py
│   │   └── test_smoke.py               # ~8 tests
│   ├── security/
│   │   ├── __init__.py
│   │   └── test_security.py            # ~10 tests
│   ├── performance/
│   │   ├── __init__.py
│   │   ├── test_performance.py         # ~6 tests
│   │   └── locustfile.py               # Load testing
│   ├── resilience/
│   │   ├── __init__.py
│   │   └── test_error_handling.py      # ~8 tests
│   ├── migration/
│   │   ├── __init__.py
│   │   └── test_migrations.py          # ~4 tests
│   └── contract/
│       ├── __init__.py
│       └── test_contracts.py           # ~6 tests
│
frontend/
├── tests/
│   ├── unit/
│   │   ├── api.test.ts                 # ~15 tests
│   │   └── stores.test.ts              # ~7 tests
│   ├── e2e/
│   │   ├── auth.spec.ts                # ~3 tests
│   │   ├── documents.spec.ts           # ~4 tests
│   │   ├── search.spec.ts              # ~2 tests
│   │   └── qa.spec.ts                  # ~1 test
│   └── smoke/
│       └── smoke.spec.ts               # ~3 tests
├── playwright.config.ts
└── vitest.config.ts
```

---

## Implementation Plan

### Phase 1: Test Infrastructure (Week 1)

1. Set up `conftest.py` with core fixtures
2. Create mock Ollama helper
3. Add sample test files (PDF, images)
4. Configure pytest settings in `pyproject.toml`
5. Add test commands to `Makefile`

**Deliverables:**
- Working test infrastructure
- `make test` command
- CI pipeline configuration

### Phase 2: Smoke + Critical Unit Tests (Week 2)

1. Implement smoke tests (~8 tests)
2. Extraction service unit tests (~12 tests)
3. Search scoring unit tests (~8 tests)
4. Auth service unit tests (~8 tests)

**Deliverables:**
- CI gate with smoke tests
- Core business logic covered

### Phase 3: Remaining Unit Tests (Week 3)

1. Embeddings service (~10 tests)
2. Watcher service (~12 tests)
3. Q&A service (~6 tests)
4. Queue service (~6 tests)
5. OCR service (~8 tests)
6. Database tests (~6 tests)
7. Router tests (~18 tests)

**Deliverables:**
- Full unit test coverage

### Phase 4: Integration Tests (Week 4)

1. Document ingestion pipeline (~6 tests)
2. Search pipeline (~6 tests)
3. Q&A pipeline (~5 tests)
4. Auth flow (~5 tests)
5. Document lifecycle (~5 tests)
6. Watcher pipeline (~4 tests)

**Deliverables:**
- Pipeline correctness verified

### Phase 5: Specialized Tests (Week 5)

1. Security tests (~10 tests)
2. Resilience tests (~8 tests)
3. Migration tests (~4 tests)
4. Contract tests (~6 tests)

**Deliverables:**
- Security vulnerabilities covered
- Error handling verified

### Phase 6: E2E + Performance (Week 6)

1. Set up Playwright
2. Implement E2E tests (~10 tests)
3. Set up performance benchmarks (~6 tests)
4. Create Locust load tests

**Deliverables:**
- Full user workflow coverage
- Performance baselines

---

## Makefile Additions

```makefile
# Run all tests
test:
	cd backend && uv run pytest

# Run specific test categories
test-unit:
	cd backend && uv run pytest tests/unit

test-integration:
	cd backend && uv run pytest tests/integration

test-smoke:
	cd backend && uv run pytest tests/smoke

test-security:
	cd backend && uv run pytest tests/security

test-performance:
	cd backend && uv run pytest tests/performance -m performance

# Run with coverage
test-coverage:
	cd backend && uv run pytest --cov=app --cov-report=html

# Run frontend tests
test-frontend:
	cd frontend && npm run test

test-e2e:
	cd frontend && npm run test:e2e

# Run all tests (backend + frontend)
test-all: test test-frontend
```

---

## CI Pipeline Configuration

```yaml
# .github/workflows/test.yml
name: Tests

on: [push, pull_request]

jobs:
  smoke:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v4
      - run: cd backend && uv sync
      - run: cd backend && uv run pytest tests/smoke -v

  unit:
    needs: smoke
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v4
      - run: cd backend && uv sync
      - run: cd backend && uv run pytest tests/unit -v --cov=app

  integration:
    needs: unit
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v4
      - run: cd backend && uv sync
      - run: cd backend && uv run pytest tests/integration -v

  security:
    needs: unit
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v4
      - run: cd backend && uv sync
      - run: cd backend && uv run pytest tests/security -v

  e2e:
    needs: integration
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
      - run: cd frontend && npm ci
      - run: cd frontend && npx playwright install --with-deps
      - run: cd frontend && npm run test:e2e
```

---

## Success Metrics

| Metric | Target |
|--------|--------|
| Unit test coverage | > 80% |
| Integration test coverage | All critical paths |
| Smoke test pass rate | 100% for deploy |
| Security test pass rate | 100% |
| E2E test pass rate | > 95% |
| CI pipeline duration | < 10 minutes |
| Flaky test rate | < 2% |
