"""Document CRUD endpoints."""

import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

import aiosqlite
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse

from app.auth import get_current_session
from app.config import get_settings
from app.models import (
    Document,
    DocumentList,
    DocumentStatus,
    DocumentUpdate,
    Tag,
)
from app.services.watcher import get_mime_type, process_document

settings = get_settings()
router = APIRouter(prefix="/api/documents", tags=["documents"])


async def get_document_by_id(doc_id: str) -> Optional[dict]:
    """Fetch a document from the database."""
    async with aiosqlite.connect(settings.database_path) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM documents WHERE id = ?", (doc_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None


async def get_document_tags(doc_id: str) -> list[Tag]:
    """Get tags for a document."""
    async with aiosqlite.connect(settings.database_path) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """
            SELECT t.id, t.name
            FROM tags t
            JOIN document_tags dt ON dt.tag_id = t.id
            WHERE dt.doc_id = ?
            """,
            (doc_id,),
        )
        rows = await cursor.fetchall()
        return [Tag(id=row["id"], name=row["name"]) for row in rows]


def row_to_document(row: dict, tags: list[Tag] = None) -> Document:
    """Convert database row to Document model."""
    return Document(
        id=row["id"],
        filename=row["filename"],
        file_path=row["file_path"],
        file_hash=row["file_hash"],
        file_size=row["file_size"],
        mime_type=row["mime_type"],
        raw_text=row["raw_text"],
        page_count=row["page_count"],
        summary=row["summary"],
        document_date=row["document_date"],
        created_at=datetime.fromisoformat(row["created_at"])
        if row["created_at"]
        else datetime.utcnow(),
        processed_at=datetime.fromisoformat(row["processed_at"]) if row["processed_at"] else None,
        status=DocumentStatus(row["status"]) if row["status"] else DocumentStatus.PENDING,
        extraction_status=row.get("extraction_status"),
        title=row.get("title"),
        counterparty=row.get("counterparty"),
        affected_person=row.get("affected_person"),
        category=row.get("category"),
        reference=row.get("reference"),
        tags=tags or [],
    )


@router.get("", response_model=DocumentList)
async def list_documents(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    category: Optional[str] = None,
    affected_person: Optional[str] = None,
    status: Optional[str] = None,
    tag: Optional[str] = None,
    _: str = Depends(get_current_session),
):
    """List documents with optional filtering and pagination."""
    offset = (page - 1) * page_size

    async with aiosqlite.connect(settings.database_path) as db:
        db.row_factory = aiosqlite.Row

        # Build query
        where_clauses = []
        params = []

        if category:
            where_clauses.append("category = ?")
            params.append(category)

        if affected_person:
            where_clauses.append("affected_person = ?")
            params.append(affected_person)

        if status:
            where_clauses.append("status = ?")
            params.append(status)

        if tag:
            where_clauses.append("""
                id IN (
                    SELECT dt.doc_id FROM document_tags dt
                    JOIN tags t ON t.id = dt.tag_id
                    WHERE t.name = ?
                )
            """)
            params.append(tag)

        where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

        # Get total count
        cursor = await db.execute(f"SELECT COUNT(*) FROM documents WHERE {where_sql}", params)
        total = (await cursor.fetchone())[0]

        # Get documents
        cursor = await db.execute(
            f"""
            SELECT * FROM documents
            WHERE {where_sql}
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
            """,
            params + [page_size, offset],
        )
        rows = await cursor.fetchall()

        documents = []
        for row in rows:
            tags = await get_document_tags(row["id"])
            documents.append(row_to_document(dict(row), tags))

        return DocumentList(
            items=documents,
            total=total,
            page=page,
            page_size=page_size,
        )


@router.get("/{doc_id}", response_model=Document)
async def get_document(
    doc_id: str,
    _: str = Depends(get_current_session),
):
    """Get a single document by ID."""
    row = await get_document_by_id(doc_id)
    if not row:
        raise HTTPException(status_code=404, detail="Document not found")

    tags = await get_document_tags(doc_id)
    return row_to_document(row, tags)


@router.post("/upload", response_model=Document)
async def upload_document(
    file: UploadFile = File(...),
    _: str = Depends(get_current_session),
):
    """Upload a new document."""
    # Validate file type
    mime_type = file.content_type or "application/octet-stream"
    if mime_type not in settings.supported_mime_types:
        # Try to detect from filename
        if file.filename:
            temp_path = Path(file.filename)
            ext_mime = get_mime_type(temp_path)
            if ext_mime in settings.supported_mime_types:
                mime_type = ext_mime
            else:
                raise HTTPException(status_code=400, detail=f"Unsupported file type: {mime_type}")

    # Save to inbox for processing
    settings.ensure_directories()

    filename = file.filename or f"upload_{uuid.uuid4()}"
    inbox_path = settings.inbox_dir / filename

    # Handle duplicate filenames
    counter = 1
    while inbox_path.exists():
        stem = Path(filename).stem
        suffix = Path(filename).suffix
        inbox_path = settings.inbox_dir / f"{stem}_{counter}{suffix}"
        counter += 1

    # Save file
    with open(inbox_path, "wb") as f:
        content = await file.read()
        f.write(content)

    # Process document
    doc_id = await process_document(inbox_path)

    if not doc_id:
        raise HTTPException(status_code=500, detail="Failed to process document")

    row = await get_document_by_id(doc_id)
    tags = await get_document_tags(doc_id)
    return row_to_document(row, tags)


@router.patch("/{doc_id}", response_model=Document)
async def update_document(
    doc_id: str,
    update: DocumentUpdate,
    _: str = Depends(get_current_session),
):
    """Update document metadata."""
    row = await get_document_by_id(doc_id)
    if not row:
        raise HTTPException(status_code=404, detail="Document not found")

    # Build update query dynamically based on provided fields
    update_data = update.model_dump(exclude_unset=True)

    if update_data:
        async with aiosqlite.connect(settings.database_path) as db:
            updates = []
            params = []

            for field, value in update_data.items():
                updates.append(f"{field} = ?")
                if hasattr(value, "isoformat"):
                    params.append(value.isoformat())
                else:
                    params.append(value)

            params.append(doc_id)
            await db.execute(f"UPDATE documents SET {', '.join(updates)} WHERE id = ?", params)
            await db.commit()

    row = await get_document_by_id(doc_id)
    tags = await get_document_tags(doc_id)
    return row_to_document(row, tags)


@router.delete("/{doc_id}")
async def delete_document(
    doc_id: str,
    _: str = Depends(get_current_session),
):
    """Delete a document."""
    row = await get_document_by_id(doc_id)
    if not row:
        raise HTTPException(status_code=404, detail="Document not found")

    # Delete file
    file_path = settings.data_dir / row["file_path"]
    if file_path.exists():
        file_path.unlink()

    # Delete from database (cascades to related tables)
    async with aiosqlite.connect(settings.database_path) as db:
        await db.execute("DELETE FROM documents WHERE id = ?", (doc_id,))
        await db.commit()

    return {"message": "Document deleted"}


@router.get("/{doc_id}/file")
async def download_file(
    doc_id: str,
    download: bool = False,
    _: str = Depends(get_current_session),
):
    """Download or view the original document file."""
    row = await get_document_by_id(doc_id)
    if not row:
        raise HTTPException(status_code=404, detail="Document not found")

    file_path = settings.data_dir / row["file_path"]
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    headers = {}
    if download:
        headers["Content-Disposition"] = f'attachment; filename="{row["filename"]}"'
    else:
        headers["Content-Disposition"] = "inline"

    return FileResponse(
        path=file_path,
        media_type=row["mime_type"],
        headers=headers,
    )


@router.get("/{doc_id}/thumbnail")
async def get_thumbnail(
    doc_id: str,
    _: str = Depends(get_current_session),
):
    """Get document thumbnail."""
    row = await get_document_by_id(doc_id)
    if not row:
        raise HTTPException(status_code=404, detail="Document not found")

    # Check for cached thumbnail
    thumb_path = settings.data_dir / "thumbnails" / f"{doc_id}.png"

    if not thumb_path.exists():
        # Generate thumbnail
        file_path = settings.data_dir / row["file_path"]
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="File not found")

        # Create thumbnails directory
        thumb_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            import subprocess

            from PIL import Image

            if row["mime_type"] == "application/pdf":
                # Use pdftoppm to convert first page
                # -singlefile outputs without page number suffix
                # Output path without .png since pdftoppm adds it
                output_base = str(thumb_path).removesuffix(".png")
                subprocess.run(
                    [
                        "pdftoppm",
                        "-png",
                        "-f",
                        "1",
                        "-singlefile",
                        "-scale-to",
                        "300",
                        str(file_path),
                        output_base,
                    ],
                    capture_output=True,
                )
            else:
                # Image file - resize
                img = Image.open(file_path)
                img.thumbnail((300, 400))
                img.save(thumb_path, "PNG")

        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to generate thumbnail: {e}")

    if not thumb_path.exists():
        raise HTTPException(status_code=404, detail="Thumbnail not available")

    return FileResponse(path=thumb_path, media_type="image/png")


@router.post("/{doc_id}/tags")
async def add_tags(
    doc_id: str,
    tags: list[str],
    _: str = Depends(get_current_session),
):
    """Add tags to a document."""
    row = await get_document_by_id(doc_id)
    if not row:
        raise HTTPException(status_code=404, detail="Document not found")

    async with aiosqlite.connect(settings.database_path) as db:
        for tag_name in tags:
            # Create tag if it doesn't exist
            await db.execute("INSERT OR IGNORE INTO tags (name) VALUES (?)", (tag_name,))

            # Get tag ID
            cursor = await db.execute("SELECT id FROM tags WHERE name = ?", (tag_name,))
            tag_row = await cursor.fetchone()
            tag_id = tag_row[0]

            # Link tag to document
            await db.execute(
                "INSERT OR IGNORE INTO document_tags (doc_id, tag_id) VALUES (?, ?)",
                (doc_id, tag_id),
            )

        await db.commit()

    return {"message": "Tags added"}


@router.delete("/{doc_id}/tags/{tag_name}")
async def remove_tag(
    doc_id: str,
    tag_name: str,
    _: str = Depends(get_current_session),
):
    """Remove a tag from a document."""
    async with aiosqlite.connect(settings.database_path) as db:
        cursor = await db.execute("SELECT id FROM tags WHERE name = ?", (tag_name,))
        tag_row = await cursor.fetchone()

        if tag_row:
            await db.execute(
                "DELETE FROM document_tags WHERE doc_id = ? AND tag_id = ?", (doc_id, tag_row[0])
            )
            await db.commit()

    return {"message": "Tag removed"}
