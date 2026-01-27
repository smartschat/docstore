"""Unit tests for OCR service."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.services.ocr import (
    OCRResult,
    extract_text_from_file,
    extract_text_with_pdftotext,
    get_pdf_page_count,
    process_image,
    process_pdf,
)


class TestOCRResult:
    """Tests for OCRResult class."""

    def test_default_values(self):
        """Default values are set correctly."""
        result = OCRResult(text="test", page_count=1)

        assert result.text == "test"
        assert result.page_count == 1
        assert result.output_path is None
        assert result.success is True
        assert result.error is None

    def test_error_result(self):
        """Error result is created correctly."""
        result = OCRResult(
            text="",
            page_count=0,
            success=False,
            error="OCR failed",
        )

        assert result.success is False
        assert result.error == "OCR failed"


class TestProcessPdf:
    """Tests for process_pdf function."""

    @pytest.mark.asyncio
    async def test_successful_ocr(self, sample_pdf, tmp_path):
        """Successful OCR returns text and page count."""
        # Create a fake sidecar file
        sidecar_path = tmp_path / "sidecar.txt"
        sidecar_path.write_text("Extracted OCR text")

        # Mock the subprocess
        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.communicate = AsyncMock(return_value=(b"", b""))

        # Mock tempfile to return our known sidecar path
        mock_tempfile = MagicMock()
        mock_tempfile.__enter__ = MagicMock(return_value=mock_tempfile)
        mock_tempfile.__exit__ = MagicMock()
        mock_tempfile.name = str(sidecar_path)

        with patch("asyncio.create_subprocess_exec", new=AsyncMock(return_value=mock_process)):
            with patch("app.services.ocr.get_pdf_page_count", new=AsyncMock(return_value=1)):
                with patch("tempfile.NamedTemporaryFile", return_value=mock_tempfile):
                    result = await process_pdf(sample_pdf)

        assert result.success is True
        assert result.page_count == 1

    @pytest.mark.asyncio
    async def test_ocr_returns_code_6(self, sample_pdf, tmp_path):
        """Return code 6 (file already has text) is treated as success."""
        # Create a fake sidecar file with skip marker
        sidecar_path = tmp_path / "sidecar.txt"
        sidecar_path.write_text("[OCR skipped on page(s) 1]")

        mock_process = MagicMock()
        mock_process.returncode = 6
        mock_process.communicate = AsyncMock(return_value=(b"", b""))

        mock_tempfile = MagicMock()
        mock_tempfile.__enter__ = MagicMock(return_value=mock_tempfile)
        mock_tempfile.__exit__ = MagicMock()
        mock_tempfile.name = str(sidecar_path)

        with patch("asyncio.create_subprocess_exec", new=AsyncMock(return_value=mock_process)):
            with patch("app.services.ocr.get_pdf_page_count", new=AsyncMock(return_value=1)):
                with patch("tempfile.NamedTemporaryFile", return_value=mock_tempfile):
                    with patch(
                        "app.services.ocr.extract_text_with_pdftotext",
                        new=AsyncMock(return_value="existing text"),
                    ):
                        result = await process_pdf(sample_pdf)

        assert result.success is True

    @pytest.mark.asyncio
    async def test_ocr_failure(self, sample_pdf):
        """OCR failure returns error result."""
        mock_process = MagicMock()
        mock_process.returncode = 1
        mock_process.communicate = AsyncMock(return_value=(b"", b"OCR error message"))

        with patch("asyncio.create_subprocess_exec", new=AsyncMock(return_value=mock_process)):
            result = await process_pdf(sample_pdf)

        assert result.success is False
        assert "OCR failed" in result.error

    @pytest.mark.asyncio
    async def test_ocrmypdf_not_installed(self, sample_pdf):
        """Missing ocrmypdf returns clear error."""
        with patch("asyncio.create_subprocess_exec", new=AsyncMock(side_effect=FileNotFoundError)):
            result = await process_pdf(sample_pdf)

        assert result.success is False
        assert "ocrmypdf not installed" in result.error

    @pytest.mark.asyncio
    async def test_uses_pdftotext_fallback(self, sample_pdf):
        """Falls back to pdftotext when sidecar is empty."""
        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.communicate = AsyncMock(return_value=(b"", b""))

        # Mock sidecar file with only skip markers
        sidecar_content = "[OCR skipped on page(s) 1-3]"

        with patch("asyncio.create_subprocess_exec", new=AsyncMock(return_value=mock_process)):
            with patch(
                "builtins.open",
                MagicMock(
                    return_value=MagicMock(
                        __enter__=MagicMock(
                            return_value=MagicMock(read=MagicMock(return_value=sidecar_content))
                        ),
                        __exit__=MagicMock(),
                    )
                ),
            ):
                with patch("pathlib.Path.unlink"):
                    with patch(
                        "app.services.ocr.extract_text_with_pdftotext",
                        new=AsyncMock(return_value="fallback text"),
                    ) as mock_fallback:
                        with patch(
                            "app.services.ocr.get_pdf_page_count", new=AsyncMock(return_value=3)
                        ):
                            await process_pdf(sample_pdf)

        mock_fallback.assert_called_once()


class TestProcessImage:
    """Tests for process_image function."""

    @pytest.mark.asyncio
    async def test_converts_and_processes(self, sample_image):
        """Image is converted to PDF and processed."""
        mock_ocr_result = OCRResult(text="Image text", page_count=1, success=True)

        with patch("app.services.ocr.process_pdf", new=AsyncMock(return_value=mock_ocr_result)):
            with patch("pathlib.Path.unlink"):
                result = await process_image(sample_image)

        assert result.success is True
        assert result.text == "Image text"

    @pytest.mark.asyncio
    async def test_handles_rgba_images(self, tmp_path):
        """RGBA images are converted to RGB before processing."""
        from PIL import Image

        # Create RGBA image
        rgba_img = Image.new("RGBA", (100, 100), color=(255, 255, 255, 128))
        rgba_path = tmp_path / "rgba.png"
        rgba_img.save(rgba_path)

        mock_ocr_result = OCRResult(text="", page_count=1, success=True)

        with patch("app.services.ocr.process_pdf", new=AsyncMock(return_value=mock_ocr_result)):
            with patch("pathlib.Path.unlink"):
                result = await process_image(rgba_path)

        assert result.success is True

    @pytest.mark.asyncio
    async def test_handles_conversion_error(self, tmp_path):
        """Conversion errors are handled gracefully."""
        # Create invalid image file
        bad_img = tmp_path / "bad.jpg"
        bad_img.write_bytes(b"not an image")

        result = await process_image(bad_img)

        assert result.success is False
        assert result.error is not None


class TestExtractTextWithPdftotext:
    """Tests for extract_text_with_pdftotext function."""

    @pytest.mark.asyncio
    async def test_successful_extraction(self, sample_pdf):
        """Successfully extracts text from PDF."""
        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.communicate = AsyncMock(return_value=(b"Extracted PDF text", b""))

        with patch("asyncio.create_subprocess_exec", new=AsyncMock(return_value=mock_process)):
            result = await extract_text_with_pdftotext(sample_pdf)

        assert result == "Extracted PDF text"

    @pytest.mark.asyncio
    async def test_handles_failure(self, sample_pdf):
        """Returns empty string on failure."""
        mock_process = MagicMock()
        mock_process.returncode = 1
        mock_process.communicate = AsyncMock(return_value=(b"", b"error"))

        with patch("asyncio.create_subprocess_exec", new=AsyncMock(return_value=mock_process)):
            result = await extract_text_with_pdftotext(sample_pdf)

        assert result == ""

    @pytest.mark.asyncio
    async def test_handles_tool_not_found(self, sample_pdf):
        """Returns empty string when pdftotext not installed."""
        with patch("asyncio.create_subprocess_exec", new=AsyncMock(side_effect=FileNotFoundError)):
            result = await extract_text_with_pdftotext(sample_pdf)

        assert result == ""


class TestGetPdfPageCount:
    """Tests for get_pdf_page_count function."""

    @pytest.mark.asyncio
    async def test_uses_pdfinfo(self, sample_pdf):
        """Uses pdfinfo to get page count."""
        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.communicate = AsyncMock(
            return_value=(b"Title: Test\nPages: 5\nSize: 100x100", b"")
        )

        with patch("asyncio.create_subprocess_exec", new=AsyncMock(return_value=mock_process)):
            result = await get_pdf_page_count(sample_pdf)

        assert result == 5

    @pytest.mark.asyncio
    async def test_fallback_to_pikepdf(self, sample_pdf):
        """Falls back to pikepdf when pdfinfo fails."""
        mock_process = MagicMock()
        mock_process.returncode = 1
        mock_process.communicate = AsyncMock(return_value=(b"", b"error"))

        mock_pdf = MagicMock()
        mock_pdf.pages = [1, 2, 3]
        mock_pdf.__enter__ = MagicMock(return_value=mock_pdf)
        mock_pdf.__exit__ = MagicMock()

        with patch("asyncio.create_subprocess_exec", new=AsyncMock(return_value=mock_process)):
            with patch("pikepdf.open", return_value=mock_pdf):
                result = await get_pdf_page_count(sample_pdf)

        assert result == 3

    @pytest.mark.asyncio
    async def test_returns_zero_on_failure(self, sample_pdf):
        """Returns 0 when all methods fail."""
        mock_process = MagicMock()
        mock_process.returncode = 1
        mock_process.communicate = AsyncMock(return_value=(b"", b"error"))

        with patch("asyncio.create_subprocess_exec", new=AsyncMock(return_value=mock_process)):
            with patch("pikepdf.open", side_effect=Exception("Cannot open")):
                result = await get_pdf_page_count(sample_pdf)

        assert result == 0


class TestExtractTextFromFile:
    """Tests for extract_text_from_file function."""

    @pytest.mark.asyncio
    async def test_routes_pdf_to_process_pdf(self, sample_pdf):
        """PDF files are routed to process_pdf."""
        mock_result = OCRResult(text="PDF text", page_count=1, success=True)

        with patch(
            "app.services.ocr.process_pdf", new=AsyncMock(return_value=mock_result)
        ) as mock_process:
            result = await extract_text_from_file(sample_pdf, "application/pdf")

        mock_process.assert_called_once_with(sample_pdf)
        assert result.text == "PDF text"

    @pytest.mark.asyncio
    async def test_routes_images_to_process_image(self, sample_image):
        """Image files are routed to process_image."""
        mock_result = OCRResult(text="Image text", page_count=1, success=True)

        with patch(
            "app.services.ocr.process_image", new=AsyncMock(return_value=mock_result)
        ) as mock_process:
            result = await extract_text_from_file(sample_image, "image/jpeg")

        mock_process.assert_called_once_with(sample_image)
        assert result.text == "Image text"

    @pytest.mark.asyncio
    async def test_rejects_unsupported_types(self, tmp_path):
        """Unsupported file types return error."""
        txt_file = tmp_path / "test.txt"
        txt_file.write_text("text")

        result = await extract_text_from_file(txt_file, "text/plain")

        assert result.success is False
        assert "Unsupported file type" in result.error
