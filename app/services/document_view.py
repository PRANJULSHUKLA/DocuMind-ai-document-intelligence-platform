"""Private, version-aware original access and deterministic extracted-text search."""
from contextlib import ExitStack
import hashlib
import os
from pathlib import Path
import re
import stat

from fastapi import HTTPException
from starlette.concurrency import run_in_threadpool
from app.services.document_access import get_authorized_document, get_ready_document
from app.db.collections.chunks import chunks_collection
from app.utils.upload_storage import original_path

UPLOAD_DIR = Path(os.getenv('UPLOAD_DIR', str(Path(__file__).resolve().parents[2] / 'uploads'))).resolve()
MAX_BYTES = int(os.getenv('MAX_UPLOAD_MB', '25')) * 1024 * 1024


def revision(document):
    value = f"{document['_id']}:{document.get('active_processing_run_id') or ''}:{document.get('content_sha256') or ''}"
    return hashlib.sha256(value.encode()).hexdigest()


def checked_path(document):
    raw = UPLOAD_DIR / str(document['_id']) / document['filename']
    if raw.is_symlink() or raw.parent.is_symlink():
        raise HTTPException(404, 'PDF_UNAVAILABLE')
    try:
        return original_path(UPLOAD_DIR, document)
    except (ValueError, OSError):
        raise HTTPException(404, 'PDF_UNAVAILABLE') from None


def read_original(document):
    checked_path(document)
    try:
        with ExitStack() as opened:
            # Anchor each component to a trusted directory descriptor. O_NOFOLLOW
            # on only the final resolved path cannot prevent parent-swap races.
            directory_flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
            root_fd = os.open(UPLOAD_DIR, directory_flags)
            opened.callback(os.close, root_fd)
            directory_fd = os.open(str(document['_id']), directory_flags, dir_fd=root_fd)
            opened.callback(os.close, directory_fd)
            fd = os.open(document['filename'], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory_fd)
            stream = opened.enter_context(os.fdopen(fd, 'rb'))
            if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
                raise HTTPException(404, 'PDF_UNAVAILABLE')
            content = stream.read(MAX_BYTES + 1)
    except OSError:
        raise HTTPException(404, 'PDF_UNAVAILABLE') from None
    if len(content) > MAX_BYTES:
        raise HTTPException(413, 'PDF_TOO_LARGE')
    expected = document.get('content_sha256')
    if expected and hashlib.sha256(content).hexdigest() != expected:
        raise HTTPException(409, 'PDF_VERSION_MISMATCH')
    return content


async def metadata(file_id, workspace_id):
    document = await get_authorized_document(file_id, workspace_id)
    try:
        available = await run_in_threadpool(lambda: checked_path(document).is_file())
    except HTTPException:
        available = False
    return {'file_id': file_id, 'filename': document['filename'], 'status': document['status'],
            'total_pages': document.get('total_pages', 0), 'version': revision(document),
            'processing_run_id': document.get('active_processing_run_id'),
            'content_sha256': document.get('content_sha256'), 'original_available': available,
            'provenance': 'verified' if document.get('active_processing_run_id') and document.get('content_sha256') else 'legacy_unverified'}


async def content(file_id, workspace_id, version=None):
    document = await get_authorized_document(file_id, workspace_id)
    if version and version != revision(document):
        raise HTTPException(409, 'SOURCE_VERSION_MISMATCH')
    data = await run_in_threadpool(read_original, document)
    current = await get_authorized_document(file_id, workspace_id)
    if revision(current) != revision(document):
        raise HTTPException(409, 'SOURCE_VERSION_MISMATCH')
    return document, data


def source_fields(chunk):
    return {'file_id': chunk.get('file_id'), 'source_id': str(chunk['_id']) if chunk.get('_id') else None,
            'processing_run_id': chunk.get('processing_run_id'), 'content_sha256': chunk.get('content_sha256')}


async def search(file_id, workspace_id, query, after=-1, limit=20):
    document = await get_ready_document(file_id, workspace_id)
    filters = {'file_id': file_id, 'workspace_id': workspace_id, 'chunk_index': {'$gt': after},
               'text': {'$regex': re.escape(query), '$options': 'i'},
               'processing_run_id': document.get('active_processing_run_id')}
    cursor = chunks_collection.find(filters).sort('chunk_index', 1).limit(limit + 1).max_time_ms(1500)
    rows = [row async for row in cursor]
    results = []
    for row in rows[:limit]:
        text = row.get('text', '')
        offset = text.lower().find(query.lower())
        start = max(0, offset - 120)
        results.append({**source_fields(row), 'filename': document['filename'],
                        'page_number': row.get('page_number'), 'chunk_index': row['chunk_index'],
                        'excerpt': text[start:start + 600]})
    return {'results': results, 'version': revision(document),
            'next_after': rows[limit - 1]['chunk_index'] if len(rows) > limit else None}
