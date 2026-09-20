from typing import Annotated
from uuid import UUID
from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session
from app.api.deps import get_session
from app.schemas.campaign import CampaignWrite, CampaignUpdate, CampaignList, CampaignArchive
from app.services import campaigns as service
from app.domain.campaigns.copy_policy import POLICIES, CURRENT_VERSION

router = APIRouter(prefix='/campaigns', tags=['campaigns'])
DB = Annotated[Session,Depends(get_session)]


@router.get('/copy-policy')
def policy(): return {'version':CURRENT_VERSION,'channels':POLICIES[CURRENT_VERSION],'format':'plain_text','demo_only':True}


@router.get('')
def listing(query:Annotated[CampaignList,Query()],session:DB): return service.list_campaigns(session,query)


@router.post('',status_code=201)
def create(payload:CampaignWrite,request:Request,session:DB): return service.save(session,payload,UUID(request.state.request_id))


@router.get('/{campaign_id}')
def detail(campaign_id:UUID,dataset_id:UUID,session:DB): return service.detail(session,dataset_id,campaign_id)


@router.put('/{campaign_id}')
def update(campaign_id:UUID,payload:CampaignUpdate,request:Request,session:DB): return service.save(session,payload,UUID(request.state.request_id),campaign_id)


@router.delete('/{campaign_id}')
def archive(campaign_id:UUID,payload:CampaignArchive,request:Request,session:DB): return service.archive(session,payload,campaign_id,UUID(request.state.request_id))
