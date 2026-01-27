"""Integration tests for document lifecycle (CRUD operations)."""

import aiosqlite
import pytest


class TestDocumentCRUD:
    """Test document create, read, update, delete operations."""

    def test_list_documents_returns_paginated_results(self, authenticated_client, seeded_db):
        """List documents returns paginated results."""
        response = authenticated_client.get("/api/documents?page=1&page_size=10")

        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert "page" in data
        assert "page_size" in data
        assert data["page"] == 1
        assert data["page_size"] == 10

    def test_list_documents_filter_by_category(self, authenticated_client, seeded_db):
        """List documents can filter by category."""
        response = authenticated_client.get("/api/documents?category=utilities")

        assert response.status_code == 200
        data = response.json()
        for item in data["items"]:
            assert item["category"] == "utilities"

    def test_list_documents_filter_by_status(self, authenticated_client, seeded_db):
        """List documents can filter by status."""
        response = authenticated_client.get("/api/documents?status=completed")

        assert response.status_code == 200
        data = response.json()
        for item in data["items"]:
            assert item["status"] == "completed"

    def test_get_document_by_id(self, authenticated_client, seeded_db):
        """Get single document by ID."""
        response = authenticated_client.get("/api/documents/doc-001")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "doc-001"
        assert data["filename"] == "invoice_2024.pdf"
        assert data["category"] == "utilities"

    def test_get_nonexistent_document_returns_404(self, authenticated_client, seeded_db):
        """Get non-existent document returns 404."""
        response = authenticated_client.get("/api/documents/nonexistent-id")

        assert response.status_code == 404

    def test_update_document_metadata(self, authenticated_client, seeded_db):
        """Update document metadata."""
        response = authenticated_client.patch(
            "/api/documents/doc-001", json={"title": "Updated Electric Bill", "category": "banking"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "Updated Electric Bill"
        assert data["category"] == "banking"

    @pytest.mark.asyncio
    async def test_delete_document_removes_all_data(
        self, authenticated_client, seeded_db, test_settings
    ):
        """Delete document removes file, database record, and related data."""
        doc_id = "doc-001"

        # Update the document file_path to match our test setup
        async with aiosqlite.connect(seeded_db) as db:
            await db.execute(
                "UPDATE documents SET file_path = ? WHERE id = ?",
                ("archive/invoice_2024.pdf", doc_id),
            )
            await db.commit()

        # Create a fake file for the document
        file_path = test_settings.data_dir / "archive" / "invoice_2024.pdf"
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_bytes(b"%PDF-1.4\ntest content")

        # Delete document
        response = authenticated_client.delete(f"/api/documents/{doc_id}")

        assert response.status_code == 200

        # Verify document removed from database
        async with aiosqlite.connect(seeded_db) as db:
            cursor = await db.execute("SELECT * FROM documents WHERE id = ?", (doc_id,))
            assert await cursor.fetchone() is None

        # Verify file removed
        assert not file_path.exists()

    def test_delete_nonexistent_document_returns_404(self, authenticated_client, seeded_db):
        """Delete non-existent document returns 404."""
        response = authenticated_client.delete("/api/documents/nonexistent-id")

        assert response.status_code == 404


class TestTagManagement:
    """Test document tag operations."""

    @pytest.mark.asyncio
    async def test_add_tags_to_document(self, authenticated_client, seeded_db):
        """Add tags to a document."""
        doc_id = "doc-001"

        response = authenticated_client.post(
            f"/api/documents/{doc_id}/tags", json=["important", "reviewed"]
        )

        assert response.status_code == 200

        # Verify tags were added
        doc_response = authenticated_client.get(f"/api/documents/{doc_id}")
        tags = [t["name"] for t in doc_response.json()["tags"]]
        assert "important" in tags
        assert "reviewed" in tags

    @pytest.mark.asyncio
    async def test_remove_tag_from_document(self, authenticated_client, seeded_db):
        """Remove tag from document."""
        doc_id = "doc-001"

        # First add a tag
        authenticated_client.post(f"/api/documents/{doc_id}/tags", json=["to-remove"])

        # Then remove it
        response = authenticated_client.delete(f"/api/documents/{doc_id}/tags/to-remove")

        assert response.status_code == 200

        # Verify tag was removed
        doc_response = authenticated_client.get(f"/api/documents/{doc_id}")
        tags = [t["name"] for t in doc_response.json()["tags"]]
        assert "to-remove" not in tags

    def test_list_all_tags(self, authenticated_client, seeded_db):
        """List all available tags."""
        # First add some tags and verify they were added
        add_response = authenticated_client.post(
            "/api/documents/doc-001/tags", json=["tag1", "tag2"]
        )
        assert add_response.status_code == 200

        # List all tags
        response = authenticated_client.get("/api/tags")

        assert response.status_code == 200
        tag_names = [t["name"] for t in response.json()]
        assert "tag1" in tag_names
        assert "tag2" in tag_names


class TestDocumentFileOperations:
    """Test document file operations."""

    @pytest.mark.asyncio
    async def test_download_document_file(self, authenticated_client, seeded_db, test_settings):
        """Download document file."""
        doc_id = "doc-001"

        # Update the document file_path to match our test setup
        async with aiosqlite.connect(seeded_db) as db:
            await db.execute(
                "UPDATE documents SET file_path = ? WHERE id = ?",
                ("archive/invoice_2024.pdf", doc_id),
            )
            await db.commit()

        # Create the file
        file_path = test_settings.data_dir / "archive" / "invoice_2024.pdf"
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_bytes(b"%PDF-1.4\ntest content")

        response = authenticated_client.get(f"/api/documents/{doc_id}/file")

        assert response.status_code == 200
        assert response.headers["content-type"] == "application/pdf"

    @pytest.mark.asyncio
    async def test_download_missing_file_returns_404(self, authenticated_client, seeded_db):
        """Download missing file returns 404."""
        # The seed data has a file_path that doesn't exist
        response = authenticated_client.get("/api/documents/doc-001/file")

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_download_with_download_header(
        self, authenticated_client, seeded_db, test_settings
    ):
        """Download with download flag sets attachment header."""
        doc_id = "doc-001"

        # Update the document file_path to match our test setup
        async with aiosqlite.connect(seeded_db) as db:
            await db.execute(
                "UPDATE documents SET file_path = ? WHERE id = ?",
                ("archive/invoice_2024.pdf", doc_id),
            )
            await db.commit()

        # Create the file
        file_path = test_settings.data_dir / "archive" / "invoice_2024.pdf"
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_bytes(b"%PDF-1.4\ntest content")

        response = authenticated_client.get(f"/api/documents/{doc_id}/file?download=true")

        assert response.status_code == 200
        assert "attachment" in response.headers.get("content-disposition", "")
