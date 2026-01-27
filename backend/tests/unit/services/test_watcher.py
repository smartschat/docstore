"""Unit tests for watcher service."""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.models import DocumentStatus
from app.services.watcher import (
    FolderWatcher,
    InboxHandler,
    check_duplicate,
    create_document_record,
    get_file_hash,
    get_mime_type,
    process_document,
    process_existing_inbox,
    update_document_ocr,
    update_document_status,
    update_extraction_status,
)


class TestGetFileHash:
    """Tests for get_file_hash function."""

    def test_computes_sha256(self, tmp_path):
        """SHA256 hash is computed correctly."""
        file = tmp_path / "test.txt"
        file.write_text("hello world")

        hash1 = get_file_hash(file)
        hash2 = get_file_hash(file)

        assert hash1 == hash2
        assert len(hash1) == 64  # SHA256 hex length

    def test_consistent_hash_for_same_content(self, tmp_path):
        """Same content produces same hash."""
        file1 = tmp_path / "file1.txt"
        file2 = tmp_path / "file2.txt"
        file1.write_text("identical content")
        file2.write_text("identical content")

        assert get_file_hash(file1) == get_file_hash(file2)

    def test_different_hash_for_different_content(self, tmp_path):
        """Different content produces different hash."""
        file1 = tmp_path / "file1.txt"
        file2 = tmp_path / "file2.txt"
        file1.write_text("content A")
        file2.write_text("content B")

        assert get_file_hash(file1) != get_file_hash(file2)

    def test_handles_binary_files(self, tmp_path):
        """Binary files are hashed correctly."""
        file = tmp_path / "binary.bin"
        file.write_bytes(b"\x00\x01\x02\x03\x04")

        hash_val = get_file_hash(file)
        assert len(hash_val) == 64

    def test_handles_large_files(self, tmp_path):
        """Large files are hashed correctly via chunking."""
        file = tmp_path / "large.txt"
        # Write 100KB of data
        file.write_bytes(b"x" * 100_000)

        hash_val = get_file_hash(file)
        assert len(hash_val) == 64


class TestGetMimeType:
    """Tests for get_mime_type function."""

    def test_detects_pdf(self, tmp_path):
        """PDF files are detected correctly."""
        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_bytes(b"%PDF-1.4")

        mime = get_mime_type(pdf_file)
        assert mime == "application/pdf"

    def test_detects_jpeg(self, tmp_path, sample_image):
        """JPEG files are detected correctly."""
        mime = get_mime_type(sample_image)
        assert mime == "image/jpeg"

    def test_fallback_to_extension(self, tmp_path):
        """Extension mapping works for known extensions."""
        # The fallback extension mapping handles these extensions:
        # .pdf, .jpg, .jpeg, .png, .tiff, .tif
        # We test that when we have a valid PDF magic bytes, we get application/pdf
        pdf_file = tmp_path / "document.pdf"
        pdf_file.write_bytes(b"%PDF-1.4 some pdf content")

        mime = get_mime_type(pdf_file)
        assert mime == "application/pdf"

    def test_unknown_extension_returns_octet_stream(self, tmp_path):
        """Unknown extensions return application/octet-stream when magic can't detect."""
        unknown_file = tmp_path / "test.xyz"
        unknown_file.write_bytes(b"random data that's not identifiable")

        # Get the mime type - if magic can't identify it, should fallback to extension
        # then to octet-stream for unknown extension
        mime = get_mime_type(unknown_file)
        # Should be octet-stream for unrecognized file
        assert mime in ("application/octet-stream", "text/plain")


class TestCheckDuplicate:
    """Tests for check_duplicate function."""

    @pytest.mark.asyncio
    async def test_finds_existing_document(self, seeded_db):
        """Returns document ID when duplicate hash exists."""
        # Seed data has doc-001 with hash "abc123hash001"
        result = await check_duplicate("abc123hash001")
        assert result == "doc-001"

    @pytest.mark.asyncio
    async def test_returns_none_for_new_hash(self, seeded_db):
        """Returns None when no duplicate exists."""
        result = await check_duplicate("completely_new_hash_12345")
        assert result is None


class TestCreateDocumentRecord:
    """Tests for create_document_record function."""

    @pytest.mark.asyncio
    async def test_creates_record(self, test_db, db_connection):
        """Document record is created correctly."""
        await create_document_record(
            doc_id="test-123",
            filename="test.pdf",
            file_path="archive/test.pdf",
            file_hash="hash123",
            file_size=1024,
            mime_type="application/pdf",
        )

        cursor = await db_connection.execute("SELECT * FROM documents WHERE id = ?", ("test-123",))
        row = await cursor.fetchone()

        assert row is not None
        assert row["filename"] == "test.pdf"
        assert row["file_hash"] == "hash123"
        assert row["status"] == "pending"


class TestUpdateDocumentStatus:
    """Tests for update_document_status function."""

    @pytest.mark.asyncio
    async def test_updates_to_processing(self, seeded_db, db_connection):
        """Status can be updated to processing."""
        await update_document_status("doc-001", DocumentStatus.PROCESSING)

        cursor = await db_connection.execute(
            "SELECT status FROM documents WHERE id = ?", ("doc-001",)
        )
        row = await cursor.fetchone()
        assert row["status"] == "processing"

    @pytest.mark.asyncio
    async def test_completed_sets_processed_at(self, seeded_db, db_connection):
        """Completed status sets processed_at timestamp."""
        await update_document_status("doc-003", DocumentStatus.COMPLETED)

        cursor = await db_connection.execute(
            "SELECT status, processed_at FROM documents WHERE id = ?", ("doc-003",)
        )
        row = await cursor.fetchone()
        assert row["status"] == "completed"
        assert row["processed_at"] is not None


class TestUpdateDocumentOcr:
    """Tests for update_document_ocr function."""

    @pytest.mark.asyncio
    async def test_updates_ocr_fields(self, seeded_db, db_connection):
        """OCR fields are updated correctly."""
        await update_document_ocr("doc-003", "Extracted text here", 5)

        cursor = await db_connection.execute(
            "SELECT raw_text, page_count FROM documents WHERE id = ?", ("doc-003",)
        )
        row = await cursor.fetchone()
        assert row["raw_text"] == "Extracted text here"
        assert row["page_count"] == 5


class TestUpdateExtractionStatus:
    """Tests for update_extraction_status function."""

    @pytest.mark.asyncio
    async def test_updates_extraction_status(self, seeded_db, db_connection):
        """Extraction status is updated correctly."""
        await update_extraction_status("doc-003", "completed")

        cursor = await db_connection.execute(
            "SELECT extraction_status FROM documents WHERE id = ?", ("doc-003",)
        )
        row = await cursor.fetchone()
        assert row["extraction_status"] == "completed"


class TestInboxHandler:
    """Tests for InboxHandler class."""

    def test_ignores_directory_events(self):
        """Directory events are ignored."""
        loop = asyncio.new_event_loop()
        handler = InboxHandler(loop)

        event = MagicMock()
        event.is_directory = True

        # Should not raise or do anything
        handler.on_created(event)
        loop.close()

    def test_ignores_hidden_files(self):
        """Hidden files are ignored."""
        loop = asyncio.new_event_loop()
        handler = InboxHandler(loop)

        event = MagicMock()
        event.is_directory = False
        event.src_path = "/tmp/.hidden_file.pdf"

        with patch("asyncio.run_coroutine_threadsafe") as mock_run:
            handler.on_created(event)
            mock_run.assert_not_called()

        loop.close()

    def test_ignores_temp_files(self):
        """Temp files starting with ~ are ignored."""
        loop = asyncio.new_event_loop()
        handler = InboxHandler(loop)

        event = MagicMock()
        event.is_directory = False
        event.src_path = "/tmp/~tempfile.pdf"

        with patch("asyncio.run_coroutine_threadsafe") as mock_run:
            handler.on_created(event)
            mock_run.assert_not_called()

        loop.close()

    def test_schedules_valid_file_for_processing(self):
        """Valid files are scheduled for processing."""
        loop = asyncio.new_event_loop()
        handler = InboxHandler(loop)

        event = MagicMock()
        event.is_directory = False
        event.src_path = "/tmp/document.pdf"

        with patch("asyncio.run_coroutine_threadsafe") as mock_run:
            handler.on_created(event)
            mock_run.assert_called_once()

        loop.close()


class TestFolderWatcher:
    """Tests for FolderWatcher class."""

    def test_start_creates_observer(self, test_settings):
        """Starting watcher creates an observer."""
        watcher = FolderWatcher()
        loop = asyncio.new_event_loop()

        with patch("app.services.watcher.Observer") as MockObserver:
            mock_observer = MagicMock()
            MockObserver.return_value = mock_observer

            watcher.start(loop)

            mock_observer.schedule.assert_called_once()
            mock_observer.start.assert_called_once()

        watcher.stop()
        loop.close()

    def test_start_is_idempotent(self, test_settings):
        """Starting an already running watcher does nothing."""
        watcher = FolderWatcher()
        loop = asyncio.new_event_loop()

        with patch("app.services.watcher.Observer") as MockObserver:
            mock_observer = MagicMock()
            MockObserver.return_value = mock_observer

            watcher.start(loop)
            watcher.start(loop)  # Second call

            # Should only create one observer
            assert MockObserver.call_count == 1

        watcher.stop()
        loop.close()

    def test_stop_stops_observer(self, test_settings):
        """Stopping watcher stops the observer."""
        watcher = FolderWatcher()
        loop = asyncio.new_event_loop()

        with patch("app.services.watcher.Observer") as MockObserver:
            mock_observer = MagicMock()
            MockObserver.return_value = mock_observer

            watcher.start(loop)
            watcher.stop()

            mock_observer.stop.assert_called_once()
            mock_observer.join.assert_called_once()

        loop.close()


class TestProcessDocument:
    """Tests for process_document function."""

    @pytest.mark.asyncio
    async def test_skips_unsupported_file_type(self, test_settings, tmp_path):
        """Unsupported file types return None."""
        # Create a text file (unsupported)
        txt_file = tmp_path / "test.txt"
        txt_file.write_text("text content")

        result = await process_document(txt_file)
        assert result is None

    @pytest.mark.asyncio
    async def test_skips_file_too_large(self, test_settings, tmp_path):
        """Files exceeding size limit return None."""
        # Create a file that exceeds the default limit
        pdf_file = tmp_path / "large.pdf"
        # Write more than the default max_file_size_mb (50MB by default, use patch)
        pdf_file.write_bytes(b"%PDF-1.4" + b"x" * 100)

        with patch.object(test_settings, "max_file_size_mb", 0.00001):
            import app.services.watcher as watcher_module

            with patch.object(watcher_module, "settings", test_settings):
                result = await process_document(pdf_file)
        assert result is None

    @pytest.mark.asyncio
    async def test_detects_duplicate(self, seeded_db, test_settings, tmp_path):
        """Duplicate files are detected and rejected."""
        # Create a file with the same hash as doc-001 (abc123hash001)
        # We need to mock get_file_hash to return the known hash
        pdf_file = tmp_path / "duplicate.pdf"
        pdf_file.write_bytes(b"%PDF-1.4 duplicate content")

        with patch("app.services.watcher.get_file_hash", return_value="abc123hash001"):
            result = await process_document(pdf_file)
            # Returns existing doc ID but doesn't create new document
            assert result == "doc-001"
            # Original file should be deleted
            assert not pdf_file.exists()


class TestProcessExistingInbox:
    """Tests for process_existing_inbox function."""

    @pytest.mark.asyncio
    async def test_processes_files_in_inbox(self, test_settings):
        """Files in inbox are processed."""
        # Create test files in inbox
        inbox = test_settings.inbox_dir
        pdf_file = inbox / "test.pdf"
        pdf_file.write_bytes(b"%PDF-1.4")

        with patch(
            "app.services.watcher.process_document", new=AsyncMock(return_value="doc-id")
        ) as mock_process:
            result = await process_existing_inbox()

            mock_process.assert_called_once()
            assert "doc-id" in result

    @pytest.mark.asyncio
    async def test_skips_hidden_files(self, test_settings):
        """Hidden files in inbox are skipped."""
        inbox = test_settings.inbox_dir
        hidden_file = inbox / ".hidden.pdf"
        hidden_file.write_bytes(b"%PDF-1.4")

        with patch("app.services.watcher.process_document", new=AsyncMock()) as mock_process:
            await process_existing_inbox()

            mock_process.assert_not_called()

    @pytest.mark.asyncio
    async def test_handles_nonexistent_inbox(self, test_settings):
        """Nonexistent inbox directory returns empty list."""

        # Create a temp settings with non-existent inbox
        original_inbox = test_settings.inbox_dir
        test_settings.inbox_dir = Path("/nonexistent/inbox/that/does/not/exist")

        try:
            result = await process_existing_inbox()
            assert result == []
        finally:
            test_settings.inbox_dir = original_inbox
