from typing import Annotated
from uuid import UUID
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session
from app.api.deps import get_session
from app.schemas.policies import PolicyUpdate, ValidationRequest, ApprovalRequest, ApprovalDecision, ResumeEditing
from app.services import policies as service

router=APIRouter(tags=['policies']); DB=Annotated[Session,Depends(get_session)]

@router.get('/policy-settings')
def get_policy(dataset_id:UUID,session:DB): return service.get_policy(session,dataset_id)

@router.put('/policy-settings')
def update_policy(payload:PolicyUpdate,request:Request,session:DB): return service.update_policy(session,payload,UUID(request.state.request_id))

@router.get('/campaigns/{campaign_id}/review')
def review(campaign_id:UUID,dataset_id:UUID,session:DB): return service.review(session,dataset_id,campaign_id)

@router.post('/campaigns/{campaign_id}/validate',status_code=201)
def validate(campaign_id:UUID,payload:ValidationRequest,request:Request,session:DB): return service.validate(session,campaign_id,payload,UUID(request.state.request_id))

@router.post('/campaigns/{campaign_id}/request-approval')
def request_approval(campaign_id:UUID,payload:ApprovalRequest,request:Request,session:DB): return service.request_approval(session,campaign_id,payload,UUID(request.state.request_id))

@router.post('/campaigns/{campaign_id}/approve')
def approve(campaign_id:UUID,payload:ApprovalDecision,request:Request,session:DB): return service.decide(session,campaign_id,payload,UUID(request.state.request_id),True)

@router.post('/campaigns/{campaign_id}/reject')
def reject(campaign_id:UUID,payload:ApprovalDecision,request:Request,session:DB): return service.decide(session,campaign_id,payload,UUID(request.state.request_id),False)

@router.post('/campaigns/{campaign_id}/resume-editing')
def resume(campaign_id:UUID,payload:ResumeEditing,request:Request,session:DB): return service.resume(session,campaign_id,payload,UUID(request.state.request_id))
