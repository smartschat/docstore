"""Main FastAPI application."""

import asyncio
from contextlib import asynccontextmanager

import aiosqlite
from fastapi import Depends, FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware

from app.auth import (
    cleanup_expired_sessions,
    clear_session_cookie,
    create_session,
    delete_session,
    generate_session_token,
    get_current_session,
    set_session_cookie,
    verify_password,
)
from app.config import get_settings
from app.database import init_database
from app.models import (
    AuthStatus,
    DashboardStats,
    Document,
    DocumentStatus,
    LoginRequest,
    LoginResponse,
    Tag,
)
from app.routers import documents, qa, search
from app.services.queue import get_queue_stats, start_queue_processor, stop_queue_processor
from app.services.watcher import folder_watcher, process_existing_inbox

settings = get_settings()


async def recover_stuck_documents() -> int:
    """Fix documents stuck in 'processing' state from interrupted processing."""
    from datetime import datetime

    import aiosqlite

    async with aiosqlite.connect(settings.database_path) as db:
        # Documents with completed extraction but stuck in processing
        cursor = await db.execute("""
            UPDATE documents
            SET status = 'completed', processed_at = ?
            WHERE status = 'processing' AND extraction_status = 'completed'
        """, (datetime.utcnow().isoformat(),))
        completed_count = cursor.rowcount
        await db.commit()

        # Documents stuck in processing without extraction (mark for retry)
        cursor = await db.execute("""
            UPDATE documents
            SET status = 'completed', extraction_status = 'pending'
            WHERE status = 'processing' AND (extraction_status IS NULL OR extraction_status = 'pending')
        """)
        pending_count = cursor.rowcount
        await db.commit()

        return completed_count + pending_count


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management."""
    # Startup
    print("Starting DocStore...")

    # Initialize database
    await init_database()

    # Recover any documents stuck from previous interrupted run
    recovered = await recover_stuck_documents()
    if recovered:
        print(f"Recovered {recovered} documents stuck in processing")

    # Clean up expired sessions
    await cleanup_expired_sessions()

    # Start folder watcher
    loop = asyncio.get_event_loop()
    folder_watcher.start(loop)

    # Process any existing files in inbox
    existing = await process_existing_inbox()
    if existing:
        print(f"Processed {len(existing)} existing files from inbox")

    # Start extraction queue processor
    start_queue_processor()

    yield

    # Shutdown
    print("Shutting down DocStore...")
    stop_queue_processor()
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
        by_status = {row["status"] or "unknown": row["count"] for row in await cursor.fetchall()}

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
                extraction_status=row_dict.get("extraction_status"),
                title=row_dict.get("title"),
                counterparty=row_dict.get("counterparty"),
                affected_person=row_dict.get("affected_person"),
                category=row_dict.get("category"),
                reference=row_dict.get("reference"),
                tags=[],
            ))

        return DashboardStats(
            total_documents=total,
            documents_by_category=by_category,
            documents_by_status=by_status,
            recent_documents=recent,
        )


@app.get("/api/queue/stats")
async def queue_stats(_: str = Depends(get_current_session)):
    """Get extraction queue statistics."""
    return await get_queue_stats()


@app.post("/api/reprocess/{doc_id}")
async def reprocess_document(
    doc_id: str,
    _: str = Depends(get_current_session),
):
    """Re-run extraction on a document."""
    from app.services.embeddings import embed_document
    from app.services.extraction import process_document_extraction
    from app.services.ocr import extract_text_from_file
    from app.services.watcher import (
        update_document_extraction,
        update_document_ocr,
        update_document_status,
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
        if ocr_result.text:
            from app.services.extraction import check_ollama_available
            from app.services.watcher import update_extraction_status

            if await check_ollama_available():
                extraction_result = await process_document_extraction(doc_id, ocr_result.text)
                await update_document_extraction(doc_id, extraction_result)
                await update_extraction_status(doc_id, "completed")
            else:
                await update_extraction_status(doc_id, "pending")

            await embed_document(doc_id, ocr_result.text)

        await update_document_status(doc_id, DocumentStatus.COMPLETED)
        return {"message": "Document reprocessed successfully"}

    except Exception as e:
        await update_document_status(doc_id, DocumentStatus.FAILED)
        raise HTTPException(status_code=500, detail=str(e))


# Serve static frontend files in production
if settings.static_dir.exists() and (settings.static_dir / "index.html").exists():
    from fastapi.responses import FileResponse
    from fastapi.staticfiles import StaticFiles

    # Mount static subdirectories if they exist
    for subdir in ["_app", "assets"]:
        subdir_path = settings.static_dir / subdir
        if subdir_path.exists():
            app.mount(f"/{subdir}", StaticFiles(directory=subdir_path), name=subdir)

    # SPA fallback - serve index.html for all non-API routes
    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        """Serve the SPA for all non-API routes."""
        # Check if it's a static file that exists
        static_file = settings.static_dir / full_path
        if static_file.is_file():
            return FileResponse(static_file)
        # Otherwise serve index.html for SPA routing
        return FileResponse(settings.static_dir / "index.html")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug,
    )
