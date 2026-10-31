"""Conservative deterministic comparison of retrieved facts, never legal equivalence.

No free-form generated claims or model-invented citations enter the result.
"""
import re
from collections import defaultdict
from datetime import date, datetime
from decimal import Decimal
from fastapi import HTTPException
from app.services import collections
from app.services.document_view import source_fields

AMOUNT = re.compile(r'\b(USD|EUR|GBP|INR)\s*([0-9]+(?:,[0-9]{3})*(?:\.[0-9]{1,2})?)(?!\w|\.\d|,\d)(?!\s*(?:million|billion|thousand|[kmb]\b))', re.I)
DATE = re.compile(r'\b(?:\d{4}-\d{2}-\d{2}|(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4})\b', re.I)
OBLIGATION = re.compile(r'\b([A-Za-z][A-Za-z ]{0,60}?)\s+(must|shall)\s+(not\s+)?((?:[^.!?;\n]|\.(?=\d)){3,160})(?=[.!?;\n])', re.I)
CONDITIONAL = re.compile(r'\b(if|unless|except|provided|subject to|may|whether)\b', re.I)


def facts(text):
    result = defaultdict(set)
    for match in AMOUNT.finditer(text):
        value = format(Decimal(match[2].replace(',', '')), 'f')
        if '.' in value:
            value = value.rstrip('0').rstrip('.')
        result['Amount (' + match[1].upper() + ')'].add(value)
    for match in DATE.finditer(text):
        raw = match[0]
        try:
            parsed = date.fromisoformat(raw) if raw[0].isdigit() else datetime.strptime(raw.replace(',', ''), '%B %d %Y').date()
        except ValueError:
            continue
        result['Explicit dates'].add(parsed.isoformat())
    # Only complete sentences are interpreted; truncation and leading conditions
    # must not turn a qualified clause into an unconditional obligation.
    for sentence in re.findall(r'(?:[^.!?;\n]|\.(?=\d))+[.!?;\n]', text):
        if CONDITIONAL.search(sentence):
            continue
        for match in OBLIGATION.finditer(sentence):
            subject = ' '.join(match[1].lower().split())
            action = ' '.join(match[4].lower().split())
            key = 'Obligation: ' + subject + ' → ' + action
            result[key].add('prohibited' if match[3] else 'required')
    return result


def compare_evidence(ready, chunks, focus):
    evidence = []
    counts = defaultdict(int)
    budget = 8000
    for chunk in chunks:
        file_id = chunk.get('file_id')
        if file_id not in {item[0] for item in ready} or counts[file_id] >= 2:
            continue
        # Never extend or paraphrase the actual source passage.
        text = str(chunk.get('text') or '')[:700]
        if not text.strip() or budget < len(text):
            continue
        budget -= len(text)
        counts[file_id] += 1
        evidence.append({**source_fields(chunk), 'filename': chunk.get('filename'),
                         'page_number': chunk.get('page_number'), 'chunk_index': chunk.get('chunk_index'),
                         'excerpt': text, 'evidence_id': 'e' + str(len(evidence) + 1)})
    by_topic = defaultdict(lambda: defaultdict(list))
    for source in evidence:
        for topic, values in facts(source['excerpt']).items():
            by_topic[topic][source['file_id']].append({'values': sorted(values), 'evidence_id': source['evidence_id']})
    findings = []
    for topic, documents in sorted(by_topic.items()):
        values = {file_id: set(value for row in rows for value in row['values']) for file_id, rows in documents.items()}
        missing = [file_id for file_id, _ in ready if file_id not in values]
        sets = list(values.values())
        if missing:
            classification = 'missing_information'
            explanation = 'No matching fact was found in the bounded retrieved passages for some documents. This does not establish absence from the full PDF.'
        elif topic.startswith('Obligation:') and any(len(value) != 1 for value in sets):
            classification = 'insufficient_evidence'
            explanation = 'Conflicting obligation polarities occur within the retrieved evidence. Review the full clauses and their conditions.'
        elif all(value == sets[0] for value in sets):
            classification = 'supported_agreement'
            explanation = 'These extracted values match across the selected documents. Matching values alone do not establish equivalent terms or obligations.'
        elif topic.startswith('Obligation:'):
            classification = 'possible_contradiction'
            explanation = 'The same explicit subject and action appear required in one passage and prohibited in another. Scope, exceptions, and applicability require human verification.'
        else:
            classification = 'supported_difference'
            explanation = 'The retrieved passages contain different explicit values. This alone is not a contradiction; compare what each value refers to.'
        findings.append({'topic': topic, 'classification': classification, 'explanation': explanation,
                         'documents': [{'file_id': file_id, 'filename': doc['filename'], 'facts': documents.get(file_id, []),
                                        'status': 'observed' if file_id in values else 'not_found_in_retrieved_evidence'} for file_id, doc in ready]})
    if not findings:
        findings.append({'topic': 'Retrieved evidence', 'classification': 'insufficient_evidence',
                         'explanation': 'No supported currency amounts, unambiguous dates, or unconditional must/shall obligations were extracted. No agreement or contradiction can be established.', 'documents': []})
    findings = findings[:30]
    counts = {label: sum(row['classification'] == label for row in findings) for label in
              ['supported_agreement', 'supported_difference', 'possible_contradiction', 'missing_information', 'insufficient_evidence']}
    return {'schema_version': 1, 'focus': focus, 'method': 'deterministic_retrieved_facts_v1',
            'summary': counts, 'findings': findings[:30], 'sources': evidence,
            'limitations': ['Comparison covers bounded retrieved evidence, not every page.',
                           'Amounts require explicit ISO currency codes; ambiguous numeric dates and conditional obligations are not interpreted.',
                           'Legacy source passages are not cryptographically verified. PDF access checks current provenance separately.']}


async def compare(collection_id, workspace, ids, focus):
    if not 2 <= len(ids) <= 5:
        raise HTTPException(400, 'Compare two to five distinct documents.')
    row, ready, skipped = await collections.context(collection_id, workspace, ids)
    if skipped:
        raise HTTPException(409, 'All selected documents must finish processing before comparison.')
    chunks = await collections.retrieve(ready, focus + ' amounts dates obligations must shall payment', workspace)
    result = compare_evidence(ready, chunks, focus)
    await collections.unchanged(row, workspace, ready)
    return result
