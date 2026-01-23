"""Search endpoints."""

from typing import Optional
from datetime import datetime

import aiosqlite
from fastapi import APIRouter, Depends, Query

from app.auth import get_current_session
from app.config import get_settings
from app.models import (
    SearchQuery,
    SearchResult,
    SearchResponse,
    Document,
    DocumentStatus,
    Tag,
)
from app.services.embeddings import semantic_search

settings = get_settings()
router = APIRouter(prefix="/api/search", tags=["search"])


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
        title=row.get("title"),
        counterparty=row.get("counterparty"),
        affected_person=row.get("affected_person"),
        category=row.get("category"),
        reference=row.get("reference"),
        tags=tags or [],
    )


async def keyword_search(
    query: str,
    category: Optional[str] = None,
    tags: Optional[list[str]] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    limit: int = 20,
) -> list[tuple[str, float, str]]:
    """
    Perform keyword search using FTS5.

    Returns:
        List of (doc_id, score, snippet) tuples
    """
    async with aiosqlite.connect(settings.database_path) as db:
        # Build base FTS query
        fts_query = f'"{query}"'

        # Build filter conditions
        where_clauses = []
        params = [fts_query]

        if category:
            where_clauses.append("d.category = ?")
            params.append(category)

        if tags:
            placeholders = ",".join("?" * len(tags))
            where_clauses.append(f"""
                d.id IN (
                    SELECT dt.doc_id FROM document_tags dt
                    JOIN tags t ON t.id = dt.tag_id
                    WHERE t.name IN ({placeholders})
                )
            """)
            params.extend(tags)

        if date_from:
            where_clauses.append("d.document_date >= ?")
            params.append(date_from)

        if date_to:
            where_clauses.append("d.document_date <= ?")
            params.append(date_to)

        where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

        params.append(limit)

        cursor = await db.execute(
            f"""
            SELECT
                d.id,
                bm25(documents_fts) as score,
                snippet(documents_fts, 2, '<mark>', '</mark>', '...', 32) as snippet
            FROM documents_fts fts
            JOIN documents d ON d.id = fts.id
            WHERE documents_fts MATCH ?
            AND {where_sql}
            ORDER BY score
            LIMIT ?
            """,
            params
        )

        rows = await cursor.fetchall()
        # BM25 returns negative scores (lower is better), convert to positive
        return [(row[0], -row[1], row[2]) for row in rows]


async def hybrid_search(
    query: str,
    category: Optional[str] = None,
    tags: Optional[list[str]] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    limit: int = 20,
    keyword_weight: float = 0.3,
    semantic_weight: float = 0.7,
) -> list[tuple[str, float, Optional[str]]]:
    """
    Perform hybrid search combining keyword and semantic search.

    Returns:
        List of (doc_id, combined_score, snippet) tuples
    """
    # Run both searches
    keyword_results = await keyword_search(
        query, category, tags, date_from, date_to, limit=limit * 2
    )
    semantic_results = await semantic_search(query, limit=limit * 2, category=category)

    # Create score maps
    keyword_scores = {doc_id: score for doc_id, score, _ in keyword_results}
    keyword_snippets = {doc_id: snippet for doc_id, _, snippet in keyword_results}
    semantic_scores = {doc_id: score for doc_id, score in semantic_results}

    # Normalize scores
    def normalize(scores: dict[str, float]) -> dict[str, float]:
        if not scores:
            return {}
        max_score = max(scores.values())
        min_score = min(scores.values())
        if max_score == min_score:
            return {k: 1.0 for k in scores}
        return {k: (v - min_score) / (max_score - min_score) for k, v in scores.items()}

    norm_keyword = normalize(keyword_scores)
    norm_semantic = normalize(semantic_scores)

    # Combine scores
    all_doc_ids = set(keyword_scores.keys()) | set(semantic_scores.keys())
    combined = []

    for doc_id in all_doc_ids:
        kw_score = norm_keyword.get(doc_id, 0)
        sem_score = norm_semantic.get(doc_id, 0)
        combined_score = keyword_weight * kw_score + semantic_weight * sem_score
        snippet = keyword_snippets.get(doc_id)
        combined.append((doc_id, combined_score, snippet))

    # Sort by combined score descending
    combined.sort(key=lambda x: x[1], reverse=True)

    # Apply filters for semantic-only results
    if tags or date_from or date_to:
        filtered = []
        async with aiosqlite.connect(settings.database_path) as db:
            for doc_id, score, snippet in combined:
                # Check if document passes filters
                where_clauses = ["id = ?"]
                params = [doc_id]

                if tags:
                    placeholders = ",".join("?" * len(tags))
                    where_clauses.append(f"""
                        id IN (
                            SELECT dt.doc_id FROM document_tags dt
                            JOIN tags t ON t.id = dt.tag_id
                            WHERE t.name IN ({placeholders})
                        )
                    """)
                    params.extend(tags)

                if date_from:
                    where_clauses.append("document_date >= ?")
                    params.append(date_from)

                if date_to:
                    where_clauses.append("document_date <= ?")
                    params.append(date_to)

                cursor = await db.execute(
                    f"SELECT 1 FROM documents WHERE {' AND '.join(where_clauses)}",
                    params
                )
                if await cursor.fetchone():
                    filtered.append((doc_id, score, snippet))

        combined = filtered

    return combined[:limit]


@router.post("", response_model=SearchResponse)
async def search_documents(
    search: SearchQuery,
    _: str = Depends(get_current_session),
):
    """
    Search documents using keyword, semantic, or hybrid search.
    """
    # Perform search based on type
    if search.search_type == "keyword":
        results = await keyword_search(
            search.query,
            search.category,
            search.tags,
            search.date_from.isoformat() if search.date_from else None,
            search.date_to.isoformat() if search.date_to else None,
            limit=search.page_size,
        )
    elif search.search_type == "semantic":
        semantic_results = await semantic_search(
            search.query,
            limit=search.page_size,
            category=search.category,
        )
        results = [(doc_id, score, None) for doc_id, score in semantic_results]
    else:  # hybrid
        results = await hybrid_search(
            search.query,
            search.category,
            search.tags,
            search.date_from.isoformat() if search.date_from else None,
            search.date_to.isoformat() if search.date_to else None,
            limit=search.page_size,
        )

    # Fetch full documents
    search_results = []
    async with aiosqlite.connect(settings.database_path) as db:
        db.row_factory = aiosqlite.Row
        for doc_id, score, snippet in results:
            cursor = await db.execute(
                "SELECT * FROM documents WHERE id = ?",
                (doc_id,)
            )
            row = await cursor.fetchone()
            if row:
                tags = await get_document_tags(doc_id)
                doc = row_to_document(dict(row), tags)
                search_results.append(SearchResult(
                    document=doc,
                    score=score,
                    snippet=snippet,
                ))

    return SearchResponse(
        results=search_results,
        total=len(search_results),
        query=search.query,
    )


@router.get("/suggest")
async def search_suggestions(
    q: str = Query(..., min_length=2),
    _: str = Depends(get_current_session),
):
    """Get autocomplete suggestions for search."""
    async with aiosqlite.connect(settings.database_path) as db:
        # Get matching filenames
        cursor = await db.execute(
            """
            SELECT DISTINCT filename FROM documents
            WHERE filename LIKE ?
            LIMIT 5
            """,
            (f"%{q}%",)
        )
        filenames = [row[0] for row in await cursor.fetchall()]

        # Get matching tags
        cursor = await db.execute(
            """
            SELECT name FROM tags
            WHERE name LIKE ?
            LIMIT 5
            """,
            (f"%{q}%",)
        )
        tags = [row[0] for row in await cursor.fetchall()]

        # Get matching counterparties
        cursor = await db.execute(
            """
            SELECT DISTINCT counterparty FROM documents
            WHERE counterparty LIKE ?
            LIMIT 5
            """,
            (f"%{q}%",)
        )
        counterparties = [row[0] for row in await cursor.fetchall() if row[0]]

    return {
        "filenames": filenames,
        "tags": tags,
        "counterparties": counterparties,
    }
