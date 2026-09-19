import hashlib
import json
import time
from datetime import datetime, timezone, timedelta
from uuid import UUID
from pydantic import ValidationError
from sqlalchemy import select
from app.ai.provider import MockProvider, OpenAIProvider, safe_prompt
from app.ai.tools import METRICS
from app.core.errors import AppError
from app.models.ai import AIActionProposal, AIExecutionLog
from app.repositories.imports import data_version
from app.schemas.segments import PreviewRequest, SegmentWrite
from app.services import segments, analytics
from app.services.datasets import require_dataset


def payload_hash(payload):
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def chat(database, settings, query, request_id, provider=None):
    started = time.monotonic()
    # Close all transactions before waiting for the model.
    with database.sessions() as session:
        require_dataset(session, query.dataset_id)
        version = data_version(session, query.dataset_id)
    status, name, tokens = 'FAILED', None, 0
    try:
        prompt = safe_prompt(query.prompt)
        provider = provider or (MockProvider() if settings.ai_mode == 'mock' else OpenAIProvider(settings))
        name, args, tokens = provider.plan(prompt, {'from': query.start.isoformat(), 'to': query.end.isoformat(), 'reference_at': query.reference_at.isoformat()})
        allowed = {'get_metric': {'metric'}, 'preview_segment': {'condition_json'}, 'create_segment_draft': {'name', 'condition_json'}, 'clarify': {'question'}}
        if name not in allowed or not isinstance(args, dict) or set(args) != allowed[name]:
            raise ValueError('Invalid tool')
        with database.sessions() as session:
            if name == 'get_metric':
                if args['metric'] not in METRICS: raise ValueError('Invalid metric')
                result = analytics.overview(session, query.model_copy(update={'data_version': version}))
                result['metrics'] = {args['metric']: result['metrics'][args['metric']]}
                kind, message = 'metric', '선택한 기간의 지표입니다.'
            else:
                require_dataset(session, query.dataset_id, lock=True)
                if data_version(session, query.dataset_id) != version:
                    raise AppError('DATA_VERSION_CONFLICT', '데이터가 변경되었습니다. 다시 요청해주세요.')
                if name == 'clarify':
                    if not isinstance(args['question'], str) or len(args['question']) > 1000: raise ValueError('Invalid question')
                    result, kind, message = {}, 'clarification', safe_prompt(args['question'])
                else:
                    if not isinstance(args['condition_json'], str) or len(args['condition_json']) > 16000: raise ValueError('Invalid DSL')
                    payload = {'dataset_id': query.dataset_id, 'condition': json.loads(args['condition_json']),
                               'reference_at': query.reference_at, 'data_version': version}
                    parsed = PreviewRequest.model_validate(payload)
                    result = segments.preview(session, parsed)
                    kind, message = 'segment_preview', '조건과 대상 고객을 확인해주세요.'
                    if name == 'create_segment_draft':
                        write = SegmentWrite.model_validate({**payload, 'name': safe_prompt(args['name'])})
                        canonical = write.model_dump(mode='json')
                        canonical['condition'] = write.condition.canonical()
                        proposal = AIActionProposal(dataset_id=query.dataset_id, payload=canonical,
                            payload_hash=payload_hash(canonical), expires_at=datetime.now(timezone.utc) + timedelta(minutes=30))
                        session.add(proposal); session.flush()
                        result = {**result, 'name': write.name, 'proposal_id': proposal.id, 'expires_at': proposal.expires_at}
                session.commit()
        status = 'SUCCESS'
        return {'message': message, 'result_type': kind, 'data': result, 'mode': settings.ai_mode,
                'dataset_id': query.dataset_id, 'reference_at': query.reference_at, 'data_version': version,
                'request_id': request_id}
    except (ValueError, TypeError, ValidationError):
        raise AppError('AI_INVALID_OUTPUT', 'AI 조건을 검증하지 못했습니다. 조건을 구체적으로 다시 입력해주세요.', 502) from None
    finally:
        with database.sessions.begin() as session:
            session.add(AIExecutionLog(dataset_id=query.dataset_id, request_id=request_id,
                provider=settings.ai_mode, model=settings.ai_model if settings.ai_mode == 'live' else 'fixture',
                status=status, tool_name=name if name in ('get_metric', 'preview_segment', 'create_segment_draft', 'clarify') else None,
                elapsed_ms=int((time.monotonic() - started) * 1000), total_tokens=tokens))


def confirm(session, proposal_id, dataset_id, request_id):
    with session.begin():
        require_dataset(session, dataset_id, lock=True)
        proposal = session.scalar(select(AIActionProposal).where(AIActionProposal.id == proposal_id,
            AIActionProposal.dataset_id == dataset_id).with_for_update())
        if proposal is None: raise AppError('NOT_FOUND', '제안을 찾을 수 없습니다.', 404)
        if proposal.confirmed_at:
            return segments.detail(session, dataset_id, proposal.segment_id)
        if proposal.expires_at <= datetime.now(timezone.utc):
            raise AppError('AI_PROPOSAL_EXPIRED', '제안이 만료되었습니다. 다시 요청해주세요.')
        if payload_hash(proposal.payload) != proposal.payload_hash or UUID(proposal.payload['dataset_id']) != dataset_id:
            raise AppError('AI_PROPOSAL_CHANGED', '제안 내용이 변경되었습니다. 다시 요청해주세요.')
        result = segments.save(session, SegmentWrite.model_validate(proposal.payload), request_id,
                               managed_transaction=True, created_source='AI')
        proposal.segment_id = result['id']
        proposal.confirmed_at = datetime.now(timezone.utc)
        return result
