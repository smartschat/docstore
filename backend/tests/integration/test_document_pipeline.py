"""Integration tests for document ingestion pipeline."""

import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
import json

import aiosqlite


class TestUploadPipeline:
    """Test full document upload pipeline."""

    @pytest.mark.asyncio
    async def test_upload_pdf_processes_complete_pipeline(
        self, authenticated_client, sample_pdf, test_db, test_settings
    ):
        """Upload PDF triggers OCR, extraction, and embedding generation."""
        # Mock OCR to return success with text
        mock_ocr_result = MagicMock()
        mock_ocr_result.success = True
        mock_ocr_result.text = "Invoice from Test Company. Total: $150.00"
        mock_ocr_result.page_count = 1
        mock_ocr_result.error = None

        # Mock Ollama extraction response
        extraction_response = {
            "counterparty": "Test Company",
            "category": "invoice",
            "total_amount": 150.00,
            "title": "Invoice from Test Company"
        }

        with patch("app.services.watcher.extract_text_from_file", new_callable=AsyncMock) as mock_ocr, \
             patch("app.services.extraction.check_ollama_available", new_callable=AsyncMock) as mock_ollama_check, \
             patch("app.services.extraction.call_ollama", new_callable=AsyncMock) as mock_call_ollama, \
             patch("app.services.embeddings.generate_embedding") as mock_embed:

            mock_ocr.return_value = mock_ocr_result
            mock_ollama_check.return_value = True
            mock_call_ollama.return_value = json.dumps(extraction_response)
            mock_embed.return_value = [0.1] * 384  # Mock embedding vector

            # Upload document
            with open(sample_pdf, "rb") as f:
                response = authenticated_client.post(
                    "/api/documents/upload",
                    files={"file": ("test.pdf", f, "application/pdf")}
                )

            assert response.status_code == 200
            doc_id = response.json()["id"]

            # Verify document was created with extracted metadata
            async with aiosqlite.connect(test_db) as db:
                db.row_factory = aiosqlite.Row
                cursor = await db.execute(
                    "SELECT * FROM documents WHERE id = ?",
                    (doc_id,)
                )
                row = await cursor.fetchone()

                assert row is not None
                assert row["raw_text"] == mock_ocr_result.text

    @pytest.mark.asyncio
    async def test_upload_queues_extraction_when_ollama_unavailable(
        self, authenticated_client, sample_pdf, test_db, test_settings
    ):
        """Upload queues extraction when Ollama is unavailable."""
        # Mock OCR to return success
        mock_ocr_result = MagicMock()
        mock_ocr_result.success = True
        mock_ocr_result.text = "Document text content"
        mock_ocr_result.page_count = 1
        mock_ocr_result.error = None

        with patch("app.services.watcher.extract_text_from_file", new_callable=AsyncMock) as mock_ocr, \
             patch("app.services.extraction.check_ollama_available", new_callable=AsyncMock) as mock_ollama_check, \
             patch("app.services.embeddings.generate_embedding") as mock_embed:

            mock_ocr.return_value = mock_ocr_result
            mock_ollama_check.return_value = False  # Ollama unavailable
            mock_embed.return_value = [0.1] * 384

            with open(sample_pdf, "rb") as f:
                response = authenticated_client.post(
                    "/api/documents/upload",
                    files={"file": ("test.pdf", f, "application/pdf")}
                )

            assert response.status_code == 200
            doc_id = response.json()["id"]

            # Verify document was created with pending extraction status
            async with aiosqlite.connect(test_db) as db:
                cursor = await db.execute(
                    "SELECT extraction_status FROM documents WHERE id = ?",
                    (doc_id,)
                )
                row = await cursor.fetchone()
                assert row[0] == "pending"

    @pytest.mark.asyncio
    async def test_upload_same_filename_different_content(
        self, authenticated_client, sample_pdf, test_db, test_settings, tmp_path
    ):
        """Uploading files with same filename but different content creates separate documents."""
        # Mock OCR and extraction
        mock_ocr_result = MagicMock()
        mock_ocr_result.success = True
        mock_ocr_result.text = "Test content"
        mock_ocr_result.page_count = 1
        mock_ocr_result.error = None

        # Create a second PDF with different content
        pdf2 = tmp_path / "test2.pdf"
        pdf2.write_bytes(b"%PDF-1.4\ndifferent content here")

        with patch("app.services.watcher.extract_text_from_file", new_callable=AsyncMock) as mock_ocr, \
             patch("app.services.extraction.check_ollama_available", new_callable=AsyncMock) as mock_ollama_check, \
             patch("app.services.embeddings.generate_embedding") as mock_embed:

            mock_ocr.return_value = mock_ocr_result
            mock_ollama_check.return_value = False
            mock_embed.return_value = [0.1] * 384

            # Upload first file
            with open(sample_pdf, "rb") as f:
                response1 = authenticated_client.post(
                    "/api/documents/upload",
                    files={"file": ("test.pdf", f, "application/pdf")}
                )
            assert response1.status_code == 200
            doc1_id = response1.json()["id"]

            # Upload second file with same name but different content
            with open(pdf2, "rb") as f:
                response2 = authenticated_client.post(
                    "/api/documents/upload",
                    files={"file": ("test.pdf", f, "application/pdf")}
                )

            # Should succeed with modified filename
            assert response2.status_code == 200
            doc2_id = response2.json()["id"]
            # Different documents created
            assert doc1_id != doc2_id

    def test_upload_unsupported_file_type_rejected(self, authenticated_client, tmp_path):
        """Uploading unsupported file type is rejected."""
        # Create an unsupported file
        unsupported_file = tmp_path / "test.exe"
        unsupported_file.write_bytes(b"MZ\x90\x00")

        with open(unsupported_file, "rb") as f:
            response = authenticated_client.post(
                "/api/documents/upload",
                files={"file": ("test.exe", f, "application/octet-stream")}
            )

        assert response.status_code == 400
        assert "Unsupported" in response.json()["detail"]


class TestReprocessDocument:
    """Test document reprocessing."""

    @pytest.mark.asyncio
    async def test_reprocess_reruns_full_pipeline(
        self, authenticated_client, seeded_db, test_settings
    ):
        """Reprocessing a document runs the full pipeline again."""
        doc_id = "doc-001"

        # Update the document file_path to match our test setup
        async with aiosqlite.connect(seeded_db) as db:
            await db.execute(
                "UPDATE documents SET file_path = ? WHERE id = ?",
                ("archive/invoice_2024.pdf", doc_id)
            )
            await db.commit()

        mock_ocr_result = MagicMock()
        mock_ocr_result.success = True
        mock_ocr_result.text = "Updated text content after reprocessing"
        mock_ocr_result.page_count = 2
        mock_ocr_result.error = None

        extraction_response = {
            "counterparty": "Updated Company",
            "category": "utilities",
            "title": "Reprocessed Document"
        }

        # Create a fake file for the document
        file_path = test_settings.data_dir / "archive" / "invoice_2024.pdf"
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_bytes(b"%PDF-1.4\ntest content")

        with patch("app.services.ocr.extract_text_from_file", new_callable=AsyncMock) as mock_ocr, \
             patch("app.services.extraction.check_ollama_available", new_callable=AsyncMock) as mock_ollama_check, \
             patch("app.services.extraction.process_document_extraction", new_callable=AsyncMock) as mock_extraction, \
             patch("app.services.embeddings.embed_document", new_callable=AsyncMock) as mock_embed:

            mock_ocr.return_value = mock_ocr_result
            mock_ollama_check.return_value = True
            mock_extraction.return_value = extraction_response
            mock_embed.return_value = None

            response = authenticated_client.post(f"/api/reprocess/{doc_id}")

            assert response.status_code == 200
            assert response.json()["message"] == "Document reprocessed successfully"

    @pytest.mark.asyncio
    async def test_reprocess_nonexistent_document_returns_404(
        self, authenticated_client, test_db
    ):
        """Reprocessing non-existent document returns 404."""
        response = authenticated_client.post("/api/reprocess/nonexistent-id")

        assert response.status_code == 404


class TestQueueProcessor:
    """Test queue processor integration."""

    @pytest.mark.asyncio
    async def test_queue_processes_pending_extractions(self, test_db, test_settings):
        """Queue processor processes pending extractions when Ollama becomes available."""
        from app.services.queue import process_pending_extraction

        raw_text = "Invoice from Queue Company. Total: $200.00"

        # Insert a document with pending extraction
        async with aiosqlite.connect(test_db) as db:
            await db.execute("""
                INSERT INTO documents (
                    id, filename, file_path, file_hash, file_size, mime_type,
                    raw_text, page_count, status, extraction_status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                "pending-doc-001", "pending.pdf", "archive/pending.pdf",
                "hash123", 1024, "application/pdf",
                raw_text,
                1, "processing", "pending", "2024-01-01T00:00:00"
            ))
            await db.commit()

        extraction_response = {
            "counterparty": "Queue Company",
            "category": "invoice",
            "total_amount": 200.00,
            "title": "Queue Test Invoice"
        }

        with patch("app.services.extraction.process_document_extraction", new_callable=AsyncMock) as mock_extraction:

            mock_extraction.return_value = extraction_response

            # Process the pending extraction - function expects a dict with 'id' and 'raw_text'
            doc = {"id": "pending-doc-001", "raw_text": raw_text}
            result = await process_pending_extraction(doc)

            assert result is True

            # Verify extraction status updated
            async with aiosqlite.connect(test_db) as db:
                cursor = await db.execute(
                    "SELECT extraction_status, counterparty FROM documents WHERE id = ?",
                    ("pending-doc-001",)
                )
                row = await cursor.fetchone()
                assert row[0] == "completed"
                assert row[1] == "Queue Company"
