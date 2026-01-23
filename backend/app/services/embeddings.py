"""Vector embeddings and semantic search using sentence-transformers (local)."""

import json
from typing import Optional
import aiosqlite
import asyncio

from app.config import get_settings

settings = get_settings()

# Global model instance (loaded once)
_model = None


def get_model():
    """Get or load the sentence-transformers model with ONNX backend for ARM compatibility."""
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        # Use ONNX backend for ARM/cross-platform compatibility
        _model = SentenceTransformer('all-MiniLM-L6-v2', backend='onnx')
    return _model


async def generate_embedding(text: str) -> list[float]:
    """
    Generate an embedding vector for the given text.

    Args:
        text: Text to embed

    Returns:
        384-dimensional embedding vector (MiniLM)
    """
    # Truncate text if too long (MiniLM has 256 token limit, ~1000 chars safe)
    max_chars = 8000
    if len(text) > max_chars:
        text = text[:max_chars]

    def _encode():
        model = get_model()
        embedding = model.encode(text, convert_to_numpy=True)
        return embedding.tolist()

    return await asyncio.get_event_loop().run_in_executor(None, _encode)


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
    def _store():
        conn = _get_vec_connection()
        if not conn:
            # Fallback: store in regular table as JSON
            import sqlite3
            conn = sqlite3.connect(str(settings.database_path))

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
            # Skip if dimensions don't match (old OpenAI embeddings)
            if len(embedding) != len(query_embedding):
                continue
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
    try:
        query_embedding = await generate_embedding(query)
        return await search_similar(query_embedding, limit, category)
    except Exception as e:
        print(f"Semantic search error: {e}")
        return []
