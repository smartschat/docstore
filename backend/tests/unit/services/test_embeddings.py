"""Unit tests for embeddings service."""

import json
import math
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import aiosqlite
import numpy as np
import pytest

from app.services.embeddings import (
    _mean_pooling,
    _normalize,
    _search_similar_fallback,
    embed_document,
    generate_embedding,
    search_similar,
    semantic_search,
    store_embedding,
)


class TestMeanPooling:
    """Tests for _mean_pooling function."""

    def test_standard_pooling(self):
        """Standard mean pooling works correctly."""
        # Model output: batch_size=1, seq_len=3, hidden_size=4
        model_output = np.array([[[1, 2, 3, 4], [5, 6, 7, 8], [9, 10, 11, 12]]])
        attention_mask = np.array([[1, 1, 1]])

        result = _mean_pooling(model_output, attention_mask)

        # Mean of each column: (1+5+9)/3, (2+6+10)/3, etc.
        expected = np.array([[5.0, 6.0, 7.0, 8.0]])
        np.testing.assert_array_almost_equal(result, expected)

    def test_pooling_with_padding(self):
        """Pooling correctly ignores padded tokens."""
        model_output = np.array([[[1, 2], [3, 4], [100, 200]]])  # Last token is padding
        attention_mask = np.array([[1, 1, 0]])  # Mask out last token

        result = _mean_pooling(model_output, attention_mask)

        # Only average first two tokens: (1+3)/2, (2+4)/2
        expected = np.array([[2.0, 3.0]])
        np.testing.assert_array_almost_equal(result, expected)

    def test_single_token(self):
        """Pooling with single token returns that token."""
        model_output = np.array([[[5, 10, 15]]])
        attention_mask = np.array([[1]])

        result = _mean_pooling(model_output, attention_mask)

        expected = np.array([[5.0, 10.0, 15.0]])
        np.testing.assert_array_almost_equal(result, expected)

    def test_batch_processing(self):
        """Pooling handles multiple sequences in batch."""
        model_output = np.array([
            [[1, 2], [3, 4]],  # Sequence 1
            [[5, 6], [7, 8]]   # Sequence 2
        ])
        attention_mask = np.array([
            [1, 1],
            [1, 1]
        ])

        result = _mean_pooling(model_output, attention_mask)

        expected = np.array([
            [2.0, 3.0],  # Mean of seq 1
            [6.0, 7.0]   # Mean of seq 2
        ])
        np.testing.assert_array_almost_equal(result, expected)


class TestNormalize:
    """Tests for _normalize function."""

    def test_l2_normalizes_vector(self):
        """L2 normalization produces unit vectors."""
        # 3-4-5 triangle: norm = 5
        embeddings = np.array([[3.0, 4.0]])
        normalized = _normalize(embeddings)

        np.testing.assert_array_almost_equal(normalized, [[0.6, 0.8]])
        assert np.isclose(np.linalg.norm(normalized[0]), 1.0)

    def test_handles_zero_vector(self):
        """Zero vector doesn't cause division by zero."""
        embeddings = np.array([[0.0, 0.0, 0.0]])
        normalized = _normalize(embeddings)

        # Should be small values, not NaN or Inf
        assert not np.any(np.isnan(normalized))
        assert not np.any(np.isinf(normalized))

    def test_batch_normalization(self):
        """Multiple vectors are normalized independently."""
        embeddings = np.array([
            [3.0, 4.0],  # norm = 5
            [1.0, 0.0]   # norm = 1
        ])
        normalized = _normalize(embeddings)

        np.testing.assert_array_almost_equal(normalized[0], [0.6, 0.8])
        np.testing.assert_array_almost_equal(normalized[1], [1.0, 0.0])

    def test_preserves_direction(self):
        """Normalization preserves vector direction."""
        embeddings = np.array([[2.0, 4.0, 6.0]])
        normalized = _normalize(embeddings)

        # Check ratios are preserved
        assert np.isclose(normalized[0, 1] / normalized[0, 0], 2.0)
        assert np.isclose(normalized[0, 2] / normalized[0, 0], 3.0)


class TestGenerateEmbedding:
    """Tests for generate_embedding function."""

    @pytest.mark.asyncio
    async def test_returns_none_when_model_unavailable(self):
        """Returns None when model fails to load."""
        with patch("app.services.embeddings._load_model", return_value=False):
            result = await generate_embedding("test text")
            assert result is None

    @pytest.mark.asyncio
    async def test_returns_384_dim_vector(self):
        """Returns 384-dimensional embedding for MiniLM model."""
        mock_embedding = np.random.randn(1, 384)

        with patch("app.services.embeddings._load_model", return_value=True):
            with patch("app.services.embeddings._tokenizer") as mock_tokenizer:
                with patch("app.services.embeddings._session") as mock_session:
                    # Mock tokenizer
                    mock_encoded = MagicMock()
                    mock_encoded.ids = list(range(10))
                    mock_encoded.attention_mask = [1] * 10
                    mock_tokenizer.encode.return_value = mock_encoded

                    # Mock session output
                    mock_session.run.return_value = [np.random.randn(1, 10, 384)]

                    result = await generate_embedding("test text")

                    assert result is not None
                    assert len(result) == 384

    @pytest.mark.asyncio
    async def test_truncates_long_text(self):
        """Text longer than max_chars is truncated."""
        long_text = "x" * 10000

        with patch("app.services.embeddings._load_model", return_value=True):
            with patch("app.services.embeddings._tokenizer") as mock_tokenizer:
                with patch("app.services.embeddings._session") as mock_session:
                    mock_encoded = MagicMock()
                    mock_encoded.ids = list(range(10))
                    mock_encoded.attention_mask = [1] * 10
                    mock_tokenizer.encode.return_value = mock_encoded
                    mock_session.run.return_value = [np.random.randn(1, 10, 384)]

                    await generate_embedding(long_text)

                    # Check that tokenizer was called with truncated text
                    call_args = mock_tokenizer.encode.call_args[0][0]
                    assert len(call_args) <= 8000


@pytest.fixture
async def fallback_db(tmp_path, test_settings):
    """Create a database with JSON fallback table (no sqlite-vec)."""
    db_path = tmp_path / "fallback.db"

    # Create database with fallback table structure
    async with aiosqlite.connect(str(db_path)) as db:
        await db.execute("PRAGMA foreign_keys = ON")

        await db.execute("""
            CREATE TABLE documents (
                id TEXT PRIMARY KEY,
                filename TEXT NOT NULL,
                file_path TEXT NOT NULL,
                file_hash TEXT NOT NULL,
                category TEXT,
                status TEXT DEFAULT 'pending'
            )
        """)

        await db.execute("""
            CREATE TABLE document_embeddings (
                doc_id TEXT PRIMARY KEY,
                embedding TEXT NOT NULL,
                FOREIGN KEY (doc_id) REFERENCES documents(id) ON DELETE CASCADE
            )
        """)
        await db.commit()

    # Patch the settings database path for the embeddings module
    with patch.object(test_settings, 'database_path', db_path):
        yield str(db_path)


class TestSearchSimilarFallback:
    """Tests for _search_similar_fallback function (Python cosine similarity)."""

    @pytest.mark.asyncio
    async def test_finds_identical_vectors(self, fallback_db, test_settings):
        """Identical vectors have similarity of 1."""
        query_embedding = [1.0, 0.0, 0.0]

        async with aiosqlite.connect(fallback_db) as db:
            await db.execute(
                "INSERT INTO document_embeddings (doc_id, embedding) VALUES (?, ?)",
                ("doc-1", json.dumps([1.0, 0.0, 0.0]))
            )
            await db.commit()

        with patch.object(test_settings, 'database_path', Path(fallback_db)):
            results = await _search_similar_fallback(query_embedding, limit=10, category=None)

        assert len(results) == 1
        assert results[0][0] == "doc-1"
        assert np.isclose(results[0][1], 1.0)

    @pytest.mark.asyncio
    async def test_orthogonal_vectors_zero_similarity(self, fallback_db, test_settings):
        """Orthogonal vectors have similarity of 0."""
        query_embedding = [1.0, 0.0, 0.0]

        async with aiosqlite.connect(fallback_db) as db:
            await db.execute(
                "INSERT INTO document_embeddings (doc_id, embedding) VALUES (?, ?)",
                ("doc-1", json.dumps([0.0, 1.0, 0.0]))  # Orthogonal to query
            )
            await db.commit()

        with patch.object(test_settings, 'database_path', Path(fallback_db)):
            results = await _search_similar_fallback(query_embedding, limit=10, category=None)

        assert len(results) == 1
        assert np.isclose(results[0][1], 0.0)

    @pytest.mark.asyncio
    async def test_opposite_vectors_negative_similarity(self, fallback_db, test_settings):
        """Opposite vectors have similarity of -1."""
        query_embedding = [1.0, 0.0, 0.0]

        async with aiosqlite.connect(fallback_db) as db:
            await db.execute(
                "INSERT INTO document_embeddings (doc_id, embedding) VALUES (?, ?)",
                ("doc-1", json.dumps([-1.0, 0.0, 0.0]))
            )
            await db.commit()

        with patch.object(test_settings, 'database_path', Path(fallback_db)):
            results = await _search_similar_fallback(query_embedding, limit=10, category=None)

        assert len(results) == 1
        assert np.isclose(results[0][1], -1.0)

    @pytest.mark.asyncio
    async def test_returns_sorted_by_similarity(self, fallback_db, test_settings):
        """Results are sorted by similarity descending."""
        query_embedding = [1.0, 0.0, 0.0]

        async with aiosqlite.connect(fallback_db) as db:
            await db.execute(
                "INSERT INTO document_embeddings (doc_id, embedding) VALUES (?, ?)",
                ("doc-low", json.dumps([0.5, 0.5, 0.0]))  # Lower similarity
            )
            await db.execute(
                "INSERT INTO document_embeddings (doc_id, embedding) VALUES (?, ?)",
                ("doc-high", json.dumps([0.9, 0.1, 0.0]))  # Higher similarity
            )
            await db.commit()

        with patch.object(test_settings, 'database_path', Path(fallback_db)):
            results = await _search_similar_fallback(query_embedding, limit=10, category=None)

        assert len(results) == 2
        assert results[0][0] == "doc-high"  # Higher similarity first
        assert results[1][0] == "doc-low"

    @pytest.mark.asyncio
    async def test_respects_limit(self, fallback_db, test_settings):
        """Returns at most 'limit' results."""
        query_embedding = [1.0, 0.0, 0.0]

        async with aiosqlite.connect(fallback_db) as db:
            for i in range(10):
                await db.execute(
                    "INSERT INTO document_embeddings (doc_id, embedding) VALUES (?, ?)",
                    (f"doc-{i}", json.dumps([1.0, 0.0, 0.0]))
                )
            await db.commit()

        with patch.object(test_settings, 'database_path', Path(fallback_db)):
            results = await _search_similar_fallback(query_embedding, limit=3, category=None)

        assert len(results) == 3

    @pytest.mark.asyncio
    async def test_filters_by_category(self, fallback_db, test_settings):
        """Filters results by category when specified."""
        query_embedding = [1.0, 0.0, 0.0]

        async with aiosqlite.connect(fallback_db) as db:
            # Add documents with different categories
            await db.execute(
                "INSERT INTO documents (id, filename, file_path, file_hash, category, status) VALUES (?, ?, ?, ?, ?, ?)",
                ("doc-001", "test1.pdf", "/path1", "hash1", "utilities", "completed")
            )
            await db.execute(
                "INSERT INTO documents (id, filename, file_path, file_hash, category, status) VALUES (?, ?, ?, ?, ?, ?)",
                ("doc-002", "test2.pdf", "/path2", "hash2", "insurance", "completed")
            )
            # Add embeddings
            await db.execute(
                "INSERT INTO document_embeddings (doc_id, embedding) VALUES (?, ?)",
                ("doc-001", json.dumps([1.0, 0.0, 0.0]))  # utilities category
            )
            await db.execute(
                "INSERT INTO document_embeddings (doc_id, embedding) VALUES (?, ?)",
                ("doc-002", json.dumps([1.0, 0.0, 0.0]))  # insurance category
            )
            await db.commit()

        with patch.object(test_settings, 'database_path', Path(fallback_db)):
            results = await _search_similar_fallback(query_embedding, limit=10, category="utilities")

        assert len(results) == 1
        assert results[0][0] == "doc-001"


class TestSemanticSearch:
    """Tests for semantic_search function."""

    @pytest.mark.asyncio
    async def test_returns_empty_when_model_unavailable(self):
        """Returns empty list when embedding model is not available."""
        with patch("app.services.embeddings.generate_embedding", new=AsyncMock(return_value=None)):
            result = await semantic_search("test query")
            assert result == []

    @pytest.mark.asyncio
    async def test_returns_results_with_scores(self):
        """Returns list of (doc_id, score) tuples."""
        mock_embedding = [0.1] * 384

        with patch("app.services.embeddings.generate_embedding", new=AsyncMock(return_value=mock_embedding)):
            with patch("app.services.embeddings.search_similar", new=AsyncMock(return_value=[
                ("doc-1", 0.95),
                ("doc-2", 0.80)
            ])):
                result = await semantic_search("test query")

                assert len(result) == 2
                assert result[0] == ("doc-1", 0.95)
                assert result[1] == ("doc-2", 0.80)


class TestStoreEmbedding:
    """Tests for store_embedding function."""

    @pytest.mark.asyncio
    async def test_stores_embedding_in_database(self, fallback_db, test_settings):
        """Embedding is stored correctly in database."""
        embedding = [0.1, 0.2, 0.3]

        # Mock to use fallback (no sqlite-vec)
        with patch("app.services.embeddings._get_vec_connection", return_value=None):
            with patch.object(test_settings, 'database_path', Path(fallback_db)):
                await store_embedding("test-doc", embedding)

        # Verify stored
        async with aiosqlite.connect(fallback_db) as db:
            cursor = await db.execute(
                "SELECT embedding FROM document_embeddings WHERE doc_id = ?",
                ("test-doc",)
            )
            row = await cursor.fetchone()
            assert row is not None
            stored_embedding = json.loads(row[0])
            assert stored_embedding == embedding

    @pytest.mark.asyncio
    async def test_replaces_existing_embedding(self, fallback_db, test_settings):
        """Existing embedding is replaced."""
        # Store initial embedding
        async with aiosqlite.connect(fallback_db) as db:
            await db.execute(
                "INSERT INTO document_embeddings (doc_id, embedding) VALUES (?, ?)",
                ("test-doc", json.dumps([1, 2, 3]))
            )
            await db.commit()

        # Store new embedding
        new_embedding = [4, 5, 6]
        with patch("app.services.embeddings._get_vec_connection", return_value=None):
            with patch.object(test_settings, 'database_path', Path(fallback_db)):
                await store_embedding("test-doc", new_embedding)

        # Verify replaced
        async with aiosqlite.connect(fallback_db) as db:
            cursor = await db.execute(
                "SELECT embedding FROM document_embeddings WHERE doc_id = ?",
                ("test-doc",)
            )
            row = await cursor.fetchone()
            stored_embedding = json.loads(row[0])
            assert stored_embedding == new_embedding


class TestEmbedDocument:
    """Tests for embed_document function."""

    @pytest.mark.asyncio
    async def test_skips_empty_text(self):
        """Does nothing for empty text."""
        with patch("app.services.embeddings.generate_embedding") as mock_gen:
            await embed_document("doc-1", "")
            mock_gen.assert_not_called()

    @pytest.mark.asyncio
    async def test_skips_whitespace_only_text(self):
        """Does nothing for whitespace-only text."""
        with patch("app.services.embeddings.generate_embedding") as mock_gen:
            await embed_document("doc-1", "   \n\t  ")
            mock_gen.assert_not_called()

    @pytest.mark.asyncio
    async def test_generates_and_stores_embedding(self):
        """Generates embedding and stores it."""
        mock_embedding = [0.1] * 384

        with patch("app.services.embeddings.generate_embedding", new=AsyncMock(return_value=mock_embedding)):
            with patch("app.services.embeddings.store_embedding", new=AsyncMock()) as mock_store:
                await embed_document("doc-1", "Some document text")

                mock_store.assert_called_once_with("doc-1", mock_embedding)

    @pytest.mark.asyncio
    async def test_handles_generation_failure_gracefully(self):
        """Gracefully handles embedding generation failure."""
        with patch("app.services.embeddings.generate_embedding", new=AsyncMock(return_value=None)):
            with patch("app.services.embeddings.store_embedding") as mock_store:
                # Should not raise
                await embed_document("doc-1", "Some text")
                mock_store.assert_not_called()
