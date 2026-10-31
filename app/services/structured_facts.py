"""Bounded literal facts from published OCR; no generated or persisted claims."""
import re
from datetime import date, datetime
from decimal import Decimal
from fastapi import HTTPException
from app.db.collections.chunks import chunks_collection
from app.services import collections
from app.services.document_view import revision, source_fields

MAX_CHUNKS = 20
MAX_TEXT = 4000
MAX_FACTS = 200
AMOUNT = re.compile(r'\b(USD|EUR|GBP|INR)\s*([0-9]+(?:,[0-9]{3})*(?:\.[0-9]{1,2})?)(?!\w|\.\d|,\d)(?!\s*(?:million|billion|thousand|[kmb]\b))', re.I)
DATE = re.compile(r'\b(?:\d{4}-\d{2}-\d{2}|(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4})\b', re.I)
CLAUSE = re.compile(r'(?:[^.!?;\n]|\.(?=\d))+[.!?;\n]')
OBLIGATION = re.compile(r'^\s*([A-Za-z][A-Za-z ]{0,60}?)\s+(must not|shall not|may not|is prohibited from|must|shall|is required to)\s+(.+?)[.!?;\n]$', re.I)
QUALIFIER = re.compile(r'\b(if|unless|except|provided|subject to|only when|when|until|after|before|during|upon|on receipt|on approval|as long as|in case|where)\b', re.I)
PARTY = re.compile(r'^\s*(Buyer|Seller|Customer|Supplier|Party)\s*:\s*([^.!?;\n]{1,100})[.!?;\n]$', re.I)


def decimal_value(raw):
    # Decimal.normalize() applies context precision and can silently round long
    # literal amounts. Formatting the parsed Decimal preserves every digit.
    value = format(Decimal(raw.replace(',', '')), 'f')
    return value.rstrip('0').rstrip('.') if '.' in value else value


def extract_chunk(chunk, document):
    """Interpret a small supported grammar; retain full, exact sentence context."""
    text = str(chunk.get('text') or '')[:MAX_TEXT]
    source = {**source_fields(chunk), 'filename': document['filename'],
              'page_number': chunk['page_number'], 'chunk_index': chunk['chunk_index'],
              'document_version': revision(document), 'provenance': 'published_ocr'}
    facts = []
    for sentence in CLAUSE.finditer(text):
        quote = sentence[0]
        if len(quote) > 1000:
            continue
        qualifier = QUALIFIER.search(quote)
        conditions = quote[qualifier.start():].strip() if qualifier else None
        def add(kind, value, uncertainty=None):
            facts.append({'kind': kind, 'value': value, 'quotation': quote,
                          'start_offset': sentence.start(), 'end_offset': sentence.end(),
                          'conditions': conditions,
                          'uncertainty': uncertainty or ('qualified_clause' if conditions else 'literal_only'),
                          'source': {**source, 'excerpt': quote}})
        for match in AMOUNT.finditer(quote):
            add('amount', {'amount': decimal_value(match[2]), 'currency': match[1].upper()})
        for match in DATE.finditer(quote):
            try:
                raw = match[0]
                parsed = date.fromisoformat(raw) if raw[0].isdigit() else datetime.strptime(raw.replace(',', ''), '%B %d %Y').date()
            except ValueError:
                continue
            add('date', {'date': parsed.isoformat()})
        match = PARTY.fullmatch(quote)
        if match:
            add('party', {'role': match[1].lower(), 'name': match[2].strip()})
        match = OBLIGATION.fullmatch(quote)
        if match:
            modal = match[2].lower()
            add('obligation', {'party': ' '.join(match[1].lower().split()),
                               'action': ' '.join(match[3].strip().lower().split()),
                               'polarity': 'prohibited' if modal in ('must not', 'shall not', 'may not', 'is prohibited from') else 'required'},
                'qualified_clause' if conditions else 'applicability_requires_review')
        if conditions:
            add('condition', {'text': conditions}, 'interpretation_requires_review')
    return facts


async def published_context(collection_id, workspace, ids):
    if not 1 <= len(ids) <= 5:
        raise HTTPException(400, 'Extract from one to five distinct documents.')
    row, ready, skipped = await collections.context(collection_id, workspace, ids)
    if skipped:
        raise HTTPException(409, 'Selected documents must finish processing.')
    chunks, versions, limitations = [], [], []
    for file_id, doc in ready:
        run, digest = doc.get('active_processing_run_id'), doc.get('content_sha256')
        versions.append({'file_id': file_id, 'filename': doc['filename'], 'document_version': revision(doc),
                         'processing_run_id': run, 'content_sha256': digest})
        if not run or not digest:
            limitations.append({'file_id': file_id, 'reason': 'legacy_unverified_no_extraction'})
            continue
        filters = {'file_id': file_id, 'workspace_id': workspace, 'processing_run_id': run, 'content_sha256': digest}
        cursor = chunks_collection.find(filters, {'embedding': 0}).sort('chunk_index', 1).limit(MAX_CHUNKS + 1).max_time_ms(2000)
        rows = [chunk async for chunk in cursor]
        if len(rows) > MAX_CHUNKS:
            limitations.append({'file_id': file_id, 'reason': 'chunk_limit_reached'})
        for chunk in rows[:MAX_CHUNKS]:
            # Defense in depth even if a repository adapter ignores filters.
            if any(chunk.get(k) != v for k, v in filters.items()):
                raise HTTPException(409, 'Published evidence identity mismatch.')
            if not chunk.get('_id') or type(chunk.get('page_number')) is not int or chunk['page_number'] < 1:
                limitations.append({'file_id': file_id, 'reason': 'missing_source_identity_or_page'})
                continue
            if len(str(chunk.get('text') or '')) > MAX_TEXT:
                limitations.append({'file_id': file_id, 'reason': 'text_limit_reached'})
            chunks.append((chunk, doc))
    return row, ready, chunks, versions, limitations


async def extract(collection_id, workspace, ids):
    row, ready, chunks, versions, limitations = await published_context(collection_id, workspace, ids)
    result = []
    truncated = False
    for chunk, doc in chunks:
        for fact in extract_chunk(chunk, doc):
            if len(result) >= MAX_FACTS:
                truncated = True
                break
            fact['fact_id'] = 'f' + str(len(result) + 1)
            result.append(fact)
    await collections.unchanged(row, workspace, ready)
    return {'schema_version': 1, 'method': 'literal_published_ocr_v1', 'facts': result,
            'documents': versions, 'truncated': truncated,
            'limits': {'documents': 5, 'chunks_per_document': MAX_CHUNKS, 'characters_per_chunk': MAX_TEXT, 'facts': MAX_FACTS},
            'limitations': limitations,
            'notice': 'Bounded literal extraction, not exhaustive interpretation. Conflicting facts are retained; missing facts do not establish absence. Published OCR provenance does not guarantee OCR accuracy.'}
