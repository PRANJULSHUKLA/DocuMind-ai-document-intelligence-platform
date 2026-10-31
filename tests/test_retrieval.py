from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from app.services import retrieval_service
from app.services.knowledge_service import KnowledgeService

FILE_ID = "507f1f77bcf86cd799439011"


@pytest.mark.parametrize("document,error", [(None, FileNotFoundError), ({"status": "processing"}, RuntimeError), ({"status": "failed"}, RuntimeError)])
async def test_chat_does_not_retrieve_inaccessible_or_unready_files(store, document, error):
    store.find_one.return_value = document
    service = KnowledgeService()
    service.pipeline = SimpleNamespace(run=AsyncMock())
    with pytest.raises(error):
        await service.ask(FILE_ID, "Question?", "test-workspace")
    service.pipeline.run.assert_not_awaited()


async def test_invalid_file_id_does_not_touch_database(store):
    with pytest.raises(ValueError):
        await KnowledgeService().ask("invalid", "Question?", "test-workspace")
    store.find_one.assert_not_awaited()


@pytest.mark.parametrize("run_id", [None, "published-run"])
async def test_vector_search_scopes_file_version_and_enforces_threshold(store, monkeypatch, run_id):
    store.find_one.return_value = {"status": "completed", "active_processing_run_id": run_id}
    generate = Mock(return_value=[.1, .2])
    monkeypatch.setattr(retrieval_service, "generate_embedding", generate)
    cursor = SimpleNamespace(to_list=AsyncMock(return_value=[]))
    collection = SimpleNamespace(aggregate=AsyncMock(return_value=cursor))
    monkeypatch.setattr(retrieval_service, "chunks_collection", collection)
    await retrieval_service.RetrievalService().retrieve_chunks(FILE_ID, "Question?", "test-workspace")
    pipeline = collection.aggregate.await_args.args[0]
    filters = pipeline[0]["$vectorSearch"]["filter"]
    assert filters["file_id"] == FILE_ID
    assert filters["workspace_id"] == "test-workspace"
    if run_id:
        assert filters["processing_run_id"] == run_id
    else:
        assert "processing_run_id" not in filters
    assert pipeline[-1]["$match"]["score"]["$gte"] == .65
