from typing import Annotated
from uuid import UUID
from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session
from app.api.deps import get_session
from app.schemas.segments import PreviewRequest, SegmentWrite, SegmentUpdate, SegmentList, SegmentArchive
from app.services import segments as service
from app.domain.segments.fields import FIELDS
router = APIRouter(prefix='/segments', tags=['segments'])
DB = Annotated[Session, Depends(get_session)]

@router.get('/fields')
def fields():
    return {'items': [{'name': name, **spec} for name, spec in FIELDS.items()], 'max_depth': 3, 'max_conditions': 20}

@router.post('/preview')
def preview(payload: PreviewRequest, session: DB):
    return service.preview(session, payload)

@router.get('')
def list_segments(query: Annotated[SegmentList, Query()], session: DB):
    return service.list_segments(session, query)

@router.post('', status_code=201)
def create(payload: SegmentWrite, request: Request, session: DB):
    return service.save(session, payload, UUID(request.state.request_id))

@router.get('/{segment_id}')
def get(segment_id: UUID, dataset_id: UUID, session: DB):
    return service.detail(session, dataset_id, segment_id)

@router.put('/{segment_id}')
def update(segment_id: UUID, payload: SegmentUpdate, request: Request, session: DB):
    return service.save(session, payload, UUID(request.state.request_id), segment_id)

@router.delete('/{segment_id}')
def archive(segment_id: UUID, payload: SegmentArchive, request: Request, session: DB):
    return service.archive(session, payload, segment_id, UUID(request.state.request_id))
