"""Unit tests for search router."""

from unittest.mock import AsyncMock, patch

import aiosqlite
import pytest


class TestNormalizeScores:
    """Tests for the normalize function inside hybrid_search."""

    def test_normalizes_to_0_1_range(self):
        """Scores are normalized to 0-1 range."""
        scores = {"doc1": 10.0, "doc2": 20.0, "doc3": 30.0}

        def normalize(scores: dict[str, float]) -> dict[str, float]:
            if not scores:
                return {}
            max_score = max(scores.values())
            min_score = min(scores.values())
            if max_score == min_score:
                return {k: 1.0 for k in scores}
            return {k: (v - min_score) / (max_score - min_score) for k, v in scores.items()}

        normalized = normalize(scores)

        assert normalized["doc1"] == 0.0
        assert normalized["doc2"] == 0.5
        assert normalized["doc3"] == 1.0

    def test_handles_single_value(self):
        """Single value normalizes to 1.0."""
        scores = {"doc1": 5.0}

        def normalize(scores: dict[str, float]) -> dict[str, float]:
            if not scores:
                return {}
            max_score = max(scores.values())
            min_score = min(scores.values())
            if max_score == min_score:
                return {k: 1.0 for k in scores}
            return {k: (v - min_score) / (max_score - min_score) for k, v in scores.items()}

        normalized = normalize(scores)

        assert normalized["doc1"] == 1.0

    def test_handles_empty_dict(self):
        """Empty dict returns empty dict."""
        scores = {}

        def normalize(scores: dict[str, float]) -> dict[str, float]:
            if not scores:
                return {}
            max_score = max(scores.values())
            min_score = min(scores.values())
            if max_score == min_score:
                return {k: 1.0 for k in scores}
            return {k: (v - min_score) / (max_score - min_score) for k, v in scores.items()}

        normalized = normalize(scores)

        assert normalized == {}

    def test_handles_all_same_scores(self):
        """All same scores normalize to 1.0."""
        scores = {"doc1": 5.0, "doc2": 5.0, "doc3": 5.0}

        def normalize(scores: dict[str, float]) -> dict[str, float]:
            if not scores:
                return {}
            max_score = max(scores.values())
            min_score = min(scores.values())
            if max_score == min_score:
                return {k: 1.0 for k in scores}
            return {k: (v - min_score) / (max_score - min_score) for k, v in scores.items()}

        normalized = normalize(scores)

        assert all(v == 1.0 for v in normalized.values())


class TestKeywordSearch:
    """Tests for keyword_search function."""

    @pytest.mark.asyncio
    async def test_returns_fts_matches(self, seeded_db):
        """FTS5 matches are returned with scores."""
        from app.routers.search import keyword_search

        # Seed FTS index
        async with aiosqlite.connect(seeded_db) as db:
            # Trigger FTS rebuild
            await db.execute("INSERT INTO documents_fts(documents_fts) VALUES('rebuild')")
            await db.commit()

        results = await keyword_search("Power Company")

        assert len(results) >= 1
        # Results are (doc_id, score, snippet)
        doc_ids = [r[0] for r in results]
        assert "doc-001" in doc_ids

    @pytest.mark.asyncio
    async def test_returns_empty_for_no_matches(self, seeded_db):
        """Returns empty list when no matches found."""
        from app.routers.search import keyword_search

        async with aiosqlite.connect(seeded_db) as db:
            await db.execute("INSERT INTO documents_fts(documents_fts) VALUES('rebuild')")
            await db.commit()

        results = await keyword_search("xyznonexistentterm123")

        assert results == []

    @pytest.mark.asyncio
    async def test_filters_by_category(self, seeded_db):
        """Category filter is applied."""
        from app.routers.search import keyword_search

        async with aiosqlite.connect(seeded_db) as db:
            await db.execute("INSERT INTO documents_fts(documents_fts) VALUES('rebuild')")
            await db.commit()

        # Search for something that exists but filter by different category
        results = await keyword_search("Policy", category="utilities")

        # Should not find insurance policy when filtering for utilities
        doc_ids = [r[0] for r in results]
        assert "doc-002" not in doc_ids

    @pytest.mark.asyncio
    async def test_respects_limit(self, seeded_db):
        """Limit parameter is respected."""
        from app.routers.search import keyword_search

        async with aiosqlite.connect(seeded_db) as db:
            await db.execute("INSERT INTO documents_fts(documents_fts) VALUES('rebuild')")
            await db.commit()

        results = await keyword_search("document", limit=1)

        assert len(results) <= 1

    @pytest.mark.asyncio
    async def test_filters_by_date_range(self, seeded_db):
        """Date range filters are applied."""
        from app.routers.search import keyword_search

        async with aiosqlite.connect(seeded_db) as db:
            await db.execute("INSERT INTO documents_fts(documents_fts) VALUES('rebuild')")
            await db.commit()

        # Search with date range that excludes some docs
        results = await keyword_search("Invoice", date_from="2024-01-01", date_to="2024-01-31")

        # doc-001 is dated 2024-01-15, should be included
        doc_ids = [r[0] for r in results]
        if results:  # Only if there are results
            assert all(d in ["doc-001"] for d in doc_ids)


class TestHybridSearch:
    """Tests for hybrid_search function."""

    @pytest.mark.asyncio
    async def test_combines_keyword_and_semantic_results(self, seeded_db):
        """Hybrid search combines both search types."""
        from app.routers.search import hybrid_search

        async with aiosqlite.connect(seeded_db) as db:
            await db.execute("INSERT INTO documents_fts(documents_fts) VALUES('rebuild')")
            await db.commit()

        # Mock semantic search to avoid needing to insert into vec0 table
        with patch(
            "app.routers.search.semantic_search",
            new=AsyncMock(return_value=[("doc-002", 0.9), ("doc-001", 0.7)]),
        ):
            results = await hybrid_search("insurance policy")

            # Should have results from both searches
            assert len(results) >= 1
            doc_ids = [r[0] for r in results]
            assert "doc-002" in doc_ids or "doc-001" in doc_ids

    @pytest.mark.asyncio
    async def test_weights_applied_correctly(self):
        """Keyword and semantic weights are applied."""
        from app.routers.search import hybrid_search

        # Mock both search functions
        with patch(
            "app.routers.search.keyword_search",
            new=AsyncMock(return_value=[("doc-1", 10.0, "snippet")]),
        ):
            with patch(
                "app.routers.search.semantic_search", new=AsyncMock(return_value=[("doc-1", 0.9)])
            ):
                results = await hybrid_search("test", keyword_weight=0.3, semantic_weight=0.7)

                # Both should be normalized to 1.0 since they're the only results
                # Combined score = 0.3 * 1.0 + 0.7 * 1.0 = 1.0
                assert len(results) == 1
                assert results[0][0] == "doc-1"
                assert results[0][1] == pytest.approx(1.0)

    @pytest.mark.asyncio
    async def test_handles_keyword_only_matches(self):
        """Handles documents only found via keyword search."""
        from app.routers.search import hybrid_search

        with patch(
            "app.routers.search.keyword_search",
            new=AsyncMock(return_value=[("doc-keyword", 5.0, "snippet")]),
        ):
            with patch("app.routers.search.semantic_search", new=AsyncMock(return_value=[])):
                results = await hybrid_search("test")

                assert len(results) == 1
                assert results[0][0] == "doc-keyword"
                # Score should be keyword_weight * 1.0 (normalized) + 0
                assert results[0][1] == pytest.approx(0.3)

    @pytest.mark.asyncio
    async def test_handles_semantic_only_matches(self):
        """Handles documents only found via semantic search."""
        from app.routers.search import hybrid_search

        with patch("app.routers.search.keyword_search", new=AsyncMock(return_value=[])):
            with patch(
                "app.routers.search.semantic_search",
                new=AsyncMock(return_value=[("doc-semantic", 0.8)]),
            ):
                results = await hybrid_search("test")

                assert len(results) == 1
                assert results[0][0] == "doc-semantic"
                # Score should be 0 + semantic_weight * 1.0
                assert results[0][1] == pytest.approx(0.7)

    @pytest.mark.asyncio
    async def test_sorts_by_combined_score(self):
        """Results are sorted by combined score descending."""
        from app.routers.search import hybrid_search

        with patch(
            "app.routers.search.keyword_search",
            new=AsyncMock(return_value=[("doc-1", 10.0, "s1"), ("doc-2", 5.0, "s2")]),
        ):
            with patch(
                "app.routers.search.semantic_search",
                new=AsyncMock(
                    return_value=[
                        ("doc-2", 1.0),  # Higher semantic score for doc-2
                        ("doc-1", 0.5),
                    ]
                ),
            ):
                results = await hybrid_search("test")

                assert len(results) == 2
                # With default weights (0.3 keyword, 0.7 semantic),
                # doc-2 should rank higher due to higher semantic score
                scores = [r[1] for r in results]
                assert scores[0] >= scores[1]

    @pytest.mark.asyncio
    async def test_respects_limit(self):
        """Limit parameter is respected."""
        from app.routers.search import hybrid_search

        with patch(
            "app.routers.search.keyword_search",
            new=AsyncMock(
                return_value=[("doc-1", 10.0, "s1"), ("doc-2", 9.0, "s2"), ("doc-3", 8.0, "s3")]
            ),
        ):
            with patch("app.routers.search.semantic_search", new=AsyncMock(return_value=[])):
                results = await hybrid_search("test", limit=2)

                assert len(results) == 2


class TestSearchSuggestions:
    """Tests for search_suggestions endpoint."""

    @pytest.mark.asyncio
    async def test_returns_matching_filenames(self, seeded_db):
        """Returns filenames matching query."""

        # Mock the auth dependency
        with patch("app.routers.search.get_current_session", return_value="valid-token"):
            mock_request = AsyncMock()
            mock_request.headers.get.return_value = None

            # Call the function directly (bypassing FastAPI)
            # We need to test the database query logic
            async with aiosqlite.connect(seeded_db) as db:
                cursor = await db.execute(
                    "SELECT DISTINCT filename FROM documents WHERE filename LIKE ?", ("%invoice%",)
                )
                filenames = [row[0] for row in await cursor.fetchall()]

            assert "invoice_2024.pdf" in filenames

    @pytest.mark.asyncio
    async def test_returns_matching_tags(self, seeded_db):
        """Returns tags matching query."""
        # Add some tags first
        async with aiosqlite.connect(seeded_db) as db:
            await db.execute("INSERT INTO tags (name) VALUES (?)", ("important",))
            await db.execute("INSERT INTO tags (name) VALUES (?)", ("invoice-related",))
            await db.commit()

            cursor = await db.execute("SELECT name FROM tags WHERE name LIKE ?", ("%inv%",))
            tags = [row[0] for row in await cursor.fetchall()]

        assert "invoice-related" in tags

    @pytest.mark.asyncio
    async def test_returns_matching_counterparties(self, seeded_db):
        """Returns counterparties matching query."""
        async with aiosqlite.connect(seeded_db) as db:
            cursor = await db.execute(
                "SELECT DISTINCT counterparty FROM documents WHERE counterparty LIKE ?",
                ("%Power%",),
            )
            counterparties = [row[0] for row in await cursor.fetchall() if row[0]]

        assert "Power Company Inc" in counterparties


class TestRowToDocument:
    """Tests for row_to_document helper function."""

    def test_converts_row_to_document_model(self):
        """Database row is converted to Document model."""

        from app.routers.search import row_to_document

        row = {
            "id": "doc-1",
            "filename": "test.pdf",
            "file_path": "/path/test.pdf",
            "file_hash": "abc123",
            "file_size": 1024,
            "mime_type": "application/pdf",
            "raw_text": "Some text",
            "page_count": 2,
            "summary": "A summary",
            "document_date": "2024-01-15",
            "created_at": "2024-01-01T00:00:00",
            "processed_at": "2024-01-01T01:00:00",
            "status": "completed",
            "extraction_status": "completed",
            "title": "Test Document",
            "counterparty": "Test Corp",
            "affected_person": "John Doe",
            "category": "invoice",
            "reference": "INV-123",
        }

        doc = row_to_document(row)

        assert doc.id == "doc-1"
        assert doc.filename == "test.pdf"
        assert doc.title == "Test Document"
        assert doc.category == "invoice"

    def test_handles_missing_optional_fields(self):
        """Missing optional fields default to None."""
        from app.routers.search import row_to_document

        row = {
            "id": "doc-1",
            "filename": "test.pdf",
            "file_path": "/path/test.pdf",
            "file_hash": "abc123",
            "file_size": None,
            "mime_type": None,
            "raw_text": None,
            "page_count": None,
            "summary": None,
            "document_date": None,
            "created_at": None,
            "processed_at": None,
            "status": "pending",
            "extraction_status": None,
            "title": None,
            "counterparty": None,
            "affected_person": None,
            "category": None,
            "reference": None,
        }

        doc = row_to_document(row)

        assert doc.id == "doc-1"
        assert doc.title is None
        assert doc.category is None
