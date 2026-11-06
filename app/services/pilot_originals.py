"""Small immutable pilot originals in MongoDB; no changes to historical records."""
import hashlib
from bson import ObjectId

from app.db.db import database
from app.utils.upload_storage import original_path, save_original

MAX_BYTES = 2 * 1024 * 1024


async def save(document, content):
    if not content or len(content) > MAX_BYTES:
        raise ValueError('Pilot PDFs must be at most 2 MB.')
    await database['render_pilot_originals'].insert_one({
        '_id': ObjectId(document['_id']), 'workspace_id': document['workspace_id'],
        'content_sha256': hashlib.sha256(content).hexdigest(), 'content': content,
    })


async def read(document):
    row = await database['render_pilot_originals'].find_one({
        '_id': ObjectId(document['_id']), 'workspace_id': document['workspace_id'],
    })
    if row is None:
        raise FileNotFoundError('The durable pilot PDF is unavailable.')
    data = row.get('content', b'')
    if (not isinstance(data, bytes) or not data or len(data) > MAX_BYTES
            or hashlib.sha256(data).hexdigest() != row.get('content_sha256')
            or row.get('content_sha256') != document.get('content_sha256')):
        raise ValueError('The durable pilot PDF failed integrity verification.')
    return data


async def restore(root, document):
    """Recreate an ephemeral worker copy only from the authorized immutable original."""
    from starlette.concurrency import run_in_threadpool
    data = await read(document)
    path = original_path(root, document)
    await run_in_threadpool(save_original, path, data)
    return path
