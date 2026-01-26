"""Tests for entity management service."""

import pytest
import pytest_asyncio

from app.models import DisambiguationStatus
from app.services import entities


class TestCounterpartyOperations:
    """Test counterparty CRUD operations."""

    @pytest.mark.asyncio
    async def test_create_counterparty(self, test_db):
        """Test creating a new counterparty."""
        entity_id = await entities.create_counterparty(
            canonical_name="Deutsche Telekom AG",
            aliases=["Telekom", "T-Mobile"],
            short_name="Telekom",
        )

        assert entity_id is not None

        # Fetch and verify
        cp = await entities.get_counterparty(entity_id)
        assert cp is not None
        assert cp.canonical_name == "Deutsche Telekom AG"
        assert cp.short_name == "Telekom"
        # Canonical name + 2 additional aliases = 3 total
        assert len(cp.aliases) == 3

    @pytest.mark.asyncio
    async def test_list_counterparties(self, test_db):
        """Test listing counterparties."""
        await entities.create_counterparty("Company A")
        await entities.create_counterparty("Company B")
        await entities.create_counterparty("Other Corp")

        # List all
        all_cps = await entities.list_counterparties()
        assert len(all_cps) == 3

        # Search
        filtered = await entities.list_counterparties(search="Company")
        assert len(filtered) == 2

    @pytest.mark.asyncio
    async def test_update_counterparty(self, test_db):
        """Test updating a counterparty."""
        entity_id = await entities.create_counterparty("Old Name")

        updated = await entities.update_counterparty(
            entity_id, canonical_name="New Name", notes="Updated"
        )

        assert updated is not None
        assert updated.canonical_name == "New Name"
        assert updated.notes == "Updated"

    @pytest.mark.asyncio
    async def test_delete_counterparty(self, test_db):
        """Test deleting a counterparty."""
        entity_id = await entities.create_counterparty("To Delete")

        success = await entities.delete_counterparty(entity_id)
        assert success is True

        # Verify deleted
        cp = await entities.get_counterparty(entity_id)
        assert cp is None

    @pytest.mark.asyncio
    async def test_add_and_remove_alias(self, test_db):
        """Test adding and removing aliases."""
        entity_id = await entities.create_counterparty("Test Corp")

        # Add alias
        success = await entities.add_counterparty_alias(entity_id, "TC")
        assert success is True

        cp = await entities.get_counterparty(entity_id)
        aliases = [a.alias for a in cp.aliases]
        assert "TC" in aliases

        # Try adding duplicate - should fail
        success = await entities.add_counterparty_alias(entity_id, "TC")
        assert success is False

        # Remove alias
        alias_id = next(a.id for a in cp.aliases if a.alias == "TC")
        success = await entities.remove_counterparty_alias(alias_id)
        assert success is True

    @pytest.mark.asyncio
    async def test_merge_counterparties(self, test_db):
        """Test merging two counterparties."""
        keep_id = await entities.create_counterparty("Main Corp", aliases=["MC"])
        merge_id = await entities.create_counterparty(
            "Subsidiary", aliases=["Sub", "S Corp"]
        )

        result = await entities.merge_counterparties(keep_id, merge_id)

        assert result is not None
        # Should have aliases from both
        aliases = [a.alias for a in result.aliases]
        assert "Main Corp" in aliases
        assert "MC" in aliases
        assert "Subsidiary" in aliases or "Sub" in aliases

        # Merged entity should be gone
        merged = await entities.get_counterparty(merge_id)
        assert merged is None


class TestPersonOperations:
    """Test person CRUD operations."""

    @pytest.mark.asyncio
    async def test_create_person(self, test_db):
        """Test creating a new person."""
        entity_id = await entities.create_person(
            canonical_name="Max Mustermann",
            first_name="Max",
            last_name="Mustermann",
            aliases=["M. Mustermann"],
        )

        assert entity_id is not None

        person = await entities.get_person(entity_id)
        assert person is not None
        assert person.canonical_name == "Max Mustermann"
        assert person.first_name == "Max"
        assert person.last_name == "Mustermann"
        assert len(person.aliases) == 2

    @pytest.mark.asyncio
    async def test_list_persons(self, test_db):
        """Test listing persons."""
        await entities.create_person("Alice Smith")
        await entities.create_person("Bob Smith")
        await entities.create_person("Charlie Brown")

        # List all
        all_persons = await entities.list_persons()
        assert len(all_persons) == 3

        # Search
        filtered = await entities.list_persons(search="Smith")
        assert len(filtered) == 2

    @pytest.mark.asyncio
    async def test_merge_persons(self, test_db):
        """Test merging two persons."""
        keep_id = await entities.create_person("John Doe", aliases=["J. Doe"])
        merge_id = await entities.create_person("Johnny Doe", aliases=["Johnny D."])

        result = await entities.merge_persons(keep_id, merge_id)

        assert result is not None
        aliases = [a.alias for a in result.aliases]
        assert "John Doe" in aliases

        # Merged person should be gone
        merged = await entities.get_person(merge_id)
        assert merged is None


class TestDocumentPersonLinking:
    """Test document-person many-to-many relationship."""

    @pytest.mark.asyncio
    async def test_link_person_to_document(self, seeded_db):
        """Test linking a person to a document."""
        person_id = await entities.create_person("Test Person")

        success = await entities.link_person_to_document(
            "doc-001", person_id, role="affected"
        )
        assert success is True

        # Verify link
        doc_persons = await entities.get_document_persons("doc-001")
        assert len(doc_persons) == 1
        assert doc_persons[0].person.id == person_id
        assert doc_persons[0].role == "affected"

    @pytest.mark.asyncio
    async def test_unlink_person_from_document(self, seeded_db):
        """Test unlinking a person from a document."""
        person_id = await entities.create_person("Test Person")
        await entities.link_person_to_document("doc-001", person_id)

        success = await entities.unlink_person_from_document("doc-001", person_id)
        assert success is True

        doc_persons = await entities.get_document_persons("doc-001")
        assert len(doc_persons) == 0

    @pytest.mark.asyncio
    async def test_get_person_documents(self, seeded_db):
        """Test getting all documents for a person."""
        person_id = await entities.create_person("Shared Person")
        await entities.link_person_to_document("doc-001", person_id)
        await entities.link_person_to_document("doc-002", person_id)

        doc_ids = await entities.get_person_documents(person_id)
        assert len(doc_ids) == 2
        assert "doc-001" in doc_ids
        assert "doc-002" in doc_ids


class TestDisambiguation:
    """Test entity disambiguation logic."""

    @pytest.mark.asyncio
    async def test_exact_match_counterparty(self, test_db):
        """Test exact alias match returns AUTO_MATCHED."""
        await entities.create_counterparty(
            "Deutsche Telekom AG", aliases=["Telekom", "T-Kom"]
        )

        result = await entities.find_counterparty_by_name("Telekom")

        assert result.status == DisambiguationStatus.AUTO_MATCHED
        assert result.matched_entity_id is not None

    @pytest.mark.asyncio
    async def test_fuzzy_match_counterparty(self, test_db):
        """Test fuzzy match returns PENDING with candidates."""
        await entities.create_counterparty("Deutsche Telekom AG", aliases=["Telekom"])

        # Similar but not exact - "Telekomm" has high similarity to "Telekom"
        result = await entities.find_counterparty_by_name("Telekomm")

        assert result.status == DisambiguationStatus.PENDING
        assert len(result.candidates) > 0
        assert result.candidates[0].entity_name == "Deutsche Telekom AG"

    @pytest.mark.asyncio
    async def test_no_match_counterparty(self, test_db):
        """Test no match returns UNMATCHED."""
        await entities.create_counterparty("Some Company")

        result = await entities.find_counterparty_by_name("Completely Different Corp")

        assert result.status == DisambiguationStatus.UNMATCHED
        assert len(result.candidates) == 0

    @pytest.mark.asyncio
    async def test_exact_match_person(self, test_db):
        """Test exact person alias match."""
        await entities.create_person("Max Mustermann", aliases=["M. Mustermann"])

        result = await entities.find_person_by_name("M. Mustermann")

        assert result.status == DisambiguationStatus.AUTO_MATCHED
        assert result.matched_entity_id is not None

    @pytest.mark.asyncio
    async def test_disambiguate_document(self, seeded_db):
        """Test full document disambiguation."""
        import aiosqlite
        from app.config import get_settings

        settings = get_settings()

        # Create entities
        cp_id = await entities.create_counterparty(
            "Power Company Inc", aliases=["Power Company", "Power Co"]
        )
        person_id = await entities.create_person("John Smith")

        # Update document with matching values
        async with aiosqlite.connect(settings.database_path) as db:
            await db.execute(
                """
                UPDATE documents
                SET counterparty = 'Power Company Inc', affected_person = 'John Smith'
                WHERE id = 'doc-001'
                """
            )
            await db.commit()

        # Run disambiguation
        cp_result, person_result = await entities.disambiguate_document("doc-001")

        # Should auto-match since exact aliases exist
        assert cp_result.status == DisambiguationStatus.AUTO_MATCHED
        assert person_result.status == DisambiguationStatus.AUTO_MATCHED

    @pytest.mark.asyncio
    async def test_resolve_counterparty_disambiguation(self, seeded_db):
        """Test resolving counterparty disambiguation."""
        cp_id = await entities.create_counterparty("Allianz Insurance")

        success = await entities.resolve_counterparty_disambiguation(
            doc_id="doc-002", entity_id=cp_id, add_alias=True
        )

        assert success is True

        # Check document was updated
        import aiosqlite
        from app.config import get_settings

        settings = get_settings()
        async with aiosqlite.connect(settings.database_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT counterparty_id, counterparty_disambiguation FROM documents WHERE id = ?",
                ("doc-002",),
            )
            row = await cursor.fetchone()
            assert row["counterparty_id"] == cp_id
            assert row["counterparty_disambiguation"] == "confirmed"

    @pytest.mark.asyncio
    async def test_resolve_person_disambiguation_with_new_entity(self, seeded_db):
        """Test resolving person disambiguation by creating new entity."""
        import aiosqlite
        from app.config import get_settings

        settings = get_settings()

        # Set affected_person on document
        async with aiosqlite.connect(settings.database_path) as db:
            await db.execute(
                "UPDATE documents SET affected_person = 'New Person Name' WHERE id = 'doc-001'"
            )
            await db.commit()

        # Resolve with entity_id=None to create new
        success = await entities.resolve_person_disambiguation(
            doc_id="doc-001", entity_id=None, add_alias=True
        )

        assert success is True

        # Check person was created and linked
        doc_persons = await entities.get_document_persons("doc-001")
        assert len(doc_persons) == 1
        assert doc_persons[0].person.canonical_name == "New Person Name"


class TestGetPendingDisambiguations:
    """Test retrieving pending disambiguations."""

    @pytest.mark.asyncio
    async def test_get_pending_with_candidates(self, seeded_db):
        """Test getting pending disambiguations with candidates."""
        import aiosqlite
        from app.config import get_settings

        settings = get_settings()

        # Create a matching counterparty
        await entities.create_counterparty("Power Company Inc", aliases=["Power Co"])

        # Set document as pending
        async with aiosqlite.connect(settings.database_path) as db:
            await db.execute(
                """
                UPDATE documents
                SET counterparty_disambiguation = 'pending',
                    persons_disambiguation = 'pending',
                    counterparty = 'Power Company',
                    affected_person = 'Unknown Person'
                WHERE id = 'doc-001'
                """
            )
            await db.commit()

        pending = await entities.get_pending_disambiguations()

        assert len(pending) >= 1
        doc = next((d for d in pending if d["document_id"] == "doc-001"), None)
        assert doc is not None
        assert doc["counterparty_raw"] == "Power Company"
        # Should have candidates for counterparty
        assert len(doc["counterparty_candidates"]) > 0
