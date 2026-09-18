from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_session
from app.core.errors import AppError
from app.models.jobs import Job
from app.schemas.jobs import JobResponse

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("/{job_id}", response_model=JobResponse)
def get_job(job_id: UUID, session: Annotated[Session, Depends(get_session)]):
    job = session.get(Job, job_id)
    if job is None:
        raise AppError("NOT_FOUND", "작업을 찾을 수 없습니다.", 404)
    return job
