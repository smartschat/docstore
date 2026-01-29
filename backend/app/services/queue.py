"""Background queue processor for pending extractions."""

import asyncio
from typing import Optional

import aiosqlite

from app.config import get_settings
from app.models import DocumentStatus
from app.services.extraction import check_ollama_available, process_document_extraction
from app.services.watcher import (
    update_document_extraction,
    update_document_status,
    update_extraction_status,
)

settings = get_settings()

# Module-level state for the queue processor
_queue_task: Optional[asyncio.Task] = None
_should_stop = False


async def get_pending_extractions(limit: int = 5) -> list[dict]:
    """Get documents with pending extraction status."""
    async with aiosqlite.connect(settings.database_path) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """
            SELECT id, raw_text, file_path FROM documents
            WHERE extraction_status = 'pending' AND raw_text IS NOT NULL
            ORDER BY created_at ASC
            LIMIT ?
            """,
            (limit,),
        )
        rows = await cursor.fetchall()
        return [
            {"id": row["id"], "raw_text": row["raw_text"], "file_path": row["file_path"]}
            for row in rows
        ]


async def get_queue_stats() -> dict:
    """Get queue statistics."""
    async with aiosqlite.connect(settings.database_path) as db:
        db.row_factory = aiosqlite.Row

        # Count pending
        cursor = await db.execute(
            "SELECT COUNT(*) as count FROM documents WHERE extraction_status = 'pending'"
        )
        pending = (await cursor.fetchone())["count"]

        # Count completed
        cursor = await db.execute(
            "SELECT COUNT(*) as count FROM documents WHERE extraction_status = 'completed'"
        )
        completed = (await cursor.fetchone())["count"]

        # Count documents with no extraction status (legacy or N/A)
        cursor = await db.execute(
            "SELECT COUNT(*) as count FROM documents WHERE extraction_status IS NULL"
        )
        no_status = (await cursor.fetchone())["count"]

    ollama_available = await check_ollama_available()

    return {
        "pending": pending,
        "completed": completed,
        "no_status": no_status,
        "ollama_available": ollama_available,
        "queue_running": _queue_task is not None and not _queue_task.done(),
    }


async def process_pending_extraction(doc: dict) -> bool:
    """Process a single pending extraction."""
    from app.services.entities import disambiguate_document

    doc_id = doc["id"]
    raw_text = doc["raw_text"]
    file_path = doc.get("file_path")

    # Resolve full path for vision model
    pdf_path = None
    if file_path:
        pdf_path = settings.data_dir / file_path
        if not pdf_path.exists():
            pdf_path = None

    try:
        print(f"Processing queued extraction for {doc_id}")
        extraction_result = await process_document_extraction(doc_id, raw_text, pdf_path=pdf_path)
        await update_document_extraction(doc_id, extraction_result)
        await update_extraction_status(doc_id, "completed")

        # Run entity disambiguation
        await disambiguate_document(doc_id)

        await update_document_status(doc_id, DocumentStatus.COMPLETED)
        print(f"Completed queued extraction for {doc_id}")
        return True
    except Exception as e:
        print(f"Error processing queued extraction for {doc_id}: {e}")
        return False


async def queue_processor_loop(interval: int = 60) -> None:
    """
    Background loop that checks for pending extractions when Ollama is available.

    Args:
        interval: Seconds between queue checks
    """
    global _should_stop

    print(f"Queue processor started (checking every {interval}s)")

    while not _should_stop:
        try:
            if await check_ollama_available():
                pending = await get_pending_extractions(limit=settings.queue_batch_size)

                if pending:
                    print(f"Found {len(pending)} pending extractions, processing...")

                    for doc in pending:
                        if _should_stop:
                            break
                        await process_pending_extraction(doc)
                        # Small delay between documents to avoid overwhelming Ollama
                        await asyncio.sleep(1)

        except Exception as e:
            print(f"Queue processor error: {e}")

        # Wait for next check interval (with early exit support)
        for _ in range(interval):
            if _should_stop:
                break
            await asyncio.sleep(1)

    print("Queue processor stopped")


def start_queue_processor(check_interval: Optional[int] = None) -> None:
    """Start the background queue processor."""
    global _queue_task, _should_stop

    if _queue_task is not None and not _queue_task.done():
        print("Queue processor already running")
        return

    _should_stop = False
    interval = check_interval or settings.queue_check_interval
    _queue_task = asyncio.create_task(queue_processor_loop(interval))


def stop_queue_processor() -> None:
    """Stop the background queue processor."""
    global _should_stop, _queue_task

    _should_stop = True

    if _queue_task is not None:
        # Task will stop on next iteration
        print("Stopping queue processor...")
