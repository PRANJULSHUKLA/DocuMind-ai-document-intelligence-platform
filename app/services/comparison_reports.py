"""Explicitly saved server-verified snapshots. No LLM calls on save or export."""
import hashlib
import json
from datetime import datetime, timezone
from bson import ObjectId
from fastapi import HTTPException
from app.db.db import database
from app.services import semantic_comparison
from app.services.document_access import get_authorized_document
from app.services.document_view import revision

reports = database['saved_comparison_reports_v1']
MAX_SNAPSHOT_BYTES = 1_000_000


def digest(result):
    canonical = {k: v for k, v in result.items() if k != 'review_digest'}
    return hashlib.sha256(json.dumps(canonical, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()


def metadata(row):
    return {'id': str(row['_id']), 'title': row['title'], 'created_at': row['created_at'],
            'collection_id': row['collection_id'], 'method': row['snapshot']['method'],
            'schema_version': row['snapshot']['schema_version'], 'review_digest': row['review_digest']}


async def save(collection_id, workspace, ids, focus, expected_digest, title):
    result = await semantic_comparison.compare(collection_id, workspace, ids, focus)
    if digest(result) != expected_digest:
        raise HTTPException(409, 'Comparison changed. Review the current findings before saving.')
    if len(json.dumps(result, ensure_ascii=False).encode()) > MAX_SNAPSHOT_BYTES:
        raise HTTPException(413, 'Report snapshot is too large.')
    row = {'workspace_id': workspace, 'collection_id': collection_id, 'title': title,
           'created_at': datetime.now(timezone.utc).isoformat(), 'review_digest': expected_digest,
           'reviewed': True, 'snapshot': result, 'model': None,
           'retention': 'Retained until explicitly deleted by an authorized workspace user. Source/collection deletion does not delete this snapshot.'}
    row['_id'] = (await reports.insert_one(row)).inserted_id
    return metadata(row)


async def owned(report_id, workspace):
    if not ObjectId.is_valid(report_id):
        raise HTTPException(404, 'Report not found.')
    row = await reports.find_one({'_id': ObjectId(report_id), 'workspace_id': workspace})
    if not row:
        raise HTTPException(404, 'Report not found.')
    return row


async def read(report_id, workspace):
    row = await owned(report_id, workspace)
    states = []
    for source in row['snapshot']['documents']:
        try:
            current = await get_authorized_document(source['file_id'], workspace)
        except FileNotFoundError:
            # Preserve the private snapshot but withhold content after source access
            # is lost. The workspace can still list its metadata and delete it.
            raise HTTPException(409, 'A source is no longer accessible. Report content/export is withheld; its metadata can still be listed or deleted.') from None
        states.append({'file_id': source['file_id'], 'saved_version': source['document_version'],
                       'current_version': revision(current),
                       'stale': revision(current) != source['document_version'] or current.get('status') != 'completed'})
    return {**metadata(row), 'reviewed': row['reviewed'], 'model': row['model'], 'retention': row['retention'],
            'source_states': states, 'stale': any(s['stale'] for s in states), 'snapshot': row['snapshot']}


async def listing(workspace, limit):
    rows = await reports.find({'workspace_id': workspace}, {'snapshot.findings': 0, 'snapshot.sources': 0, 'snapshot.extracted_facts': 0}).sort('_id', -1).limit(limit).to_list(length=limit)
    return [metadata(row) for row in rows]


async def delete(report_id, workspace):
    row = await owned(report_id, workspace)
    await reports.delete_one({'_id': row['_id'], 'workspace_id': workspace})
