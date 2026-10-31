"""Offline boundaries: tests must never use developer credentials or services."""
import os
import socket
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

for key, value in {
    "PYTHON_DOTENV_DISABLED": "1",
    "GEMINI_API_KEY": "offline-test-key",
    "MONGODB_URI": "mongodb://127.0.0.1:1/?directConnection=true",
    "DATABASE_NAME": "documind_offline_tests",
    "REDIS_URL": "redis://127.0.0.1:1/15",
    "MODEL_NAME": "offline-test-model",
    "VISION_MODEL": "offline-test-model",
    "WORKFLOW_MODEL": "offline-test-model",
    "EMBEDDING_MODEL": "offline-test-embedding",
    "GEMINI_FALLBACK_MODELS": "",
    "AUTH_MODE": "oidc",
    "APP_ENV": "test",
    "OIDC_ISSUER": "https://issuer.test",
    "OIDC_AUDIENCE": "documind-api",
    "OIDC_JWKS_URL": "",
}.items():
    os.environ[key] = value


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    def deny(*args, **kwargs):
        raise AssertionError("External network/model/queue call attempted in offline test")

    from google.genai.models import Models
    from rq import Queue

    monkeypatch.setattr(socket.socket, "connect", deny)
    monkeypatch.setattr(socket, "create_connection", deny)
    monkeypatch.setattr(Models, "generate_content", deny)
    monkeypatch.setattr(Models, "embed_content", deny)
    monkeypatch.setattr(Queue, "enqueue", deny)


@pytest.fixture
def store(monkeypatch):
    from app import server
    from app.queue import workers
    from app.services import document_access, upload_dispatch

    collection = SimpleNamespace(
        insert_one=AsyncMock(return_value=SimpleNamespace(inserted_id="507f1f77bcf86cd799439011")),
        update_one=AsyncMock(return_value=SimpleNamespace(matched_count=1)),
        find_one_and_update=AsyncMock(return_value={"status": "processing", "workspace_id": "test-workspace"}),
        find_one=AsyncMock(return_value=None),
        find=MagicMock(),
    )
    for module in (server, workers, document_access, upload_dispatch):
        monkeypatch.setattr(module, "files_collection", collection)
    return collection


@pytest.fixture
def api(store, monkeypatch, tmp_path):
    from fastapi.testclient import TestClient
    from app import server
    from app.auth import Identity, current_identity

    monkeypatch.setattr(server, "UPLOAD_DIR", tmp_path)
    server.app.dependency_overrides[current_identity] = lambda: Identity("https://issuer.test", "alice")
    with TestClient(server.app) as client:
        yield client
    server.app.dependency_overrides.clear()
