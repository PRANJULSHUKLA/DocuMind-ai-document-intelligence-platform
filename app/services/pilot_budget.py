"""Opt-in, fail-closed limits for the small hosted pilot, shared across processes."""
import os
from datetime import datetime, timezone

from pymongo import MongoClient, ReturnDocument

from app.errors import GenerationUnavailableError

_clients = {}
_blocked_days = set()


def enabled():
    return os.getenv('DOCUMIND_RENDER_PILOT') == '1'


def collection():
    pid = os.getpid()
    if pid not in _clients:
        _clients[pid] = MongoClient(os.environ['MONGODB_URI'], serverSelectionTimeoutMS=5000,
                                   connectTimeoutMS=5000, socketTimeoutMS=5000)
    return _clients[pid][os.environ['DATABASE_NAME']]['render_pilot_budgets']


def key(kind):
    suffix = datetime.now(timezone.utc).strftime('%Y-%m-%d') if kind == 'model' else 'lifetime'
    return f'{kind}:{suffix}'


def reserve(kind):
    if not enabled():
        return
    if kind not in {'model', 'upload'}:
        raise ValueError('Invalid pilot budget.')
    maximum = 30 if kind == 'model' else 5
    try:
        store = collection()
        identifier = key(kind)
        if kind == 'model' and identifier in _blocked_days:
            raise ValueError('Provider quota is exhausted for this UTC day.')
        store.update_one({'_id': identifier}, {'$setOnInsert': {'used': 0}}, upsert=True)
        row = store.find_one_and_update(
            {'_id': identifier, 'used': {'$lt': maximum}, 'blocked': {'$ne': True}},
            {'$inc': {'used': 1}}, return_document=ReturnDocument.AFTER)
        if row is None:
            raise ValueError('Pilot budget reached.')
    except Exception:
        raise GenerationUnavailableError('Pilot usage budget is unavailable or exhausted.') from None


def exhausted():
    """A provider 429 stops further model calls for this UTC day; never retry it."""
    if enabled():
        _blocked_days.add(key('model'))
        try:
            collection().update_one({'_id': key('model')}, {'$set': {'blocked': True}}, upsert=True)
        except Exception:
            # Fail the current request as well. Future reservations fail closed on DB outage.
            raise GenerationUnavailableError('Pilot quota state is unavailable.') from None
