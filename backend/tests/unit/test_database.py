"""Unit tests for database module."""

from unittest.mock import MagicMock, patch

import aiosqlite
import pytest
from app.database import init_database, init_sqlite_vec


class TestInitDatabase:
    """Tests for init_database function."""

    @pytest.mark.asyncio
    async def test_creates_documents_table(self, test_db):
        """Documents table is created with correct columns."""
        async with aiosqlite.connect(test_db) as db:
            cursor = await db.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='documents'"
            )
            row = await cursor.fetchone()
            assert row is not None

            # Check columns
            cursor = await db.execute("PRAGMA table_info(documents)")
            columns = {row[1] for row in await cursor.fetchall()}

            expected_columns = {
                "id",
                "filename",
                "file_path",
                "file_hash",
                "file_size",
                "mime_type",
                "raw_text",
                "page_count",
                "summary",
                "document_date",
                "created_at",
                "processed_at",
                "status",
                "extraction_status",
                "title",
                "counterparty",
                "affected_person",
                "category",
                "reference",
            }
            assert expected_columns.issubset(columns)

    @pytest.mark.asyncio
    async def test_creates_fts_table(self, test_db):
        """FTS5 virtual table is created."""
        async with aiosqlite.connect(test_db) as db:
            cursor = await db.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='documents_fts'"
            )
            row = await cursor.fetchone()
            assert row is not None

    @pytest.mark.asyncio
    async def test_creates_tags_table(self, test_db):
        """Tags table is created."""
        async with aiosqlite.connect(test_db) as db:
            cursor = await db.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='tags'"
            )
            row = await cursor.fetchone()
            assert row is not None

    @pytest.mark.asyncio
    async def test_creates_document_tags_table(self, test_db):
        """Document-tags junction table is created."""
        async with aiosqlite.connect(test_db) as db:
            cursor = await db.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='document_tags'"
            )
            row = await cursor.fetchone()
            assert row is not None

    @pytest.mark.asyncio
    async def test_creates_sessions_table(self, test_db):
        """Sessions table is created."""
        async with aiosqlite.connect(test_db) as db:
            cursor = await db.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='sessions'"
            )
            row = await cursor.fetchone()
            assert row is not None

    @pytest.mark.asyncio
    async def test_creates_embeddings_table(self, test_db):
        """Document embeddings table is created."""
        async with aiosqlite.connect(test_db) as db:
            cursor = await db.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='document_embeddings'"
            )
            row = await cursor.fetchone()
            assert row is not None

    @pytest.mark.asyncio
    async def test_creates_fts_triggers(self, test_db):
        """FTS sync triggers are created."""
        async with aiosqlite.connect(test_db) as db:
            cursor = await db.execute("SELECT name FROM sqlite_master WHERE type='trigger'")
            triggers = {row[0] for row in await cursor.fetchall()}

            assert "documents_ai" in triggers  # After Insert
            assert "documents_ad" in triggers  # After Delete
            assert "documents_au" in triggers  # After Update

    @pytest.mark.asyncio
    async def test_creates_indexes(self, test_db):
        """Required indexes are created."""
        async with aiosqlite.connect(test_db) as db:
            cursor = await db.execute("SELECT name FROM sqlite_master WHERE type='index'")
            indexes = {row[0] for row in await cursor.fetchall()}

            assert "idx_documents_file_hash" in indexes
            assert "idx_documents_status" in indexes
            assert "idx_documents_extraction_status" in indexes

    @pytest.mark.asyncio
    async def test_fts_insert_trigger_works(self, test_db):
        """FTS is updated when document is inserted."""
        async with aiosqlite.connect(test_db) as db:
            # Insert a document
            await db.execute("""
                INSERT INTO documents (id, filename, file_path, file_hash, raw_text, status)
                VALUES ('test-1', 'test.pdf', '/path/test.pdf', 'hash123',
                        'searchable text content', 'completed')
            """)
            await db.commit()

            # Search FTS
            cursor = await db.execute(
                "SELECT id FROM documents_fts WHERE documents_fts MATCH 'searchable'"
            )
            row = await cursor.fetchone()
            assert row is not None
            assert row[0] == "test-1"

    @pytest.mark.asyncio
    async def test_fts_update_trigger_works(self, test_db):
        """FTS is updated when document is updated."""
        async with aiosqlite.connect(test_db) as db:
            # Insert a document
            await db.execute("""
                INSERT INTO documents (id, filename, file_path, file_hash, raw_text, status)
                VALUES ('test-1', 'test.pdf', '/path/test.pdf', 'hash123',
                        'old content', 'completed')
            """)
            await db.commit()

            # Update the document
            await db.execute(
                "UPDATE documents SET raw_text = 'new unique content' WHERE id = 'test-1'"
            )
            await db.commit()

            # Search for new content
            cursor = await db.execute(
                "SELECT id FROM documents_fts WHERE documents_fts MATCH 'unique'"
            )
            row = await cursor.fetchone()
            assert row is not None

            # Old content should not be found
            cursor = await db.execute(
                "SELECT id FROM documents_fts WHERE documents_fts MATCH 'old'"
            )
            row = await cursor.fetchone()
            assert row is None

    @pytest.mark.asyncio
    async def test_fts_delete_trigger_works(self, test_db):
        """FTS entry is removed when document is deleted."""
        async with aiosqlite.connect(test_db) as db:
            # Insert a document
            await db.execute("""
                INSERT INTO documents (id, filename, file_path, file_hash, raw_text, status)
                VALUES ('test-1', 'test.pdf', '/path/test.pdf', 'hash123',
                        'deletable content', 'completed')
            """)
            await db.commit()

            # Delete the document
            await db.execute("DELETE FROM documents WHERE id = 'test-1'")
            await db.commit()

            # FTS should not find it
            cursor = await db.execute(
                "SELECT id FROM documents_fts WHERE documents_fts MATCH 'deletable'"
            )
            row = await cursor.fetchone()
            assert row is None


class TestInitSqliteVec:
    """Tests for init_sqlite_vec function."""

    def test_loads_extension_when_available(self):
        """Loads sqlite-vec extension when available."""
        mock_conn = MagicMock()
        mock_vec = MagicMock()

        # We need to patch the import inside the function
        with patch.dict("sys.modules", {"sqlite_vec": mock_vec}):
            init_sqlite_vec(mock_conn)

            mock_conn.enable_load_extension.assert_any_call(True)
            mock_vec.load.assert_called_once_with(mock_conn)
            mock_conn.enable_load_extension.assert_any_call(False)

    def test_handles_extension_not_available(self):
        """Gracefully handles sqlite-vec not being available."""
        mock_conn = MagicMock()

        # Simulate import error by making the import raise
        with patch.dict("sys.modules", {"sqlite_vec": None}):
            with patch("builtins.__import__", side_effect=ImportError("No module")):
                # Should not raise
                init_sqlite_vec(mock_conn)


class TestMigration:
    """Tests for database migrations."""

    @pytest.mark.asyncio
    async def test_adds_extraction_status_column(self, tmp_path, test_settings):
        """Migration adds extraction_status column to existing DB."""
        db_path = tmp_path / "old.db"

        # Create old schema without extraction_status
        async with aiosqlite.connect(str(db_path)) as db:
            await db.execute("""
                CREATE TABLE documents (
                    id TEXT PRIMARY KEY,
                    filename TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    file_hash TEXT NOT NULL,
                    status TEXT DEFAULT 'pending'
                )
            """)
            await db.execute(
                """INSERT INTO documents VALUES
                ('doc1', 'test.pdf', '/path/test.pdf', 'hash1', 'completed')"""
            )
            await db.commit()

        # Patch settings to use this db
        with patch.object(test_settings, "database_path", db_path):
            await init_database()

        # Verify column was added and data preserved
        async with aiosqlite.connect(str(db_path)) as db:
            cursor = await db.execute("PRAGMA table_info(documents)")
            columns = {row[1] for row in await cursor.fetchall()}
            assert "extraction_status" in columns

            # Data should be preserved
            cursor = await db.execute("SELECT id, filename FROM documents WHERE id = 'doc1'")
            row = await cursor.fetchone()
            assert row is not None
            assert row[1] == "test.pdf"

    @pytest.mark.asyncio
    async def test_idempotent_initialization(self, test_db, test_settings):
        """Running init_database multiple times is safe."""
        # First call already done by test_db fixture
        # Second call should not raise
        await init_database()

        # Verify tables still exist
        async with aiosqlite.connect(test_db) as db:
            cursor = await db.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'")
            count = (await cursor.fetchone())[0]
            assert count > 0


class TestForeignKeys:
    """Tests for foreign key constraints."""

    @pytest.mark.asyncio
    async def test_document_tags_cascade_delete(self, test_db):
        """Deleting document cascades to document_tags."""
        async with aiosqlite.connect(test_db) as db:
            await db.execute("PRAGMA foreign_keys = ON")

            # Insert document
            await db.execute("""
                INSERT INTO documents (id, filename, file_path, file_hash, status)
                VALUES ('doc-1', 'test.pdf', '/path', 'hash', 'completed')
            """)

            # Insert tag
            await db.execute("INSERT INTO tags (id, name) VALUES (1, 'important')")

            # Link them
            await db.execute("INSERT INTO document_tags (doc_id, tag_id) VALUES ('doc-1', 1)")
            await db.commit()

            # Delete document
            await db.execute("DELETE FROM documents WHERE id = 'doc-1'")
            await db.commit()

            # document_tags entry should be gone
            cursor = await db.execute("SELECT COUNT(*) FROM document_tags WHERE doc_id = 'doc-1'")
            count = (await cursor.fetchone())[0]
            assert count == 0
