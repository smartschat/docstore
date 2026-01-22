"""Database setup and utilities."""

import sqlite3
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings


class Base(DeclarativeBase):
    """Base class for SQLAlchemy models."""
    pass


settings = get_settings()

engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
)

async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for getting async database session."""
    async with async_session_maker() as session:
        try:
            yield session
        finally:
            await session.close()


def init_sqlite_vec(conn: sqlite3.Connection) -> None:
    """Load sqlite-vec extension."""
    try:
        import sqlite_vec
        conn.enable_load_extension(True)
        sqlite_vec.load(conn)
        conn.enable_load_extension(False)
    except Exception as e:
        print(f"Warning: Could not load sqlite-vec: {e}")


async def init_database() -> None:
    """Initialize database schema."""
    settings.ensure_directories()

    # Create tables using raw SQL for full control
    import aiosqlite

    async with aiosqlite.connect(settings.database_path) as db:
        # Enable foreign keys
        await db.execute("PRAGMA foreign_keys = ON")

        # Core documents table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS documents (
                id TEXT PRIMARY KEY,
                filename TEXT NOT NULL,
                file_path TEXT NOT NULL,
                file_hash TEXT NOT NULL,
                file_size INTEGER,
                mime_type TEXT,
                raw_text TEXT,
                page_count INTEGER,
                summary TEXT,
                document_date DATE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                processed_at TIMESTAMP,
                status TEXT DEFAULT 'pending',
                -- Extracted fields
                title TEXT,
                counterparty TEXT,
                affected_person TEXT,
                category TEXT,
                reference TEXT,
                due_date DATE,
                amount REAL,
                currency TEXT DEFAULT 'EUR'
            )
        """)

        # Create index on file_hash for deduplication
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_documents_file_hash
            ON documents(file_hash)
        """)

        # Create index on status for filtering
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_documents_status
            ON documents(status)
        """)

        # FTS5 for full-text search
        await db.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS documents_fts USING fts5(
                id,
                filename,
                raw_text,
                summary,
                title,
                counterparty,
                affected_person,
                category,
                reference,
                content='documents',
                content_rowid='rowid'
            )
        """)

        # Triggers to keep FTS in sync
        await db.execute("""
            CREATE TRIGGER IF NOT EXISTS documents_ai AFTER INSERT ON documents BEGIN
                INSERT INTO documents_fts(rowid, id, filename, raw_text, summary, title, counterparty, affected_person, category, reference)
                VALUES (new.rowid, new.id, new.filename, new.raw_text, new.summary, new.title, new.counterparty, new.affected_person, new.category, new.reference);
            END
        """)

        await db.execute("""
            CREATE TRIGGER IF NOT EXISTS documents_ad AFTER DELETE ON documents BEGIN
                INSERT INTO documents_fts(documents_fts, rowid, id, filename, raw_text, summary, title, counterparty, affected_person, category, reference)
                VALUES('delete', old.rowid, old.id, old.filename, old.raw_text, old.summary, old.title, old.counterparty, old.affected_person, old.category, old.reference);
            END
        """)

        await db.execute("""
            CREATE TRIGGER IF NOT EXISTS documents_au AFTER UPDATE ON documents BEGIN
                INSERT INTO documents_fts(documents_fts, rowid, id, filename, raw_text, summary, title, counterparty, affected_person, category, reference)
                VALUES('delete', old.rowid, old.id, old.filename, old.raw_text, old.summary, old.title, old.counterparty, old.affected_person, old.category, old.reference);
                INSERT INTO documents_fts(rowid, id, filename, raw_text, summary, title, counterparty, affected_person, category, reference)
                VALUES (new.rowid, new.id, new.filename, new.raw_text, new.summary, new.title, new.counterparty, new.affected_person, new.category, new.reference);
            END
        """)

        # Tags table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS tags (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL
            )
        """)

        # Document-tag relationship
        await db.execute("""
            CREATE TABLE IF NOT EXISTS document_tags (
                doc_id TEXT REFERENCES documents(id) ON DELETE CASCADE,
                tag_id INTEGER REFERENCES tags(id) ON DELETE CASCADE,
                PRIMARY KEY (doc_id, tag_id)
            )
        """)

        # Sessions table for auth
        await db.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                token TEXT PRIMARY KEY,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP NOT NULL
            )
        """)

        await db.commit()

    # Create vector table using sync connection (sqlite-vec doesn't work well with aiosqlite threading)
    try:
        import sqlite_vec
        sync_conn = sqlite3.connect(str(settings.database_path))
        sync_conn.enable_load_extension(True)
        sqlite_vec.load(sync_conn)
        sync_conn.enable_load_extension(False)

        sync_conn.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS document_embeddings USING vec0(
                doc_id TEXT PRIMARY KEY,
                embedding FLOAT[1536]
            )
        """)
        sync_conn.commit()
        sync_conn.close()
        print("Vector table created successfully")
    except Exception as e:
        print(f"Note: Vector table not created (sqlite-vec may not be installed): {e}")

    print("Database initialized successfully")
