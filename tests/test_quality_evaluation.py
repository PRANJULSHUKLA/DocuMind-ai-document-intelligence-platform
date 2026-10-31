import copy
import json
from pathlib import Path
import pytest
from app.evaluation.quality import evaluate

ROOT = Path(__file__).resolve().parents[1] / 'evaluation'


def fixtures():
    return json.loads((ROOT / 'synthetic-v1.json').read_text()), json.loads((ROOT / 'replay-v1.json').read_text())


def test_replay_detects_seeded_misses_bad_citations_claims_and_isolation():
    data, observations = fixtures()
    report = evaluate(data, observations)
    assert report['counts'] == dict(relevant=10, expected=11, retrieved=12,
        correct_citations=7, citations=10, supported_claims=3, claims=7,
        isolated=9, scoped=10, expected_abstentions=2, abstentions=2)
    assert report['observed_latency_ms_mean'] is None
    assert report['observed_usage'] == []


def test_missing_or_duplicate_observations_fail_instead_of_inflating_scores():
    data, observations = fixtures()
    with pytest.raises(ValueError):
        evaluate(data, observations[:-1])
    with pytest.raises(ValueError):
        evaluate(data, observations + observations[:1])


def test_claim_needs_all_annotated_sources_and_reported_citation():
    data, observations = fixtures()
    partial = copy.deepcopy(observations)
    partial[1]['claims'][0]['source_ids'] = ['a1']
    assert evaluate(data, partial)['counts']['supported_claims'] == 2


def test_foreign_or_unprovenanced_citations_cannot_count_as_correct():
    data, observations = fixtures()
    data['cases'][0]['allowed_file_ids'] = []
    report = evaluate(data, observations)
    assert report['counts']['correct_citations'] == 6
    data, observations = fixtures()
    data['cases'][0]['sources'][0]['processing_run_id'] = None
    observations[0]['citations'][0]['processing_run_id'] = None
    assert evaluate(data, observations)['counts']['correct_citations'] == 6


async def test_production_source_builder_preserves_fixture_identity(monkeypatch):
    from app.services import rag_pipeline
    from types import SimpleNamespace
    data, _ = fixtures()
    source = data['cases'][0]['sources'][0]
    chunk = {**source, '_id': source['source_id'], 'filename': 'Synthetic.pdf', 'chunk_index': 0}
    monkeypatch.setattr(rag_pipeline, 'generate_content_with_fallback', lambda **kwargs: SimpleNamespace(text='USD 100.', candidates=[]))
    result = await rag_pipeline.RAGPipeline().answer_chunks('Amount?', [chunk])
    actual = result['sources'][0]
    assert all(actual[k] == source[k] for k in ('source_id', 'file_id', 'page_number', 'processing_run_id', 'content_sha256'))
    assert actual['excerpt'] == source['text']
