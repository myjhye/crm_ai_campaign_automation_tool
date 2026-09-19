from typing import Annotated, Literal
from uuid import UUID
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.api.deps import get_session
from app.schemas.analytics import AnalyticsQuery, CustomerQuery, CustomerPage, DashboardSummary
from app.services import analytics as service

router = APIRouter(tags=["customer analytics"])
DB = Annotated[Session, Depends(get_session)]

@router.get("/customers", response_model=CustomerPage)
def customers(query: Annotated[CustomerQuery, Query()], session: DB):
    return service.list_customers(session, query)

@router.get("/customers/{customer_id}")
def customer(customer_id: UUID, query: Annotated[AnalyticsQuery, Query()], session: DB):
    return service.detail(session, query, customer_id)

@router.get("/customers/{customer_id}/events")
def events(customer_id: UUID, query: Annotated[CustomerQuery, Query()], session: DB):
    return service.customer_events(session, query, customer_id)

@router.get("/customers/{customer_id}/deliveries")
def deliveries(customer_id: UUID, query: Annotated[AnalyticsQuery, Query()], session: DB):
    return service.pending_history(session, query, customer_id, "deliveries")

@router.get("/customers/{customer_id}/segments")
def segments(customer_id: UUID, query: Annotated[AnalyticsQuery, Query()], session: DB):
    return service.pending_history(session, query, customer_id, "segments")

@router.get("/dashboard/overview", response_model=DashboardSummary)
def overview(query: Annotated[AnalyticsQuery, Query()], session: DB):
    return service.overview(session, query)

@router.get("/dashboard/funnel")
def funnel(query: Annotated[AnalyticsQuery, Query()], session: DB):
    return service.funnel(session, query)

@router.get("/dashboard/segments")
def distribution(query: Annotated[AnalyticsQuery, Query()], session: DB):
    return service.distribution(session, query)
