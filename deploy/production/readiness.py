"""Read-only dependency probe: no model calls, writes, index changes or record reads."""
import asyncio
import os
import sys
from pathlib import Path


async def check():
    from pymongo import AsyncMongoClient
    from redis import Redis
    path = Path(os.environ['UPLOAD_DIR'])
    if not path.is_dir() or not os.access(path, os.W_OK):
        raise RuntimeError('Private upload storage is unavailable')
    redis = Redis.from_url(os.environ['REDIS_URL'], socket_timeout=4, socket_connect_timeout=4)
    try:
        await asyncio.to_thread(redis.ping)
    finally:
        redis.close()
    client = AsyncMongoClient(os.environ['MONGODB_URI'], serverSelectionTimeoutMS=5000, connectTimeoutMS=5000)
    try:
        await client.admin.command('ping')
    finally:
        await client.close()


if __name__ == '__main__':
    try:
        asyncio.run(check())
    except Exception as error:
        print(f'Not ready: {type(error).__name__}', file=sys.stderr)
        raise SystemExit(1) from None
