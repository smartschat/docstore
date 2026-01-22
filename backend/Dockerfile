# Backend Dockerfile
FROM python:3.11-slim

# Install system dependencies for OCR and uv
RUN apt-get update && apt-get install -y --no-install-recommends \
    ocrmypdf \
    tesseract-ocr \
    tesseract-ocr-deu \
    tesseract-ocr-eng \
    poppler-utils \
    libmagic1 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Copy dependency files
COPY pyproject.toml uv.lock* ./

# Install Python dependencies with uv
RUN uv sync --frozen --no-dev

# Copy application code
COPY app/ ./app/

# Create data directories
RUN mkdir -p /app/data/inbox /app/data/archive

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV DATA_DIR=/app/data
ENV INBOX_DIR=/app/data/inbox
ENV ARCHIVE_DIR=/app/data/archive
ENV DATABASE_PATH=/app/data/docstore.db

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
