"""LLM-powered structured data extraction using Ollama."""

import base64
import json
from datetime import date
from pathlib import Path
from typing import Any

import httpx

from app.config import get_settings

settings = get_settings()


async def pdf_to_base64_images(pdf_path: Path, max_pages: int = 1) -> list[str]:
    """Convert PDF pages to base64-encoded images for vision models.

    Args:
        pdf_path: Path to the PDF file
        max_pages: Maximum number of pages to convert (default: 3)

    Returns:
        List of base64-encoded PNG images
    """
    import asyncio
    import io

    try:
        # pdf2image requires poppler
        from pdf2image import convert_from_path

        # Run in thread pool since pdf2image is blocking
        loop = asyncio.get_event_loop()
        images = await loop.run_in_executor(
            None,
            lambda: convert_from_path(
                pdf_path,
                first_page=1,
                last_page=max_pages,
                dpi=150,  # Balance between quality and size
            ),
        )

        base64_images = []
        for img in images:
            buffer = io.BytesIO()
            img.save(buffer, format="PNG")
            b64 = base64.b64encode(buffer.getvalue()).decode("utf-8")
            base64_images.append(b64)

        return base64_images
    except Exception as e:
        print(f"Failed to convert PDF to images: {e}")
        return []


# Vision prompt - extracts everything in one call
VISION_EXTRACT_PROMPT = """Don't think too much. Use at most two paragraphs of thinking.

Look at this document image and extract the following. Return JSON only.

{
  "counterparty": "Company or organization that issued this document",
  "affected_persons": ["List of full names of people this document is about"],
  "category": "One of: salary, tax, insurance, medical, banking, utilities, invoice, receipt, contract, legal, correspondence, other",
  "reference": "Reference/invoice/policy number",
  "document_date": "Main date as YYYY-MM-DD",
  "summary": "3-4 sentence summary in German",
  "title": "Short title in German (2-5 words)"
}

Return only valid JSON. Use null for unknown fields.

JSON:"""


# Step 1: Extract structured metadata
METADATA_PROMPT = """Extract these fields from the document. Return JSON only.

- counterparty: Company or organization that issued this document (the employer for salary docs, the company for invoices)
- affected_persons: List of full names of people this document is about (look for "Herr/Frau", names in address, or names in body). Return as JSON array, e.g. ["Max Mustermann", "Erika Mustermann"]
- category: Choose one:
  - salary: Lohnsteuerbescheinigung, Gehaltsabrechnung, payslips, wage documents
  - tax: Steuerbescheid, tax assessments, Finanzamt letters
  - insurance: Versicherung, policies, claims
  - medical: Arzt, hospital, health documents
  - banking: Bank statements, account documents
  - utilities: Strom, Gas, water, internet bills
  - invoice: Rechnung, bills to pay
  - receipt: Quittung, proof of payment
  - contract: Vertrag, agreements
  - legal: Court, lawyer documents
  - correspondence: General letters
  - other: If none fit
- reference: Reference/invoice/policy number or Aktenzeichen
- document_date: Main date (YYYY-MM-DD)

Return only valid JSON. Use null for unknown fields.

Document:
{text}

JSON:"""


# Step 2: Generate title (from summary)
TITLE_PROMPT = """Create a short German title (2-5 words) for a document with this summary:

{summary}

Title:"""


# Step 3: Generate summary
SUMMARY_PROMPT = """Write a 3-4 sentence summary of this document in German.

Document:
{text}

Summary:"""


def get_empty_extraction() -> dict[str, Any]:
    """Return empty extraction result."""
    return {
        "title": None,
        "counterparty": None,
        "affected_person": None,
        "category": None,
        "reference": None,
        "document_date": None,
        "summary": None,
    }


async def check_ollama_available() -> bool:
    """Check if Ollama server is reachable."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{settings.ollama_base_url}/api/tags")
            return response.status_code == 200
    except Exception:
        return False


def parse_json_response(content: str) -> dict[str, Any]:
    """Parse JSON from LLM response, handling markdown code blocks."""
    content = content.strip()

    # Handle markdown code blocks
    if content.startswith("```"):
        content = content.split("```")[1]
        if content.startswith("json"):
            content = content[4:]
        content = content.strip()

    return json.loads(content)


def strip_thinking(text: str) -> str:
    """Remove <think>...</think> blocks from model output."""
    import re

    # Remove think blocks (can be multiline)
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    return text.strip()


async def call_ollama(prompt: str, images: list[str] | None = None) -> str:
    """Make a single call to Ollama and return the response text.

    Args:
        prompt: The prompt text
        images: Optional list of base64-encoded images for vision models
    """
    async with httpx.AsyncClient(timeout=settings.ollama_timeout) as client:
        if images:
            # Vision models use the /api/chat endpoint with images in the message
            payload = {
                "model": settings.ollama_model,
                "messages": [
                    {
                        "role": "user",
                        "content": prompt,
                        "images": images,
                    }
                ],
                "stream": False,
                "options": {
                    "temperature": 0,
                },
            }
            response = await client.post(
                f"{settings.ollama_base_url}/api/chat",
                json=payload,
            )
            response.raise_for_status()
            result = response.json()
            text = result.get("message", {}).get("content", "").strip()
        else:
            # Text-only models use /api/generate
            payload = {
                "model": settings.ollama_model,
                "prompt": prompt,
                "stream": False,
                "think": False,
                "options": {
                    "temperature": 0,
                },
            }
            response = await client.post(
                f"{settings.ollama_base_url}/api/generate",
                json=payload,
            )
            response.raise_for_status()
            result = response.json()
            text = result.get("response", "").strip()

        # Strip any thinking blocks that might be included
        return strip_thinking(text)


async def extract_all_with_vision(images: list[str]) -> dict[str, Any]:
    """Extract all fields in one vision API call."""
    try:
        response = await call_ollama(VISION_EXTRACT_PROMPT, images=images)
        data = parse_json_response(response)

        # Validate date
        if data.get("document_date"):
            try:
                date.fromisoformat(data["document_date"])
            except (ValueError, TypeError):
                data["document_date"] = None

        # Validate title length
        title = data.get("title")
        if title:
            title = title.strip().strip("\"'").split("\n")[0]
            if not (3 <= len(title) <= 100):
                title = None
            data["title"] = title

        return data
    except Exception as e:
        print(f"Vision extraction error: {e}")
        return {}


async def extract_metadata(text: str) -> dict[str, Any]:
    """Extract structured metadata fields from text."""
    try:
        truncated = text[:6000]
        response = await call_ollama(METADATA_PROMPT.format(text=truncated))
        data = parse_json_response(response)

        # Validate date
        if data.get("document_date"):
            try:
                date.fromisoformat(data["document_date"])
            except (ValueError, TypeError):
                data["document_date"] = None

        return data
    except Exception as e:
        print(f"Metadata extraction error: {e}")
        return {}


async def generate_title(summary: str) -> str | None:
    """Step 2: Generate a descriptive title from the summary."""
    try:
        prompt = TITLE_PROMPT.format(summary=summary)
        response = await call_ollama(prompt)

        # Clean up the response - remove quotes, newlines
        title = response.strip().strip("\"'").split("\n")[0]

        # Sanity check - title should be reasonable length
        if title and 3 <= len(title) <= 100:
            return title
        return None
    except Exception as e:
        print(f"Title generation error: {e}")
        return None


async def generate_summary(text: str) -> str | None:
    """Generate a summary in the document's language."""
    try:
        truncated = text[:4000]
        response = await call_ollama(SUMMARY_PROMPT.format(text=truncated))

        # Clean up - take first 1-2 sentences
        summary = response.strip()
        if summary:
            return summary
        return None
    except Exception as e:
        print(f"Summary generation error: {e}")
        return None


async def extract_document_data(text: str, pdf_path: Path | None = None) -> dict[str, Any]:
    """
    Extract structured data from document text using multi-step extraction.

    Args:
        text: Document text (from OCR)
        pdf_path: Optional path to PDF for vision model extraction

    Returns:
        Dict with extracted fields
    """
    if not await check_ollama_available():
        print("Warning: Ollama not available, skipping extraction")
        return get_empty_extraction()

    # Prepare images for vision mode if enabled and PDF available
    images = None
    if settings.ollama_use_vision and pdf_path and pdf_path.exists():
        print("  Preparing images for vision model...")
        images = await pdf_to_base64_images(pdf_path, max_pages=1)
        if images:
            print(f"  Converted {len(images)} page(s) to images")
        else:
            print("  Warning: Failed to convert PDF to images, falling back to text")

    # Vision mode: single API call for everything
    if images and settings.ollama_use_vision:
        print("  Extracting all fields with vision (single call)...")
        data = await extract_all_with_vision(images)

        # Handle affected_persons list
        affected_persons = data.get("affected_persons") or data.get("affected_person")
        if isinstance(affected_persons, list):
            affected_person = "; ".join(p.strip() for p in affected_persons if p and p.strip())
        else:
            affected_person = affected_persons

        return {
            "title": data.get("title"),
            "counterparty": data.get("counterparty"),
            "affected_person": affected_person,
            "category": data.get("category"),
            "reference": data.get("reference"),
            "document_date": data.get("document_date"),
            "summary": data.get("summary"),
        }

    # Text mode: multi-step extraction
    # Step 1: Extract metadata
    print("  Step 1: Extracting metadata...")
    metadata = await extract_metadata(text)

    # Step 2: Generate summary
    print("  Step 2: Generating summary...")
    summary = await generate_summary(text)

    # Step 3: Generate title from summary
    print("  Step 3: Generating title...")
    title = await generate_title(summary) if summary else None

    # Handle affected_persons list - join with semicolon for storage
    affected_persons = metadata.get("affected_persons") or metadata.get("affected_person")
    if isinstance(affected_persons, list):
        affected_person = "; ".join(p.strip() for p in affected_persons if p and p.strip())
    else:
        affected_person = affected_persons

    # Combine results
    return {
        "title": title,
        "counterparty": metadata.get("counterparty"),
        "affected_person": affected_person,
        "category": metadata.get("category"),
        "reference": metadata.get("reference"),
        "document_date": metadata.get("document_date"),
        "summary": summary,
    }


async def process_document_extraction(
    doc_id: str, text: str, pdf_path: Path | None = None
) -> dict[str, Any]:
    """
    Run extraction pipeline on a document.

    Args:
        doc_id: Document ID
        text: Document text
        pdf_path: Optional path to PDF for vision model extraction

    Returns:
        Dict with all extracted fields
    """
    return await extract_document_data(text, pdf_path=pdf_path)
