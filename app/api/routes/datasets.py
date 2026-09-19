from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.api.deps import get_session
from app.repositories import datasets as repository
from app.schemas.common import Page, Pagination
from app.schemas.datasets import DatasetCreate, DatasetResponse, DatasetUpdate
from app.services import datasets as service

router = APIRouter(prefix="/datasets", tags=["datasets"])
DB = Annotated[Session, Depends(get_session)]


@router.post("", response_model=DatasetResponse, status_code=201)
def create_dataset(payload: DatasetCreate, request: Request, session: DB):
    return service.create_dataset(session, payload, UUID(request.state.request_id))


@router.get("", response_model=Page[DatasetResponse])
def list_datasets(pagination: Annotated[Pagination, Query()], session: DB):
    rows, total = repository.list_page(session, pagination)
    return Page[DatasetResponse](items=rows, total=total, page=pagination.page, page_size=pagination.page_size)


@router.get("/{dataset_id}", response_model=DatasetResponse)
def get_dataset(dataset_id: UUID, session: DB):
    return service.require_dataset(session, dataset_id)


@router.put("/{dataset_id}", response_model=DatasetResponse)
def update_dataset(dataset_id: UUID, payload: DatasetUpdate, request: Request, session: DB):
    return service.update_dataset(session, dataset_id, payload, UUID(request.state.request_id))
