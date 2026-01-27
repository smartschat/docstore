"""Unit tests for Q&A service."""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from app.services.qa import (
    answer_question,
    answer_with_ollama,
    build_context_prompt,
    check_ollama_available,
    get_document_context,
    get_document_qa,
)


class TestCheckOllamaAvailable:
    """Tests for check_ollama_available function."""

    @pytest.mark.asyncio
    async def test_returns_true_when_available(self):
        """Returns True when Ollama responds with 200."""
        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch("app.services.qa.httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )
            result = await check_ollama_available()

        assert result is True

    @pytest.mark.asyncio
    async def test_returns_false_on_error(self):
        """Returns False when connection fails."""
        with patch("app.services.qa.httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                side_effect=httpx.ConnectError("Connection refused")
            )
            result = await check_ollama_available()

        assert result is False

    @pytest.mark.asyncio
    async def test_returns_false_on_timeout(self):
        """Returns False when request times out."""
        with patch("app.services.qa.httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                side_effect=httpx.TimeoutException("Timeout")
            )
            result = await check_ollama_available()

        assert result is False


class TestGetDocumentContext:
    """Tests for get_document_context function."""

    @pytest.mark.asyncio
    async def test_fetches_single_document(self, seeded_db):
        """Fetches context for a single document."""
        result = await get_document_context(["doc-001"])

        assert len(result) == 1
        assert result[0]["id"] == "doc-001"
        assert result[0]["filename"] == "invoice_2024.pdf"
        assert "Power Company" in result[0]["text"]

    @pytest.mark.asyncio
    async def test_fetches_multiple_documents(self, seeded_db):
        """Fetches context for multiple documents."""
        result = await get_document_context(["doc-001", "doc-002"])

        assert len(result) == 2
        ids = [ctx["id"] for ctx in result]
        assert "doc-001" in ids
        assert "doc-002" in ids

    @pytest.mark.asyncio
    async def test_handles_nonexistent_document(self, seeded_db):
        """Skips nonexistent documents."""
        result = await get_document_context(["doc-001", "nonexistent"])

        assert len(result) == 1
        assert result[0]["id"] == "doc-001"

    @pytest.mark.asyncio
    async def test_empty_list_returns_empty(self, seeded_db):
        """Empty input returns empty list."""
        result = await get_document_context([])

        assert result == []


class TestBuildContextPrompt:
    """Tests for build_context_prompt function."""

    def test_builds_prompt_from_contexts(self):
        """Builds formatted prompt from contexts."""
        contexts = [
            {
                "filename": "doc1.pdf",
                "category": "invoice",
                "summary": "This is a test summary.",
                "text": "Full text here",
            }
        ]

        result = build_context_prompt(contexts)

        assert "[Document: doc1.pdf]" in result
        assert "(Category: invoice)" in result
        assert "This is a test summary." in result

    def test_uses_text_when_no_summary(self):
        """Uses text when summary is empty."""
        contexts = [
            {
                "filename": "doc1.pdf",
                "category": None,
                "summary": "",
                "text": "Full document text",
            }
        ]

        result = build_context_prompt(contexts)

        assert "Full document text" in result

    def test_truncates_at_max_chars(self):
        """Truncates content at max_chars limit."""
        contexts = [
            {
                "filename": "doc1.pdf",
                "category": None,
                "summary": "x" * 5000,
                "text": "",
            },
            {
                "filename": "doc2.pdf",
                "category": None,
                "summary": "y" * 5000,
                "text": "",
            },
        ]

        result = build_context_prompt(contexts, max_chars=200)

        assert len(result) <= 300  # Some buffer for headers
        assert "..." in result

    def test_empty_contexts_returns_empty(self):
        """Empty contexts list returns empty string."""
        result = build_context_prompt([])

        assert result == ""


class TestAnswerWithOllama:
    """Tests for answer_with_ollama function."""

    @pytest.mark.asyncio
    async def test_successful_answer(self):
        """Successfully generates answer."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"response": "This is the answer."}
        mock_response.raise_for_status = MagicMock()

        with patch("app.services.qa.httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=mock_response
            )
            result = await answer_with_ollama("What is this?", "Document context here")

        assert result == "This is the answer."

    @pytest.mark.asyncio
    async def test_handles_error(self):
        """Handles errors gracefully."""
        with patch("app.services.qa.httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                side_effect=Exception("Connection failed")
            )
            result = await answer_with_ollama("Question?", "Context")

        assert "Error generating answer" in result


class TestAnswerQuestion:
    """Tests for answer_question function."""

    @pytest.mark.asyncio
    async def test_returns_error_when_ollama_unavailable(self, seeded_db):
        """Returns error message when Ollama is unavailable."""
        with patch("app.services.qa.check_ollama_available", new=AsyncMock(return_value=False)):
            result = await answer_question("What is this document?")

        assert "not available" in result["answer"]
        assert result["sources"] == []

    @pytest.mark.asyncio
    async def test_uses_semantic_search_for_context(self, seeded_db):
        """Uses semantic search to find relevant documents."""
        with patch("app.services.qa.check_ollama_available", new=AsyncMock(return_value=True)):
            with patch(
                "app.services.qa.semantic_search", new=AsyncMock(return_value=[("doc-001", 0.9)])
            ) as mock_search:
                with patch(
                    "app.services.qa.answer_with_ollama", new=AsyncMock(return_value="Answer")
                ):
                    result = await answer_question("Tell me about the electric bill")

        mock_search.assert_called_once()
        assert "doc-001" in result["sources"]

    @pytest.mark.asyncio
    async def test_uses_provided_doc_ids(self, seeded_db):
        """Uses provided document IDs instead of searching."""
        with patch("app.services.qa.check_ollama_available", new=AsyncMock(return_value=True)):
            with patch("app.services.qa.semantic_search", new=AsyncMock()) as mock_search:
                with patch(
                    "app.services.qa.answer_with_ollama", new=AsyncMock(return_value="Answer")
                ):
                    result = await answer_question("Question", doc_ids=["doc-002"])

        mock_search.assert_not_called()
        assert "doc-002" in result["sources"]

    @pytest.mark.asyncio
    async def test_handles_no_relevant_documents(self, seeded_db):
        """Returns appropriate message when no documents found."""
        with patch("app.services.qa.check_ollama_available", new=AsyncMock(return_value=True)):
            with patch("app.services.qa.semantic_search", new=AsyncMock(return_value=[])):
                result = await answer_question("Unrelated question")

        assert "No relevant documents found" in result["answer"]
        assert result["sources"] == []

    @pytest.mark.asyncio
    async def test_respects_max_sources(self, seeded_db):
        """Respects max_sources parameter by passing limit to semantic_search."""
        mock_search = AsyncMock(
            return_value=[
                ("doc-001", 0.9),
                ("doc-002", 0.8),
            ]
        )

        with patch("app.services.qa.check_ollama_available", new=AsyncMock(return_value=True)):
            with patch("app.services.qa.semantic_search", mock_search):
                with patch(
                    "app.services.qa.answer_with_ollama", new=AsyncMock(return_value="Answer")
                ):
                    result = await answer_question("Question", max_sources=2)

        # Verify semantic_search was called with correct limit
        mock_search.assert_called_once_with("Question", limit=2)
        assert len(result["sources"]) == 2


class TestGetDocumentQa:
    """Tests for get_document_qa function."""

    @pytest.mark.asyncio
    async def test_answers_about_specific_document(self, seeded_db):
        """Answers question about a specific document."""
        with patch("app.services.qa.check_ollama_available", new=AsyncMock(return_value=True)):
            with patch(
                "app.services.qa.answer_with_ollama", new=AsyncMock(return_value="The answer")
            ):
                result = await get_document_qa("doc-001", "What is the amount?")

        assert result["answer"] == "The answer"
        assert "doc-001" in result["sources"]
