.PHONY: help install dev backend frontend build clean lint test test-unit test-integration test-coverage docker-build docker-run docker-stop db-init process-inbox add update pre-commit

# Default target
help:
	@echo "DocStore - Document Digitization System"
	@echo ""
	@echo "Usage:"
	@echo "  make install       Install all dependencies"
	@echo "  make dev           Run both backend and frontend in development mode"
	@echo "  make backend       Run backend only"
	@echo "  make frontend      Run frontend only"
	@echo "  make build         Build frontend for production"
	@echo "  make lint          Run linters (ruff + svelte-check)"
	@echo "  make test          Run all tests"
	@echo "  make test-unit     Run unit tests only"
	@echo "  make test-integration Run integration tests only"
	@echo "  make test-coverage Run tests with coverage report"
	@echo "  make clean         Remove build artifacts"
	@echo "  make docker-build  Build production Docker image"
	@echo "  make docker-run    Run production container locally"
	@echo "  make docker-stop   Stop production container"
	@echo "  make db-init       Initialize database"
	@echo "  make process-inbox Process files in inbox"
	@echo "  make add pkg=name  Add a Python dependency"
	@echo "  make update        Update all dependencies"
	@echo ""

# Install dependencies
install:
	@echo "Installing backend dependencies with uv..."
	cd backend && uv sync
	@echo "Installing frontend dependencies..."
	cd frontend && npm install
	@echo "Creating data directories..."
	mkdir -p data/inbox data/archive
	@echo "Installing pre-commit hooks..."
	cd backend && uv run pre-commit install

# Development
dev:
	@echo "Starting development servers..."
	make -j2 backend frontend

backend:
	@echo "Starting backend..."
	cd backend && uv run python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

frontend:
	@echo "Starting frontend..."
	cd frontend && npm run dev

# Build
build:
	@echo "Building frontend..."
	cd frontend && npm run build
	@echo "Build complete. Static files in frontend/build/"

# Lint
lint:
	@echo "Running Python formatter check (ruff)..."
	cd backend && uv run ruff format --check .
	@echo "Running Python linter (ruff)..."
	cd backend && uv run ruff check .
	@echo "Running Svelte/TypeScript checker..."
	cd frontend && npm run check
	@echo "All checks passed!"

# Pre-commit hooks
pre-commit:
	@echo "Installing pre-commit hooks..."
	cd backend && uv run pre-commit install
	@echo "Pre-commit hooks installed!"

# Tests
test:
	@echo "Running all tests..."
	cd backend && uv run pytest

test-unit:
	@echo "Running unit tests..."
	cd backend && uv run pytest tests/unit -v

test-integration:
	@echo "Running integration tests..."
	cd backend && uv run pytest tests/integration -v

test-coverage:
	@echo "Running tests with coverage..."
	cd backend && uv run pytest --cov=app --cov-report=html --cov-report=term
	@echo "HTML coverage report: backend/htmlcov/index.html"

# Clean
clean:
	@echo "Cleaning build artifacts..."
	rm -rf frontend/build
	rm -rf frontend/.svelte-kit
	rm -rf backend/__pycache__
	rm -rf backend/app/__pycache__
	rm -rf backend/app/services/__pycache__
	rm -rf backend/app/routers/__pycache__
	rm -rf backend/.venv
	find . -name "*.pyc" -delete
	find . -name ".DS_Store" -delete

# Docker (local testing)
docker-build:
	docker build -t docstore .

docker-run:
	docker run -d --name docstore \
		-p 8000:8000 \
		-v docstore-data:/app/data \
		--env-file backend/.env \
		docstore

docker-stop:
	docker stop docstore && docker rm docstore

# Database
db-init:
	cd backend && uv run python -c "import asyncio; from app.database import init_database; asyncio.run(init_database())"

# Process inbox
process-inbox:
	cd backend && uv run python -c "import asyncio; from app.services.watcher import process_existing_inbox; asyncio.run(process_existing_inbox())"

# Add a dependency
add:
	cd backend && uv add $(pkg)

# Update dependencies
update:
	cd backend && uv sync --upgrade
