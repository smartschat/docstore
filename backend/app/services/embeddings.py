"""Vector embeddings and semantic search using OpenAI."""

import json
from typing import Optional
import aiosqlite
from openai import AsyncOpenAI

from app.config import get_settings

settings = get_settings()


def get_openai_client() -> AsyncOpenAI:
    """Get OpenAI client instance."""
    return AsyncOpenAI(api_key=settings.openai_api_key)


async def generate_embedding(text: str) -> list[float]:
    """
    Generate an embedding vector for the given text.

    Args:
        text: Text to embed

    Returns:
        1536-dimensional embedding vector
    """
    if not settings.openai_api_key:
        raise ValueError("OpenAI API key not configured")

    client = get_openai_client()

    # Truncate text if too long (ada-002 has 8191 token limit)
    # Rough estimate: 4 chars per token
    max_chars = 8000 * 4
    if len(text) > max_chars:
        text = text[:max_chars]

    response = await client.embeddings.create(
        model=settings.openai_embedding_model,
        input=text,
    )

    return response.data[0].embedding


def _get_vec_connection():
    """Get a sync connection with sqlite-vec loaded."""
    import sqlite3
    try:
        import sqlite_vec
        conn = sqlite3.connect(str(settings.database_path))
        conn.enable_load_extension(True)
        sqlite_vec.load(conn)
        conn.enable_load_extension(False)
        return conn
    except Exception:
        return None


async def store_embedding(doc_id: str, embedding: list[float]) -> None:
    """
    Store an embedding in the vector database.

    Args:
        doc_id: Document ID
        embedding: Embedding vector
    """
    import asyncio

    def _store():
        conn = _get_vec_connection()
        if not conn:
            return

        try:
            embedding_json = json.dumps(embedding)
            conn.execute("DELETE FROM document_embeddings WHERE doc_id = ?", (doc_id,))
            conn.execute(
                "INSERT INTO document_embeddings (doc_id, embedding) VALUES (?, ?)",
                (doc_id, embedding_json)
            )
            conn.commit()
        finally:
            conn.close()

    await asyncio.get_event_loop().run_in_executor(None, _store)


async def search_similar(
    query_embedding: list[float],
    limit: int = 10,
    category: Optional[str] = None,
) -> list[tuple[str, float]]:
    """
    Search for documents similar to the query embedding.

    Args:
        query_embedding: Query embedding vector
        limit: Maximum number of results
        category: Optional category filter

    Returns:
        List of (doc_id, similarity_score) tuples
    """
    import asyncio

    def _search():
        conn = _get_vec_connection()
        if not conn:
            return None

        try:
            query_json = json.dumps(query_embedding)

            if category:
                cursor = conn.execute(
                    """
                    SELECT e.doc_id, vec_distance_cosine(e.embedding, ?) as distance
                    FROM document_embeddings e
                    JOIN documents d ON d.id = e.doc_id
                    WHERE d.category = ?
                    ORDER BY distance ASC
                    LIMIT ?
                    """,
                    (query_json, category, limit)
                )
            else:
                cursor = conn.execute(
                    """
                    SELECT doc_id, vec_distance_cosine(embedding, ?) as distance
                    FROM document_embeddings
                    ORDER BY distance ASC
                    LIMIT ?
                    """,
                    (query_json, limit)
                )

            rows = cursor.fetchall()
            # Convert distance to similarity (1 - distance for cosine)
            return [(row[0], 1 - row[1]) for row in rows]
        except Exception:
            return None
        finally:
            conn.close()

    result = await asyncio.get_event_loop().run_in_executor(None, _search)
    if result is not None:
        return result

    # Fallback: compute cosine similarity in Python
    return await _search_similar_fallback(query_embedding, limit, category)


async def _search_similar_fallback(
    query_embedding: list[float],
    limit: int,
    category: Optional[str],
) -> list[tuple[str, float]]:
    """
    Fallback vector search using Python (when sqlite-vec is not available).
    """
    import math

    def cosine_similarity(a: list[float], b: list[float]) -> float:
        dot_product = sum(x * y for x, y in zip(a, b))
        magnitude_a = math.sqrt(sum(x * x for x in a))
        magnitude_b = math.sqrt(sum(x * x for x in b))
        if magnitude_a == 0 or magnitude_b == 0:
            return 0
        return dot_product / (magnitude_a * magnitude_b)

    async with aiosqlite.connect(settings.database_path) as db:
        if category:
            cursor = await db.execute(
                """
                SELECT e.doc_id, e.embedding
                FROM document_embeddings e
                JOIN documents d ON d.id = e.doc_id
                WHERE d.category = ?
                """,
                (category,)
            )
        else:
            cursor = await db.execute(
                "SELECT doc_id, embedding FROM document_embeddings"
            )

        results = []
        async for row in cursor:
            doc_id = row[0]
            embedding = json.loads(row[1])
            similarity = cosine_similarity(query_embedding, embedding)
            results.append((doc_id, similarity))

        # Sort by similarity descending
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:limit]


async def embed_document(doc_id: str, text: str) -> None:
    """
    Generate and store an embedding for a document.

    Args:
        doc_id: Document ID
        text: Document text to embed
    """
    if not text or not text.strip():
        return

    try:
        embedding = await generate_embedding(text)
        await store_embedding(doc_id, embedding)
    except Exception as e:
        # Embedding is optional - log but don't fail the document processing
        print(f"Warning: Could not generate/store embedding for {doc_id}: {e}")


async def semantic_search(
    query: str,
    limit: int = 10,
    category: Optional[str] = None,
) -> list[tuple[str, float]]:
    """
    Perform semantic search for documents matching the query.

    Args:
        query: Search query
        limit: Maximum number of results
        category: Optional category filter

    Returns:
        List of (doc_id, similarity_score) tuples
    """
    query_embedding = await generate_embedding(query)
    return await search_similar(query_embedding, limit, category)
