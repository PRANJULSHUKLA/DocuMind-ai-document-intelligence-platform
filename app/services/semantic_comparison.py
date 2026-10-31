"""Verified normalization of a bounded obligation grammar, not legal equivalence.

Unrecognized paraphrases abstain. No similarity threshold or model loop is used.
The existing literal comparator is retained alongside these additional findings.
"""
from collections import defaultdict
from datetime import date, datetime
from decimal import Decimal
from fastapi import HTTPException
from app.services import structured_facts
from app.services.comparison import compare_evidence


def normalized_action(text):
    def amount(match):
        return match[1].upper() + ' ' + format(Decimal(match[2].replace(',', '')).normalize(), 'f')
    def parsed_date(match):
        raw = match[0]
        try:
            value = date.fromisoformat(raw) if raw[0].isdigit() else datetime.strptime(raw.replace(',', '').title(), '%B %d %Y').date()
            return value.isoformat()
        except ValueError:
            return raw
    value = structured_facts.AMOUNT.sub(amount, text)
    value = structured_facts.DATE.sub(parsed_date, value)
    # Reviewable, deliberately small payment paraphrase rule. No fuzzy matching.
    if value.startswith('make payment of '):
        value = 'pay ' + value[len('make payment of '):]
    return ' '.join(value.lower().split())


def action_key(value):
    value = structured_facts.AMOUNT.sub('<amount>', value)
    return structured_facts.DATE.sub('<date>', value)


def compare_facts(extraction, focus):
    docs = extraction['documents']
    versions = {doc['file_id']: doc for doc in docs}
    ready = [(doc['file_id'], doc) for doc in docs]
    chunks, seen = [], set()
    sources, grouped = [], defaultdict(lambda: defaultdict(list))
    for fact in extraction['facts']:
        source = fact['source']
        doc = versions.get(source['file_id'])
        if not doc or not fact['quotation'] or fact['quotation'] != source.get('excerpt') or not source.get('source_id') or any(source.get(k) != doc.get(k) or not doc.get(k) for k in ('document_version', 'processing_run_id', 'content_sha256')):
            raise HTTPException(409, 'Evidence provenance validation failed.')
        key = (source['source_id'], fact['quotation'])
        if key not in seen:
            seen.add(key)
            chunks.append({**source, '_id': source['source_id'], 'text': fact['quotation']})
        if fact['kind'] != 'obligation':
            continue
        value = fact['value']
        action = normalized_action(value['action'])
        grouped[(value['party'], action_key(action))][source['file_id']].append((fact, action))
        sources.append({**source, 'evidence_id': fact['fact_id']})
    baseline = compare_evidence(ready, chunks, focus)
    findings = []
    for (party, action), by_file in sorted(grouped.items()):
        signatures = {file_id: {(normalized, f['value']['polarity']) for f, normalized in facts} for file_id, facts in by_file.items()}
        conditional = any(f['conditions'] for facts in by_file.values() for f, _ in facts)
        if len(by_file) != len(docs):
            label, explanation = 'missing_information', 'No aligned obligation was observed for some selected documents. Different parties or unrecognized paraphrases are not assumed equivalent.'
        elif conditional or any(len(values) != 1 for values in signatures.values()):
            label, explanation = 'insufficient_evidence', 'Conditions, applicability qualifiers or conflicting observations require human review. No equivalence or contradiction is established.'
        else:
            values = [next(iter(value)) for value in signatures.values()]
            actions = {v[0] for v in values}
            polarities = {v[1] for v in values}
            if len(actions) == 1 and len(polarities) == 1:
                label, explanation = 'supported_agreement', 'The bounded obligation propositions align under the documented normalization rules. This does not establish contractual equivalence or applicability.'
            elif len(actions) == 1:
                label, explanation = 'possible_contradiction', 'Aligned parties and actions have opposite explicit obligation polarities. Check full scope, exceptions and applicability before concluding contradiction.'
            else:
                label, explanation = 'supported_difference', 'Aligned obligation wording contains different explicit values. This is a difference in observed propositions, not proof of contradiction.'
        findings.append({'topic': f'Normalized obligation: {party} → {action}', 'classification': label, 'explanation': explanation,
                         'documents': [{'file_id': doc['file_id'], 'filename': doc['filename'],
                                        'facts': [{'values': [normalized, f['value']['polarity']], 'evidence_id': f['fact_id']} for f, normalized in by_file.get(doc['file_id'], [])]} for doc in docs]})
    if not findings:
        findings = [{'topic': 'Normalized obligations', 'classification': 'insufficient_evidence',
                     'explanation': 'No obligations in the supported grammar were observed. Arbitrary semantic paraphrases remain unverified.', 'documents': []}]
    all_findings = baseline['findings'] + findings[:30]
    return {**baseline, 'schema_version': 2, 'method': 'literal_plus_verified_normalization_v1',
            'documents': docs, 'extracted_facts': extraction['facts'], 'extraction_limits': extraction['limits'],
            'extraction_limitations': extraction['limitations'], 'extraction_truncated': extraction['truncated'],
            'findings': all_findings, 'sources': baseline['sources'] + sources,
            'summary': {label: sum(f['classification'] == label for f in all_findings) for label in baseline['summary']},
            'limitations': baseline['limitations'] + [extraction['notice'],
                'Semantic coverage is limited to modal normalization, explicit dates/currencies and one reviewed payment paraphrase. No general semantic equivalence is claimed.',
                'Qualified clauses abstain; distinct party labels are not entity-resolved. No model calls or whole-document completeness claim.']}


async def compare(collection_id, workspace, ids, focus):
    if not 2 <= len(ids) <= 5:
        raise HTTPException(400, 'Compare two to five distinct documents.')
    extraction = await structured_facts.extract(collection_id, workspace, ids)
    result = compare_facts(extraction, focus)
    from app.services.comparison_reports import digest
    return {**result, 'review_digest': digest(result)}
