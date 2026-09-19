from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.api.deps import get_session
from app.core.errors import AppError
from app.models.jobs import Job
from app.schemas.imports import Kind, Mode
from app.services import imports as service

router = APIRouter(prefix="/data/import", tags=["data imports"])
DB = Annotated[Session, Depends(get_session)]

class ImportResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    import_batch_id: UUID = Field(validation_alias="id")
    dataset_id: UUID
    kind: str
    status: str
    file_hash: str
    job_id: UUID | None
    summary: dict
    expires_at: datetime | None


def stage(session, **kwargs):
    with session.begin():
        batch = service.preview(session, **kwargs)
        return ImportResponse.model_validate(batch)


@router.post("/{kind}/preview", response_model=ImportResponse, status_code=201,
             openapi_extra={"requestBody": {"required": True, "content": {
                 "text/csv": {"schema": {"type": "string", "format": "binary"}}}}})
async def preview(kind: Kind, request: Request, session: DB, dataset_id: UUID,
                  reference_at: Annotated[AwareDatetime, Query()], mode: Mode = "insert"):
    if request.headers.get("content-type", "").split(";")[0].lower() != "text/csv":
        raise AppError("CSV_REQUIRED", "Send the CSV as a text/csv request body.", 415)
    content = bytearray()
    async for chunk in request.stream():
        if len(content) + len(chunk) > service.MAX_BYTES:
            raise AppError("IMPORT_TOO_LARGE", "CSV exceeds 20 MiB.", 413)
        content.extend(chunk)
    return await run_in_threadpool(stage, session, dataset_id=dataset_id, kind=kind,
                                   content=bytes(content), mode=mode, reference_at=reference_at,
                                   request_id=UUID(request.state.request_id))


@router.post("/{batch_id}/commit", response_model=ImportResponse, status_code=202)
def commit(batch_id: UUID, session: DB):
    with session.begin():
        return ImportResponse.model_validate(service.commit_batch(session, batch_id))


@router.get("/{batch_id}", response_model=ImportResponse)
def detail(batch_id: UUID, session: DB):
    batch = service.require_batch(session, batch_id)
    result = ImportResponse.model_validate(batch)
    if batch.job_id and batch.status == "QUEUED":
        job = session.get(Job, batch.job_id)
        if job.status == "FAILED":
            result.status = "FAILED"
    return result
