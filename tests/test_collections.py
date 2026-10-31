from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from bson import ObjectId
from fastapi import HTTPException
import pytest
from app.services import collections as service

ID = '507f1f77bcf86cd799439011'
OTHER = '507f1f77bcf86cd799439012'

@pytest.fixture
def collection_store(monkeypatch):
    row = {'_id': ObjectId(ID), 'workspace_id': 'workspace', 'name': 'Project', 'revision': 1, 'file_ids': [ID, OTHER]}
    store = SimpleNamespace(find_one=AsyncMock(return_value=row), insert_one=AsyncMock(return_value=SimpleNamespace(inserted_id=ObjectId(ID))), update_one=AsyncMock(return_value=SimpleNamespace(matched_count=1)), delete_one=AsyncMock())
    monkeypatch.setattr(service, 'collections', store)
    return store

async def test_create_update_and_revision_conflict(collection_store, monkeypatch):
    result = await service.create('Project', 'workspace')
    assert result['revision'] == 1
    assert collection_store.insert_one.call_args.args[0]['workspace_id'] == 'workspace'
    auth = AsyncMock(return_value={'status': 'completed'})
    monkeypatch.setattr(service, 'get_authorized_document', auth)
    result = await service.update(ID, 'workspace', 1, 'Renamed', [OTHER])
    assert result['name'] == 'Renamed' and result['file_ids'] == [OTHER]
    auth.assert_awaited_once_with(OTHER, 'workspace')
    assert collection_store.update_one.call_args.args[0]['revision'] == 1
    collection_store.update_one.return_value.matched_count = 0
    with pytest.raises(HTTPException) as error:
        await service.update(ID, 'workspace', 1, name='Other')
    assert error.value.status_code == 409

async def test_owner_query_and_missing_collection(collection_store):
    await service.owned(ID, 'other-workspace')
    assert collection_store.find_one.call_args.args[0]['workspace_id'] == 'other-workspace'
    collection_store.find_one.return_value = None
    with pytest.raises(HTTPException) as error:
        await service.owned(ID, 'other-workspace')
    assert error.value.status_code == 404

async def test_unauthorized_membership_is_not_written(collection_store, monkeypatch):
    monkeypatch.setattr(service, 'get_authorized_document', AsyncMock(side_effect=FileNotFoundError()))
    with pytest.raises(FileNotFoundError):
        await service.update(ID, 'workspace', 1, file_ids=[OTHER])
    collection_store.update_one.assert_not_awaited()

@pytest.mark.parametrize('ids', [[ID, ID], [str(i) for i in range(11)]])
async def test_document_budget_and_duplicates(ids):
    with pytest.raises(HTTPException):
        await service.authorize_ids(ids, 'workspace')

async def test_selected_must_belong_to_collection(collection_store):
    with pytest.raises(HTTPException):
        await service.context(ID, 'workspace', ['507f1f77bcf86cd799439013'])

async def test_partial_ingestion_skips_failed_documents(collection_store, monkeypatch):
    monkeypatch.setattr(service, 'get_authorized_document', AsyncMock(side_effect=[{'status': 'completed'}, {'status': 'failed'}]))
    _, ready, skipped = await service.context(ID, 'workspace')
    assert [item[0] for item in ready] == [ID]
    assert skipped == [{'file_id': OTHER, 'status': 'failed'}]

async def test_retrieval_one_embedding_filters_stale_sources(monkeypatch):
    embedding = Mock(return_value=[.1])
    monkeypatch.setattr(service, 'generate_embedding', embedding)
    retrieve = AsyncMock(side_effect=[[
        {'file_id': ID, 'processing_run_id': 'r1', 'content_sha256': 'hash', 'score': .8},
        {'file_id': OTHER, 'processing_run_id': 'r1', 'content_sha256': 'hash', 'score': .9},
        {'file_id': ID, 'processing_run_id': 'stale', 'content_sha256': 'hash', 'score': .9}],
        [{'file_id': OTHER, 'processing_run_id': 'r2', 'content_sha256': 'hash2', 'score': .9}]])
    monkeypatch.setattr(service, 'RAGPipeline', lambda: SimpleNamespace(retriever=SimpleNamespace(retrieve_chunks=retrieve)))
    rows = await service.retrieve([(ID, {'active_processing_run_id': 'r1', 'content_sha256': 'hash'}), (OTHER, {'active_processing_run_id': 'r2', 'content_sha256': 'hash2'})], 'Question', 'workspace')
    assert [row['file_id'] for row in rows] == [OTHER, ID]
    embedding.assert_called_once_with('Question')
    assert all(call.kwargs['query_embedding'] == [.1] and call.kwargs['limit'] == 3 for call in retrieve.await_args_list)

async def test_concurrent_document_change_rejects_answer(collection_store, monkeypatch):
    monkeypatch.setattr(service, 'get_authorized_document', AsyncMock(return_value={'status': 'completed', 'active_processing_run_id': 'new'}))
    with pytest.raises(HTTPException) as error:
        await service.unchanged(collection_store.find_one.return_value, 'workspace', [(ID, {'active_processing_run_id': 'old'})])
    assert error.value.status_code == 409


def test_collection_routes_require_auth(api):
    from app import server
    server.app.dependency_overrides.clear()
    assert api.get('/collections').status_code == 401
    assert api.post('/collections', json={'name': 'x'}).status_code == 401


def test_delete_only_removes_owned_collection(api, collection_store):
    assert api.delete('/collections/' + ID).status_code == 204
    assert collection_store.delete_one.call_args.args[0]['workspace_id']


def test_blank_name_rejected(api):
    assert api.post('/collections', json={'name': '   '}).status_code == 422
