from uuid import UUID
from fastapi import APIRouter, Request
from app.ai.schemas import ChatRequest, Confirmation
from app.ai import orchestrator
from app.core.errors import AppError
from app.ai.campaigns import CopyRevision, revise
from pydantic import ValidationError

router = APIRouter(prefix='/ai', tags=['ai'])


@router.post('/campaign-plan')
def campaign_plan(payload: ChatRequest,request: Request):
    from app.ai.planning import plan
    database=request.app.state.database
    if database is None:raise AppError('DATABASE_UNAVAILABLE','DB 연결이 필요합니다.',503)
    return plan(database,request.app.state.settings,payload,UUID(request.state.request_id),getattr(request.app.state,'ai_provider',None))


@router.post('/actions/{proposal_id}/revise')
def revise_copy(proposal_id: UUID, payload: CopyRevision, request: Request):
    database=request.app.state.database
    if database is None: raise AppError('DATABASE_UNAVAILABLE','DB 연결이 필요합니다.',503)
    try:
        with database.sessions() as session: return revise(session,proposal_id,payload)
    except ValidationError:
        raise AppError('INVALID_COPY','카피가 채널 입력 기준에 맞지 않습니다.',422) from None


@router.get('/status')
def status(request: Request):
    settings = request.app.state.settings
    return {'mode': settings.ai_mode, 'available': settings.ai_mode == 'mock' or bool(settings.openai_api_key)}


@router.post('/chat')
def chat(payload: ChatRequest, request: Request):
    database = request.app.state.database
    if database is None: raise AppError('DATABASE_UNAVAILABLE', 'DB 연결이 필요합니다.', 503)
    return orchestrator.chat(database, request.app.state.settings, payload, UUID(request.state.request_id),
                             getattr(request.app.state, 'ai_provider', None))


@router.post('/campaign-draft')
def campaign_draft(payload: ChatRequest, request: Request):
    if not payload.campaign_brief or payload.campaign_id:
        raise AppError('AI_CAMPAIGN_INPUT','새 캠페인 조건을 입력해주세요.',422)
    return chat(payload,request)


@router.post('/copy-variants')
def copy_variants(payload: ChatRequest, request: Request):
    if not payload.campaign_id or payload.campaign_brief:
        raise AppError('AI_CAMPAIGN_INPUT','기존 캠페인을 선택해주세요.',422)
    return chat(payload,request)


@router.post('/actions/{proposal_id}/confirm')
def confirm(proposal_id: UUID, payload: Confirmation, request: Request):
    database = request.app.state.database
    if database is None: raise AppError('DATABASE_UNAVAILABLE', 'DB 연결이 필요합니다.', 503)
    with database.sessions() as session:
        return orchestrator.confirm(session, proposal_id, payload.dataset_id, UUID(request.state.request_id))
