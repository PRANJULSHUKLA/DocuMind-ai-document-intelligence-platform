from copy import deepcopy
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from bson import ObjectId
from fastapi import HTTPException
from pypdf import PdfReader
import pytest
from app.services import comparison_reports as service
from app.services.document_view import revision
from app.services.report_pdf import render

ID = '507f1f77bcf86cd799439011'
SOURCE = {'_id': ObjectId(ID), 'filename': 'Synthetic.pdf', 'status': 'completed', 'active_processing_run_id': 'published', 'content_sha256': 'a' * 64}


def snapshot():
    source = {'evidence_id': 'f1', 'file_id': ID, 'source_id': 'chunk-1', 'filename': 'Synthetic.pdf', 'page_number': 1, 'processing_run_id': 'published', 'content_sha256': 'a' * 64, 'document_version': revision(SOURCE), 'excerpt': 'Buyer must pay USD 100.'}
    return {'schema_version': 2, 'method': 'literal_plus_verified_normalization_v1', 'focus': 'Payment',
            'summary': {'supported_agreement': 1}, 'limitations': ['Bounded evidence only.'], 'sources': [source],
            'documents': [{'file_id': ID, 'filename': source['filename'], 'document_version': revision(SOURCE), 'processing_run_id': 'published', 'content_sha256': 'a' * 64}],
            'findings': [{'topic': 'Buyer payment', 'classification': 'supported_agreement', 'explanation': 'The observed propositions align. Legal equivalence is not established.', 'documents': [{'file_id': ID, 'filename': source['filename'], 'facts': [{'values': ['pay USD 100', 'required'], 'evidence_id': 'f1'}]}]}]}


def row():
    result = snapshot()
    return {'_id': ObjectId(ID), 'workspace_id': 'owned', 'title': 'Synthetic payment review', 'collection_id': 'collection', 'snapshot': result, 'review_digest': service.digest(result), 'created_at': '2026-11-01T00:00:00+00:00', 'reviewed': True, 'model': None, 'retention': 'Retained until explicitly deleted.'}


def export_fixture(stale=False):
    value = row()
    return {**service.metadata(value), 'snapshot': value['snapshot'], 'retention': value['retention'], 'stale': stale,
            'source_states': [{'file_id': ID, 'saved_version': revision(SOURCE), 'current_version': 'new' if stale else revision(SOURCE), 'stale': stale}]}


async def test_save_recomputes_server_result_and_rejects_unreviewed_changes(monkeypatch):
    result = snapshot()
    compare = AsyncMock(return_value=result)
    insert = AsyncMock(return_value=SimpleNamespace(inserted_id=ObjectId(ID)))
    monkeypatch.setattr(service.semantic_comparison, 'compare', compare)
    monkeypatch.setattr(service, 'reports', SimpleNamespace(insert_one=insert))
    with pytest.raises(HTTPException) as failure:
        await service.save('collection', 'owned', ['a', 'b'], 'Payment', '0' * 64, 'Title')
    assert failure.value.status_code == 409
    insert.assert_not_called()
    saved = await service.save('collection', 'owned', ['a', 'b'], 'Payment', service.digest(result), 'Title')
    assert saved['id'] == ID
    assert insert.call_args.args[0]['workspace_id'] == 'owned'
    assert insert.call_args.args[0]['snapshot'] == result
    assert insert.call_args.args[0]['model'] is None


async def test_snapshot_size_limit(monkeypatch):
    result = snapshot(); result['focus'] = 'a' * (service.MAX_SNAPSHOT_BYTES + 1)
    monkeypatch.setattr(service.semantic_comparison, 'compare', AsyncMock(return_value=result))
    with pytest.raises(HTTPException) as error:
        await service.save('c', 'w', ['a', 'b'], '', service.digest(result), 'title')
    assert error.value.status_code == 413


async def test_report_ownership_and_stale_source_checks(monkeypatch):
    find = AsyncMock(return_value=row())
    monkeypatch.setattr(service, 'reports', SimpleNamespace(find_one=find))
    current = AsyncMock(return_value=SOURCE)
    monkeypatch.setattr(service, 'get_authorized_document', current)
    result = await service.read(ID, 'owned')
    assert result['stale'] is False
    assert find.call_args.args[0] == {'_id': ObjectId(ID), 'workspace_id': 'owned'}
    current.assert_awaited_with(ID, 'owned')
    current.return_value = {**SOURCE, 'active_processing_run_id': 'new'}
    result = await service.read(ID, 'owned')
    assert result['stale'] is True
    assert result['snapshot'] == snapshot()
    current.side_effect = FileNotFoundError()
    with pytest.raises(HTTPException) as unavailable:
        await service.read(ID, 'owned')
    assert unavailable.value.status_code == 409
    find.return_value = None
    with pytest.raises(HTTPException) as foreign:
        await service.read(ID, 'foreign')
    assert foreign.value.status_code == 404


async def test_delete_only_deletes_owned_snapshot(monkeypatch):
    delete = AsyncMock()
    monkeypatch.setattr(service, 'reports', SimpleNamespace(find_one=AsyncMock(return_value=row()), delete_one=delete))
    await service.delete(ID, 'owned')
    delete.assert_awaited_once_with({'_id': ObjectId(ID), 'workspace_id': 'owned'})


def test_json_and_pdf_exports_do_not_recompute_or_call_models(api, monkeypatch):
    read = AsyncMock(return_value=export_fixture(stale=True))
    compare = AsyncMock(side_effect=AssertionError('Export must not recompute'))
    monkeypatch.setattr(service, 'read', read)
    monkeypatch.setattr(service.semantic_comparison, 'compare', compare)
    response = api.get(f'/comparison-reports/{ID}/export?format=json')
    assert response.status_code == 200 and response.json()['stale'] is True
    assert response.headers['cache-control'] == 'private, no-store'
    response = api.get(f'/comparison-reports/{ID}/export?format=pdf')
    assert response.status_code == 200 and response.content.startswith(b'%PDF-')
    text = '\n'.join(page.extract_text() for page in PdfReader(BytesIO(response.content)).pages)
    assert 'STALE SOURCE REVISION' in text
    assert 'Buyer must pay USD 100.' in text
    assert 'Content SHA-256' in text
    compare.assert_not_called()
    assert api.get(f'/comparison-reports/{ID}/export?format=html').status_code == 422


def test_pdf_escapes_markup_long_text_and_unsupported_glyphs_without_losing_pages():
    report = export_fixture()
    report['title'] = '<script> & synthetic review'
    report['snapshot']['sources'][0]['excerpt'] = '<b>Literal</b> & quotation. ' + ('Long evidence clause. ' * 70) + '\u4e2d'
    report['snapshot']['findings'] *= 3
    content = render(report)
    reader = PdfReader(BytesIO(content))
    text = '\n'.join(page.extract_text() for page in reader.pages)
    assert len(reader.pages) > 1
    assert '<script> & synthetic review' in text
    assert '<b>Literal</b>' in text and '[U+4E2D]' in text
    assert 'Document revisions' in text
    from app.services.report_pdf import FONT, BOLD, WIDTH, HEIGHT, MARGIN
    from reportlab.pdfbase import pdfmetrics
    def inside_page(text, cm, tm, font, size):
        if not text.strip(): return
        x = cm[0] * tm[4] + cm[2] * tm[5] + cm[4]
        y = cm[1] * tm[4] + cm[3] * tm[5] + cm[5]
        font_name = BOLD if 'Bold' in str(font.get('/BaseFont')) else FONT
        width = pdfmetrics.stringWidth(text.rstrip('\n'), font_name, size)
        assert x >= MARGIN - .1 and x + width <= WIDTH - MARGIN + .1
        assert 20 <= y <= HEIGHT - MARGIN
    for page in reader.pages:
        page.extract_text(visitor_text=inside_page)


def test_save_requires_explicit_review_and_identity_workspace(api, monkeypatch):
    save = AsyncMock(return_value={'id': ID})
    monkeypatch.setattr(service, 'save', save)
    body = {'file_ids': [ID, '507f1f77bcf86cd799439012'], 'title': 'Review', 'expected_digest': 'a' * 64, 'reviewed': False}
    assert api.post('/comparison-reports/collection/project', json=body).status_code == 422
    save.assert_not_called()
    body['reviewed'] = True
    assert api.post('/comparison-reports/collection/project', json=body).status_code == 201
    assert save.call_args.args[1]


def test_new_endpoints_require_authentication(api):
    from app import server
    from app.auth import current_identity
    override = server.app.dependency_overrides.pop(current_identity)
    try:
        for path in ('/comparison-reports', f'/comparison-reports/{ID}', f'/comparison-reports/{ID}/export'):
            assert api.get(path).status_code == 401
        assert api.post('/comparison-reports/collection/project', json={}).status_code == 401
    finally:
        server.app.dependency_overrides[current_identity] = override


def test_offline_demo_produces_real_pdf_hashes_and_validated_examples(tmp_path):
    import hashlib
    import json
    from pathlib import Path
    import subprocess
    import sys
    output = tmp_path / 'synthetic-demo'
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run([sys.executable, 'scripts/demo_evidence_review.py', '--output-dir', str(output)], cwd=root, capture_output=True, text=True, timeout=30, check=True)
    metrics = json.loads(result.stdout)
    assert metrics['provider_requests'] == 0
    assert metrics['semantic_examples'] == 3
    assert metrics['exact_quote_checks_passed'] == metrics['facts']
    report = json.loads((output / 'reviewed-report.json').read_text())
    for source in report['snapshot']['documents']:
        assert hashlib.sha256((output / source['filename']).read_bytes()).hexdigest() == source['content_sha256']
    text = '\n'.join(page.extract_text() for page in PdfReader(output / 'reviewed-report.pdf').pages)
    assert 'No live ingestion' in text
    assert 'disclose records' in text
