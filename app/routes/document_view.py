from urllib.parse import quote
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from app.auth import Identity, current_identity
from app.errors import GenerationUnavailableError
from app.services import document_view

router = APIRouter()


async def mapped(operation):
    try:
        return await operation
    except FileNotFoundError:
        raise HTTPException(404, 'Document not found.') from None
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from None
    except GenerationUnavailableError:
        raise HTTPException(503, "Generation is temporarily unavailable. Please try again later.") from None
    except RuntimeError as exc:
        raise HTTPException(409, str(exc)) from None


@router.get('/files/{file_id}/view')
async def view(file_id: str, identity: Identity = Depends(current_identity)):
    return await mapped(document_view.metadata(file_id, identity.workspace_id))


@router.get('/files/{file_id}/content')
async def content(file_id: str, version: str | None = Query(None, max_length=64), identity: Identity = Depends(current_identity)):
    document, data = await mapped(document_view.content(file_id, identity.workspace_id, version))
    return Response(data, media_type='application/pdf', headers={
        'Cache-Control': 'private, no-store', 'X-Content-Type-Options': 'nosniff',
        'Content-Disposition': "inline; filename*=UTF-8''" + quote(document['filename'], safe=''),
        'ETag': '"' + document_view.revision(document) + '"',
    })


@router.get('/files/{file_id}/search')
async def search(file_id: str, q: str = Query(..., min_length=2, max_length=200), after: int = Query(-1, ge=-1),
                 limit: int = Query(20, ge=1, le=25), identity: Identity = Depends(current_identity)):
    return await mapped(document_view.search(file_id, identity.workspace_id, q, after, limit))
