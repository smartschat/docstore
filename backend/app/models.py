"""Pydantic models for API requests and responses."""

from datetime import date, datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel


class DocumentStatus(str, Enum):
    """Document processing status."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


# Base models
class TagBase(BaseModel):
    name: str


class TagCreate(TagBase):
    pass


class Tag(TagBase):
    id: int

    class Config:
        from_attributes = True


class DocumentBase(BaseModel):
    filename: str


class DocumentCreate(DocumentBase):
    pass


class DocumentUpdate(BaseModel):
    """Fields that can be manually updated."""

    title: Optional[str] = None
    counterparty: Optional[str] = None
    affected_person: Optional[str] = None
    category: Optional[str] = None
    reference: Optional[str] = None
    document_date: Optional[date] = None
    summary: Optional[str] = None
    # Entity linking
    counterparty_id: Optional[str] = None
    # Control whether to add extracted name as alias (not persisted)
    add_counterparty_alias: Optional[bool] = None


class LinkedPerson(BaseModel):
    id: str
    canonical_name: str
    role: str = "affected"


class Document(DocumentBase):
    id: str
    file_path: str
    file_hash: str
    file_size: Optional[int] = None
    mime_type: Optional[str] = None
    raw_text: Optional[str] = None
    page_count: Optional[int] = None
    summary: Optional[str] = None
    document_date: Optional[date] = None
    created_at: datetime
    processed_at: Optional[datetime] = None
    status: DocumentStatus = DocumentStatus.PENDING
    extraction_status: Optional[str] = None  # pending, completed, or None
    # Extracted fields (raw text values)
    title: Optional[str] = None
    counterparty: Optional[str] = None  # Raw extracted counterparty name
    affected_person: Optional[str] = None  # Raw extracted person name
    category: Optional[str] = None
    reference: Optional[str] = None
    # Entity disambiguation
    counterparty_id: Optional[str] = None
    counterparty_disambiguation: Optional[str] = None
    persons_disambiguation: Optional[str] = None
    # Resolved entity names (for display)
    counterparty_name: Optional[str] = None  # Canonical name of linked counterparty
    linked_persons: list[LinkedPerson] = []  # Linked persons with roles
    # Relations
    tags: list[Tag] = []

    class Config:
        from_attributes = True


class DocumentList(BaseModel):
    """Paginated document list response."""

    items: list[Document]
    total: int
    page: int
    page_size: int


# Search models
class SearchQuery(BaseModel):
    query: str
    search_type: str = "hybrid"  # keyword, semantic, hybrid
    category: Optional[str] = None
    affected_person: Optional[str] = None
    tags: Optional[list[str]] = None
    date_from: Optional[date] = None
    date_to: Optional[date] = None
    page: int = 1
    page_size: int = 20


class SearchResult(BaseModel):
    document: Document
    score: float
    snippet: Optional[str] = None


class SearchResponse(BaseModel):
    results: list[SearchResult]
    total: int
    query: str


# Q&A models
class QuestionRequest(BaseModel):
    question: str
    doc_ids: Optional[list[str]] = None  # Limit to specific documents


class QuestionResponse(BaseModel):
    answer: str
    sources: list[Document]
    confidence: Optional[float] = None


# Auth models
class LoginRequest(BaseModel):
    password: str


class LoginResponse(BaseModel):
    success: bool
    message: str = ""


class AuthStatus(BaseModel):
    authenticated: bool


# Stats models
class EntityCount(BaseModel):
    id: str
    name: str
    count: int


class DashboardStats(BaseModel):
    total_documents: int
    documents_by_category: dict[str, int]
    documents_by_status: dict[str, int]
    recent_documents: list[Document]
    top_counterparties: list[EntityCount] = []
    top_persons: list[EntityCount] = []
    pending_reviews: int = 0


# Entity models
class DisambiguationStatus(str, Enum):
    """Entity disambiguation status."""

    PENDING = "pending"
    AUTO_MATCHED = "auto_matched"
    CONFIRMED = "confirmed"
    UNMATCHED = "unmatched"


class AliasSource(str, Enum):
    """Source of an alias."""

    MANUAL = "manual"
    LLM_EXTRACTED = "llm_extracted"
    MERGED = "merged"


class AliasBase(BaseModel):
    alias: str
    source: AliasSource = AliasSource.MANUAL


class Alias(AliasBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


class CounterpartyBase(BaseModel):
    canonical_name: str
    short_name: Optional[str] = None
    notes: Optional[str] = None


class CounterpartyCreate(CounterpartyBase):
    aliases: Optional[list[str]] = None


class CounterpartyUpdate(BaseModel):
    canonical_name: Optional[str] = None
    short_name: Optional[str] = None
    notes: Optional[str] = None


class Counterparty(CounterpartyBase):
    id: str
    aliases: list[Alias] = []
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CounterpartyList(BaseModel):
    items: list[Counterparty]
    total: int


class PersonBase(BaseModel):
    canonical_name: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    notes: Optional[str] = None


class PersonCreate(PersonBase):
    aliases: Optional[list[str]] = None


class PersonUpdate(BaseModel):
    canonical_name: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    notes: Optional[str] = None


class Person(PersonBase):
    id: str
    aliases: list[Alias] = []
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class PersonList(BaseModel):
    items: list[Person]
    total: int


class DocumentPerson(BaseModel):
    person: Person
    role: str = "affected"


class DocumentPersonLink(BaseModel):
    person_id: str
    role: str = "affected"
    add_alias: bool = True


class DisambiguationCandidate(BaseModel):
    entity_id: str
    entity_name: str
    score: float
    matched_alias: Optional[str] = None


class DisambiguationResult(BaseModel):
    raw_name: str
    status: DisambiguationStatus
    matched_entity_id: Optional[str] = None
    candidates: list[DisambiguationCandidate] = []


class DocumentDisambiguation(BaseModel):
    document_id: str
    filename: str
    title: Optional[str]
    counterparty_raw: Optional[str]
    counterparty_candidates: list[DisambiguationCandidate] = []
    affected_person_raw: Optional[str]
    person_candidates: list[DisambiguationCandidate] = []


class DisambiguationResolve(BaseModel):
    entity_type: str  # 'counterparty' or 'person'
    entity_id: Optional[str] = None  # None = create new entity
    add_alias: bool = True  # Add raw name as alias for future matching


class MergeRequest(BaseModel):
    keep_id: str
    merge_id: str
