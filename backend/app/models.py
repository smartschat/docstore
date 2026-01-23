"""Pydantic models for API requests and responses."""

from datetime import date, datetime
from typing import Optional
from enum import Enum
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
    # Extracted fields
    title: Optional[str] = None
    counterparty: Optional[str] = None
    affected_person: Optional[str] = None
    category: Optional[str] = None
    reference: Optional[str] = None
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
class DashboardStats(BaseModel):
    total_documents: int
    documents_by_category: dict[str, int]
    documents_by_status: dict[str, int]
    recent_documents: list[Document]


