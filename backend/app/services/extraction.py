"""LLM-powered structured data extraction using Ollama."""

import json
from typing import Any
from datetime import date
import httpx

from app.config import get_settings

settings = get_settings()


# Step 1: Extract structured metadata
METADATA_PROMPT = """Extract these fields from the document. Return JSON only.

- counterparty: Company or organization that issued this document (the employer for salary docs, the company for invoices)
- affected_person: Full name of the person this document is about (look for "Herr/Frau" or name in address)
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
SUMMARY_PROMPT = """Write a 1-2 sentence summary of this document.
IMPORTANT: Write in the SAME LANGUAGE as the document.
If the document is in German, write German. If English, write English.

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
    text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
    return text.strip()


async def call_ollama(prompt: str) -> str:
    """Make a single call to Ollama and return the response text."""
    async with httpx.AsyncClient(timeout=settings.ollama_timeout) as client:
        response = await client.post(
            f"{settings.ollama_base_url}/api/generate",
            json={
                "model": settings.ollama_model,
                "prompt": prompt,
                "stream": False,
                "think": False,
                "options": {
                    "temperature": 0,
                },
            },
        )
        response.raise_for_status()
        result = response.json()
        text = result.get("response", "").strip()
        # Strip any thinking blocks that might be included
        return strip_thinking(text)


async def extract_metadata(text: str) -> dict[str, Any]:
    """Step 1: Extract structured metadata fields."""
    truncated = text[:6000]

    try:
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
        title = response.strip().strip('"\'').split('\n')[0]

        # Sanity check - title should be reasonable length
        if title and 3 <= len(title) <= 100:
            return title
        return None
    except Exception as e:
        print(f"Title generation error: {e}")
        return None


async def generate_summary(text: str) -> str | None:
    """Step 3: Generate a summary in the document's language."""
    truncated = text[:4000]

    try:
        response = await call_ollama(SUMMARY_PROMPT.format(text=truncated))

        # Clean up - take first 1-2 sentences
        summary = response.strip()
        if summary:
            return summary
        return None
    except Exception as e:
        print(f"Summary generation error: {e}")
        return None


async def extract_document_data(text: str) -> dict[str, Any]:
    """
    Extract structured data from document text using multi-step extraction.

    Args:
        text: Document text (from OCR)

    Returns:
        Dict with extracted fields
    """
    if not await check_ollama_available():
        print("Warning: Ollama not available, skipping extraction")
        return get_empty_extraction()

    # Step 1: Extract metadata
    print("  Step 1: Extracting metadata...")
    metadata = await extract_metadata(text)

    # Step 2: Generate summary
    print("  Step 2: Generating summary...")
    summary = await generate_summary(text)

    # Step 3: Generate title from summary
    print("  Step 3: Generating title...")
    title = await generate_title(summary) if summary else None

    # Combine results
    return {
        "title": title,
        "counterparty": metadata.get("counterparty"),
        "affected_person": metadata.get("affected_person"),
        "category": metadata.get("category"),
        "reference": metadata.get("reference"),
        "document_date": metadata.get("document_date"),
        "summary": summary,
    }


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
