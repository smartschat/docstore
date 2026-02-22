"""Unit tests for extraction service."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from app.services.extraction import (
    VISION_EXTRACT_PROMPT,
    call_ollama,
    check_ollama_available,
    extract_all_with_vision,
    extract_document_data,
    extract_metadata,
    generate_summary,
    generate_title,
    get_empty_extraction,
    parse_json_response,
    strip_thinking,
)


class TestParseJsonResponse:
    """Tests for parse_json_response function."""

    def test_parses_plain_json(self):
        """Valid JSON is parsed correctly."""
        response = '{"title": "Invoice", "category": "utilities"}'
        result = parse_json_response(response)
        assert result == {"title": "Invoice", "category": "utilities"}

    def test_parses_json_in_markdown_block(self):
        """JSON in markdown code block is parsed correctly."""
        response = '```json\n{"title": "Invoice"}\n```'
        result = parse_json_response(response)
        assert result == {"title": "Invoice"}

    def test_parses_json_with_code_block_no_lang(self):
        """JSON in code block without language specifier."""
        response = '```\n{"title": "Invoice"}\n```'
        result = parse_json_response(response)
        assert result == {"title": "Invoice"}

    def test_handles_whitespace(self):
        """Leading/trailing whitespace is handled."""
        response = '  \n{"title": "Test"}\n  '
        result = parse_json_response(response)
        assert result == {"title": "Test"}

    def test_raises_on_malformed_json(self):
        """Malformed JSON raises JSONDecodeError."""
        response = '{"title": broken}'
        with pytest.raises(json.JSONDecodeError):
            parse_json_response(response)

    def test_parses_nested_json(self):
        """Nested JSON structures are parsed correctly."""
        response = '{"data": {"title": "Test", "items": [1, 2, 3]}}'
        result = parse_json_response(response)
        assert result["data"]["title"] == "Test"
        assert result["data"]["items"] == [1, 2, 3]


class TestStripThinking:
    """Tests for strip_thinking function."""

    def test_removes_think_tags(self):
        """Removes <think>...</think> blocks."""
        text = "<think>internal reasoning</think>Final answer"
        result = strip_thinking(text)
        assert result == "Final answer"

    def test_handles_no_tags(self):
        """Text without tags is returned unchanged."""
        text = "Just a normal response"
        result = strip_thinking(text)
        assert result == "Just a normal response"

    def test_removes_multiline_thinking(self):
        """Multi-line thinking blocks are removed."""
        text = "<think>\nStep 1\nStep 2\nStep 3\n</think>Result"
        result = strip_thinking(text)
        assert result == "Result"

    def test_removes_multiple_think_blocks(self):
        """Multiple thinking blocks are all removed."""
        text = "<think>first</think>Middle<think>second</think>End"
        result = strip_thinking(text)
        assert result == "MiddleEnd"

    def test_handles_think_at_end(self):
        """Thinking block at end is removed."""
        text = "Answer<think>reasoning</think>"
        result = strip_thinking(text)
        assert result == "Answer"

    def test_strips_whitespace(self):
        """Result is stripped of whitespace."""
        text = "  <think>thinking</think>  Result  "
        result = strip_thinking(text)
        assert result == "Result"


class TestCheckOllamaAvailable:
    """Tests for check_ollama_available function."""

    @pytest.mark.asyncio
    async def test_returns_true_when_available(self):
        """Returns True when Ollama responds with 200."""
        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch("app.services.extraction.httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )
            result = await check_ollama_available()
            assert result is True

    @pytest.mark.asyncio
    async def test_returns_false_on_connection_error(self):
        """Returns False when connection fails."""
        with patch("app.services.extraction.httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                side_effect=httpx.ConnectError("Connection refused")
            )
            result = await check_ollama_available()
            assert result is False

    @pytest.mark.asyncio
    async def test_returns_false_on_timeout(self):
        """Returns False when request times out."""
        with patch("app.services.extraction.httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                side_effect=httpx.TimeoutException("Timeout")
            )
            result = await check_ollama_available()
            assert result is False

    @pytest.mark.asyncio
    async def test_returns_false_on_non_200(self):
        """Returns False when Ollama responds with non-200."""
        mock_response = MagicMock()
        mock_response.status_code = 500

        with patch("app.services.extraction.httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )
            result = await check_ollama_available()
            assert result is False


class TestCallOllama:
    """Tests for call_ollama function."""

    @pytest.mark.asyncio
    async def test_successful_call(self):
        """Successful API call returns response text."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"response": "Generated text"}
        mock_response.raise_for_status = MagicMock()

        with patch("app.services.extraction.httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=mock_response
            )
            result = await call_ollama("Test prompt")
            assert result == "Generated text"

    @pytest.mark.asyncio
    async def test_strips_thinking_from_response(self):
        """Thinking blocks are stripped from response."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"response": "<think>reasoning</think>Final answer"}
        mock_response.raise_for_status = MagicMock()

        with patch("app.services.extraction.httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=mock_response
            )
            result = await call_ollama("Test prompt")
            assert result == "Final answer"

    @pytest.mark.asyncio
    async def test_raises_on_http_error(self):
        """HTTP errors are raised."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Server Error", request=MagicMock(), response=mock_response
        )

        with patch("app.services.extraction.httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=mock_response
            )
            with pytest.raises(httpx.HTTPStatusError):
                await call_ollama("Test prompt")


class TestExtractMetadata:
    """Tests for extract_metadata function."""

    @pytest.mark.asyncio
    async def test_extracts_valid_metadata(self):
        """Valid metadata is extracted correctly."""
        mock_json = json.dumps(
            {"counterparty": "Test Company", "category": "invoice", "document_date": "2024-01-15"}
        )

        with patch("app.services.extraction.call_ollama", new=AsyncMock(return_value=mock_json)):
            result = await extract_metadata("Some document text")
            assert result["counterparty"] == "Test Company"
            assert result["category"] == "invoice"
            assert result["document_date"] == "2024-01-15"

    @pytest.mark.asyncio
    async def test_handles_invalid_date_format(self):
        """Invalid date format results in None."""
        mock_json = json.dumps({"counterparty": "Test Company", "document_date": "invalid-date"})

        with patch("app.services.extraction.call_ollama", new=AsyncMock(return_value=mock_json)):
            result = await extract_metadata("Some document text")
            assert result["counterparty"] == "Test Company"
            assert result["document_date"] is None

    @pytest.mark.asyncio
    async def test_handles_malformed_json(self):
        """Malformed JSON returns empty dict."""
        with patch("app.services.extraction.call_ollama", new=AsyncMock(return_value="not json")):
            result = await extract_metadata("Some document text")
            assert result == {}

    @pytest.mark.asyncio
    async def test_truncates_long_text(self):
        """Long text is truncated before sending to Ollama."""
        long_text = "x" * 10000

        with patch("app.services.extraction.call_ollama", new=AsyncMock(return_value="{}")) as mock:
            await extract_metadata(long_text)
            # Check that the prompt was called with truncated text
            call_args = mock.call_args[0][0]
            assert len(call_args) < len(long_text) + 1000  # Some buffer for prompt


class TestGenerateTitle:
    """Tests for generate_title function."""

    @pytest.mark.asyncio
    async def test_generates_valid_title(self):
        """Valid title is generated."""
        with patch(
            "app.services.extraction.call_ollama", new=AsyncMock(return_value="Electric Bill")
        ):
            result = await generate_title("Summary of electric bill document")
            assert result == "Electric Bill"

    @pytest.mark.asyncio
    async def test_rejects_too_short_title(self):
        """Title shorter than 3 chars returns None."""
        with patch("app.services.extraction.call_ollama", new=AsyncMock(return_value="AB")):
            result = await generate_title("Summary")
            assert result is None

    @pytest.mark.asyncio
    async def test_rejects_too_long_title(self):
        """Title longer than 100 chars returns None."""
        long_title = "x" * 101
        with patch("app.services.extraction.call_ollama", new=AsyncMock(return_value=long_title)):
            result = await generate_title("Summary")
            assert result is None

    @pytest.mark.asyncio
    async def test_strips_quotes_from_title(self):
        """Quotes are stripped from generated title."""
        with patch(
            "app.services.extraction.call_ollama", new=AsyncMock(return_value='"Electric Bill"')
        ):
            result = await generate_title("Summary")
            assert result == "Electric Bill"

    @pytest.mark.asyncio
    async def test_takes_first_line_only(self):
        """Multi-line response uses first line only."""
        with patch(
            "app.services.extraction.call_ollama", new=AsyncMock(return_value="Title\nExtra line")
        ):
            result = await generate_title("Summary")
            assert result == "Title"

    @pytest.mark.asyncio
    async def test_handles_exception(self):
        """Exception returns None."""
        with patch(
            "app.services.extraction.call_ollama", new=AsyncMock(side_effect=Exception("Error"))
        ):
            result = await generate_title("Summary")
            assert result is None


class TestGenerateSummary:
    """Tests for generate_summary function."""

    @pytest.mark.asyncio
    async def test_generates_summary(self):
        """Summary is generated successfully."""
        with patch(
            "app.services.extraction.call_ollama", new=AsyncMock(return_value="This is a summary.")
        ):
            result = await generate_summary("Document text here")
            assert result == "This is a summary."

    @pytest.mark.asyncio
    async def test_handles_empty_response(self):
        """Empty response returns None."""
        with patch("app.services.extraction.call_ollama", new=AsyncMock(return_value="")):
            result = await generate_summary("Document text")
            assert result is None

    @pytest.mark.asyncio
    async def test_handles_exception(self):
        """Exception returns None."""
        with patch(
            "app.services.extraction.call_ollama", new=AsyncMock(side_effect=Exception("Error"))
        ):
            result = await generate_summary("Document text")
            assert result is None


class TestGetEmptyExtraction:
    """Tests for get_empty_extraction function."""

    def test_returns_dict_with_all_keys(self):
        """Returns dict with all expected keys set to None."""
        result = get_empty_extraction()
        expected_keys = [
            "title",
            "counterparty",
            "affected_person",
            "category",
            "reference",
            "document_date",
            "summary",
        ]
        for key in expected_keys:
            assert key in result
            assert result[key] is None

    def test_returns_new_dict_each_time(self):
        """Returns a new dict instance each time."""
        result1 = get_empty_extraction()
        result2 = get_empty_extraction()
        assert result1 is not result2


class TestExtractDocumentData:
    """Tests for extract_document_data function."""

    @pytest.mark.asyncio
    async def test_returns_empty_when_ollama_unavailable(self):
        """Returns empty extraction when Ollama is not available."""
        with patch(
            "app.services.extraction.check_ollama_available", new=AsyncMock(return_value=False)
        ):
            result = await extract_document_data("Document text")
            assert result["title"] is None
            assert result["counterparty"] is None

    @pytest.mark.asyncio
    async def test_full_extraction_pipeline(self):
        """Full extraction pipeline works correctly."""
        mock_metadata = json.dumps(
            {"counterparty": "Test Corp", "category": "invoice", "document_date": "2024-01-15"}
        )

        async def mock_call_ollama(prompt):
            if "Extract these fields" in prompt:
                return mock_metadata
            elif "Create a short" in prompt:  # Title prompt starts with this
                return "Test Invoice"
            elif "Write a 3-4 sentence summary" in prompt:  # Summary prompt
                return "This is a test invoice."
            return ""

        with patch(
            "app.services.extraction.check_ollama_available", new=AsyncMock(return_value=True)
        ):
            with patch("app.services.extraction.call_ollama", side_effect=mock_call_ollama):
                result = await extract_document_data("Invoice text here")

                assert result["counterparty"] == "Test Corp"
                assert result["category"] == "invoice"
                assert result["document_date"] == "2024-01-15"
                assert result["summary"] == "This is a test invoice."
                assert result["title"] == "Test Invoice"


class TestVisionPrompt:
    """Tests for vision prompt configuration."""

    def test_vision_prompt_requests_extraction(self):
        """Vision prompt includes instruction to extract from image."""
        assert "Look at this document image" in VISION_EXTRACT_PROMPT

    def test_vision_prompt_requests_json(self):
        """Vision prompt requests JSON output."""
        assert "Return JSON only" in VISION_EXTRACT_PROMPT
        assert "JSON:" in VISION_EXTRACT_PROMPT

    def test_vision_prompt_includes_all_fields(self):
        """Vision prompt includes all required fields."""
        required_fields = [
            "counterparty",
            "affected_persons",
            "category",
            "reference",
            "document_date",
            "summary",
            "title",
        ]
        for field in required_fields:
            assert field in VISION_EXTRACT_PROMPT


class TestCallOllamaWithImages:
    """Tests for call_ollama with vision/images."""

    @pytest.mark.asyncio
    async def test_uses_chat_endpoint_for_images(self):
        """Uses /api/chat endpoint when images are provided."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"message": {"content": "Response text"}}
        mock_response.raise_for_status = MagicMock()

        with patch("app.services.extraction.httpx.AsyncClient") as mock_client:
            mock_post = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__.return_value.post = mock_post

            result = await call_ollama("Test prompt", images=["base64imagedata"])

            # Verify chat endpoint was called
            call_args = mock_post.call_args
            assert "/api/chat" in call_args[0][0]
            assert result == "Response text"

    @pytest.mark.asyncio
    async def test_uses_generate_endpoint_without_images(self):
        """Uses /api/generate endpoint when no images provided."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"response": "Response text"}
        mock_response.raise_for_status = MagicMock()

        with patch("app.services.extraction.httpx.AsyncClient") as mock_client:
            mock_post = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__.return_value.post = mock_post

            result = await call_ollama("Test prompt")

            # Verify generate endpoint was called
            call_args = mock_post.call_args
            assert "/api/generate" in call_args[0][0]
            assert result == "Response text"

    @pytest.mark.asyncio
    async def test_images_included_in_chat_payload(self):
        """Images are included in the chat message payload."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"message": {"content": "Response"}}
        mock_response.raise_for_status = MagicMock()

        test_images = ["base64image1", "base64image2"]

        with patch("app.services.extraction.httpx.AsyncClient") as mock_client:
            mock_post = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__.return_value.post = mock_post

            await call_ollama("Test prompt", images=test_images)

            # Check payload includes images
            call_kwargs = mock_post.call_args[1]
            payload = call_kwargs["json"]
            assert "messages" in payload
            assert payload["messages"][0]["images"] == test_images


class TestExtractAllWithVision:
    """Tests for extract_all_with_vision function."""

    @pytest.mark.asyncio
    async def test_extracts_all_fields(self):
        """Extracts all fields from vision response."""
        mock_json = json.dumps(
            {
                "counterparty": "Test Company",
                "affected_persons": ["John Doe", "Jane Doe"],
                "category": "legal",
                "reference": "REF-123",
                "document_date": "2024-01-15",
                "summary": "Test summary",
                "title": "Test Document",
            }
        )

        with patch("app.services.extraction.call_ollama", new=AsyncMock(return_value=mock_json)):
            result = await extract_all_with_vision(["base64image"])

            assert result["counterparty"] == "Test Company"
            assert result["affected_persons"] == ["John Doe", "Jane Doe"]
            assert result["category"] == "legal"
            assert result["reference"] == "REF-123"
            assert result["document_date"] == "2024-01-15"
            assert result["summary"] == "Test summary"
            assert result["title"] == "Test Document"

    @pytest.mark.asyncio
    async def test_validates_date_format(self):
        """Invalid date format results in None."""
        mock_json = json.dumps(
            {
                "counterparty": "Test",
                "document_date": "invalid-date",
            }
        )

        with patch("app.services.extraction.call_ollama", new=AsyncMock(return_value=mock_json)):
            result = await extract_all_with_vision(["base64image"])
            assert result["document_date"] is None

    @pytest.mark.asyncio
    async def test_validates_title_length(self):
        """Title too short or too long results in None."""
        # Too short
        mock_json = json.dumps({"title": "AB"})
        with patch("app.services.extraction.call_ollama", new=AsyncMock(return_value=mock_json)):
            result = await extract_all_with_vision(["base64image"])
            assert result["title"] is None

        # Too long
        mock_json = json.dumps({"title": "x" * 101})
        with patch("app.services.extraction.call_ollama", new=AsyncMock(return_value=mock_json)):
            result = await extract_all_with_vision(["base64image"])
            assert result["title"] is None

    @pytest.mark.asyncio
    async def test_handles_malformed_json(self):
        """Malformed JSON returns empty dict."""
        with patch("app.services.extraction.call_ollama", new=AsyncMock(return_value="not json")):
            result = await extract_all_with_vision(["base64image"])
            assert result == {}

    @pytest.mark.asyncio
    async def test_handles_exception(self):
        """Exception returns empty dict."""
        with patch(
            "app.services.extraction.call_ollama",
            new=AsyncMock(side_effect=Exception("Error")),
        ):
            result = await extract_all_with_vision(["base64image"])
            assert result == {}


class TestExtractDocumentDataVisionMode:
    """Tests for extract_document_data in vision mode."""

    @pytest.mark.asyncio
    async def test_uses_vision_when_enabled_and_images_available(self):
        """Uses vision extraction when enabled and PDF exists."""
        mock_json = json.dumps(
            {
                "counterparty": "Vision Company",
                "affected_persons": ["Test Person"],
                "category": "banking",
                "document_date": "2024-01-15",
                "summary": "Vision summary",
                "title": "Vision Title",
            }
        )

        mock_settings = MagicMock()
        mock_settings.ollama_use_vision = True

        with patch("app.services.extraction.settings", mock_settings):
            with patch(
                "app.services.extraction.check_ollama_available",
                new=AsyncMock(return_value=True),
            ):
                with patch(
                    "app.services.extraction.pdf_to_base64_images",
                    new=AsyncMock(return_value=["base64image"]),
                ):
                    with patch(
                        "app.services.extraction.call_ollama",
                        new=AsyncMock(return_value=mock_json),
                    ):
                        # Create a mock path that "exists"
                        mock_path = MagicMock()
                        mock_path.exists.return_value = True

                        result = await extract_document_data("", pdf_path=mock_path)

                        assert result["counterparty"] == "Vision Company"
                        assert result["title"] == "Vision Title"

    @pytest.mark.asyncio
    async def test_falls_back_to_text_when_images_fail(self):
        """Falls back to text extraction when image conversion fails."""
        mock_metadata = json.dumps({"counterparty": "Text Company", "category": "invoice"})

        mock_settings = MagicMock()
        mock_settings.ollama_use_vision = True

        async def mock_call_ollama(prompt, images=None):
            if images:
                raise Exception("Should not be called with images")
            if "Extract these fields" in prompt:
                return mock_metadata
            elif "Create a short" in prompt:
                return "Text Title"
            elif "Write a 1-2 sentence summary" in prompt:
                return "Text summary"
            return ""

        with patch("app.services.extraction.settings", mock_settings):
            with patch(
                "app.services.extraction.check_ollama_available",
                new=AsyncMock(return_value=True),
            ):
                with patch(
                    "app.services.extraction.pdf_to_base64_images",
                    new=AsyncMock(return_value=[]),  # Empty list = conversion failed
                ):
                    with patch(
                        "app.services.extraction.call_ollama",
                        side_effect=mock_call_ollama,
                    ):
                        mock_path = MagicMock()
                        mock_path.exists.return_value = True

                        result = await extract_document_data("Some text", pdf_path=mock_path)

                        # Should use text extraction fallback
                        assert result["counterparty"] == "Text Company"
