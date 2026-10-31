from unittest.mock import AsyncMock
import pytest
from fastapi import HTTPException
from app.services import comparison

A = '507f1f77bcf86cd799439011'
B = '507f1f77bcf86cd799439012'
READY = [(A, {'filename': 'A.pdf'}), (B, {'filename': 'B.pdf'})]


def compare(a, b):
    return comparison.compare_evidence(READY, [
        {'file_id': A, 'filename': 'A.pdf', 'text': a, 'page_number': 1, 'processing_run_id': 'run-a', 'content_sha256': 'hash-a'},
        {'file_id': B, 'filename': 'B.pdf', 'text': b, 'page_number': 2, 'processing_run_id': 'run-b', 'content_sha256': 'hash-b'}], 'Payment terms')


def finding(result, topic):
    return next(row for row in result['findings'] if row['topic'] == topic)


def test_amount_difference_with_exact_evidence_and_provenance():
    result = compare('Payment USD 100.', 'Payment USD 200.')
    row = finding(result, 'Amount (USD)')
    assert row['classification'] == 'supported_difference'
    assert row['documents'][0]['facts'][0]['values'] == ['100']
    assert result['sources'][1]['excerpt'] == 'Payment USD 200.'
    assert result['sources'][1]['file_id'] == B and result['sources'][1]['page_number'] == 2
    assert result['sources'][1]['content_sha256'] == 'hash-b'
    assert result['summary']['possible_contradiction'] == 0


def test_equal_amounts_and_normalized_dates_are_only_fact_agreements():
    result = compare('USD 1,000.00 due December 1, 2026.', 'USD 1000 due 2026-12-01.')
    assert finding(result, 'Amount (USD)')['classification'] == 'supported_agreement'
    assert finding(result, 'Explicit dates')['classification'] == 'supported_agreement'


def test_missing_is_only_missing_in_retrieved_evidence():
    result = compare('Payment USD 100.', 'No payment amount stated here.')
    row = finding(result, 'Amount (USD)')
    assert row['classification'] == 'missing_information'
    assert row['documents'][1]['status'] == 'not_found_in_retrieved_evidence'
    assert 'does not establish absence' in row['explanation']


def test_explicit_opposite_obligation_is_possible_not_confirmed():
    result = compare('Buyer must disclose records.', 'Buyer must not disclose records.')
    row = finding(result, 'Obligation: buyer → disclose records')
    assert row['classification'] == 'possible_contradiction'
    assert 'human verification' in row['explanation']


@pytest.mark.parametrize('a,b', [('Buyer must disclose records.', 'Buyer shall provide records.'), ('Buyer may disclose records.', 'Buyer may not disclose records.'), ('Buyer must disclose records unless prohibited.', 'Buyer must not disclose records if prohibited.')])
def test_wording_or_conditional_obligations_never_claim_contradiction(a, b):
    assert compare(a, b)['summary']['possible_contradiction'] == 0


def test_internal_opposite_obligations_are_ambiguous():
    result = compare('Buyer must disclose records. Buyer must not disclose records.', 'Buyer must disclose records.')
    assert finding(result, 'Obligation: buyer → disclose records')['classification'] == 'insufficient_evidence'


def test_unsupported_dates_and_empty_evidence_do_not_invent_facts():
    result = compare('Due 12/01/26 or February 31, 2026.', 'Amount unknown.')
    assert result['findings'][0]['classification'] == 'insufficient_evidence'
    assert not result['summary']['supported_agreement']


async def test_comparison_reuses_collection_authorization_and_version_checks(monkeypatch):
    context = AsyncMock(return_value=({'revision': 1}, READY, []))
    retrieve = AsyncMock(return_value=[])
    unchanged = AsyncMock()
    monkeypatch.setattr(comparison.collections, 'context', context)
    monkeypatch.setattr(comparison.collections, 'retrieve', retrieve)
    monkeypatch.setattr(comparison.collections, 'unchanged', unchanged)
    result = await comparison.compare('collection', 'workspace', [A, B], 'Payment')
    context.assert_awaited_once_with('collection', 'workspace', [A, B])
    unchanged.assert_awaited_once()
    assert result['schema_version'] == 1


async def test_incomplete_document_blocks_comparison_before_retrieval(monkeypatch):
    monkeypatch.setattr(comparison.collections, 'context', AsyncMock(return_value=({}, READY[:1], [{'file_id': B, 'status': 'failed'}])))
    retrieve = AsyncMock()
    monkeypatch.setattr(comparison.collections, 'retrieve', retrieve)
    with pytest.raises(HTTPException) as error:
        await comparison.compare('collection', 'workspace', [A, B], 'Payment')
    assert error.value.status_code == 409
    retrieve.assert_not_awaited()


async def test_comparison_unauthorized_member_is_rejected(monkeypatch):
    monkeypatch.setattr(comparison.collections, 'context', AsyncMock(side_effect=FileNotFoundError()))
    with pytest.raises(FileNotFoundError):
        await comparison.compare('collection', 'workspace', [A, B], 'Payment')


def test_comparison_requires_auth(api):
    from app import server
    server.app.dependency_overrides.clear()
    assert api.post('/collections/any/compare', json={'file_ids': [A, B]}).status_code == 401


def test_comparison_request_bounds(api):
    assert api.post('/collections/any/compare', json={'file_ids': [A]}).status_code == 422
    assert api.post('/collections/any/compare', json={'file_ids': [A, B], 'focus': ' '}).status_code == 422


def test_comparison_api_synthetic_two_document_scenario(api, monkeypatch):
    monkeypatch.setattr(comparison.collections, 'context', AsyncMock(return_value=({'revision': 1}, READY, [])))
    monkeypatch.setattr(comparison.collections, 'retrieve', AsyncMock(return_value=[
        {'file_id': A, 'filename': 'A.pdf', 'page_number': 1, 'text': 'Payment USD 100. Buyer must disclose records.'},
        {'file_id': B, 'filename': 'B.pdf', 'page_number': 2, 'text': 'Payment USD 200. Buyer must not disclose records.'}]))
    monkeypatch.setattr(comparison.collections, 'unchanged', AsyncMock())
    response = api.post('/collections/' + A + '/compare', json={'file_ids': [A, B], 'focus': 'Payment and disclosure'})
    assert response.status_code == 200
    result = response.json()
    assert result['summary']['supported_difference'] == 1
    assert result['summary']['possible_contradiction'] == 1
    assert {row['file_id'] for row in result['sources']} == {A, B}


def test_malformed_amount_not_partially_extracted():
    assert not comparison.facts('USD 100.123 or USD 1,23.')


def test_leading_conditions_and_truncated_clauses_are_not_opposite_obligations():
    assert not compare('If requested, Buyer must disclose records.', 'Buyer must not disclose records.')['summary']['possible_contradiction']
    assert not compare('Buyer must disclose records', 'Buyer must not disclose records.')['summary']['possible_contradiction']


def test_decimal_obligations_preserve_entire_amount():
    result = compare('Buyer must pay USD 100.50.', 'Buyer must not pay USD 100.75.')
    assert result['summary']['possible_contradiction'] == 0
    assert finding(result, 'Amount (USD)')['classification'] == 'supported_difference'


def test_scaled_and_exponential_amounts_are_not_misinterpreted():
    assert not comparison.facts('USD 100 million and USD 10e3 and USD 20k.')
