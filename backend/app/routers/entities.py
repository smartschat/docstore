"""Entity management API endpoints."""

from fastapi import APIRouter, Depends, HTTPException

from app.auth import get_current_session
from app.models import (
    Counterparty,
    CounterpartyCreate,
    CounterpartyList,
    CounterpartyUpdate,
    DisambiguationResolve,
    DocumentDisambiguation,
    MergeRequest,
    Person,
    PersonCreate,
    PersonList,
    PersonUpdate,
)
from app.services import entities

router = APIRouter(prefix="/api/entities", tags=["entities"])


# ============== Counterparties ==============


@router.get("/counterparties", response_model=CounterpartyList)
async def list_counterparties(
    search: str | None = None,
    _: str = Depends(get_current_session),
):
    """List all counterparties, optionally filtered by search term."""
    items = await entities.list_counterparties(search)
    return CounterpartyList(items=items, total=len(items))


@router.post("/counterparties", response_model=Counterparty)
async def create_counterparty(
    data: CounterpartyCreate,
    _: str = Depends(get_current_session),
):
    """Create a new counterparty."""
    entity_id = await entities.create_counterparty(
        canonical_name=data.canonical_name,
        aliases=data.aliases,
        short_name=data.short_name,
        notes=data.notes,
    )
    result = await entities.get_counterparty(entity_id)
    if not result:
        raise HTTPException(status_code=500, detail="Failed to create counterparty")
    return result


@router.get("/counterparties/{entity_id}", response_model=Counterparty)
async def get_counterparty(
    entity_id: str,
    _: str = Depends(get_current_session),
):
    """Get a counterparty by ID."""
    result = await entities.get_counterparty(entity_id)
    if not result:
        raise HTTPException(status_code=404, detail="Counterparty not found")
    return result


@router.patch("/counterparties/{entity_id}", response_model=Counterparty)
async def update_counterparty(
    entity_id: str,
    data: CounterpartyUpdate,
    _: str = Depends(get_current_session),
):
    """Update a counterparty."""
    result = await entities.update_counterparty(
        entity_id=entity_id,
        canonical_name=data.canonical_name,
        short_name=data.short_name,
        notes=data.notes,
    )
    if not result:
        raise HTTPException(status_code=404, detail="Counterparty not found")
    return result


@router.delete("/counterparties/{entity_id}")
async def delete_counterparty(
    entity_id: str,
    _: str = Depends(get_current_session),
):
    """Delete a counterparty."""
    success = await entities.delete_counterparty(entity_id)
    if not success:
        raise HTTPException(status_code=404, detail="Counterparty not found")
    return {"message": "Counterparty deleted"}


@router.post("/counterparties/{entity_id}/aliases")
async def add_counterparty_alias(
    entity_id: str,
    alias: str,
    _: str = Depends(get_current_session),
):
    """Add an alias to a counterparty."""
    # Check entity exists
    cp = await entities.get_counterparty(entity_id)
    if not cp:
        raise HTTPException(status_code=404, detail="Counterparty not found")

    success = await entities.add_counterparty_alias(entity_id, alias)
    if not success:
        raise HTTPException(status_code=400, detail="Alias already exists")
    return {"message": "Alias added"}


@router.delete("/counterparties/{entity_id}/aliases/{alias_id}")
async def remove_counterparty_alias(
    entity_id: str,
    alias_id: int,
    _: str = Depends(get_current_session),
):
    """Remove an alias from a counterparty."""
    success = await entities.remove_counterparty_alias(alias_id)
    if not success:
        raise HTTPException(status_code=404, detail="Alias not found")
    return {"message": "Alias removed"}


@router.post("/counterparties/merge", response_model=Counterparty)
async def merge_counterparties(
    data: MergeRequest,
    _: str = Depends(get_current_session),
):
    """Merge two counterparties."""
    # Verify both exist
    keep = await entities.get_counterparty(data.keep_id)
    merge = await entities.get_counterparty(data.merge_id)

    if not keep:
        raise HTTPException(status_code=404, detail="Keep counterparty not found")
    if not merge:
        raise HTTPException(status_code=404, detail="Merge counterparty not found")

    result = await entities.merge_counterparties(data.keep_id, data.merge_id)
    if not result:
        raise HTTPException(status_code=500, detail="Failed to merge counterparties")
    return result


# ============== Persons ==============


@router.get("/persons", response_model=PersonList)
async def list_persons(
    search: str | None = None,
    _: str = Depends(get_current_session),
):
    """List all persons, optionally filtered by search term."""
    items = await entities.list_persons(search)
    return PersonList(items=items, total=len(items))


@router.post("/persons", response_model=Person)
async def create_person(
    data: PersonCreate,
    _: str = Depends(get_current_session),
):
    """Create a new person."""
    entity_id = await entities.create_person(
        canonical_name=data.canonical_name,
        aliases=data.aliases,
        first_name=data.first_name,
        last_name=data.last_name,
        notes=data.notes,
    )
    result = await entities.get_person(entity_id)
    if not result:
        raise HTTPException(status_code=500, detail="Failed to create person")
    return result


@router.get("/persons/{entity_id}", response_model=Person)
async def get_person(
    entity_id: str,
    _: str = Depends(get_current_session),
):
    """Get a person by ID."""
    result = await entities.get_person(entity_id)
    if not result:
        raise HTTPException(status_code=404, detail="Person not found")
    return result


@router.patch("/persons/{entity_id}", response_model=Person)
async def update_person(
    entity_id: str,
    data: PersonUpdate,
    _: str = Depends(get_current_session),
):
    """Update a person."""
    result = await entities.update_person(
        entity_id=entity_id,
        canonical_name=data.canonical_name,
        first_name=data.first_name,
        last_name=data.last_name,
        notes=data.notes,
    )
    if not result:
        raise HTTPException(status_code=404, detail="Person not found")
    return result


@router.delete("/persons/{entity_id}")
async def delete_person(
    entity_id: str,
    _: str = Depends(get_current_session),
):
    """Delete a person."""
    success = await entities.delete_person(entity_id)
    if not success:
        raise HTTPException(status_code=404, detail="Person not found")
    return {"message": "Person deleted"}


@router.post("/persons/{entity_id}/aliases")
async def add_person_alias(
    entity_id: str,
    alias: str,
    _: str = Depends(get_current_session),
):
    """Add an alias to a person."""
    person = await entities.get_person(entity_id)
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")

    success = await entities.add_person_alias(entity_id, alias)
    if not success:
        raise HTTPException(status_code=400, detail="Alias already exists")
    return {"message": "Alias added"}


@router.delete("/persons/{entity_id}/aliases/{alias_id}")
async def remove_person_alias(
    entity_id: str,
    alias_id: int,
    _: str = Depends(get_current_session),
):
    """Remove an alias from a person."""
    success = await entities.remove_person_alias(alias_id)
    if not success:
        raise HTTPException(status_code=404, detail="Alias not found")
    return {"message": "Alias removed"}


@router.post("/persons/merge", response_model=Person)
async def merge_persons(
    data: MergeRequest,
    _: str = Depends(get_current_session),
):
    """Merge two persons."""
    keep = await entities.get_person(data.keep_id)
    merge = await entities.get_person(data.merge_id)

    if not keep:
        raise HTTPException(status_code=404, detail="Keep person not found")
    if not merge:
        raise HTTPException(status_code=404, detail="Merge person not found")

    result = await entities.merge_persons(data.keep_id, data.merge_id)
    if not result:
        raise HTTPException(status_code=500, detail="Failed to merge persons")
    return result


# ============== Disambiguation ==============


@router.get("/disambiguation/pending", response_model=list[DocumentDisambiguation])
async def get_pending_disambiguations(
    _: str = Depends(get_current_session),
):
    """Get documents with pending disambiguation."""
    return await entities.get_pending_disambiguations()


@router.post("/disambiguation/{doc_id}/resolve")
async def resolve_disambiguation(
    doc_id: str,
    data: DisambiguationResolve,
    _: str = Depends(get_current_session),
):
    """Resolve disambiguation for a document."""
    if data.entity_type == "counterparty":
        success = await entities.resolve_counterparty_disambiguation(
            doc_id=doc_id,
            entity_id=data.entity_id,
            add_alias=data.add_alias,
        )
    elif data.entity_type == "person":
        success = await entities.resolve_person_disambiguation(
            doc_id=doc_id,
            entity_id=data.entity_id,
            add_alias=data.add_alias,
        )
    else:
        raise HTTPException(status_code=400, detail="Invalid entity_type")

    if not success:
        raise HTTPException(status_code=404, detail="Document not found")

    return {"message": "Disambiguation resolved"}
