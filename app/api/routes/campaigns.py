from typing import Annotated
from uuid import UUID
from fastapi import APIRouter, Depends, Query, Request, Header
from datetime import datetime
from sqlalchemy.orm import Session
from app.api.deps import get_session
from app.schemas.campaign import CampaignWrite, CampaignUpdate, CampaignList, CampaignArchive
from app.services import campaigns as service
from app.domain.campaigns.copy_policy import POLICIES, CURRENT_VERSION
from app.schemas.simulations import SimulateSendRequest
from app.services import simulations
from app.services import performance

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


@router.post('/{campaign_id}/simulate-send',status_code=202)
def simulate_send(campaign_id:UUID,payload:SimulateSendRequest,request:Request,session:DB,
                  idempotency_key:Annotated[str|None,Header(alias='Idempotency-Key')]=None):
    return simulations.simulate(session,campaign_id,payload,idempotency_key,UUID(request.state.request_id))


@router.get('/{campaign_id}/runs/{run_id}')
def run_detail(campaign_id:UUID,run_id:UUID,dataset_id:UUID,session:DB):
    return simulations.get_run(session,dataset_id,campaign_id,run_id)


@router.get('/{campaign_id}/runs')
def latest_run(campaign_id:UUID,dataset_id:UUID,session:DB):
    return {'run':simulations.latest_run(session,dataset_id,campaign_id)}


@router.get('/{campaign_id}/performance')
def campaign_performance(campaign_id:UUID,dataset_id:UUID,session:DB,
                         start:Annotated[datetime,Query(alias='from')]=None,
                         end:Annotated[datetime,Query(alias='to')]=None,
                         observation_to:datetime|None=None):
    if start is None or end is None or end<=start:
        from app.core.errors import AppError
        raise AppError('INVALID_PERIOD','성과 기간의 시작과 종료를 올바르게 입력해주세요.',422)
    return performance.campaign_performance(session,dataset_id,campaign_id,start,end,observation_to)
