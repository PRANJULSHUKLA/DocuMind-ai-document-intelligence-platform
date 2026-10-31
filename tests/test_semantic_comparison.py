from copy import deepcopy
from unittest.mock import AsyncMock
from bson import ObjectId
from fastapi import HTTPException
import pytest
from app.services.structured_facts import extract_chunk
from app.services.semantic_comparison import compare_facts
from app.services.document_view import revision


def extraction(left, right):
    facts, docs = [], []
    for i, text in enumerate((left, right)):
        file_id = '507f1f77bcf86cd79943901' + str(i)
        doc = {'_id': ObjectId(file_id), 'filename': f'{i}.pdf', 'active_processing_run_id': f'run-{i}', 'content_sha256': str(i) * 64}
        docs.append({'file_id': file_id, 'filename': doc['filename'], 'document_version': revision(doc), 'processing_run_id': f'run-{i}', 'content_sha256': str(i) * 64})
        chunk = {'_id': ObjectId(), 'file_id': file_id, 'processing_run_id': f'run-{i}', 'content_sha256': str(i) * 64, 'text': text, 'page_number': i + 1, 'chunk_index': 0}
        for fact in extract_chunk(chunk, doc):
            facts.append({**fact, 'fact_id': 'f' + str(len(facts) + 1)})
    return {'documents': docs, 'facts': facts, 'limits': {}, 'limitations': [], 'truncated': False, 'notice': 'Bounded synthetic sample.'}


@pytest.mark.parametrize('left,right,expected', [
    ('Buyer must pay USD 100.', 'Buyer is required to make payment of USD 100.00.', 'supported_agreement'),
    ('Buyer must pay by December 1, 2026.', 'Buyer shall pay by 2026-12-01.', 'supported_agreement'),
    ('Buyer must pay USD 100.', 'Buyer shall not pay USD 100.', 'possible_contradiction'),
    ('Buyer must pay USD 100.', 'Buyer must pay USD 200.', 'supported_difference'),
    ('Buyer must pay by 2026-12-01.', 'Buyer must pay by 2026-12-02.', 'supported_difference'),
    ('Buyer must pay USD 100.', 'Seller must pay USD 100.', 'missing_information'),
    ('Buyer must pay USD 100 unless approved.', 'Buyer must pay USD 100 unless approved.', 'insufficient_evidence'),
    ('Buyer must pay USD 100. Buyer must not pay USD 100.', 'Buyer shall pay USD 100.', 'insufficient_evidence'),
    ('Payment could possibly be required.', 'A transfer is expected.', 'insufficient_evidence'),
])
def test_representative_bounded_semantic_examples(left, right, expected):
    result = compare_facts(extraction(left, right), 'Synthetic obligations')
    semantic = [f for f in result['findings'] if f['topic'].startswith('Normalized')]
    assert semantic and all(f['classification'] == expected for f in semantic)
    sources = {s['evidence_id']: s for s in result['sources']}
    for finding in semantic:
        for doc in finding['documents']:
            for fact in doc['facts']:
                source = sources[fact['evidence_id']]
                assert source['file_id'] == doc['file_id']
                assert source['document_version']
                assert any(source['excerpt'] in text for text in (left, right))


def test_stale_or_fabricated_provenance_rejected():
    data = extraction('Buyer must pay USD 100.', 'Buyer shall pay USD 100.')
    broken = deepcopy(data)
    broken['facts'][0]['source']['processing_run_id'] = 'stale'
    with pytest.raises(HTTPException): compare_facts(broken, 'Focus')
    broken = deepcopy(data)
    broken['facts'][0]['quotation'] = 'Invented'
    with pytest.raises(HTTPException): compare_facts(broken, 'Focus')


def test_authenticated_route_uses_workspace(api, monkeypatch):
    from app.services import semantic_comparison
    mock = AsyncMock(return_value={'findings': []})
    monkeypatch.setattr(semantic_comparison, 'compare', mock)
    ids = ['507f1f77bcf86cd799439010', '507f1f77bcf86cd799439011']
    response = api.post('/collections/project/compare-semantic', json={'file_ids': ids})
    assert response.status_code == 200
    assert mock.call_args.args[1]
    assert mock.call_args.args[2] == ids
