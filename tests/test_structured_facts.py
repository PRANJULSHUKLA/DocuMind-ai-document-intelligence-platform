from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from bson import ObjectId
import pytest
from fastapi import HTTPException
from app.services import structured_facts as service

ID = '507f1f77bcf86cd799439011'
DOC = {'_id': ObjectId(ID), 'filename': 'Synthetic.pdf', 'status': 'completed', 'active_processing_run_id': 'published', 'content_sha256': 'a' * 64}


def chunk(text='Buyer must pay USD 100 by December 1, 2026.'):
    return {'_id': ObjectId(), 'workspace_id': 'owned', 'file_id': ID, 'processing_run_id': 'published', 'content_sha256': 'a' * 64, 'page_number': 2, 'chunk_index': 0, 'text': text}


class Cursor:
    def __init__(self, rows): self.rows = rows
    def sort(self, *args): return self
    def limit(self, limit): self.rows = self.rows[:limit]; return self
    def max_time_ms(self, *args): return self
    def __aiter__(self): return self.iterate()
    async def iterate(self):
        for row in self.rows: yield row


def test_typed_facts_have_exact_quote_offsets_and_published_identity():
    row = chunk('Buyer: Acme. Buyer must pay USD 1,200.50 by December 1, 2026. Supplier shall deliver goods unless approval is withheld.')
    facts = service.extract_chunk(row, DOC)
    assert {f['kind'] for f in facts} == {'party', 'obligation', 'condition', 'amount', 'date'}
    assert next(f['value'] for f in facts if f['kind'] == 'amount') == {'amount': '1200.5', 'currency': 'USD'}
    assert next(f['value'] for f in facts if f['kind'] == 'date') == {'date': '2026-12-01'}
    for fact in facts:
        assert row['text'][fact['start_offset']:fact['end_offset']] == fact['quotation']
        assert fact['source']['source_id'] == str(row['_id'])
        assert fact['source']['processing_run_id'] == 'published'
        assert fact['source']['page_number'] == 2
        assert fact['source']['document_version']
    qualified = [f for f in facts if f['conditions']]
    assert qualified and all(f['uncertainty'] != 'literal_only' for f in qualified)


def test_missing_ambiguous_dates_truncated_clauses_and_scale_are_not_invented():
    result = service.extract_chunk(chunk('Date 01/02/2026. Cost USD 10 million. Buyer must provide'), DOC)
    assert result == []
    facts = service.extract_chunk(chunk('Buyer must pay USD 100. Buyer must pay USD 200.'), DOC)
    assert [f['value']['amount'] for f in facts if f['kind'] == 'amount'] == ['100', '200']


async def setup(monkeypatch, rows, doc=None):
    doc = DOC if doc is None else doc
    monkeypatch.setattr(service.collections, 'context', AsyncMock(return_value=({'revision': 1}, [(ID, doc)], [])))
    unchanged = AsyncMock()
    monkeypatch.setattr(service.collections, 'unchanged', unchanged)
    find = Mock(return_value=Cursor(rows))
    monkeypatch.setattr(service, 'chunks_collection', SimpleNamespace(find=find))
    return find, unchanged


async def test_published_query_is_scoped_and_final_version_check_runs(monkeypatch):
    find, unchanged = await setup(monkeypatch, [chunk()])
    result = await service.extract(ID, 'owned', [ID])
    assert result['facts']
    assert find.call_args.args[0] == {'workspace_id': 'owned', 'file_id': ID, 'processing_run_id': 'published', 'content_sha256': 'a' * 64}
    unchanged.assert_awaited_once()


async def test_foreign_or_stale_rows_fail_closed(monkeypatch):
    row = chunk(); row['workspace_id'] = 'foreign'
    await setup(monkeypatch, [row])
    with pytest.raises(HTTPException) as error:
        await service.extract(ID, 'owned', [ID])
    assert error.value.status_code == 409


async def test_legacy_is_explicitly_unverified_and_does_not_query_chunks(monkeypatch):
    find, _ = await setup(monkeypatch, [], {**DOC, 'content_sha256': None})
    result = await service.extract(ID, 'owned', [ID])
    assert result['facts'] == []
    assert result['limitations'][0]['reason'] == 'legacy_unverified_no_extraction'
    find.assert_not_called()


async def test_limits_and_no_ready_documents(monkeypatch):
    with pytest.raises(HTTPException):
        await service.extract(ID, 'owned', [ID] * 6)
    await setup(monkeypatch, [chunk()] * 21)
    result = await service.extract(ID, 'owned', [ID])
    assert any(item['reason'] == 'chunk_limit_reached' for item in result['limitations'])
    monkeypatch.setattr(service.collections, 'context', AsyncMock(return_value=({}, [], [{'file_id': ID}])))
    with pytest.raises(HTTPException):
        await service.extract(ID, 'owned', [ID])


def test_route_uses_identity_workspace_and_validates_bound(api, monkeypatch):
    mocked = AsyncMock(return_value={'facts': []})
    monkeypatch.setattr(service, 'extract', mocked)
    assert api.post(f'/collections/{ID}/facts', json={'file_ids': [ID]}).status_code == 200
    assert mocked.call_args.args[1] != 'owned'
    assert mocked.call_args.args[2] == [ID]
    assert api.post(f'/collections/{ID}/facts', json={'file_ids': [ID] * 6}).status_code == 422


def test_fact_extraction_cannot_include_foreign_members(api, monkeypatch):
    monkeypatch.setattr(service.collections, 'owned', AsyncMock(return_value={'file_ids': [ID]}))
    response = api.post(f'/collections/{ID}/facts', json={'file_ids': ['507f1f77bcf86cd799439012']})
    assert response.status_code == 400
