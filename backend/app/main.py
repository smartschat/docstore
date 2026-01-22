"""Main FastAPI application."""

import asyncio
from contextlib import asynccontextmanager

import aiosqlite
from fastapi import FastAPI, Depends, Response, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.database import init_database
from app.auth import (
    verify_password,
    generate_session_token,
    create_session,
    delete_session,
    get_current_session,
    set_session_cookie,
    clear_session_cookie,
    cleanup_expired_sessions,
    validate_session,
)
from app.models import (
    LoginRequest,
    LoginResponse,
    AuthStatus,
    DashboardStats,
    SpendingStats,
    Document,
    DocumentStatus,
    Tag,
)
from app.services.watcher import folder_watcher, process_existing_inbox, process_document
from app.routers import documents, search, qa

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management."""
    # Startup
    print("Starting DocStore...")

    # Initialize database
    await init_database()

    # Clean up expired sessions
    await cleanup_expired_sessions()

    # Start folder watcher
    loop = asyncio.get_event_loop()
    folder_watcher.start(loop)

    # Process any existing files in inbox
    existing = await process_existing_inbox()
    if existing:
        print(f"Processed {len(existing)} existing files from inbox")

    yield

    # Shutdown
    print("Shutting down DocStore...")
    folder_watcher.stop()


app = FastAPI(
    title="DocStore",
    description="Document digitization system with OCR and semantic search",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],  # Vite dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(documents.router)
app.include_router(search.router)
app.include_router(qa.router)


# Health check (no auth required)
@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "version": "0.1.0"}


# Auth endpoints
@app.post("/api/auth/login", response_model=LoginResponse)
async def login(request: LoginRequest, response: Response):
    """Login with password."""
    if not verify_password(request.password):
        raise HTTPException(status_code=401, detail="Invalid password")

    token = generate_session_token()
    await create_session(token)
    set_session_cookie(response, token)

    return LoginResponse(success=True, message="Logged in successfully")


@app.post("/api/auth/logout")
async def logout(
    response: Response,
    session_token: str = Depends(get_current_session),
):
    """Logout and invalidate session."""
    await delete_session(session_token)
    clear_session_cookie(response)
    return {"message": "Logged out successfully"}


@app.get("/api/auth/check", response_model=AuthStatus)
async def check_auth(
    session_token: str = Depends(get_current_session),
):
    """Check if authenticated."""
    return AuthStatus(authenticated=True)


# Tags endpoints
@app.get("/api/tags", response_model=list[Tag])
async def list_tags(_: str = Depends(get_current_session)):
    """List all tags."""
    async with aiosqlite.connect(settings.database_path) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT id, name FROM tags ORDER BY name")
        rows = await cursor.fetchall()
        return [Tag(id=row["id"], name=row["name"]) for row in rows]


# Stats endpoints
@app.get("/api/stats", response_model=DashboardStats)
async def get_stats(_: str = Depends(get_current_session)):
    """Get dashboard statistics."""
    async with aiosqlite.connect(settings.database_path) as db:
        db.row_factory = aiosqlite.Row

        # Total documents
        cursor = await db.execute("SELECT COUNT(*) as count FROM documents")
        total = (await cursor.fetchone())["count"]

        # By category
        cursor = await db.execute(
            "SELECT category, COUNT(*) as count FROM documents GROUP BY category"
        )
        by_category = {row["category"] or "uncategorized": row["count"] for row in await cursor.fetchall()}

        # By status
        cursor = await db.execute(
            "SELECT status, COUNT(*) as count FROM documents GROUP BY status"
        )
        by_status = {row["status"]: row["count"] for row in await cursor.fetchall()}

        # Recent documents
        cursor = await db.execute(
            "SELECT * FROM documents ORDER BY created_at DESC LIMIT 5"
        )
        recent_rows = await cursor.fetchall()

        recent = []
        for row in recent_rows:
            from datetime import datetime
            row_dict = dict(row)
            recent.append(Document(
                id=row_dict["id"],
                filename=row_dict["filename"],
                file_path=row_dict["file_path"],
                file_hash=row_dict["file_hash"],
                file_size=row_dict["file_size"],
                mime_type=row_dict["mime_type"],
                raw_text=row_dict["raw_text"],
                page_count=row_dict["page_count"],
                summary=row_dict["summary"],
                document_date=row_dict["document_date"],
                created_at=datetime.fromisoformat(row_dict["created_at"]) if row_dict["created_at"] else datetime.utcnow(),
                processed_at=datetime.fromisoformat(row_dict["processed_at"]) if row_dict["processed_at"] else None,
                status=DocumentStatus(row_dict["status"]) if row_dict["status"] else DocumentStatus.PENDING,
                title=row_dict.get("title"),
                counterparty=row_dict.get("counterparty"),
                affected_person=row_dict.get("affected_person"),
                category=row_dict.get("category"),
                reference=row_dict.get("reference"),
                due_date=row_dict.get("due_date"),
                amount=row_dict.get("amount"),
                currency=row_dict.get("currency") or "EUR",
                tags=[],
            ))

        return DashboardStats(
            total_documents=total,
            documents_by_category=by_category,
            documents_by_status=by_status,
            recent_documents=recent,
        )


@app.get("/api/stats/spending", response_model=SpendingStats)
async def get_spending_stats(_: str = Depends(get_current_session)):
    """Get spending statistics from documents with amounts."""
    async with aiosqlite.connect(settings.database_path) as db:
        # Total spending
        cursor = await db.execute(
            "SELECT COALESCE(SUM(amount), 0) as total FROM documents WHERE amount IS NOT NULL"
        )
        total_spending = (await cursor.fetchone())[0]

        # By category
        cursor = await db.execute(
            """
            SELECT category, SUM(amount) as total
            FROM documents
            WHERE category IS NOT NULL AND amount IS NOT NULL
            GROUP BY category
            """
        )
        by_category = {row[0]: row[1] for row in await cursor.fetchall()}

        # By month
        cursor = await db.execute(
            """
            SELECT strftime('%Y-%m', document_date) as month, SUM(amount) as total
            FROM documents
            WHERE document_date IS NOT NULL AND amount IS NOT NULL
            GROUP BY month
            """
        )
        monthly = {row[0]: row[1] for row in await cursor.fetchall() if row[0]}

        return SpendingStats(
            total_spending=total_spending,
            spending_by_category=by_category,
            spending_by_month=monthly,
        )


@app.post("/api/reprocess/{doc_id}")
async def reprocess_document(
    doc_id: str,
    _: str = Depends(get_current_session),
):
    """Re-run extraction on a document."""
    from pathlib import Path
    from app.services.ocr import extract_text_from_file
    from app.services.extraction import process_document_extraction
    from app.services.embeddings import embed_document
    from app.services.watcher import (
        update_document_status,
        update_document_ocr,
        update_document_extraction,
    )

    async with aiosqlite.connect(settings.database_path) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM documents WHERE id = ?",
            (doc_id,)
        )
        row = await cursor.fetchone()

        if not row:
            raise HTTPException(status_code=404, detail="Document not found")

        file_path = settings.data_dir / row["file_path"]
        mime_type = row["mime_type"]

    await update_document_status(doc_id, DocumentStatus.PROCESSING)

    try:
        # Re-run OCR
        ocr_result = await extract_text_from_file(file_path, mime_type)

        if not ocr_result.success:
            await update_document_status(doc_id, DocumentStatus.FAILED)
            return {"error": ocr_result.error}

        await update_document_ocr(doc_id, ocr_result.text, ocr_result.page_count)

        # Re-run extraction
        if ocr_result.text and settings.openai_api_key:
            extraction_result = await process_document_extraction(doc_id, ocr_result.text)
            await update_document_extraction(doc_id, extraction_result)
            await embed_document(doc_id, ocr_result.text)

        await update_document_status(doc_id, DocumentStatus.COMPLETED)
        return {"message": "Document reprocessed successfully"}

    except Exception as e:
        await update_document_status(doc_id, DocumentStatus.FAILED)
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug,
    )
