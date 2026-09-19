from uuid import UUID
from fastapi import APIRouter, Request
from app.ai.schemas import ChatRequest, Confirmation
from app.ai import orchestrator
from app.core.errors import AppError

router = APIRouter(prefix='/ai', tags=['ai'])


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


@router.post('/actions/{proposal_id}/confirm')
def confirm(proposal_id: UUID, payload: Confirmation, request: Request):
    database = request.app.state.database
    if database is None: raise AppError('DATABASE_UNAVAILABLE', 'DB 연결이 필요합니다.', 503)
    with database.sessions() as session:
        return orchestrator.confirm(session, proposal_id, payload.dataset_id, UUID(request.state.request_id))
