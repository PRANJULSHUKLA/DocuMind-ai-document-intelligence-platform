import hashlib
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from fastapi.testclient import TestClient

from bson import ObjectId
import pytest

from app.errors import GenerationUnavailableError
from app.services import pilot_budget, pilot_originals, document_view

ID = ObjectId('507f1f77bcf86cd799439011')
PDF = b'%PDF-1.7 synthetic only'


@pytest.fixture(autouse=True)
def reset_process_quota_latch(monkeypatch):
    monkeypatch.setattr(pilot_budget, '_blocked_days', set())


@pytest.fixture
def original(monkeypatch):
    document = {'_id': ID, 'filename': 'synthetic.pdf', 'workspace_id': 'workspace-a',
                'content_sha256': hashlib.sha256(PDF).hexdigest(), 'original_storage': 'mongo_pilot'}
    store = SimpleNamespace(insert_one=AsyncMock(), find_one=AsyncMock(return_value={
        '_id': ID, 'workspace_id': 'workspace-a', 'content': PDF,
        'content_sha256': document['content_sha256']}))
    monkeypatch.setattr(pilot_originals, 'database', {'render_pilot_originals': store})
    return document, store


async def test_durable_pdf_restores_after_ephemeral_disk_loss(original, tmp_path):
    doc, store = original
    path = await pilot_originals.restore(tmp_path, doc)
    assert path.read_bytes() == PDF
    path.unlink()
    assert (await pilot_originals.restore(tmp_path, doc)).read_bytes() == PDF
    assert store.find_one.await_args.args[0] == {'_id': ID, 'workspace_id': 'workspace-a'}


async def test_durable_read_rejects_changed_bytes(original):
    doc, store = original
    store.find_one.return_value['content'] = PDF + b'changed'
    with pytest.raises(ValueError, match='integrity'):
        await pilot_originals.read(doc)


async def test_durable_read_rejects_different_document_version(original):
    doc, _ = original
    doc['content_sha256'] = '0' * 64
    with pytest.raises(ValueError, match='integrity'):
        await pilot_originals.read(doc)


async def test_durable_copy_missing_or_other_workspace_is_unavailable(original):
    doc, store = original
    store.find_one.return_value = None
    with pytest.raises(FileNotFoundError):
        await pilot_originals.read({**doc, 'workspace_id': 'workspace-b'})
    assert store.find_one.await_args.args[0]['workspace_id'] == 'workspace-b'


async def test_oversize_original_is_not_written(original):
    doc, store = original
    with pytest.raises(ValueError):
        await pilot_originals.save(doc, b'x' * (pilot_originals.MAX_BYTES + 1))
    store.insert_one.assert_not_awaited()


async def test_pdf_viewer_reads_durable_copy_without_local_file(original, monkeypatch):
    doc, _ = original
    monkeypatch.setattr(document_view, 'get_authorized_document', AsyncMock(return_value=doc))
    _, data = await document_view.content(str(ID), 'workspace-a')
    assert data == PDF


def test_pilot_budget_disabled_has_no_database_side_effect(monkeypatch):
    monkeypatch.delenv('DOCUMIND_RENDER_PILOT', raising=False)
    store = Mock(side_effect=AssertionError('Must not access storage'))
    monkeypatch.setattr(pilot_budget, 'collection', store)
    pilot_budget.reserve('model')
    store.assert_not_called()


@pytest.mark.parametrize('kind,maximum', [('model', 30), ('upload', 5)])
def test_budget_uses_shared_atomic_bounded_increment(monkeypatch, kind, maximum):
    monkeypatch.setenv('DOCUMIND_RENDER_PILOT', '1')
    store = Mock()
    store.find_one_and_update.return_value = {'used': 1}
    monkeypatch.setattr(pilot_budget, 'collection', lambda: store)
    pilot_budget.reserve(kind)
    query, update = store.find_one_and_update.call_args.args
    assert query['used'] == {'$lt': maximum}
    assert query['blocked'] == {'$ne': True}
    assert update == {'$inc': {'used': 1}}


@pytest.mark.parametrize('unavailable', [False, True])
def test_budget_exhaustion_or_database_failure_prevents_provider_call(monkeypatch, unavailable):
    monkeypatch.setenv('DOCUMIND_RENDER_PILOT', '1')
    store = Mock()
    store.find_one_and_update.return_value = None
    if unavailable:
        store.update_one.side_effect = RuntimeError('private connection details')
    monkeypatch.setattr(pilot_budget, 'collection', lambda: store)
    with pytest.raises(GenerationUnavailableError) as error:
        pilot_budget.reserve('model')
    assert 'private' not in str(error.value)


def test_quota_exhaustion_latches_until_next_utc_day(monkeypatch):
    monkeypatch.setenv('DOCUMIND_RENDER_PILOT', '1')
    store = Mock()
    monkeypatch.setattr(pilot_budget, 'collection', lambda: store)
    pilot_budget.exhausted()
    assert store.update_one.call_args.args[1] == {'$set': {'blocked': True}}
    assert store.update_one.call_args.args[0]['_id'].startswith('model:')


def test_quota_write_failure_still_blocks_the_current_process(monkeypatch):
    monkeypatch.setenv('DOCUMIND_RENDER_PILOT', '1')
    store = Mock()
    store.update_one.side_effect = RuntimeError('Database timeout')
    monkeypatch.setattr(pilot_budget, 'collection', lambda: store)
    with pytest.raises(GenerationUnavailableError):
        pilot_budget.exhausted()
    store.update_one.reset_mock(side_effect=True)
    with pytest.raises(GenerationUnavailableError):
        pilot_budget.reserve('model')
    store.find_one_and_update.assert_not_called()


async def test_pilot_worker_rejects_page_limit_before_ocr(store, monkeypatch, tmp_path):
    from app.queue import workers
    pdf = tmp_path / 'synthetic.pdf'
    pdf.write_bytes(PDF)
    monkeypatch.setenv('DOCUMIND_RENDER_PILOT', '1')
    monkeypatch.setattr(workers, 'pdfinfo_from_path', Mock(return_value={'Pages': 4}))
    monkeypatch.setattr(workers, 'image_to_markdown', Mock())
    monkeypatch.setattr(workers, 'convert_from_path', Mock())
    with pytest.raises(RuntimeError):
        await workers._process_file_async(str(ID), str(pdf))
    workers.image_to_markdown.assert_not_called()
    workers.convert_from_path.assert_not_called()


def test_vision_pilot_never_retries_429(monkeypatch, tmp_path):
    from app.llm import vision
    monkeypatch.setenv('DOCUMIND_RENDER_PILOT', '1')
    monkeypatch.setattr(pilot_budget, 'reserve', Mock())
    latch = Mock()
    monkeypatch.setattr(pilot_budget, 'exhausted', latch)
    post = Mock(return_value=SimpleNamespace(status_code=429, ok=False))
    monkeypatch.setattr(vision.requests, 'post', post)
    image = tmp_path / 'synthetic.jpg'
    image.write_bytes(b'synthetic image')
    with pytest.raises(RuntimeError):
        vision.image_to_markdown(str(image), max_retries=10)
    assert post.call_count == 1
    latch.assert_called_once()


def test_supervisor_rejects_missing_identity_allowlist():
    path = Path(__file__).resolve().parents[1] / 'deploy/render/start.py'
    spec = spec_from_file_location('render_start', path)
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    # Test the complete validator with production prerequisites, not dev auth.
    env = {'APP_ENV': 'production', 'AUTH_MODE': 'oidc', 'OIDC_ISSUER': 'https://issuer.test/',
           'OIDC_AUDIENCE': 'pilot', 'MONGODB_URI': 'mongodb+srv://user:placeholder@cluster.test/',
           'GEMINI_API_KEY': 'offline-only', 'REDIS_URL': 'redis://127.0.0.1:6379/0',
           'CORS_ORIGINS': 'https://pilot.onrender.com', 'UPLOAD_DIR': '/srv/uploads',
           'GEMINI_MAX_RETRIES': '0', 'GEMINI_FALLBACK_MODELS': '', 'LANGSMITH_TRACING': 'false',
           'DOCUMIND_RENDER_PILOT': '1', 'MAX_UPLOAD_MB': '2', 'DATABASE_NAME': 'offline',
           **{name: 'explicit-model' for name in ('MODEL_NAME', 'VISION_MODEL', 'WORKFLOW_MODEL', 'EMBEDDING_MODEL')}}
    with pytest.raises(ValueError, match='subject'):
        module.validate(env)
    module.validate({**env, 'PILOT_ALLOWED_SUBJECTS': 'auth0|synthetic-user'})


def test_pilot_gateway_rejects_unauthenticated_requests(store):
    from app.pilot_server import app
    with TestClient(app) as client:
        response = client.get('/api/session')
    assert response.status_code == 401
    assert response.headers['cache-control'] == 'no-store'
    assert response.headers['x-frame-options'] == 'DENY'


def test_pilot_request_size_limit_precedes_multipart_parsing(store):
    from app.pilot_server import app
    with TestClient(app) as client:
        response = client.post('/api/upload', content=b'x' * (2 * 1024 * 1024 + 65537))
    assert response.status_code == 413
    store.insert_one.assert_not_awaited()


@pytest.mark.parametrize('allowed,status', [('', 403), ('auth0|other', 403), ('auth0|alice', 200)])
def test_pilot_requires_explicit_subject_allowlist(monkeypatch, store, allowed, status):
    from app import auth, server
    monkeypatch.setenv('DOCUMIND_RENDER_PILOT', '1')
    monkeypatch.setenv('PILOT_ALLOWED_SUBJECTS', allowed)
    monkeypatch.setattr(auth, 'verify_token', Mock(return_value=auth.Identity('https://issuer.test', 'auth0|alice')))
    with TestClient(server.app) as client:
        response = client.get('/session', headers={'Authorization': 'Bearer offline-test-token'})
    assert response.status_code == status


def test_sdk_pilot_disables_automatic_retry_without_network():
    from google import genai
    client = genai.Client(api_key='offline-test-key', http_options={'retry_options': {'attempts': 1}})
    client.close()


def test_runtime_secret_file_is_exact_and_never_evaluated(tmp_path, monkeypatch):
    import json
    path = Path(__file__).resolve().parents[1] / 'deploy/render/start.py'
    spec = spec_from_file_location('render_secret_start', path)
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    secret = tmp_path / 'secrets.json'
    monkeypatch.setenv('MONGODB_URI', 'offline-test')
    monkeypatch.setenv('GEMINI_API_KEY', 'offline-test')
    values = {'MONGODB_URI': 'mongodb+srv://offline:placeholder@cluster.test/',
              'GEMINI_API_KEY': 'offline-$literal-placeholder'}
    secret.write_text(json.dumps(values))
    module.load_secrets(secret)
    import os
    assert os.environ['GEMINI_API_KEY'] == values['GEMINI_API_KEY']
    secret.write_text(json.dumps({**values, 'AUTH_MODE': 'development'}))
    with pytest.raises(ValueError, match='secret file is invalid'):
        module.load_secrets(secret)
