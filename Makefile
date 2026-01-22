.PHONY: help install dev backend frontend build clean docker-build docker-up docker-down

# Default target
help:
	@echo "DocStore - Document Digitization System"
	@echo ""
	@echo "Usage:"
	@echo "  make install     Install all dependencies"
	@echo "  make dev         Run both backend and frontend in development mode"
	@echo "  make backend     Run backend only"
	@echo "  make frontend    Run frontend only"
	@echo "  make build       Build frontend for production"
	@echo "  make clean       Remove build artifacts"
	@echo "  make docker-build Build Docker images"
	@echo "  make docker-up   Start Docker containers"
	@echo "  make docker-down Stop Docker containers"
	@echo ""

# Install dependencies
install:
	@echo "Installing backend dependencies with uv..."
	cd backend && uv sync
	@echo "Installing frontend dependencies..."
	cd frontend && npm install
	@echo "Creating data directories..."
	mkdir -p data/inbox data/archive

# Development
dev:
	@echo "Starting development servers..."
	make -j2 backend frontend

backend:
	@echo "Starting backend..."
	cd backend && uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

frontend:
	@echo "Starting frontend..."
	cd frontend && npm run dev

# Build
build:
	@echo "Building frontend..."
	cd frontend && npm run build
	@echo "Build complete. Static files in frontend/build/"

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

# Docker
docker-build:
	docker-compose build

docker-up:
	docker-compose up -d

docker-down:
	docker-compose down

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
