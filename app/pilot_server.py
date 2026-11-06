"""Same-origin gateway used only by the restricted, opt-in Render pilot."""
import asyncio
import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.server import app as api


class BodyLimit:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http' or scope['method'] not in {'POST', 'PUT', 'PATCH'}:
            return await self.app(scope, receive, send)
        body = bytearray()
        while True:
            message = await receive()
            if message['type'] == 'http.disconnect':
                return
            part = message.get('body', b'')
            if len(body) + len(part) > 2 * 1024 * 1024 + 65536:
                return await JSONResponse({'detail': 'Pilot request is too large.'}, status_code=413)(scope, receive, send)
            body.extend(part)
            if not message.get('more_body', False):
                break
        delivered = False

        async def bounded_receive():
            nonlocal delivered
            if not delivered:
                delivered = True
                return {'type': 'http.request', 'body': bytes(body), 'more_body': False}
            return await receive()

        return await self.app(scope, bounded_receive, send)


app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
app.add_middleware(BodyLimit)
_busy = asyncio.Semaphore(1)


@app.middleware('http')
async def single_request(request, call_next):
    # A small request backlog bounds concurrent API/model memory. Static assets
    # are separate so PDF.js can still load while a document request is running.
    if request.url.path.startswith('/api/'):
        if _busy.locked():
            return JSONResponse({'detail': 'Pilot is busy. Retry after the current request finishes.'},
                                status_code=503, headers={'Retry-After': '5'})
        async with _busy:
            return await call_next(request)
    return await call_next(request)


@app.middleware('http')
async def security_headers(request, call_next):
    response = await call_next(request)
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['Referrer-Policy'] = 'no-referrer'
    issuer = os.environ.get('OIDC_ISSUER', '').rstrip('/')
    response.headers['Content-Security-Policy'] = (
        "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
        f"connect-src 'self' {issuer}; img-src 'self' data: blob:; worker-src 'self' blob:; "
        "font-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'none'")
    if request.url.path.startswith('/api/') or request.url.path == '/auth/callback':
        response.headers['Cache-Control'] = 'no-store'
    return response


@app.get('/healthz')
async def readiness():
    from app.db.client import mongo_client
    from app.queue.q import redis_connection
    try:
        await mongo_client.admin.command('ping')
        await asyncio.to_thread(redis_connection.ping)
    except Exception:
        return JSONResponse({'status': 'unavailable'}, status_code=503)
    return {'status': 'ready', 'profile': 'restricted-render-pilot'}


app.mount('/api', api)
FRONTEND = Path('/srv/documind/frontend-dist')


@app.get('/auth/callback')
async def callback():
    return FileResponse(FRONTEND / 'index.html', headers={'Cache-Control': 'no-store'})


app.mount('/', StaticFiles(directory=str(FRONTEND), html=True, check_dir=False), name='frontend')
