from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field, field_validator
from app.auth import Identity, current_identity
from app.routes.document_view import mapped
from app.services import collections as service

router = APIRouter(prefix='/collections')


class Create(BaseModel):
    name: str = Field(min_length=1, max_length=100)

    @field_validator('name')
    @classmethod
    def clean(cls, value):
        if not value.strip():
            raise ValueError('Name cannot be empty.')
        return value.strip()


class Edit(BaseModel):
    revision: int = Field(ge=1)
    name: str | None = Field(default=None, min_length=1, max_length=100)
    file_ids: list[str] | None = Field(default=None, max_length=10)

    @field_validator('name')
    @classmethod
    def clean(cls, value):
        return Create.clean(value) if value is not None else None


class Ask(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    file_ids: list[str] | None = Field(default=None, max_length=10)

    @field_validator('question')
    @classmethod
    def clean(cls, value):
        if not value.strip():
            raise ValueError('Question cannot be empty.')
        return value.strip()


@router.get('')
async def listing(identity: Identity = Depends(current_identity), limit: int = Query(100, ge=1, le=100)):
    rows = await service.collections.find({'workspace_id': identity.workspace_id}).sort('_id', -1).limit(limit).to_list(length=limit)
    return [service.public(row) for row in rows]


@router.post('', status_code=201)
async def create(body: Create, identity: Identity = Depends(current_identity)):
    return await service.create(body.name, identity.workspace_id)


@router.patch('/{collection_id}')
async def edit(collection_id: str, body: Edit, identity: Identity = Depends(current_identity)):
    return await mapped(service.update(collection_id, identity.workspace_id, body.revision, body.name, body.file_ids))


@router.delete('/{collection_id}', status_code=204)
async def delete(collection_id: str, identity: Identity = Depends(current_identity)):
    row = await service.owned(collection_id, identity.workspace_id)
    await service.collections.delete_one({'_id': row['_id'], 'workspace_id': identity.workspace_id})


@router.post('/{collection_id}/chat')
async def ask(collection_id: str, body: Ask, identity: Identity = Depends(current_identity)):
    return await mapped(service.ask(collection_id, identity.workspace_id, body.question, body.file_ids))


class Compare(BaseModel):
    file_ids: list[str] = Field(min_length=2, max_length=5)
    focus: str = Field(default='Key amounts, dates and obligations', min_length=2, max_length=500)

    @field_validator('focus')
    @classmethod
    def clean(cls, value):
        if not value.strip():
            raise ValueError('Enter a comparison focus.')
        return value.strip()


@router.post('/{collection_id}/compare')
async def compare(collection_id: str, body: Compare, identity: Identity = Depends(current_identity)):
    from app.services.comparison import compare as run
    return await mapped(run(collection_id, identity.workspace_id, body.file_ids, body.focus))


class Extract(BaseModel):
    file_ids: list[str] = Field(min_length=1, max_length=5)


@router.post('/{collection_id}/facts')
async def extract_facts(collection_id: str, body: Extract, identity: Identity = Depends(current_identity)):
    from app.services.structured_facts import extract
    return await mapped(extract(collection_id, identity.workspace_id, body.file_ids))
