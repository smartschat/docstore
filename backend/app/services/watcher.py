"""Folder watcher for automatic document ingestion."""

import asyncio
import hashlib
import shutil
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

import aiosqlite
from watchdog.events import FileCreatedEvent, FileSystemEventHandler
from watchdog.observers import Observer

from app.config import get_settings
from app.models import DocumentStatus
from app.services.embeddings import embed_document
from app.services.extraction import process_document_extraction
from app.services.ocr import extract_text_from_file

settings = get_settings()


def get_file_hash(file_path: Path) -> str:
    """Calculate SHA256 hash of a file."""
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256_hash.update(chunk)
    return sha256_hash.hexdigest()


def get_mime_type(file_path: Path) -> str:
    """Detect MIME type of a file."""
    try:
        import magic

        return magic.from_file(str(file_path), mime=True)
    except Exception:
        # Fallback based on extension
        ext = file_path.suffix.lower()
        mime_map = {
            ".pdf": "application/pdf",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".tiff": "image/tiff",
            ".tif": "image/tiff",
        }
        return mime_map.get(ext, "application/octet-stream")


async def check_duplicate(file_hash: str) -> Optional[str]:
    """Check if a document with the same hash already exists."""
    async with aiosqlite.connect(settings.database_path) as db:
        cursor = await db.execute("SELECT id FROM documents WHERE file_hash = ?", (file_hash,))
        row = await cursor.fetchone()
        return row[0] if row else None


async def create_document_record(
    doc_id: str,
    filename: str,
    file_path: str,
    file_hash: str,
    file_size: int,
    mime_type: str,
) -> None:
    """Create initial document record in database."""
    async with aiosqlite.connect(settings.database_path) as db:
        await db.execute(
            """
            INSERT INTO documents (id, filename, file_path, file_hash, file_size, mime_type, status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                doc_id,
                filename,
                file_path,
                file_hash,
                file_size,
                mime_type,
                DocumentStatus.PENDING.value,
            ),
        )
        await db.commit()


async def update_document_status(
    doc_id: str, status: DocumentStatus, error: Optional[str] = None
) -> None:
    """Update document processing status."""
    async with aiosqlite.connect(settings.database_path) as db:
        if status == DocumentStatus.COMPLETED:
            await db.execute(
                "UPDATE documents SET status = ?, processed_at = ? WHERE id = ?",
                (status.value, datetime.utcnow().isoformat(), doc_id),
            )
        else:
            await db.execute("UPDATE documents SET status = ? WHERE id = ?", (status.value, doc_id))
        await db.commit()


async def update_document_ocr(
    doc_id: str,
    raw_text: str,
    page_count: int,
) -> None:
    """Update document with OCR results."""
    async with aiosqlite.connect(settings.database_path) as db:
        await db.execute(
            "UPDATE documents SET raw_text = ?, page_count = ? WHERE id = ?",
            (raw_text, page_count, doc_id),
        )
        await db.commit()


async def update_document_extraction(doc_id: str, data: dict) -> None:
    """Update document with extraction results."""
    async with aiosqlite.connect(settings.database_path) as db:
        await db.execute(
            """
            UPDATE documents SET
                title = ?,
                counterparty = ?,
                affected_person = ?,
                category = ?,
                reference = ?,
                document_date = ?,
                summary = ?
            WHERE id = ?
            """,
            (
                data.get("title"),
                data.get("counterparty"),
                data.get("affected_person"),
                data.get("category"),
                data.get("reference"),
                data.get("document_date"),
                data.get("summary"),
                doc_id,
            ),
        )
        await db.commit()


async def update_extraction_status(doc_id: str, status: str) -> None:
    """Update document extraction status (pending, completed, or None)."""
    async with aiosqlite.connect(settings.database_path) as db:
        await db.execute(
            "UPDATE documents SET extraction_status = ? WHERE id = ?", (status, doc_id)
        )
        await db.commit()


async def process_document(file_path: Path) -> Optional[str]:
    """
    Process a single document through the full pipeline.

    Args:
        file_path: Path to the document file

    Returns:
        Document ID if successful, None otherwise
    """
    # Check if file is supported
    mime_type = get_mime_type(file_path)
    if mime_type not in settings.supported_mime_types:
        print(f"Skipping unsupported file type: {mime_type}")
        return None

    # Check file size
    file_size = file_path.stat().st_size
    if file_size > settings.max_file_size_mb * 1024 * 1024:
        print(f"Skipping file too large: {file_size} bytes")
        return None

    # Calculate hash for deduplication
    file_hash = get_file_hash(file_path)

    # Check for duplicates
    existing_id = await check_duplicate(file_hash)
    if existing_id:
        print(f"Duplicate detected, existing document: {existing_id}")
        # Move to archive anyway (or delete)
        file_path.unlink()
        return existing_id

    # Generate document ID
    doc_id = str(uuid.uuid4())

    # Move file to archive
    archive_filename = f"{doc_id}_{file_path.name}"
    archive_path = settings.archive_dir / archive_filename
    shutil.move(str(file_path), str(archive_path))

    # Create database record
    await create_document_record(
        doc_id=doc_id,
        filename=file_path.name,
        file_path=str(archive_path.relative_to(settings.data_dir)),
        file_hash=file_hash,
        file_size=file_size,
        mime_type=mime_type,
    )

    # Update status to processing
    await update_document_status(doc_id, DocumentStatus.PROCESSING)

    try:
        # Run OCR
        ocr_result = await extract_text_from_file(archive_path, mime_type)

        if not ocr_result.success:
            print(f"OCR failed: {ocr_result.error}")
            await update_document_status(doc_id, DocumentStatus.FAILED)
            return doc_id

        await update_document_ocr(doc_id, ocr_result.text, ocr_result.page_count)

        # Run extraction if we have text
        if ocr_result.text:
            from app.services.extraction import check_ollama_available

            if await check_ollama_available():
                extraction_result = await process_document_extraction(
                    doc_id, ocr_result.text, pdf_path=archive_path
                )
                await update_document_extraction(doc_id, extraction_result)
                await update_extraction_status(doc_id, "completed")

                # Run entity disambiguation
                from app.services.entities import disambiguate_document

                await disambiguate_document(doc_id)

                # Fully processed
                await update_document_status(doc_id, DocumentStatus.COMPLETED)
                print(f"Successfully processed document: {doc_id}")
            else:
                print(f"Ollama unavailable - queueing extraction for {doc_id}")
                await update_extraction_status(doc_id, "pending")
                # Stay in processing until extraction completes
                print(f"Document {doc_id} waiting for extraction")

            # Embeddings use local model, always run
            await embed_document(doc_id, ocr_result.text)
        else:
            # No text, nothing to extract - mark as completed
            await update_document_status(doc_id, DocumentStatus.COMPLETED)
            print(f"Successfully processed document (no text): {doc_id}")

        return doc_id

    except Exception as e:
        print(f"Error processing document: {e}")
        await update_document_status(doc_id, DocumentStatus.FAILED)
        return doc_id


class InboxHandler(FileSystemEventHandler):
    """Handle file system events in the inbox folder."""

    def __init__(self, loop: asyncio.AbstractEventLoop):
        self.loop = loop

    def on_created(self, event: FileCreatedEvent) -> None:
        if event.is_directory:
            return

        file_path = Path(event.src_path)

        # Skip hidden files and temp files
        if file_path.name.startswith(".") or file_path.name.startswith("~"):
            return

        # Wait a bit for file to be fully written
        asyncio.run_coroutine_threadsafe(
            self._process_with_delay(file_path),
            self.loop,
        )

    async def _process_with_delay(self, file_path: Path) -> None:
        """Process file after a short delay to ensure it's fully written."""
        await asyncio.sleep(2)

        if file_path.exists():
            await process_document(file_path)


class FolderWatcher:
    """Watch inbox folder for new documents."""

    def __init__(self):
        self.observer: Optional[Observer] = None
        self._running = False

    def start(self, loop: asyncio.AbstractEventLoop) -> None:
        """Start watching the inbox folder."""
        if self._running:
            return

        settings.ensure_directories()

        handler = InboxHandler(loop)
        self.observer = Observer()
        self.observer.schedule(handler, str(settings.inbox_dir), recursive=False)
        self.observer.start()
        self._running = True

        print(f"Watching inbox folder: {settings.inbox_dir}")

    def stop(self) -> None:
        """Stop watching."""
        if self.observer:
            self.observer.stop()
            self.observer.join()
            self._running = False


# Global watcher instance
folder_watcher = FolderWatcher()


async def process_existing_inbox() -> list[str]:
    """Process any files already in the inbox."""
    processed = []

    if not settings.inbox_dir.exists():
        return processed

    for file_path in settings.inbox_dir.iterdir():
        if file_path.is_file() and not file_path.name.startswith("."):
            doc_id = await process_document(file_path)
            if doc_id:
                processed.append(doc_id)

    return processed
