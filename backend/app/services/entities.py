"""Entity management service for counterparties and persons."""

import uuid
from datetime import datetime
from difflib import SequenceMatcher

import aiosqlite

from app.config import get_settings
from app.models import (
    Alias,
    AliasSource,
    Counterparty,
    DisambiguationCandidate,
    DisambiguationResult,
    DisambiguationStatus,
    DocumentPerson,
    Person,
)

settings = get_settings()


def generate_id() -> str:
    """Generate a unique ID for entities."""
    return str(uuid.uuid4())


def similarity_score(s1: str, s2: str) -> float:
    """Calculate similarity between two strings."""
    return SequenceMatcher(None, s1.lower(), s2.lower()).ratio()


# ============== Counterparty CRUD ==============


async def create_counterparty(
    canonical_name: str,
    aliases: list[str] | None = None,
    short_name: str | None = None,
    notes: str | None = None,
) -> str:
    """Create a new counterparty with optional aliases."""
    entity_id = generate_id()
    now = datetime.utcnow().isoformat()

    async with aiosqlite.connect(settings.database_path) as db:
        await db.execute(
            """
            INSERT INTO counterparties (id, canonical_name, short_name, notes, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (entity_id, canonical_name, short_name, notes, now, now),
        )

        # Add canonical name as an alias
        await db.execute(
            """
            INSERT OR IGNORE INTO counterparty_aliases (counterparty_id, alias, source, created_at)
            VALUES (?, ?, 'manual', ?)
            """,
            (entity_id, canonical_name, now),
        )

        # Add additional aliases
        if aliases:
            for alias in aliases:
                if alias != canonical_name:
                    await db.execute(
                        """
                        INSERT OR IGNORE INTO counterparty_aliases (counterparty_id, alias, source, created_at)
                        VALUES (?, ?, 'manual', ?)
                        """,
                        (entity_id, alias, now),
                    )

        await db.commit()

    return entity_id


async def get_counterparty(entity_id: str) -> Counterparty | None:
    """Get a counterparty by ID with its aliases."""
    async with aiosqlite.connect(settings.database_path) as db:
        db.row_factory = aiosqlite.Row

        cursor = await db.execute(
            "SELECT * FROM counterparties WHERE id = ?", (entity_id,)
        )
        row = await cursor.fetchone()

        if not row:
            return None

        # Get aliases
        cursor = await db.execute(
            "SELECT * FROM counterparty_aliases WHERE counterparty_id = ?",
            (entity_id,),
        )
        alias_rows = await cursor.fetchall()

        aliases = [
            Alias(
                id=a["id"],
                alias=a["alias"],
                source=AliasSource(a["source"]) if a["source"] else AliasSource.MANUAL,
                created_at=datetime.fromisoformat(a["created_at"])
                if a["created_at"]
                else datetime.utcnow(),
            )
            for a in alias_rows
        ]

        return Counterparty(
            id=row["id"],
            canonical_name=row["canonical_name"],
            short_name=row["short_name"],
            notes=row["notes"],
            aliases=aliases,
            created_at=datetime.fromisoformat(row["created_at"])
            if row["created_at"]
            else datetime.utcnow(),
            updated_at=datetime.fromisoformat(row["updated_at"])
            if row["updated_at"]
            else datetime.utcnow(),
        )


async def list_counterparties(search: str | None = None) -> list[Counterparty]:
    """List all counterparties, optionally filtered by search term."""
    async with aiosqlite.connect(settings.database_path) as db:
        db.row_factory = aiosqlite.Row

        if search:
            # Search in canonical name, short name, and aliases
            cursor = await db.execute(
                """
                SELECT DISTINCT c.* FROM counterparties c
                LEFT JOIN counterparty_aliases a ON a.counterparty_id = c.id
                WHERE c.canonical_name LIKE ? OR c.short_name LIKE ? OR a.alias LIKE ?
                ORDER BY c.canonical_name
                """,
                (f"%{search}%", f"%{search}%", f"%{search}%"),
            )
        else:
            cursor = await db.execute(
                "SELECT * FROM counterparties ORDER BY canonical_name"
            )

        rows = await cursor.fetchall()

        counterparties = []
        for row in rows:
            cp = await get_counterparty(row["id"])
            if cp:
                counterparties.append(cp)

        return counterparties


async def update_counterparty(
    entity_id: str,
    canonical_name: str | None = None,
    short_name: str | None = None,
    notes: str | None = None,
) -> Counterparty | None:
    """Update a counterparty's fields."""
    async with aiosqlite.connect(settings.database_path) as db:
        updates = []
        params = []

        if canonical_name is not None:
            updates.append("canonical_name = ?")
            params.append(canonical_name)
        if short_name is not None:
            updates.append("short_name = ?")
            params.append(short_name)
        if notes is not None:
            updates.append("notes = ?")
            params.append(notes)

        if updates:
            updates.append("updated_at = ?")
            params.append(datetime.utcnow().isoformat())
            params.append(entity_id)

            await db.execute(
                f"UPDATE counterparties SET {', '.join(updates)} WHERE id = ?",
                params,
            )
            await db.commit()

    return await get_counterparty(entity_id)


async def delete_counterparty(entity_id: str) -> bool:
    """Delete a counterparty and unlink from documents."""
    async with aiosqlite.connect(settings.database_path) as db:
        # Unlink documents
        await db.execute(
            "UPDATE documents SET counterparty_id = NULL WHERE counterparty_id = ?",
            (entity_id,),
        )

        # Delete counterparty (cascades to aliases)
        cursor = await db.execute(
            "DELETE FROM counterparties WHERE id = ?", (entity_id,)
        )
        await db.commit()

        return cursor.rowcount > 0


async def add_counterparty_alias(
    entity_id: str, alias: str, source: str = "manual"
) -> bool:
    """Add an alias to a counterparty."""
    async with aiosqlite.connect(settings.database_path) as db:
        try:
            await db.execute(
                """
                INSERT INTO counterparty_aliases (counterparty_id, alias, source, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (entity_id, alias, source, datetime.utcnow().isoformat()),
            )
            await db.commit()
            return True
        except aiosqlite.IntegrityError:
            # Alias already exists
            return False


async def remove_counterparty_alias(alias_id: int) -> bool:
    """Remove an alias from a counterparty."""
    async with aiosqlite.connect(settings.database_path) as db:
        cursor = await db.execute(
            "DELETE FROM counterparty_aliases WHERE id = ?", (alias_id,)
        )
        await db.commit()
        return cursor.rowcount > 0


async def merge_counterparties(keep_id: str, merge_id: str) -> Counterparty | None:
    """Merge two counterparties, keeping one and moving aliases from the other."""
    async with aiosqlite.connect(settings.database_path) as db:
        # Move aliases from merge_id to keep_id
        await db.execute(
            """
            UPDATE OR IGNORE counterparty_aliases
            SET counterparty_id = ?, source = 'merged'
            WHERE counterparty_id = ?
            """,
            (keep_id, merge_id),
        )

        # Update documents to point to keep_id
        await db.execute(
            "UPDATE documents SET counterparty_id = ? WHERE counterparty_id = ?",
            (keep_id, merge_id),
        )

        # Delete the merged counterparty
        await db.execute("DELETE FROM counterparties WHERE id = ?", (merge_id,))

        await db.commit()

    return await get_counterparty(keep_id)


# ============== Person CRUD ==============


async def create_person(
    canonical_name: str,
    aliases: list[str] | None = None,
    first_name: str | None = None,
    last_name: str | None = None,
    notes: str | None = None,
) -> str:
    """Create a new person with optional aliases."""
    entity_id = generate_id()
    now = datetime.utcnow().isoformat()

    async with aiosqlite.connect(settings.database_path) as db:
        await db.execute(
            """
            INSERT INTO persons (id, canonical_name, first_name, last_name, notes, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (entity_id, canonical_name, first_name, last_name, notes, now, now),
        )

        # Add canonical name as an alias
        await db.execute(
            """
            INSERT OR IGNORE INTO person_aliases (person_id, alias, source, created_at)
            VALUES (?, ?, 'manual', ?)
            """,
            (entity_id, canonical_name, now),
        )

        # Add additional aliases
        if aliases:
            for alias in aliases:
                if alias != canonical_name:
                    await db.execute(
                        """
                        INSERT OR IGNORE INTO person_aliases (person_id, alias, source, created_at)
                        VALUES (?, ?, 'manual', ?)
                        """,
                        (entity_id, alias, now),
                    )

        await db.commit()

    return entity_id


async def get_person(entity_id: str) -> Person | None:
    """Get a person by ID with their aliases."""
    async with aiosqlite.connect(settings.database_path) as db:
        db.row_factory = aiosqlite.Row

        cursor = await db.execute("SELECT * FROM persons WHERE id = ?", (entity_id,))
        row = await cursor.fetchone()

        if not row:
            return None

        # Get aliases
        cursor = await db.execute(
            "SELECT * FROM person_aliases WHERE person_id = ?", (entity_id,)
        )
        alias_rows = await cursor.fetchall()

        aliases = [
            Alias(
                id=a["id"],
                alias=a["alias"],
                source=AliasSource(a["source"]) if a["source"] else AliasSource.MANUAL,
                created_at=datetime.fromisoformat(a["created_at"])
                if a["created_at"]
                else datetime.utcnow(),
            )
            for a in alias_rows
        ]

        return Person(
            id=row["id"],
            canonical_name=row["canonical_name"],
            first_name=row["first_name"],
            last_name=row["last_name"],
            notes=row["notes"],
            aliases=aliases,
            created_at=datetime.fromisoformat(row["created_at"])
            if row["created_at"]
            else datetime.utcnow(),
            updated_at=datetime.fromisoformat(row["updated_at"])
            if row["updated_at"]
            else datetime.utcnow(),
        )


async def list_persons(search: str | None = None) -> list[Person]:
    """List all persons, optionally filtered by search term."""
    async with aiosqlite.connect(settings.database_path) as db:
        db.row_factory = aiosqlite.Row

        if search:
            cursor = await db.execute(
                """
                SELECT DISTINCT p.* FROM persons p
                LEFT JOIN person_aliases a ON a.person_id = p.id
                WHERE p.canonical_name LIKE ? OR p.first_name LIKE ?
                    OR p.last_name LIKE ? OR a.alias LIKE ?
                ORDER BY p.canonical_name
                """,
                (f"%{search}%", f"%{search}%", f"%{search}%", f"%{search}%"),
            )
        else:
            cursor = await db.execute("SELECT * FROM persons ORDER BY canonical_name")

        rows = await cursor.fetchall()

        persons = []
        for row in rows:
            p = await get_person(row["id"])
            if p:
                persons.append(p)

        return persons


async def update_person(
    entity_id: str,
    canonical_name: str | None = None,
    first_name: str | None = None,
    last_name: str | None = None,
    notes: str | None = None,
) -> Person | None:
    """Update a person's fields."""
    async with aiosqlite.connect(settings.database_path) as db:
        updates = []
        params = []

        if canonical_name is not None:
            updates.append("canonical_name = ?")
            params.append(canonical_name)
        if first_name is not None:
            updates.append("first_name = ?")
            params.append(first_name)
        if last_name is not None:
            updates.append("last_name = ?")
            params.append(last_name)
        if notes is not None:
            updates.append("notes = ?")
            params.append(notes)

        if updates:
            updates.append("updated_at = ?")
            params.append(datetime.utcnow().isoformat())
            params.append(entity_id)

            await db.execute(
                f"UPDATE persons SET {', '.join(updates)} WHERE id = ?",
                params,
            )
            await db.commit()

    return await get_person(entity_id)


async def delete_person(entity_id: str) -> bool:
    """Delete a person and unlink from documents."""
    async with aiosqlite.connect(settings.database_path) as db:
        # Unlink documents
        await db.execute(
            "DELETE FROM document_persons WHERE person_id = ?", (entity_id,)
        )

        # Delete person (cascades to aliases)
        cursor = await db.execute("DELETE FROM persons WHERE id = ?", (entity_id,))
        await db.commit()

        return cursor.rowcount > 0


async def add_person_alias(entity_id: str, alias: str, source: str = "manual") -> bool:
    """Add an alias to a person."""
    async with aiosqlite.connect(settings.database_path) as db:
        try:
            await db.execute(
                """
                INSERT INTO person_aliases (person_id, alias, source, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (entity_id, alias, source, datetime.utcnow().isoformat()),
            )
            await db.commit()
            return True
        except aiosqlite.IntegrityError:
            return False


async def remove_person_alias(alias_id: int) -> bool:
    """Remove an alias from a person."""
    async with aiosqlite.connect(settings.database_path) as db:
        cursor = await db.execute(
            "DELETE FROM person_aliases WHERE id = ?", (alias_id,)
        )
        await db.commit()
        return cursor.rowcount > 0


async def merge_persons(keep_id: str, merge_id: str) -> Person | None:
    """Merge two persons, keeping one and moving aliases from the other."""
    async with aiosqlite.connect(settings.database_path) as db:
        # Move aliases from merge_id to keep_id
        await db.execute(
            """
            UPDATE OR IGNORE person_aliases
            SET person_id = ?, source = 'merged'
            WHERE person_id = ?
            """,
            (keep_id, merge_id),
        )

        # Update document_persons to point to keep_id
        await db.execute(
            """
            UPDATE OR IGNORE document_persons
            SET person_id = ?
            WHERE person_id = ?
            """,
            (keep_id, merge_id),
        )

        # Delete any remaining document_persons (duplicates)
        await db.execute(
            "DELETE FROM document_persons WHERE person_id = ?", (merge_id,)
        )

        # Delete the merged person
        await db.execute("DELETE FROM persons WHERE id = ?", (merge_id,))

        await db.commit()

    return await get_person(keep_id)


# ============== Document-Person Linking ==============


async def link_person_to_document(
    doc_id: str, person_id: str, role: str = "affected"
) -> bool:
    """Link a person to a document."""
    async with aiosqlite.connect(settings.database_path) as db:
        try:
            await db.execute(
                """
                INSERT INTO document_persons (document_id, person_id, role, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (doc_id, person_id, role, datetime.utcnow().isoformat()),
            )
            await db.commit()
            return True
        except aiosqlite.IntegrityError:
            return False


async def unlink_person_from_document(doc_id: str, person_id: str) -> bool:
    """Unlink a person from a document."""
    async with aiosqlite.connect(settings.database_path) as db:
        cursor = await db.execute(
            "DELETE FROM document_persons WHERE document_id = ? AND person_id = ?",
            (doc_id, person_id),
        )
        await db.commit()
        return cursor.rowcount > 0


async def get_document_persons(doc_id: str) -> list[DocumentPerson]:
    """Get all persons linked to a document."""
    async with aiosqlite.connect(settings.database_path) as db:
        db.row_factory = aiosqlite.Row

        cursor = await db.execute(
            """
            SELECT dp.role, p.id as person_id
            FROM document_persons dp
            JOIN persons p ON p.id = dp.person_id
            WHERE dp.document_id = ?
            """,
            (doc_id,),
        )
        rows = await cursor.fetchall()

        result = []
        for row in rows:
            person = await get_person(row["person_id"])
            if person:
                result.append(DocumentPerson(person=person, role=row["role"]))

        return result


async def get_person_documents(person_id: str) -> list[str]:
    """Get all document IDs linked to a person."""
    async with aiosqlite.connect(settings.database_path) as db:
        cursor = await db.execute(
            "SELECT document_id FROM document_persons WHERE person_id = ?",
            (person_id,),
        )
        rows = await cursor.fetchall()
        return [row[0] for row in rows]


# ============== Disambiguation ==============


async def find_counterparty_by_name(name: str) -> DisambiguationResult:
    """Find a counterparty by name using exact alias match then fuzzy matching."""
    if not name:
        return DisambiguationResult(
            raw_name=name or "",
            status=DisambiguationStatus.UNMATCHED,
        )

    async with aiosqlite.connect(settings.database_path) as db:
        db.row_factory = aiosqlite.Row

        # Step 1: Exact alias match (case-insensitive)
        cursor = await db.execute(
            """
            SELECT c.id, c.canonical_name, a.alias
            FROM counterparties c
            JOIN counterparty_aliases a ON a.counterparty_id = c.id
            WHERE a.alias = ? COLLATE NOCASE
            """,
            (name,),
        )
        exact_match = await cursor.fetchone()

        if exact_match:
            return DisambiguationResult(
                raw_name=name,
                status=DisambiguationStatus.AUTO_MATCHED,
                matched_entity_id=exact_match["id"],
            )

        # Step 2: Find candidates using fuzzy matching
        cursor = await db.execute(
            "SELECT id, canonical_name FROM counterparties"
        )
        all_counterparties = await cursor.fetchall()

        candidates = []
        for cp in all_counterparties:
            # Check canonical name
            score = similarity_score(name, cp["canonical_name"])
            if score > 0.6:
                candidates.append(
                    DisambiguationCandidate(
                        entity_id=cp["id"],
                        entity_name=cp["canonical_name"],
                        score=score,
                    )
                )
            else:
                # Check aliases
                cursor = await db.execute(
                    "SELECT alias FROM counterparty_aliases WHERE counterparty_id = ?",
                    (cp["id"],),
                )
                aliases = await cursor.fetchall()

                for alias_row in aliases:
                    alias_score = similarity_score(name, alias_row[0])
                    if alias_score > 0.6:
                        candidates.append(
                            DisambiguationCandidate(
                                entity_id=cp["id"],
                                entity_name=cp["canonical_name"],
                                score=alias_score,
                                matched_alias=alias_row[0],
                            )
                        )
                        break

        # Sort by score descending
        candidates.sort(key=lambda x: x.score, reverse=True)

        return DisambiguationResult(
            raw_name=name,
            status=DisambiguationStatus.PENDING if candidates else DisambiguationStatus.UNMATCHED,
            candidates=candidates[:5],  # Top 5 candidates
        )


async def find_person_by_name(name: str) -> DisambiguationResult:
    """Find a person by name using exact alias match then fuzzy matching."""
    if not name:
        return DisambiguationResult(
            raw_name=name or "",
            status=DisambiguationStatus.UNMATCHED,
        )

    async with aiosqlite.connect(settings.database_path) as db:
        db.row_factory = aiosqlite.Row

        # Step 1: Exact alias match (case-insensitive)
        cursor = await db.execute(
            """
            SELECT p.id, p.canonical_name, a.alias
            FROM persons p
            JOIN person_aliases a ON a.person_id = p.id
            WHERE a.alias = ? COLLATE NOCASE
            """,
            (name,),
        )
        exact_match = await cursor.fetchone()

        if exact_match:
            return DisambiguationResult(
                raw_name=name,
                status=DisambiguationStatus.AUTO_MATCHED,
                matched_entity_id=exact_match["id"],
            )

        # Step 2: Find candidates using fuzzy matching
        cursor = await db.execute("SELECT id, canonical_name FROM persons")
        all_persons = await cursor.fetchall()

        candidates = []
        for p in all_persons:
            score = similarity_score(name, p["canonical_name"])
            if score > 0.6:
                candidates.append(
                    DisambiguationCandidate(
                        entity_id=p["id"],
                        entity_name=p["canonical_name"],
                        score=score,
                    )
                )
            else:
                # Check aliases
                cursor = await db.execute(
                    "SELECT alias FROM person_aliases WHERE person_id = ?",
                    (p["id"],),
                )
                aliases = await cursor.fetchall()

                for alias_row in aliases:
                    alias_score = similarity_score(name, alias_row[0])
                    if alias_score > 0.6:
                        candidates.append(
                            DisambiguationCandidate(
                                entity_id=p["id"],
                                entity_name=p["canonical_name"],
                                score=alias_score,
                                matched_alias=alias_row[0],
                            )
                        )
                        break

        candidates.sort(key=lambda x: x.score, reverse=True)

        return DisambiguationResult(
            raw_name=name,
            status=DisambiguationStatus.PENDING if candidates else DisambiguationStatus.UNMATCHED,
            candidates=candidates[:5],
        )


async def disambiguate_document(doc_id: str) -> tuple[DisambiguationResult, DisambiguationResult]:
    """Run disambiguation on a document's extracted counterparty and affected_person."""
    # Get document data first
    async with aiosqlite.connect(settings.database_path) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT counterparty, affected_person FROM documents WHERE id = ?",
            (doc_id,),
        )
        row = await cursor.fetchone()

    if not row:
        return (
            DisambiguationResult(raw_name="", status=DisambiguationStatus.UNMATCHED),
            DisambiguationResult(raw_name="", status=DisambiguationStatus.UNMATCHED),
        )

    # Find matches (these don't hold locks)
    counterparty_result = await find_counterparty_by_name(row["counterparty"])
    person_result = await find_person_by_name(row["affected_person"])

    # Update counterparty disambiguation
    if counterparty_result.status == DisambiguationStatus.AUTO_MATCHED:
        async with aiosqlite.connect(settings.database_path) as db:
            await db.execute(
                """
                UPDATE documents
                SET counterparty_id = ?, counterparty_disambiguation = 'auto_matched'
                WHERE id = ?
                """,
                (counterparty_result.matched_entity_id, doc_id),
            )
            await db.commit()

        # Add raw name as alias if it's new (for future matching)
        if row["counterparty"]:
            await add_counterparty_alias(
                counterparty_result.matched_entity_id,
                row["counterparty"],
                "llm_extracted",
            )
    elif counterparty_result.status == DisambiguationStatus.PENDING:
        async with aiosqlite.connect(settings.database_path) as db:
            await db.execute(
                "UPDATE documents SET counterparty_disambiguation = 'pending' WHERE id = ?",
                (doc_id,),
            )
            await db.commit()
    elif counterparty_result.status == DisambiguationStatus.UNMATCHED:
        async with aiosqlite.connect(settings.database_path) as db:
            await db.execute(
                "UPDATE documents SET counterparty_disambiguation = 'unmatched' WHERE id = ?",
                (doc_id,),
            )
            await db.commit()

    # Update person disambiguation
    if person_result.status == DisambiguationStatus.AUTO_MATCHED:
        # Link person to document
        await link_person_to_document(doc_id, person_result.matched_entity_id)
        async with aiosqlite.connect(settings.database_path) as db:
            await db.execute(
                "UPDATE documents SET persons_disambiguation = 'auto_matched' WHERE id = ?",
                (doc_id,),
            )
            await db.commit()

        # Add raw name as alias if it's new (for future matching)
        if row["affected_person"]:
            await add_person_alias(
                person_result.matched_entity_id,
                row["affected_person"],
                "llm_extracted",
            )
    elif person_result.status == DisambiguationStatus.PENDING:
        async with aiosqlite.connect(settings.database_path) as db:
            await db.execute(
                "UPDATE documents SET persons_disambiguation = 'pending' WHERE id = ?",
                (doc_id,),
            )
            await db.commit()
    elif person_result.status == DisambiguationStatus.UNMATCHED:
        async with aiosqlite.connect(settings.database_path) as db:
            await db.execute(
                "UPDATE documents SET persons_disambiguation = 'unmatched' WHERE id = ?",
                (doc_id,),
            )
            await db.commit()

    return counterparty_result, person_result


async def get_pending_disambiguations() -> list[dict]:
    """Get documents with pending disambiguation."""
    async with aiosqlite.connect(settings.database_path) as db:
        db.row_factory = aiosqlite.Row

        # Only get documents that have pending status AND have raw values to disambiguate
        cursor = await db.execute(
            """
            SELECT id, filename, title, counterparty, affected_person,
                   counterparty_disambiguation, persons_disambiguation
            FROM documents
            WHERE (counterparty_disambiguation = 'pending' AND counterparty IS NOT NULL AND counterparty != '')
               OR (persons_disambiguation = 'pending' AND affected_person IS NOT NULL AND affected_person != '')
            ORDER BY created_at DESC
            """
        )
        rows = await cursor.fetchall()

        results = []
        for row in rows:
            doc_data = {
                "document_id": row["id"],
                "filename": row["filename"],
                "title": row["title"],
                "counterparty_raw": row["counterparty"],
                "counterparty_candidates": [],
                "affected_person_raw": row["affected_person"],
                "person_candidates": [],
            }

            has_pending_items = False

            if row["counterparty_disambiguation"] == "pending" and row["counterparty"]:
                result = await find_counterparty_by_name(row["counterparty"])
                doc_data["counterparty_candidates"] = [c.model_dump() for c in result.candidates]
                has_pending_items = True

            if row["persons_disambiguation"] == "pending" and row["affected_person"]:
                result = await find_person_by_name(row["affected_person"])
                doc_data["person_candidates"] = [c.model_dump() for c in result.candidates]
                has_pending_items = True

            # Only include documents that actually have something to review
            if has_pending_items:
                results.append(doc_data)

        return results


async def resolve_counterparty_disambiguation(
    doc_id: str,
    entity_id: str | None,
    add_alias: bool = True,
) -> bool:
    """Resolve counterparty disambiguation for a document."""
    # Get raw name first
    async with aiosqlite.connect(settings.database_path) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT counterparty FROM documents WHERE id = ?", (doc_id,)
        )
        row = await cursor.fetchone()

        if not row:
            return False

        raw_name = row["counterparty"]

    # Process outside the connection to avoid locking
    if entity_id:
        # Link to existing entity
        async with aiosqlite.connect(settings.database_path) as db:
            await db.execute(
                """
                UPDATE documents
                SET counterparty_id = ?, counterparty_disambiguation = 'confirmed'
                WHERE id = ?
                """,
                (entity_id, doc_id),
            )
            await db.commit()

        # Add raw name as alias
        if add_alias and raw_name:
            await add_counterparty_alias(entity_id, raw_name, "llm_extracted")
    else:
        # Create new entity from raw name
        if raw_name:
            new_id = await create_counterparty(raw_name)
            async with aiosqlite.connect(settings.database_path) as db:
                await db.execute(
                    """
                    UPDATE documents
                    SET counterparty_id = ?, counterparty_disambiguation = 'confirmed'
                    WHERE id = ?
                    """,
                    (new_id, doc_id),
                )
                await db.commit()

    return True


async def resolve_person_disambiguation(
    doc_id: str,
    entity_id: str | None,
    add_alias: bool = True,
    role: str = "affected",
) -> bool:
    """Resolve person disambiguation for a document."""
    # Get raw name first
    async with aiosqlite.connect(settings.database_path) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT affected_person FROM documents WHERE id = ?", (doc_id,)
        )
        row = await cursor.fetchone()

        if not row:
            return False

        raw_name = row["affected_person"]

    # Process outside the connection to avoid locking
    if entity_id:
        # Link to existing entity
        await link_person_to_document(doc_id, entity_id, role)

        async with aiosqlite.connect(settings.database_path) as db:
            await db.execute(
                "UPDATE documents SET persons_disambiguation = 'confirmed' WHERE id = ?",
                (doc_id,),
            )
            await db.commit()

        # Add raw name as alias
        if add_alias and raw_name:
            await add_person_alias(entity_id, raw_name, "llm_extracted")
    else:
        # Create new entity from raw name
        if raw_name:
            new_id = await create_person(raw_name)
            await link_person_to_document(doc_id, new_id, role)

            async with aiosqlite.connect(settings.database_path) as db:
                await db.execute(
                    "UPDATE documents SET persons_disambiguation = 'confirmed' WHERE id = ?",
                    (doc_id,),
                )
                await db.commit()

    return True
