from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_session
from app.repositories.audit import list_page
from app.schemas.audit import AuditFilters, AuditResponse
from app.schemas.common import Page

router = APIRouter(tags=["audit"])


@router.get("/audit-logs", response_model=Page[AuditResponse])
def list_audit_logs(filters: Annotated[AuditFilters, Query()],
                    session: Annotated[Session, Depends(get_session)]):
    rows, total = list_page(session, filters)
    return Page[AuditResponse](items=rows, total=total, page=filters.page, page_size=filters.page_size)
