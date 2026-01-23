"""Question answering endpoints."""

from datetime import datetime

import aiosqlite
from fastapi import APIRouter, Depends

from app.auth import get_current_session
from app.config import get_settings
from app.models import (
    QuestionRequest,
    QuestionResponse,
    Document,
    DocumentStatus,
    Tag,
)
from app.services.qa import answer_question

settings = get_settings()
router = APIRouter(prefix="/api", tags=["qa"])


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
            (doc_id,)
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
        created_at=datetime.fromisoformat(row["created_at"]) if row["created_at"] else datetime.utcnow(),
        processed_at=datetime.fromisoformat(row["processed_at"]) if row["processed_at"] else None,
        status=DocumentStatus(row["status"]) if row["status"] else DocumentStatus.PENDING,
        title=row["title"],
        counterparty=row["counterparty"],
        affected_person=row["affected_person"],
        category=row["category"],
        reference=row["reference"],
        tags=tags or [],
    )


@router.post("/ask", response_model=QuestionResponse)
async def ask_question(
    request: QuestionRequest,
    _: str = Depends(get_current_session),
):
    """
    Ask a question about your documents.

    Uses RAG (Retrieval-Augmented Generation) to find relevant documents
    and generate an answer.
    """
    result = await answer_question(
        question=request.question,
        doc_ids=request.doc_ids,
    )

    # Fetch source documents
    sources = []
    async with aiosqlite.connect(settings.database_path) as db:
        db.row_factory = aiosqlite.Row
        for doc_id in result["sources"]:
            cursor = await db.execute(
                "SELECT * FROM documents WHERE id = ?",
                (doc_id,)
            )
            row = await cursor.fetchone()
            if row:
                tags = await get_document_tags(doc_id)
                sources.append(row_to_document(dict(row), tags))

    return QuestionResponse(
        answer=result["answer"],
        sources=sources,
    )
