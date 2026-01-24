"""Vector embeddings and semantic search using ONNX Runtime (ARM compatible)."""

import asyncio
import json
from pathlib import Path
from typing import Optional

import aiosqlite
import numpy as np

from app.config import get_settings

settings = get_settings()

# Global model components (loaded once)
_tokenizer = None
_session = None
_model_loaded = False

# Model configuration
MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
MODEL_DIR = Path.home() / ".cache" / "docstore" / "models" / "all-MiniLM-L6-v2"


def _download_onnx_model():
    """Download the ONNX model from Hugging Face if not cached."""
    MODEL_DIR.mkdir(parents=True, exist_ok=True)

    model_path = MODEL_DIR / "model.onnx"
    tokenizer_path = MODEL_DIR / "tokenizer.json"

    if model_path.exists() and tokenizer_path.exists():
        return model_path, tokenizer_path

    print(f"Downloading ONNX model to {MODEL_DIR}...")
    from huggingface_hub import hf_hub_download

    # Download ONNX model
    hf_hub_download(
        repo_id=MODEL_NAME,
        filename="onnx/model.onnx",
        local_dir=MODEL_DIR,
        local_dir_use_symlinks=False,
    )
    # Move from onnx subfolder
    (MODEL_DIR / "onnx" / "model.onnx").rename(model_path)

    # Download tokenizer
    hf_hub_download(
        repo_id=MODEL_NAME,
        filename="tokenizer.json",
        local_dir=MODEL_DIR,
        local_dir_use_symlinks=False,
    )

    print("Model downloaded successfully")
    return model_path, tokenizer_path


def _load_model():
    """Load the ONNX model and tokenizer."""
    global _tokenizer, _session, _model_loaded

    if _model_loaded:
        return _session is not None

    try:
        model_path, tokenizer_path = _download_onnx_model()

        # Load tokenizer
        from tokenizers import Tokenizer

        _tokenizer = Tokenizer.from_file(str(tokenizer_path))

        # Load ONNX model
        import onnxruntime as ort

        _session = ort.InferenceSession(str(model_path), providers=["CPUExecutionProvider"])

        _model_loaded = True
        print("Embedding model loaded (ONNX)")
        return True
    except Exception as e:
        print(f"Failed to load embedding model: {e}")
        _model_loaded = True  # Don't retry
        return False


def _mean_pooling(model_output: np.ndarray, attention_mask: np.ndarray) -> np.ndarray:
    """Apply mean pooling to get sentence embeddings."""
    # model_output shape: (batch_size, sequence_length, hidden_size)
    # attention_mask shape: (batch_size, sequence_length)

    # Expand attention mask to match hidden size
    mask_expanded = np.expand_dims(attention_mask, -1)  # (batch, seq, 1)
    mask_expanded = np.broadcast_to(mask_expanded, model_output.shape)  # (batch, seq, hidden)

    # Sum embeddings weighted by attention mask
    sum_embeddings = np.sum(model_output * mask_expanded, axis=1)  # (batch, hidden)
    sum_mask = np.sum(mask_expanded, axis=1)  # (batch, hidden)
    sum_mask = np.clip(sum_mask, a_min=1e-9, a_max=None)  # Avoid division by zero

    return sum_embeddings / sum_mask


def _normalize(embeddings: np.ndarray) -> np.ndarray:
    """L2 normalize embeddings."""
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    norms = np.clip(norms, a_min=1e-9, a_max=None)
    return embeddings / norms


async def generate_embedding(text: str) -> list[float]:
    """
    Generate an embedding vector for the given text.

    Args:
        text: Text to embed

    Returns:
        384-dimensional embedding vector (MiniLM)
    """

    def _encode():
        if not _load_model():
            return None

        # Truncate text if too long
        max_chars = 8000
        if len(text) > max_chars:
            truncated = text[:max_chars]
        else:
            truncated = text

        # Tokenize
        encoded = _tokenizer.encode(truncated)
        input_ids = np.array([encoded.ids], dtype=np.int64)
        attention_mask = np.array([encoded.attention_mask], dtype=np.int64)
        token_type_ids = np.zeros_like(input_ids)

        # Run inference
        outputs = _session.run(
            None,
            {
                "input_ids": input_ids,
                "attention_mask": attention_mask,
                "token_type_ids": token_type_ids,
            },
        )

        # Get sentence embedding via mean pooling
        embeddings = _mean_pooling(outputs[0], attention_mask)
        embeddings = _normalize(embeddings)

        return embeddings[0].tolist()

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
                (doc_id, embedding_json),
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
                    (query_json, category, limit),
                )
            else:
                cursor = conn.execute(
                    """
                    SELECT doc_id, vec_distance_cosine(embedding, ?) as distance
                    FROM document_embeddings
                    ORDER BY distance ASC
                    LIMIT ?
                    """,
                    (query_json, limit),
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
                (category,),
            )
        else:
            cursor = await db.execute("SELECT doc_id, embedding FROM document_embeddings")

        results = []
        async for row in cursor:
            doc_id = row[0]
            embedding = json.loads(row[1])
            # Skip if dimensions don't match
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
        if embedding is None:
            return  # Model not available
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
        if query_embedding is None:
            return []  # Model not available
        return await search_similar(query_embedding, limit, category)
    except Exception as e:
        print(f"Semantic search error: {e}")
        return []
