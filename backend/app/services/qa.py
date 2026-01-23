"""Question answering service using RAG."""

from typing import Optional
import aiosqlite
from openai import AsyncOpenAI

from app.config import get_settings
from app.services.embeddings import semantic_search

settings = get_settings()


def get_openai_client() -> AsyncOpenAI:
    """Get OpenAI client instance."""
    return AsyncOpenAI(api_key=settings.openai_api_key)


QA_SYSTEM_PROMPT = """You are a helpful assistant that answers questions about documents.
You will be provided with relevant excerpts from documents to help answer the user's question.
Always base your answers on the provided document context. If the documents don't contain enough information to answer the question, say so.
When referencing information, mention which document it came from when possible.
Answer in the same language as the question."""


async def get_document_context(doc_ids: list[str]) -> list[dict]:
    """
    Fetch document content for context.

    Args:
        doc_ids: List of document IDs

    Returns:
        List of document context dictionaries
    """
    contexts = []

    async with aiosqlite.connect(settings.database_path) as db:
        for doc_id in doc_ids:
            cursor = await db.execute(
                """
                SELECT id, filename, raw_text, summary, category
                FROM documents
                WHERE id = ?
                """,
                (doc_id,)
            )
            row = await cursor.fetchone()

            if row:
                contexts.append({
                    "id": row[0],
                    "filename": row[1],
                    "text": row[2] or "",
                    "summary": row[3] or "",
                    "category": row[4],
                })

    return contexts


def build_context_prompt(contexts: list[dict], max_chars: int = 12000) -> str:
    """
    Build a context prompt from document contexts.

    Args:
        contexts: List of document context dictionaries
        max_chars: Maximum characters for context

    Returns:
        Formatted context string
    """
    prompt_parts = []
    current_length = 0

    for ctx in contexts:
        # Use summary if available, otherwise truncate text
        content = ctx["summary"] if ctx["summary"] else ctx["text"]

        # Calculate how much space we have left
        remaining = max_chars - current_length

        if remaining <= 0:
            break

        # Truncate if needed
        if len(content) > remaining:
            content = content[:remaining] + "..."

        doc_header = f"[Document: {ctx['filename']}]"
        if ctx["category"]:
            doc_header += f" (Category: {ctx['category']})"

        part = f"{doc_header}\n{content}\n"
        prompt_parts.append(part)
        current_length += len(part)

    return "\n".join(prompt_parts)


async def answer_question(
    question: str,
    doc_ids: Optional[list[str]] = None,
    max_sources: int = 5,
) -> dict:
    """
    Answer a question using RAG.

    Args:
        question: User's question
        doc_ids: Optional list of document IDs to limit search to
        max_sources: Maximum number of source documents to use

    Returns:
        Dict with answer and source document IDs
    """
    if not settings.openai_api_key:
        return {
            "answer": "OpenAI API key not configured. Cannot answer questions.",
            "sources": [],
        }

    # Find relevant documents
    if doc_ids:
        # Use specified documents
        relevant_doc_ids = doc_ids[:max_sources]
    else:
        # Use semantic search to find relevant documents
        search_results = await semantic_search(question, limit=max_sources)
        relevant_doc_ids = [doc_id for doc_id, _ in search_results]

    if not relevant_doc_ids:
        return {
            "answer": "No relevant documents found to answer this question.",
            "sources": [],
        }

    # Get document contexts
    contexts = await get_document_context(relevant_doc_ids)

    if not contexts:
        return {
            "answer": "Could not retrieve document content.",
            "sources": [],
        }

    # Build context prompt
    context_prompt = build_context_prompt(contexts)

    # Call OpenAI
    client = get_openai_client()

    messages = [
        {"role": "system", "content": QA_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": f"""Based on the following documents, please answer this question: {question}

Documents:
{context_prompt}

Question: {question}"""
        }
    ]

    response = await client.chat.completions.create(
        model=settings.openai_chat_model,
        messages=messages,
        max_tokens=1000,
        temperature=0.3,
    )

    answer = response.choices[0].message.content.strip()

    return {
        "answer": answer,
        "sources": relevant_doc_ids,
    }


async def get_document_qa(doc_id: str, question: str) -> dict:
    """
    Answer a question about a specific document.

    Args:
        doc_id: Document ID
        question: User's question

    Returns:
        Dict with answer
    """
    return await answer_question(question, doc_ids=[doc_id])
