"""Unit tests for queue service."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.queue import (
    get_pending_extractions,
    get_queue_stats,
    process_pending_extraction,
    queue_processor_loop,
    start_queue_processor,
    stop_queue_processor,
)


class TestGetPendingExtractions:
    """Tests for get_pending_extractions function."""

    @pytest.mark.asyncio
    async def test_returns_pending_documents(self, seeded_db):
        """Returns documents with pending extraction status."""
        result = await get_pending_extractions(limit=10)

        # doc-003 has pending extraction status
        assert len(result) == 1
        assert result[0]["id"] == "doc-003"
        assert result[0]["raw_text"] == "Some document text"

    @pytest.mark.asyncio
    async def test_respects_limit(self, seeded_db, db_connection):
        """Respects the limit parameter."""
        # Add more pending documents with all required fields
        for i in range(5):
            await db_connection.execute("""
                INSERT INTO documents (id, filename, file_path, file_hash, file_size, mime_type,
                                      raw_text, status, extraction_status, created_at)
                VALUES (?, ?, ?, ?, 1024, 'application/pdf', ?, 'processing', 'pending', datetime('now', ? || ' seconds'))
            """, (f"pending-{i}", f"file{i}.pdf", f"archive/file{i}.pdf", f"hash{i}", f"text {i}", -i))
        await db_connection.commit()

        result = await get_pending_extractions(limit=3)
        assert len(result) == 3

    @pytest.mark.asyncio
    async def test_orders_by_created_at(self, seeded_db, db_connection):
        """Returns documents in order of creation (oldest first)."""
        from datetime import datetime, timedelta

        # Get the created_at from doc-003 and add time after it
        cursor = await db_connection.execute(
            "SELECT created_at FROM documents WHERE id = 'doc-003'"
        )
        row = await cursor.fetchone()
        older_time = row["created_at"]

        # Parse and add 1 hour
        older_dt = datetime.fromisoformat(older_time)
        newer_dt = older_dt + timedelta(hours=1)

        await db_connection.execute("""
            INSERT INTO documents (id, filename, file_path, file_hash, file_size, mime_type,
                                  raw_text, status, extraction_status, created_at)
            VALUES ('newer', 'newer.pdf', 'archive/newer.pdf', 'hashnewer', 1024, 'application/pdf',
                    'newer text', 'processing', 'pending', ?)
        """, (newer_dt.isoformat(),))
        await db_connection.commit()

        result = await get_pending_extractions(limit=10)

        # doc-003 was created first, should be first in list
        ids = [doc["id"] for doc in result]
        assert ids.index("doc-003") < ids.index("newer")

    @pytest.mark.asyncio
    async def test_excludes_documents_without_text(self, seeded_db, db_connection):
        """Excludes documents that have no raw_text."""
        # Add pending document without text
        await db_connection.execute("""
            INSERT INTO documents (id, filename, file_path, file_hash, file_size, mime_type,
                                  raw_text, status, extraction_status, created_at)
            VALUES ('no-text', 'notext.pdf', 'archive/notext.pdf', 'hashnotext', 1024, 'application/pdf',
                    NULL, 'processing', 'pending', datetime('now'))
        """)
        await db_connection.commit()

        result = await get_pending_extractions(limit=10)

        ids = [doc["id"] for doc in result]
        assert "no-text" not in ids


class TestGetQueueStats:
    """Tests for get_queue_stats function."""

    @pytest.mark.asyncio
    async def test_counts_by_status(self, seeded_db):
        """Returns correct counts by extraction status."""
        with patch("app.services.queue.check_ollama_available", new=AsyncMock(return_value=True)):
            stats = await get_queue_stats()

        assert stats["pending"] == 1  # doc-003
        assert stats["completed"] == 2  # doc-001, doc-002
        assert stats["no_status"] == 0
        assert stats["ollama_available"] is True

    @pytest.mark.asyncio
    async def test_reports_ollama_unavailable(self, seeded_db):
        """Reports when Ollama is unavailable."""
        with patch("app.services.queue.check_ollama_available", new=AsyncMock(return_value=False)):
            stats = await get_queue_stats()

        assert stats["ollama_available"] is False


class TestProcessPendingExtraction:
    """Tests for process_pending_extraction function."""

    @pytest.mark.asyncio
    async def test_successful_extraction(self, seeded_db):
        """Successfully processes extraction."""
        doc = {"id": "doc-003", "raw_text": "Some document text"}

        mock_result = {
            "title": "Test Title",
            "counterparty": "Test Company",
            "category": "invoice",
        }

        with patch("app.services.queue.process_document_extraction", new=AsyncMock(return_value=mock_result)):
            with patch("app.services.queue.update_document_extraction", new=AsyncMock()) as mock_update_ext:
                with patch("app.services.queue.update_extraction_status", new=AsyncMock()) as mock_update_status:
                    with patch("app.services.queue.update_document_status", new=AsyncMock()) as mock_update_doc:
                        result = await process_pending_extraction(doc)

        assert result is True
        mock_update_ext.assert_called_once_with("doc-003", mock_result)
        mock_update_status.assert_called_once_with("doc-003", "completed")

    @pytest.mark.asyncio
    async def test_handles_extraction_error(self, seeded_db):
        """Handles extraction errors gracefully."""
        doc = {"id": "doc-003", "raw_text": "Some document text"}

        with patch("app.services.queue.process_document_extraction", new=AsyncMock(side_effect=Exception("Error"))):
            result = await process_pending_extraction(doc)

        assert result is False


class TestQueueProcessorLoop:
    """Tests for queue_processor_loop function."""

    @pytest.mark.asyncio
    async def test_processes_pending_when_ollama_available(self, seeded_db):
        """Processes pending documents when Ollama is available."""
        import app.services.queue as queue_module

        # Set up stop signal after one iteration
        queue_module._should_stop = False

        async def set_stop_after_delay():
            await asyncio.sleep(0.1)
            queue_module._should_stop = True

        with patch("app.services.queue.check_ollama_available", new=AsyncMock(return_value=True)):
            with patch("app.services.queue.get_pending_extractions", new=AsyncMock(return_value=[])) as mock_get:
                # Run loop with very short interval
                task = asyncio.create_task(queue_processor_loop(interval=1))
                stop_task = asyncio.create_task(set_stop_after_delay())

                await asyncio.gather(task, stop_task, return_exceptions=True)

                mock_get.assert_called()

    @pytest.mark.asyncio
    async def test_skips_when_ollama_unavailable(self, seeded_db):
        """Skips processing when Ollama is unavailable."""
        import app.services.queue as queue_module

        queue_module._should_stop = False

        async def set_stop_after_delay():
            await asyncio.sleep(0.1)
            queue_module._should_stop = True

        with patch("app.services.queue.check_ollama_available", new=AsyncMock(return_value=False)):
            with patch("app.services.queue.get_pending_extractions", new=AsyncMock()) as mock_get:
                task = asyncio.create_task(queue_processor_loop(interval=1))
                stop_task = asyncio.create_task(set_stop_after_delay())

                await asyncio.gather(task, stop_task, return_exceptions=True)

                # Should not try to get pending extractions
                mock_get.assert_not_called()


class TestStartStopQueueProcessor:
    """Tests for start_queue_processor and stop_queue_processor functions."""

    def test_start_creates_task(self):
        """Starting processor creates a task."""
        import app.services.queue as queue_module

        # Reset state
        queue_module._queue_task = None
        queue_module._should_stop = False

        with patch("app.services.queue.asyncio.create_task") as mock_create:
            mock_task = MagicMock()
            mock_task.done.return_value = False
            mock_create.return_value = mock_task

            start_queue_processor(check_interval=60)

            mock_create.assert_called_once()

        # Cleanup
        queue_module._should_stop = True
        queue_module._queue_task = None

    def test_start_is_idempotent(self):
        """Starting already running processor does nothing."""
        import app.services.queue as queue_module

        mock_task = MagicMock()
        mock_task.done.return_value = False
        queue_module._queue_task = mock_task
        queue_module._should_stop = False

        with patch("app.services.queue.asyncio.create_task") as mock_create:
            start_queue_processor()

            mock_create.assert_not_called()

        # Cleanup
        queue_module._queue_task = None

    def test_stop_sets_flag(self):
        """Stopping processor sets the stop flag."""
        import app.services.queue as queue_module

        queue_module._should_stop = False
        queue_module._queue_task = MagicMock()

        stop_queue_processor()

        assert queue_module._should_stop is True

        # Cleanup
        queue_module._queue_task = None
