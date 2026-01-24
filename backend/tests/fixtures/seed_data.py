"""Seed data for tests."""

SEED_DOCUMENTS = [
    {
        "id": "doc-001",
        "filename": "invoice_2024.pdf",
        "file_path": "/data/archive/invoice_2024.pdf",
        "file_hash": "abc123hash001",
        "file_size": 1024,
        "mime_type": "application/pdf",
        "raw_text": "Invoice from Power Company Inc. Total: $150.00 Date: January 15, 2024",
        "page_count": 1,
        "summary": "Electric bill for January 2024",
        "title": "Electric Bill January 2024",
        "category": "utilities",
        "counterparty": "Power Company Inc",
        "total_amount": 150.00,
        "document_date": "2024-01-15",
        "status": "completed",
        "extraction_status": "completed",
    },
    {
        "id": "doc-002",
        "filename": "insurance_policy.pdf",
        "file_path": "/data/archive/insurance_policy.pdf",
        "file_hash": "def456hash002",
        "file_size": 2048,
        "mime_type": "application/pdf",
        "raw_text": "Insurance Policy from Allianz. Policy Number: POL-12345",
        "page_count": 3,
        "summary": "Home insurance policy",
        "title": "Allianz Home Insurance",
        "category": "insurance",
        "counterparty": "Allianz",
        "document_date": "2024-02-01",
        "status": "completed",
        "extraction_status": "completed",
    },
    {
        "id": "doc-003",
        "filename": "pending_doc.pdf",
        "file_path": "/data/archive/pending_doc.pdf",
        "file_hash": "ghi789hash003",
        "file_size": 512,
        "mime_type": "application/pdf",
        "raw_text": "Some document text",
        "page_count": 1,
        "summary": None,
        "title": None,
        "category": None,
        "counterparty": None,
        "document_date": None,
        "status": "processing",
        "extraction_status": "pending",
    },
]

SEED_TAGS = [
    {"id": 1, "name": "important"},
    {"id": 2, "name": "archive"},
    {"id": 3, "name": "2024"},
]

SEED_DOCUMENT_TAGS = [
    {"doc_id": "doc-001", "tag_id": 1},
    {"doc_id": "doc-001", "tag_id": 3},
    {"doc_id": "doc-002", "tag_id": 2},
]
