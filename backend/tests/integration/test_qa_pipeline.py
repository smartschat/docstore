"""Integration tests for Q&A (RAG) pipeline."""

import pytest
from unittest.mock import patch, AsyncMock
import json

import aiosqlite


@pytest.fixture
async def seeded_db_with_embeddings(seeded_db):
    """Database with documents and embeddings stored via service."""
    from app.services.embeddings import store_embedding

    embeddings = {
        "doc-001": [0.1] * 192 + [0.9] * 192,
        "doc-002": [0.9] * 192 + [0.1] * 192,
    }

    for doc_id, embedding in embeddings.items():
        await store_embedding(doc_id, embedding)

    return seeded_db


class TestQuestionAnswering:
    """Test Q&A endpoint with RAG."""

    @pytest.mark.asyncio
    async def test_question_returns_answer_with_sources(
        self, authenticated_client, seeded_db_with_embeddings
    ):
        """Question returns answer generated from relevant documents."""
        with patch("app.services.embeddings.generate_embedding") as mock_embed, \
             patch("app.services.qa.check_ollama_available", new_callable=AsyncMock) as mock_check, \
             patch("app.services.qa.answer_with_ollama", new_callable=AsyncMock) as mock_ollama:

            # Return embedding similar to utilities doc
            mock_embed.return_value = [0.1] * 192 + [0.9] * 192
            mock_check.return_value = True
            mock_ollama.return_value = "Your electric bill from Power Company Inc is $150.00 for January 2024."

            response = authenticated_client.post(
                "/api/ask",
                json={"question": "What was my electric bill?"}
            )

            assert response.status_code == 200
            data = response.json()
            assert "answer" in data
            assert "sources" in data
            assert len(data["answer"]) > 0

    @pytest.mark.asyncio
    async def test_question_about_specific_document(
        self, authenticated_client, seeded_db_with_embeddings
    ):
        """Question can be scoped to specific documents."""
        with patch("app.services.qa.check_ollama_available", new_callable=AsyncMock) as mock_check, \
             patch("app.services.qa.answer_with_ollama", new_callable=AsyncMock) as mock_ollama:

            mock_check.return_value = True
            mock_ollama.return_value = "Your insurance policy number is POL-12345."

            response = authenticated_client.post(
                "/api/ask",
                json={
                    "question": "What is my policy number?",
                    "doc_ids": ["doc-002"]
                }
            )

            assert response.status_code == 200
            data = response.json()
            assert "answer" in data
            # Should only use the specified document as source
            source_ids = [s["id"] for s in data["sources"]]
            assert source_ids == ["doc-002"]

    @pytest.mark.asyncio
    async def test_question_no_relevant_documents(
        self, authenticated_client, seeded_db_with_embeddings
    ):
        """Question with no relevant documents returns appropriate response."""
        with patch("app.services.embeddings.generate_embedding") as mock_embed, \
             patch("app.services.qa.check_ollama_available", new_callable=AsyncMock) as mock_check, \
             patch("app.services.qa.answer_with_ollama", new_callable=AsyncMock) as mock_ollama:

            # Return embedding dissimilar to all docs
            mock_embed.return_value = [0.5] * 384
            mock_check.return_value = True
            mock_ollama.return_value = "I don't have enough information to answer that question."

            response = authenticated_client.post(
                "/api/ask",
                json={"question": "What is the weather today?"}
            )

            assert response.status_code == 200
            # Should still return a response, even if unhelpful
            assert "answer" in response.json()

    @pytest.mark.asyncio
    async def test_question_ollama_unavailable_returns_error(
        self, authenticated_client, seeded_db_with_embeddings
    ):
        """Question when Ollama unavailable returns error."""
        with patch("app.services.qa.check_ollama_available", new_callable=AsyncMock) as mock_check:

            mock_check.return_value = False

            response = authenticated_client.post(
                "/api/ask",
                json={"question": "What is my electric bill?"}
            )

            # Should return 200 with error message in answer
            assert response.status_code == 200
            data = response.json()
            assert "unavailable" in data["answer"].lower() or "ollama" in data["answer"].lower()


class TestContextBuilding:
    """Test context building for RAG."""

    @pytest.mark.asyncio
    async def test_context_includes_relevant_document_text(
        self, seeded_db_with_embeddings
    ):
        """Context includes text from relevant documents."""
        from app.services.qa import get_document_context, build_context_prompt

        # get_document_context takes doc_ids, not a question
        contexts = await get_document_context(["doc-001", "doc-002"])

        # Should return context for both documents
        assert len(contexts) == 2

        # Build context prompt from contexts
        context_prompt = build_context_prompt(contexts)

        # Context should contain document info - uses summary if available, otherwise text
        # The seed data has summaries, so check for those
        assert "Electric bill" in context_prompt or "insurance" in context_prompt.lower()
