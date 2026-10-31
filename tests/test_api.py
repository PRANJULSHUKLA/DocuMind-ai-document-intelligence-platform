from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

from bson import ObjectId
import pytest

FILE_ID = "507f1f77bcf86cd799439011"


def test_health_does_not_require_services(api):
    assert api.get("/").json()["status"] == "healthy"


@pytest.mark.parametrize("filename,content,status", [
    ("empty.pdf", b"", 400),
    ("notes.txt", b"%PDF-1.7", 415),
    ("fake.pdf", b"not a pdf", 415),
])
def test_invalid_upload_does_not_create_records(api, store, filename, content, status):
    response = api.post("/upload", files={"file": (filename, content, "application/pdf")})
    assert response.status_code == status
    store.insert_one.assert_not_awaited()


def test_upload_size_limit(api, store, monkeypatch):
    from app import server
    monkeypatch.setattr(server, "MAX_UPLOAD_BYTES", 10)
    assert api.post("/upload", files={"file": ("big.pdf", b"%PDF-" + b"x" * 10)}).status_code == 413
    store.insert_one.assert_not_awaited()


def test_upload_sanitizes_path_and_enqueues(api, store, monkeypatch, tmp_path):
    from app import server
    enqueue = Mock()
    monkeypatch.setattr(server.q, "enqueue", enqueue)
    response = api.post("/upload", files={"file": ("../../safe.pdf", b"%PDF-1.7\n")})
    assert response.status_code == 200
    assert response.json()["file_id"] == FILE_ID
    assert (tmp_path / FILE_ID / "safe.pdf").read_bytes() == b"%PDF-1.7\n"
    assert enqueue.call_args.args[1] == FILE_ID
    assert enqueue.call_args.kwargs["job_timeout"] == 1200


def test_queue_failure_marks_upload_failed(api, store, monkeypatch):
    from app import server
    monkeypatch.setattr(server.q, "enqueue", Mock(side_effect=RuntimeError("queue unavailable")))
    assert api.post("/upload", files={"file": ("test.pdf", b"%PDF-1.7")}).status_code == 500
    assert store.update_one.await_args.args[1]["$set"]["status"] == "failed"


@pytest.mark.parametrize("path", ["/files/not-an-id", "/status/not-an-id"])
def test_invalid_ids(api, store, path):
    assert api.get(path).status_code == 400
    store.find_one.assert_not_awaited()


def test_missing_file(api):
    assert api.get(f"/files/{FILE_ID}").status_code == 404


def test_status_contract(api, store):
    store.find_one.return_value = {"_id": ObjectId(FILE_ID), "filename": "test.pdf", "status": "completed", "total_pages": 2}
    response = api.get(f"/status/{FILE_ID}")
    assert response.status_code == 200
    assert response.json()["total_pages"] == 2


@pytest.mark.parametrize("error,status", [(FileNotFoundError("missing"), 404), (ValueError("invalid"), 400), (RuntimeError("not ready"), 409)])
def test_chat_service_errors(api, monkeypatch, error, status):
    from app import server
    monkeypatch.setattr(server, "KnowledgeService", lambda: SimpleNamespace(ask=AsyncMock(side_effect=error)))
    assert api.post("/chat", json={"file_id": FILE_ID, "question": "What is due?"}).status_code == status


def test_chat_preserves_contract(api, monkeypatch):
    from app import server
    result = {"answer": "Payment is due Friday.", "sources": [{"filename": "test.pdf", "page_number": 1, "chunk_index": 0, "score": .9}], "retrieval_time_ms": 1, "generation_time_ms": 2, "total_time_ms": 3}
    monkeypatch.setattr(server, "KnowledgeService", lambda: SimpleNamespace(ask=AsyncMock(return_value=result)))
    response = api.post("/chat", json={"file_id": FILE_ID, "question": "What is due?"})
    assert response.status_code == 200
    assert response.json() == result
