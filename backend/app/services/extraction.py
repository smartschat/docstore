"""LLM-powered structured data extraction using Ollama."""

import json
from typing import Any
from datetime import date
import httpx

from app.config import get_settings

settings = get_settings()


EXTRACTION_PROMPT = """Analyze this document and extract the following information. Return a JSON object with these fields:

- title: A short, descriptive title for the document (e.g., "Stromrechnung Januar 2024", "Mietvertrag Hauptstraße 5")
- counterparty: The other party involved - company, organization, or person (e.g., "Vodafone", "Finanzamt Berlin", "Dr. Müller")
- affected_person: If the document is addressed to or concerns a specific person, extract their name. If unclear or general, use null.
- category: Categorize the document. Use one of: utilities, insurance, tax, medical, banking, salary, contract, legal, correspondence, receipt, invoice, other
- reference: Any reference number, invoice number, policy number, Aktenzeichen, or similar identifier
- document_date: The main date of the document (YYYY-MM-DD format)
- due_date: Payment deadline or action required date, if any (YYYY-MM-DD format)
- amount: The primary monetary amount, if any (number only, no currency symbol)
- currency: Currency code (EUR, USD, etc.) - default to EUR if unclear
- summary: A 1-2 sentence summary of what this document is about, in the same language as the document

If a field cannot be determined, use null. Return only valid JSON, no other text.

Document text:
{text}

JSON:"""


def get_empty_extraction() -> dict[str, Any]:
    """Return empty extraction result."""
    return {
        "title": None,
        "counterparty": None,
        "affected_person": None,
        "category": None,
        "reference": None,
        "document_date": None,
        "due_date": None,
        "amount": None,
        "currency": "EUR",
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


async def extract_with_ollama(text: str) -> dict[str, Any]:
    """
    Extract structured data using Ollama.

    Args:
        text: Document text (from OCR)

    Returns:
        Dict with extracted fields
    """
    # Use first 8000 chars for extraction
    truncated_text = text[:8000] if len(text) > 8000 else text

    try:
        async with httpx.AsyncClient(timeout=settings.ollama_timeout) as client:
            response = await client.post(
                f"{settings.ollama_base_url}/api/generate",
                json={
                    "model": settings.ollama_model,
                    "prompt": EXTRACTION_PROMPT.format(text=truncated_text),
                    "stream": False,
                },
            )
            response.raise_for_status()
            result = response.json()
            content = result.get("response", "").strip()

            # Parse JSON response
            # Handle markdown code blocks
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]

            data = json.loads(content)

            # Validate and clean up dates
            for date_field in ["document_date", "due_date"]:
                if data.get(date_field):
                    try:
                        date.fromisoformat(data[date_field])
                    except (ValueError, TypeError):
                        data[date_field] = None

            # Ensure amount is a number or None
            if data.get("amount") is not None:
                try:
                    data["amount"] = float(data["amount"])
                except (ValueError, TypeError):
                    data["amount"] = None

            return data

    except Exception as e:
        print(f"Ollama extraction error: {e}")
        return get_empty_extraction()


async def extract_document_data(text: str) -> dict[str, Any]:
    """
    Extract structured data from document text.

    Args:
        text: Document text (from OCR)

    Returns:
        Dict with extracted fields
    """
    # Try Ollama first
    if await check_ollama_available():
        return await extract_with_ollama(text)

    # No LLM available
    print("Warning: Ollama not available, skipping extraction")
    return get_empty_extraction()


async def process_document_extraction(doc_id: str, text: str) -> dict[str, Any]:
    """
    Run extraction pipeline on a document.

    Args:
        doc_id: Document ID
        text: Document text

    Returns:
        Dict with all extracted fields
    """
    return await extract_document_data(text)
