import json
from fastapi import APIRouter, Depends, Query, Response
from pydantic import BaseModel, Field, field_validator
from starlette.concurrency import run_in_threadpool
from app.auth import Identity, current_identity
from app.routes.collections import Compare
from app.routes.document_view import mapped
from app.services import comparison_reports as service

def private_response(response: Response):
    response.headers['Cache-Control'] = 'private, no-store'
    response.headers['X-Content-Type-Options'] = 'nosniff'


router = APIRouter(prefix='/comparison-reports', dependencies=[Depends(private_response)])


class Save(Compare):
    title: str = Field(min_length=1, max_length=100)
    expected_digest: str = Field(pattern=r'^[a-f0-9]{64}$')
    reviewed: bool

    @field_validator('title')
    @classmethod
    def title_not_blank(cls, value):
        if not value.strip(): raise ValueError('Enter a title.')
        return value.strip()

    @field_validator('reviewed')
    @classmethod
    def explicit_review(cls, value):
        if value is not True: raise ValueError('Confirm that you reviewed the findings.')
        return value


@router.post('/collection/{collection_id}', status_code=201)
async def save(collection_id: str, body: Save, identity: Identity = Depends(current_identity)):
    return await mapped(service.save(collection_id, identity.workspace_id, body.file_ids, body.focus, body.expected_digest, body.title))


@router.get('')
async def listing(identity: Identity = Depends(current_identity), limit: int = Query(50, ge=1, le=100)):
    return await service.listing(identity.workspace_id, limit)


@router.get('/{report_id}')
async def read(report_id: str, identity: Identity = Depends(current_identity)):
    return await mapped(service.read(report_id, identity.workspace_id))


@router.delete('/{report_id}', status_code=204)
async def delete(report_id: str, identity: Identity = Depends(current_identity)):
    await mapped(service.delete(report_id, identity.workspace_id))


@router.get('/{report_id}/export')
async def export(report_id: str, format: str = Query('json', pattern='^(json|pdf)$'), identity: Identity = Depends(current_identity)):
    result = await mapped(service.read(report_id, identity.workspace_id))
    if format == 'pdf':
        from app.services.report_pdf import render
        content = await run_in_threadpool(render, result)
        media_type = 'application/pdf'
    else:
        content = json.dumps(result, ensure_ascii=False).encode()
        media_type = 'application/json'
    return Response(content, media_type=media_type, headers={'Content-Disposition': f'attachment; filename="documind-report-{report_id}.{format}"', 'Cache-Control': 'private, no-store', 'X-Content-Type-Options': 'nosniff'})
