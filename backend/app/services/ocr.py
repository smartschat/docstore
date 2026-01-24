"""OCR processing using ocrmypdf."""

import asyncio
import tempfile
from pathlib import Path
from typing import Optional

from app.config import get_settings

settings = get_settings()


class OCRResult:
    """Result of OCR processing."""

    def __init__(
        self,
        text: str,
        page_count: int,
        output_path: Optional[Path] = None,
        success: bool = True,
        error: Optional[str] = None,
    ):
        self.text = text
        self.page_count = page_count
        self.output_path = output_path
        self.success = success
        self.error = error


async def process_pdf(
    input_path: Path,
    output_path: Optional[Path] = None,
) -> OCRResult:
    """
    Process a PDF file with OCR.

    Args:
        input_path: Path to the input PDF
        output_path: Optional path for the OCR'd PDF output

    Returns:
        OCRResult with extracted text and metadata
    """
    if output_path is None:
        output_path = input_path

    try:
        # Build ocrmypdf command
        cmd = [
            "ocrmypdf",
            "--language",
            settings.ocr_language,
            "--jobs",
            "2",  # Limit CPU usage for Pi
            "--skip-text",  # Don't re-OCR pages that already have text
            "--output-type",
            "pdf",
        ]

        if settings.ocr_deskew:
            cmd.append("--deskew")

        if settings.ocr_rotate_pages:
            cmd.append("--rotate-pages")

        # Add sidecar for text extraction
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as sidecar:
            sidecar_path = sidecar.name

        cmd.extend(["--sidecar", sidecar_path])
        cmd.extend([str(input_path), str(output_path)])

        # Run ocrmypdf
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout, stderr = await process.communicate()

        if process.returncode not in (0, 6):  # 6 = "file already has text"
            return OCRResult(
                text="",
                page_count=0,
                success=False,
                error=f"OCR failed: {stderr.decode()}",
            )

        # Read extracted text
        text = ""
        try:
            with open(sidecar_path, "r", encoding="utf-8") as f:
                text = f.read()
        finally:
            Path(sidecar_path).unlink(missing_ok=True)

        # If sidecar is empty or only contains skip markers, try extracting existing text
        # Skip markers look like: "[OCR skipped on page(s) 1-3]" or "[OCR skipped on page(s) 1]"
        import re

        text_without_markers = re.sub(r"\[OCR skipped on page\(s\)[^\]]*\]", "", text).strip()
        if not text_without_markers:
            text = await extract_text_with_pdftotext(output_path)

        # Get page count using pdfinfo or similar
        page_count = await get_pdf_page_count(output_path)

        return OCRResult(
            text=text,
            page_count=page_count,
            output_path=output_path,
            success=True,
        )

    except FileNotFoundError:
        return OCRResult(
            text="",
            page_count=0,
            success=False,
            error="ocrmypdf not installed. Install with: apt install ocrmypdf",
        )
    except Exception as e:
        return OCRResult(
            text="",
            page_count=0,
            success=False,
            error=str(e),
        )


async def process_image(input_path: Path) -> OCRResult:
    """
    Process an image file with OCR.

    Converts the image to PDF first, then runs OCR.

    Args:
        input_path: Path to the input image

    Returns:
        OCRResult with extracted text
    """
    try:
        from PIL import Image

        # Convert image to PDF
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp_pdf:
            tmp_pdf_path = Path(tmp_pdf.name)

        img = Image.open(input_path)
        if img.mode == "RGBA":
            img = img.convert("RGB")
        img.save(tmp_pdf_path, "PDF", resolution=300)

        # Process the PDF
        result = await process_pdf(tmp_pdf_path)

        # Clean up temp file
        tmp_pdf_path.unlink(missing_ok=True)

        return result

    except Exception as e:
        return OCRResult(
            text="",
            page_count=0,
            success=False,
            error=str(e),
        )


async def extract_text_with_pdftotext(pdf_path: Path) -> str:
    """Extract text from a PDF using pdftotext (for PDFs with embedded text)."""
    try:
        process = await asyncio.create_subprocess_exec(
            "pdftotext",
            "-layout",
            str(pdf_path),
            "-",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await process.communicate()
        if process.returncode == 0:
            return stdout.decode("utf-8", errors="replace")
    except Exception:
        pass
    return ""


async def get_pdf_page_count(pdf_path: Path) -> int:
    """Get the number of pages in a PDF."""
    try:
        # Try using pdfinfo (from poppler-utils)
        process = await asyncio.create_subprocess_exec(
            "pdfinfo",
            str(pdf_path),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await process.communicate()

        for line in stdout.decode().split("\n"):
            if line.startswith("Pages:"):
                return int(line.split(":")[1].strip())
    except Exception:
        pass

    # Fallback: try to count using PyPDF or pikepdf
    try:
        import pikepdf

        with pikepdf.open(pdf_path) as pdf:
            return len(pdf.pages)
    except Exception:
        pass

    return 0


async def extract_text_from_file(file_path: Path, mime_type: str) -> OCRResult:
    """
    Extract text from a file based on its MIME type.

    Args:
        file_path: Path to the file
        mime_type: MIME type of the file

    Returns:
        OCRResult with extracted text
    """
    if mime_type == "application/pdf":
        return await process_pdf(file_path)
    elif mime_type.startswith("image/"):
        return await process_image(file_path)
    else:
        return OCRResult(
            text="",
            page_count=0,
            success=False,
            error=f"Unsupported file type: {mime_type}",
        )
