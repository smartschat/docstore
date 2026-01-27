"""Integration tests for search pipeline."""

from unittest.mock import patch

import pytest


@pytest.fixture
async def seeded_db_with_embeddings(seeded_db):
    """Database with documents and embeddings stored via service."""
    from app.services.embeddings import store_embedding

    # Create slightly different embeddings for each document
    embeddings = {
        "doc-001": [0.1] * 192 + [0.9] * 192,  # "utilities" semantic
        "doc-002": [0.9] * 192 + [0.1] * 192,  # "insurance" semantic
    }

    for doc_id, embedding in embeddings.items():
        await store_embedding(doc_id, embedding)

    return seeded_db


class TestKeywordSearch:
    """Test keyword search via FTS5."""

    @pytest.mark.asyncio
    async def test_keyword_search_returns_fts_matches(self, authenticated_client, seeded_db):
        """Keyword search returns documents matching FTS5 query."""
        response = authenticated_client.post(
            "/api/search", json={"query": "Power Company", "search_type": "keyword"}
        )

        assert response.status_code == 200
        results = response.json()["results"]
        assert len(results) >= 1
        # Should find the utilities document
        doc_ids = [r["document"]["id"] for r in results]
        assert "doc-001" in doc_ids

    @pytest.mark.asyncio
    async def test_keyword_search_with_category_filter(self, authenticated_client, seeded_db):
        """Keyword search respects category filter."""
        response = authenticated_client.post(
            "/api/search",
            json={"query": "Policy", "search_type": "keyword", "category": "insurance"},
        )

        assert response.status_code == 200
        results = response.json()["results"]
        # All results should have insurance category
        for result in results:
            assert result["document"]["category"] == "insurance"

    @pytest.mark.asyncio
    async def test_keyword_search_escapes_special_characters(self, authenticated_client, seeded_db):
        """Keyword search handles special characters safely."""
        # FTS5 special characters should be handled
        response = authenticated_client.post(
            "/api/search", json={"query": "test OR DROP TABLE", "search_type": "keyword"}
        )

        # Should not crash
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_keyword_search_no_results_returns_empty(self, authenticated_client, seeded_db):
        """Keyword search with no matches returns empty results."""
        response = authenticated_client.post(
            "/api/search", json={"query": "xyznonexistentterm123", "search_type": "keyword"}
        )

        assert response.status_code == 200
        assert response.json()["results"] == []


class TestSemanticSearch:
    """Test semantic search via embeddings."""

    @pytest.mark.asyncio
    async def test_semantic_search_returns_similar_documents(
        self, authenticated_client, seeded_db_with_embeddings
    ):
        """Semantic search returns semantically similar documents."""
        # Mock embedding generation for the query
        with patch("app.services.embeddings.generate_embedding") as mock_embed:
            # Query embedding similar to utilities document
            mock_embed.return_value = [0.1] * 192 + [0.9] * 192

            response = authenticated_client.post(
                "/api/search", json={"query": "electric bill payment", "search_type": "semantic"}
            )

            assert response.status_code == 200
            results = response.json()["results"]
            assert len(results) > 0

    @pytest.mark.asyncio
    async def test_semantic_search_respects_category_filter(
        self, authenticated_client, seeded_db_with_embeddings
    ):
        """Semantic search respects category filter."""
        with patch("app.services.embeddings.generate_embedding") as mock_embed:
            mock_embed.return_value = [0.5] * 384

            response = authenticated_client.post(
                "/api/search",
                json={"query": "document", "search_type": "semantic", "category": "utilities"},
            )

            assert response.status_code == 200
            results = response.json()["results"]
            for result in results:
                assert result["document"]["category"] == "utilities"


class TestHybridSearch:
    """Test hybrid search combining keyword and semantic."""

    @pytest.mark.asyncio
    async def test_hybrid_search_combines_scores(
        self, authenticated_client, seeded_db_with_embeddings
    ):
        """Hybrid search combines keyword and semantic scores."""
        with patch("app.services.embeddings.generate_embedding") as mock_embed:
            mock_embed.return_value = [0.1] * 192 + [0.9] * 192

            response = authenticated_client.post(
                "/api/search", json={"query": "Power Company", "search_type": "hybrid"}
            )

            assert response.status_code == 200
            results = response.json()["results"]
            assert len(results) > 0

            # Scores should be normalized 0-1
            for result in results:
                assert 0 <= result["score"] <= 1

    @pytest.mark.asyncio
    async def test_hybrid_search_keyword_only_matches(
        self, authenticated_client, seeded_db_with_embeddings
    ):
        """Hybrid search includes keyword-only matches."""
        with patch("app.services.embeddings.generate_embedding") as mock_embed:
            # Return an embedding that's dissimilar to all docs
            mock_embed.return_value = [0.0] * 384

            response = authenticated_client.post(
                "/api/search", json={"query": "Insurance Policy", "search_type": "hybrid"}
            )

            assert response.status_code == 200
            # Should still find insurance document via keyword match
            results = response.json()["results"]
            doc_ids = [r["document"]["id"] for r in results]
            assert "doc-002" in doc_ids


class TestSearchSuggestions:
    """Test search autocomplete suggestions."""

    @pytest.mark.asyncio
    async def test_suggestions_returns_matching_data(self, authenticated_client, seeded_db):
        """Suggestions return matching filenames, tags, and counterparties."""
        response = authenticated_client.get("/api/search/suggest?q=Power")

        assert response.status_code == 200
        data = response.json()
        assert "filenames" in data
        assert "tags" in data
        assert "counterparties" in data

        # Should find Power Company in counterparties
        assert "Power Company Inc" in data["counterparties"]

    @pytest.mark.asyncio
    async def test_suggestions_minimum_query_length(self, authenticated_client, seeded_db):
        """Suggestions require minimum query length."""
        response = authenticated_client.get("/api/search/suggest?q=P")

        # Should fail validation (min_length=2)
        assert response.status_code == 422
