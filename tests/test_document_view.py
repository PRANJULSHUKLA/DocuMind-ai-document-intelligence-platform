import hashlib
from types import SimpleNamespace
from unittest.mock import Mock
from bson import ObjectId
import pytest
from app.services import document_view
from app.auth import Identity

ID = '507f1f77bcf86cd799439011'

@pytest.fixture
def original(api, store, monkeypatch, tmp_path):
    monkeypatch.setattr(document_view, 'UPLOAD_DIR', tmp_path)
    data = b'%PDF-1.7\nsynthetic only'
    path = tmp_path / ID / 'test.pdf'
    path.parent.mkdir(); path.write_bytes(data)
    document = {'_id': ObjectId(ID), 'filename': 'test.pdf', 'status': 'completed', 'total_pages': 2,
                'workspace_id': Identity('https://issuer.test', 'alice').workspace_id,
                'active_processing_run_id': 'run-1', 'content_sha256': hashlib.sha256(data).hexdigest()}
    store.find_one.return_value = document
    return SimpleNamespace(path=path, data=data, document=document)


def test_private_original_bytes_and_headers(api, original):
    response = api.get(f'/files/{ID}/content')
    assert response.status_code == 200 and response.content == original.data
    assert response.headers['cache-control'] == 'private, no-store'
    assert response.headers['content-type'] == 'application/pdf'
    assert api.get(f'/files/{ID}/view').json()['provenance'] == 'verified'


def test_legacy_is_not_silently_verified(api, original, store):
    original.document.pop('content_sha256'); original.document.pop('active_processing_run_id')
    response = api.get(f'/files/{ID}/view')
    assert response.json()['provenance'] == 'legacy_unverified'
    assert response.json()['content_sha256'] is None
    store.update_one.assert_not_awaited()


def test_stale_version_and_changed_original_rejected(api, original):
    assert api.get(f'/files/{ID}/content?version=stale').status_code == 409
    original.path.write_bytes(b'%PDF-1.7\nchanged')
    assert api.get(f'/files/{ID}/content').status_code == 409


def test_missing_original_preserves_metadata(api, original, store):
    original.path.unlink()
    assert api.get(f'/files/{ID}/content').status_code == 404
    assert api.get(f'/files/{ID}/view').json()['original_available'] is False
    store.update_one.assert_not_awaited()


@pytest.mark.parametrize('filename', ['../other.pdf', '/tmp/other.pdf', 'sub\\other.pdf'])
def test_unsafe_reference_is_never_read(api, original, filename):
    original.document['filename'] = filename
    assert api.get(f'/files/{ID}/content').status_code == 404


def test_symlink_is_rejected(api, original, tmp_path):
    original.path.unlink(); target = tmp_path / 'other.pdf'; target.write_bytes(original.data)
    original.path.symlink_to(target)
    assert api.get(f'/files/{ID}/content').status_code == 404


@pytest.mark.parametrize('suffix', ['view','content','search?q=payment'])
def test_cross_workspace_access_is_not_found(api, original, store, suffix):
    store.find_one.side_effect = lambda query: None if query.get('workspace_id') != 'other' else original.document
    assert api.get(f'/files/{ID}/{suffix}').status_code == 404


def test_processing_pdf_is_readable_but_search_not_ready(api, original):
    original.document['status'] = 'processing'
    assert api.get(f'/files/{ID}/content').status_code == 200
    assert api.get(f'/files/{ID}/search?q=payment').status_code == 409


def test_search_is_scoped_literal_and_versioned(api, original, monkeypatch):
    class Cursor:
        def sort(self,*args): return self
        def limit(self,*args): return self
        def max_time_ms(self,*args): return self
        def __aiter__(self):
            async def rows():
                yield {'_id': ObjectId(), 'file_id': ID, 'processing_run_id': 'run-1', 'page_number': 2, 'chunk_index': 3, 'text': 'Payment is $100.', 'content_sha256': original.document['content_sha256']}
            return rows()
    collection = SimpleNamespace(find=Mock(return_value=Cursor()))
    monkeypatch.setattr(document_view, 'chunks_collection', collection)
    response = api.get(f'/files/{ID}/search?q=$100')
    assert response.status_code == 200
    assert response.json()['results'][0]['page_number'] == 2
    query = collection.find.call_args.args[0]
    assert query['workspace_id'] == original.document['workspace_id']
    assert query['processing_run_id'] == 'run-1'
    assert query['text']['$regex'] == r'\$100'

@pytest.mark.parametrize('suffix', ['view', 'content', 'search?q=payment'])
def test_viewer_routes_require_identity(store, suffix):
    from fastapi.testclient import TestClient
    from app.server import app
    with TestClient(app) as client:
        assert client.get(f'/files/{ID}/{suffix}').status_code == 401
    store.find_one.assert_not_awaited()


def test_parent_symlink_swap_between_validation_and_open_is_rejected(api, original, monkeypatch, tmp_path):
    check = document_view.checked_path
    def swap(document):
        path = check(document)
        directory = path.parent
        moved = tmp_path / 'moved'
        directory.rename(moved)
        directory.symlink_to(moved, target_is_directory=True)
        return path
    monkeypatch.setattr(document_view, 'checked_path', swap)
    assert api.get(f'/files/{ID}/content').status_code == 404


def test_file_symlink_swap_between_validation_and_open_is_rejected(api, original, monkeypatch, tmp_path):
    check = document_view.checked_path
    def swap(document):
        path = check(document)
        path.unlink()
        target = tmp_path / 'other.pdf'
        target.write_bytes(original.data)
        path.symlink_to(target)
        return path
    monkeypatch.setattr(document_view, 'checked_path', swap)
    assert api.get(f'/files/{ID}/content').status_code == 404


def test_version_change_during_read_is_rejected(api, original, monkeypatch, store):
    read = document_view.read_original
    def change(document):
        data = read(document)
        store.find_one.return_value = {**document, 'active_processing_run_id': 'new-run'}
        return data
    monkeypatch.setattr(document_view, 'read_original', change)
    assert api.get(f'/files/{ID}/content').status_code == 409
