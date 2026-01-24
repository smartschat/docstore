"""Shared fixtures for integration tests."""

import pytest
from fastapi.testclient import TestClient


def reset_global_state():
    """Reset all global state in services to ensure test isolation."""
    # Reset queue processor state
    from app.services import queue
    queue._queue_task = None
    queue._should_stop = False

    # Reset folder watcher state
    from app.services.watcher import folder_watcher
    if folder_watcher._running:
        folder_watcher.stop()
    folder_watcher._running = False
    folder_watcher.observer = None

    # Reset embedding model state (optional, but good for isolation)
    from app.services import embeddings
    embeddings._model_loaded = False
    embeddings._tokenizer = None
    embeddings._session = None


@pytest.fixture
def client(test_db):
    """FastAPI TestClient with properly managed lifespan."""
    from app.main import app

    # Reset state before starting
    reset_global_state()

    # Use TestClient context manager to properly handle lifespan
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client

    # Reset state after test completes
    reset_global_state()


@pytest.fixture
def authenticated_client(client):
    """Client with valid authentication."""
    response = client.post(
        "/api/auth/login",
        json={"password": "testpassword"}
    )
    assert response.status_code == 200
    return client
