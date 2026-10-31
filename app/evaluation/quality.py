"""Evaluate recorded retrieval and claim observations against human-authored gold.

No model-as-judge and no network calls. Support means an exact annotated claim
and validated citation, not a general-purpose semantic entailment judgment.
"""
import argparse
import json
from pathlib import Path
from statistics import mean
from time import perf_counter


def ratio(numerator, denominator):
    return round(numerator / denominator, 4) if denominator else None


def evaluate(dataset, observations):
    if dataset.get('schema_version') != 1:
        raise ValueError('Unsupported evaluation schema')
    cases = dataset['cases']
    if len(cases) > 1000 or len({c['id'] for c in cases}) != len(cases):
        raise ValueError('Cases must have unique IDs; maximum 1000')
    by_id = {o['id']: o for o in observations}
    if len(by_id) != len(observations) or set(by_id) != {c['id'] for c in cases}:
        raise ValueError('Exactly one observation is required for every case')
    totals = dict(relevant=0, expected=0, retrieved=0, correct_citations=0,
                  citations=0, supported_claims=0, claims=0, isolated=0,
                  scoped=0, expected_abstentions=0, abstentions=0)
    details, latencies, usage = [], [], []
    for case in cases:
        observation = by_id[case['id']]
        gold = {s['source_id']: s for s in case['sources']}
        relevant = set(case['relevant_source_ids'])
        retrieved = set(observation['retrieved_source_ids'])
        hits = len(retrieved & relevant)
        totals['relevant'] += hits
        totals['expected'] += len(relevant)
        totals['retrieved'] += len(retrieved)
        valid = set()
        for citation in observation.get('citations', []):
            totals['citations'] += 1
            source = gold.get(citation.get('source_id'))
            if source and all(citation.get(k) == source.get(k) for k in
                              ('file_id', 'page_number', 'processing_run_id', 'content_sha256')) and citation.get('quote') and citation['quote'] in source['text'] and source['source_id'] in retrieved:
                valid.add(source['source_id'])
                totals['correct_citations'] += 1
        claims = observation.get('claims', [])
        supported = 0
        for claim in claims:
            expected = next((g for g in case['supported_claims'] if g['text'] == claim['text']), None)
            cited = set(claim.get('source_ids', []))
            if expected and cited and cited.issubset(valid) and set(expected['source_ids']).issubset(cited):
                supported += 1
        totals['claims'] += len(claims)
        totals['supported_claims'] += supported
        allowed = set(case['allowed_file_ids'])
        scope_ok = all(s in gold and gold[s]['file_id'] in allowed for s in retrieved)
        totals['isolated'] += int(scope_ok)
        totals['scoped'] += 1
        if case.get('expect_abstention'):
            totals['expected_abstentions'] += 1
            totals['abstentions'] += int(observation.get('abstained') is True and not claims)
        if observation.get('latency_ms') is not None:
            value = float(observation['latency_ms'])
            if value < 0:
                raise ValueError('Latency cannot be negative')
            latencies.append(value)
        if observation.get('usage') is not None:
            usage.append({'case_id': case['id'], **observation['usage']})
        details.append({'id': case['id'], 'recall': ratio(hits, len(relevant)),
                        'supported_claims': supported, 'claims': len(claims), 'scope_ok': scope_ok})
    return {'schema_version': 1, 'cases': len(cases), 'counts': totals,
            'metrics': {'retrieval_recall': ratio(totals['relevant'], totals['expected']),
                        'retrieval_precision': ratio(totals['relevant'], totals['retrieved']),
                        'citation_correctness': ratio(totals['correct_citations'], totals['citations']),
                        'annotated_claim_support': ratio(totals['supported_claims'], totals['claims']),
                        'scope_isolation': ratio(totals['isolated'], totals['scoped']),
                        'missing_or_conflicting_abstention': ratio(totals['abstentions'], totals['expected_abstentions'])},
            'observed_latency_ms_mean': round(mean(latencies), 3) if latencies else None,
            'observed_usage': usage, 'details': details,
            'limitations': ['Exact gold annotations measure this corpus only; not general semantic entailment.',
                            'Recorded/replay observations do not measure live Atlas or Gemini quality.',
                            'Missing latency/usage remains null or empty; no cost is estimated.']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset', default='evaluation/synthetic-v1.json')
    parser.add_argument('--observations', default='evaluation/replay-v1.json')
    args = parser.parse_args()
    started = perf_counter()
    result = evaluate(json.loads(Path(args.dataset).read_text()), json.loads(Path(args.observations).read_text()))
    result['evaluator_runtime_ms'] = round((perf_counter() - started) * 1000, 3)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
