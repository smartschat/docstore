"""Unit tests for documents router."""

from unittest.mock import patch

import aiosqlite
import pytest
from app.models import DocumentStatus, Tag
from app.routers.documents import (
    get_document_by_id,
    get_document_tags,
    row_to_document,
)


class TestGetDocumentById:
    """Tests for get_document_by_id function."""

    @pytest.mark.asyncio
    async def test_returns_document(self, seeded_db, test_settings):
        """Returns document when found."""
        # Directly query the database to verify seeding worked
        async with aiosqlite.connect(seeded_db) as db:
            cursor = await db.execute("SELECT id FROM documents WHERE id = 'doc-001'")
            row = await cursor.fetchone()
            assert row is not None, "Seed data not found in database"

        result = await get_document_by_id("doc-001")

        assert result is not None
        assert result["id"] == "doc-001"
        assert result["filename"] == "invoice_2024.pdf"

    @pytest.mark.asyncio
    async def test_returns_none_for_nonexistent(self, seeded_db, test_settings):
        """Returns None when document not found."""
        result = await get_document_by_id("nonexistent-id")

        assert result is None


class TestGetDocumentTags:
    """Tests for get_document_tags function."""

    @pytest.mark.asyncio
    async def test_returns_empty_for_no_tags(self, seeded_db):
        """Returns empty list when document has no tags."""
        result = await get_document_tags("doc-001")

        assert result == []

    @pytest.mark.asyncio
    async def test_returns_tags(self, seeded_db, db_connection):
        """Returns tags for a document."""
        # Add a tag to doc-001
        await db_connection.execute("INSERT INTO tags (id, name) VALUES (1, 'important')")
        await db_connection.execute(
            "INSERT INTO document_tags (doc_id, tag_id) VALUES ('doc-001', 1)"
        )
        await db_connection.commit()

        result = await get_document_tags("doc-001")

        assert len(result) == 1
        assert result[0].name == "important"


class TestRowToDocument:
    """Tests for row_to_document function."""

    def test_converts_row_to_document(self):
        """Converts database row to Document model."""
        row = {
            "id": "test-id",
            "filename": "test.pdf",
            "file_path": "archive/test.pdf",
            "file_hash": "hash123",
            "file_size": 1024,
            "mime_type": "application/pdf",
            "raw_text": "Document content",
            "page_count": 2,
            "summary": "A summary",
            "document_date": "2024-01-15",
            "created_at": "2024-01-01T00:00:00",
            "processed_at": "2024-01-01T00:01:00",
            "status": "completed",
            "extraction_status": "completed",
            "title": "Test Document",
            "counterparty": "Test Corp",
            "affected_person": "John Doe",
            "category": "invoice",
            "reference": "INV-001",
        }

        result = row_to_document(row)

        assert result.id == "test-id"
        assert result.filename == "test.pdf"
        assert result.title == "Test Document"
        assert result.counterparty == "Test Corp"
        assert result.status == DocumentStatus.COMPLETED

    def test_handles_null_timestamps(self):
        """Handles null timestamps correctly."""
        row = {
            "id": "test-id",
            "filename": "test.pdf",
            "file_path": "archive/test.pdf",
            "file_hash": "hash123",
            "file_size": 1024,
            "mime_type": "application/pdf",
            "raw_text": None,
            "page_count": 0,
            "summary": None,
            "document_date": None,
            "created_at": None,
            "processed_at": None,
            "status": "pending",
            "extraction_status": None,
            "title": None,
            "counterparty": None,
            "affected_person": None,
            "category": None,
            "reference": None,
        }

        result = row_to_document(row)

        assert result.created_at is not None  # Falls back to utcnow
        assert result.processed_at is None

    def test_includes_tags(self):
        """Includes tags when provided."""
        row = {
            "id": "test-id",
            "filename": "test.pdf",
            "file_path": "archive/test.pdf",
            "file_hash": "hash123",
            "file_size": 1024,
            "mime_type": "application/pdf",
            "raw_text": None,
            "page_count": 0,
            "summary": None,
            "document_date": None,
            "created_at": "2024-01-01T00:00:00",
            "processed_at": None,
            "status": "completed",
        }

        tags = [Tag(id=1, name="important"), Tag(id=2, name="urgent")]
        result = row_to_document(row, tags)

        assert len(result.tags) == 2
        assert result.tags[0].name == "important"


class TestListDocumentsEndpoint:
    """Tests for GET /api/documents endpoint."""

    @pytest.mark.asyncio
    async def test_list_documents_pagination(self, seeded_db, db_connection):
        """Pagination works correctly."""
        from app.routers.documents import list_documents

        # Mock the dependency
        with patch("app.routers.documents.get_current_session", return_value="valid-session"):
            result = await list_documents(page=1, page_size=2)

        assert result.page == 1
        assert result.page_size == 2
        assert len(result.items) <= 2

    @pytest.mark.asyncio
    async def test_list_documents_filter_by_category(self, seeded_db):
        """Category filter works correctly."""
        from app.routers.documents import list_documents

        with patch("app.routers.documents.get_current_session", return_value="valid-session"):
            result = await list_documents(page=1, page_size=20, category="utilities")

        assert all(doc.category == "utilities" for doc in result.items)

    @pytest.mark.asyncio
    async def test_list_documents_filter_by_status(self, seeded_db):
        """Status filter works correctly."""
        from app.routers.documents import list_documents

        with patch("app.routers.documents.get_current_session", return_value="valid-session"):
            result = await list_documents(page=1, page_size=20, status="completed")

        assert all(doc.status == DocumentStatus.COMPLETED for doc in result.items)


class TestGetDocumentEndpoint:
    """Tests for GET /api/documents/{doc_id} endpoint."""

    @pytest.mark.asyncio
    async def test_returns_document(self, seeded_db):
        """Returns document when found."""
        from app.routers.documents import get_document

        with patch("app.routers.documents.get_current_session", return_value="valid-session"):
            result = await get_document("doc-001")

        assert result.id == "doc-001"
        assert result.filename == "invoice_2024.pdf"

    @pytest.mark.asyncio
    async def test_returns_404_for_nonexistent(self, seeded_db):
        """Returns 404 when document not found."""
        from app.routers.documents import get_document
        from fastapi import HTTPException

        with patch("app.routers.documents.get_current_session", return_value="valid-session"):
            with pytest.raises(HTTPException) as exc_info:
                await get_document("nonexistent")

        assert exc_info.value.status_code == 404


class TestUpdateDocumentEndpoint:
    """Tests for PATCH /api/documents/{doc_id} endpoint."""

    @pytest.mark.asyncio
    async def test_updates_title(self, seeded_db, db_connection):
        """Updates document title."""
        from app.models import DocumentUpdate
        from app.routers.documents import update_document

        update = DocumentUpdate(title="New Title")

        with patch("app.routers.documents.get_current_session", return_value="valid-session"):
            result = await update_document("doc-001", update)

        assert result.title == "New Title"

        # Verify in database
        cursor = await db_connection.execute(
            "SELECT title FROM documents WHERE id = ?", ("doc-001",)
        )
        row = await cursor.fetchone()
        assert row["title"] == "New Title"

    @pytest.mark.asyncio
    async def test_updates_category(self, seeded_db, db_connection):
        """Updates document category."""
        from app.models import DocumentUpdate
        from app.routers.documents import update_document

        update = DocumentUpdate(category="tax")

        with patch("app.routers.documents.get_current_session", return_value="valid-session"):
            result = await update_document("doc-001", update)

        assert result.category == "tax"

    @pytest.mark.asyncio
    async def test_returns_404_for_nonexistent(self, seeded_db):
        """Returns 404 when document not found."""
        from app.models import DocumentUpdate
        from app.routers.documents import update_document
        from fastapi import HTTPException

        update = DocumentUpdate(title="New Title")

        with patch("app.routers.documents.get_current_session", return_value="valid-session"):
            with pytest.raises(HTTPException) as exc_info:
                await update_document("nonexistent", update)

        assert exc_info.value.status_code == 404


class TestDeleteDocumentEndpoint:
    """Tests for DELETE /api/documents/{doc_id} endpoint."""

    @pytest.mark.asyncio
    async def test_deletes_document(self, seeded_db, db_connection, test_settings):
        """Deletes document from database."""
        from app.routers.documents import delete_document

        # Create fake file
        file_path = test_settings.data_dir / "archive" / "invoice_2024.pdf"
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_bytes(b"%PDF-1.4")

        # Update document to point to real file
        await db_connection.execute(
            "UPDATE documents SET file_path = ? WHERE id = ?",
            ("archive/invoice_2024.pdf", "doc-001"),
        )
        await db_connection.commit()

        with patch("app.routers.documents.get_current_session", return_value="valid-session"):
            result = await delete_document("doc-001")

        assert result["message"] == "Document deleted"

        # Verify deleted from database
        cursor = await db_connection.execute("SELECT id FROM documents WHERE id = ?", ("doc-001",))
        row = await cursor.fetchone()
        assert row is None

    @pytest.mark.asyncio
    async def test_returns_404_for_nonexistent(self, seeded_db):
        """Returns 404 when document not found."""
        from app.routers.documents import delete_document
        from fastapi import HTTPException

        with patch("app.routers.documents.get_current_session", return_value="valid-session"):
            with pytest.raises(HTTPException) as exc_info:
                await delete_document("nonexistent")

        assert exc_info.value.status_code == 404


class TestAddTagsEndpoint:
    """Tests for POST /api/documents/{doc_id}/tags endpoint."""

    @pytest.mark.asyncio
    async def test_adds_tags(self, seeded_db, db_connection):
        """Adds tags to document."""
        from app.routers.documents import add_tags

        with patch("app.routers.documents.get_current_session", return_value="valid-session"):
            result = await add_tags("doc-001", ["important", "reviewed"])

        assert result["message"] == "Tags added"

        # Verify tags in database
        cursor = await db_connection.execute(
            """
            SELECT t.name FROM tags t
            JOIN document_tags dt ON dt.tag_id = t.id
            WHERE dt.doc_id = ?
        """,
            ("doc-001",),
        )
        rows = await cursor.fetchall()
        tag_names = [row["name"] for row in rows]
        assert "important" in tag_names
        assert "reviewed" in tag_names

    @pytest.mark.asyncio
    async def test_returns_404_for_nonexistent_document(self, seeded_db):
        """Returns 404 when document not found."""
        from app.routers.documents import add_tags
        from fastapi import HTTPException

        with patch("app.routers.documents.get_current_session", return_value="valid-session"):
            with pytest.raises(HTTPException) as exc_info:
                await add_tags("nonexistent", ["tag"])

        assert exc_info.value.status_code == 404


class TestRemoveTagEndpoint:
    """Tests for DELETE /api/documents/{doc_id}/tags/{tag_name} endpoint."""

    @pytest.mark.asyncio
    async def test_removes_tag(self, seeded_db, db_connection):
        """Removes tag from document."""
        from app.routers.documents import add_tags, remove_tag

        # First add a tag
        with patch("app.routers.documents.get_current_session", return_value="valid-session"):
            await add_tags("doc-001", ["to-remove"])
            result = await remove_tag("doc-001", "to-remove")

        assert result["message"] == "Tag removed"

        # Verify tag removed
        cursor = await db_connection.execute(
            """
            SELECT t.name FROM tags t
            JOIN document_tags dt ON dt.tag_id = t.id
            WHERE dt.doc_id = ? AND t.name = ?
        """,
            ("doc-001", "to-remove"),
        )
        row = await cursor.fetchone()
        assert row is None


class TestDownloadFileEndpoint:
    """Tests for GET /api/documents/{doc_id}/file endpoint."""

    @pytest.mark.asyncio
    async def test_returns_404_for_nonexistent_document(self, seeded_db):
        """Returns 404 when document not found."""
        from app.routers.documents import download_file
        from fastapi import HTTPException

        with patch("app.routers.documents.get_current_session", return_value="valid-session"):
            with pytest.raises(HTTPException) as exc_info:
                await download_file("nonexistent")

        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_returns_404_for_missing_file(self, seeded_db, db_connection, test_settings):
        """Returns 404 when file doesn't exist on disk."""
        from app.routers.documents import download_file
        from fastapi import HTTPException

        # Update document to point to non-existent file
        await db_connection.execute(
            "UPDATE documents SET file_path = ? WHERE id = ?", ("archive/missing.pdf", "doc-001")
        )
        await db_connection.commit()

        with patch("app.routers.documents.get_current_session", return_value="valid-session"):
            with pytest.raises(HTTPException) as exc_info:
                await download_file("doc-001")

        assert exc_info.value.status_code == 404
