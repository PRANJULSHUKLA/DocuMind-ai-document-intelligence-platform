"""Additive workspace collections; no deletion or re-ingestion of original files."""
import asyncio
import time
from datetime import datetime, timezone
from bson import ObjectId
from fastapi import HTTPException
from app.db.db import database
from app.services.document_access import get_authorized_document
from app.llm.embeddings import generate_embedding
from app.services.rag_pipeline import RAGPipeline

collections = database['document_collections']
MAX_DOCUMENTS = 10


def public(row):
    return {'id': str(row['_id']), 'name': row['name'], 'file_ids': row.get('file_ids', []), 'revision': row.get('revision', 1)}


async def owned(collection_id, workspace):
    if not ObjectId.is_valid(collection_id):
        raise HTTPException(404, 'Collection not found.')
    row = await collections.find_one({'_id': ObjectId(collection_id), 'workspace_id': workspace})
    if not row:
        raise HTTPException(404, 'Collection not found.')
    return row


async def authorize_ids(ids, workspace):
    if len(ids) > MAX_DOCUMENTS or len(ids) != len(set(ids)):
        raise HTTPException(400, 'Select up to 10 distinct documents.')
    return [await get_authorized_document(file_id, workspace) for file_id in ids]


async def create(name, workspace):
    row = {'name': name, 'workspace_id': workspace, 'file_ids': [], 'revision': 1, 'created_at': datetime.now(timezone.utc)}
    row['_id'] = (await collections.insert_one(row)).inserted_id
    return public(row)


async def update(collection_id, workspace, revision, name=None, file_ids=None):
    row = await owned(collection_id, workspace)
    if file_ids is not None:
        await authorize_ids(file_ids, workspace)
    fields = {key: value for key, value in {'name': name, 'file_ids': file_ids}.items() if value is not None}
    result = await collections.update_one({'_id': row['_id'], 'workspace_id': workspace, 'revision': revision},
                                          {'$set': fields, '$inc': {'revision': 1}})
    if not result.matched_count:
        raise HTTPException(409, 'Collection changed. Refresh before editing.')
    return public({**row, **fields, 'revision': revision + 1})


async def context(collection_id, workspace, selected=None):
    row = await owned(collection_id, workspace)
    ids = row.get('file_ids', []) if selected is None else selected
    if not ids or not set(ids).issubset(row.get('file_ids', [])):
        raise HTTPException(400, 'Select documents belonging to this collection.')
    documents = await authorize_ids(ids, workspace)
    ready = [(file_id, doc) for file_id, doc in zip(ids, documents) if doc.get('status') == 'completed']
    skipped = [{'file_id': file_id, 'status': doc.get('status')} for file_id, doc in zip(ids, documents) if doc.get('status') != 'completed']
    return row, ready, skipped


async def retrieve(ready, question, workspace):
    if not ready:
        return []
    pipeline = RAGPipeline()
    embedding = await asyncio.to_thread(generate_embedding, question)
    chunks = []
    # Bounded fan-out reuses one embedding, preserving the existing Atlas index.
    for file_id, document in ready:
        rows = await pipeline.retriever.retrieve_chunks(file_id, question, workspace, limit=3, query_embedding=embedding)
        chunks.extend(row for row in rows if row.get('file_id') == file_id and
                      row.get('processing_run_id') == document.get('active_processing_run_id') and
                      row.get('content_sha256') == document.get('content_sha256'))
    return sorted(chunks, key=lambda row: row.get('score', 0), reverse=True)


async def unchanged(row, workspace, ready):
    current = await owned(str(row['_id']), workspace)
    if current.get('revision') != row.get('revision'):
        raise HTTPException(409, 'Collection changed during the request. Ask again.')
    for file_id, document in ready:
        latest = await get_authorized_document(file_id, workspace)
        if latest.get('status') != 'completed' or latest.get('active_processing_run_id') != document.get('active_processing_run_id') or latest.get('content_sha256') != document.get('content_sha256'):
            raise HTTPException(409, 'Document changed during the request. Ask again.')


async def ask(collection_id, workspace, question, selected=None):
    started = time.perf_counter()
    row, ready, skipped = await context(collection_id, workspace, selected)
    chunks = await retrieve(ready, question, workspace)
    retrieval_ms = (time.perf_counter() - started) * 1000
    result = await RAGPipeline().answer_chunks(
        question, chunks, retrieval_ms=retrieval_ms,
        overall_start=started, file_id=collection_id,
    )
    await unchanged(row, workspace, ready)
    result["total_time_ms"] = round((time.perf_counter() - started) * 1000, 2)
    return {**result, 'skipped_documents': skipped, 'eligible_documents': len(ready)}
