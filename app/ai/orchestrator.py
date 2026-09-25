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
from app.schemas.policies import ValidationRequest
from app.services.ai_context import resolve_hint, segment_hint, segment_options


def payload_hash(payload):
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def chat(database, settings, query, request_id, provider=None):
    if query.analysis_campaign_id:
        from app.ai.performance import analyze, PerformanceRequest
        return analyze(database,settings,PerformanceRequest(dataset_id=query.dataset_id,campaign_id=query.analysis_campaign_id,
            start=query.start,end=query.end,prompt=query.prompt,conversation_id=query.conversation_id),request_id,provider)
    if query.campaign_brief or query.campaign_id:
        from app.ai.campaigns import propose
        return propose(database,settings,query,request_id,provider)
    started = time.monotonic()
    # Close all transactions before waiting for the model.
    validation_campaign = None
    with database.sessions() as session:
        require_dataset(session, query.dataset_id)
        version = data_version(session, query.dataset_id)
        hint = resolve_hint(session, query.dataset_id, query.context_hint)
        options = segment_options(session, query.dataset_id)
        if query.validation_campaign_id:
            from app.services.campaigns import detail
            validation_campaign = detail(session, query.dataset_id, query.validation_campaign_id)
            if validation_campaign['status'] != 'DRAFT' or validation_campaign['version'] != query.validation_campaign_version:
                raise AppError('VERSION_CONFLICT', '작성 중인 최신 캠페인만 검수할 수 있습니다.')
    status, name, tokens = 'FAILED', None, 0
    try:
        prompt = safe_prompt(query.prompt)
        safe_prompt(json.dumps([item['name'] for item in options], ensure_ascii=False))
        provider = provider or (MockProvider() if settings.ai_mode == 'mock' else OpenAIProvider(settings))
        context = {'from': query.start.isoformat(), 'to': query.end.isoformat(), 'reference_at': query.reference_at.isoformat()}
        context.update(prior_context=hint, available_segments=options)
        if validation_campaign:
            context['validation_campaign'] = {key: validation_campaign[key] for key in ('id','name','channel','status','version')}
        if query.context_hint and hint is None:
            name, args = 'clarify', {'question':'이전 대상이 변경되었거나 더 이상 사용할 수 없습니다. 대상부터 다시 선택해주세요.'}
        elif prompt.strip().rstrip('.?!') in ('이 세그먼트로 캠페인 초안 만들어', '이 세그먼트로 캠페인 초안 만들어줘'):
            # The UI's explicit continuation must not depend on model tool selection.
            name = 'clarify'
            args = {'question': (f"‘{hint['name']}’ 대상으로 캠페인을 준비할게요. 사용할 채널과 혜택을 알려주세요. 예: 이메일로 15% 할인 쿠폰, 다정한 말투로 만들어줘."
                if hint and hint['kind'] == 'segment' else '먼저 대상 세그먼트를 저장하고 해당 결과의 캠페인 초안 버튼을 눌러주세요.')}
        else:
            name, args, tokens = provider.plan(prompt, context)
        if name == 'compare_campaigns' and isinstance(args,dict):
            args={'scope':'dataset',**args}
            from app.services.ai_context import comparison_scope
            if args['scope'] in ('dataset','context'):
                args['scope']=comparison_scope(prompt,args['scope'])
        allowed = {'get_metric': {'metric'}, 'preview_segment': {'condition_json'}, 'create_segment_draft': {'name', 'condition_json'},
                   'clarify': {'question'}, 'validate_campaign': set(),
                   'compare_campaigns': {'filter','sort','order','limit','scope'},
                   'prepare_campaign': {'channel','benefit','objective','brand_tone'}}
        if name not in allowed or not isinstance(args, dict) or set(args) != allowed[name]:
            raise ValueError('Invalid tool')
        # Re-resolve references after the external call; never trust client labels.
        with database.sessions() as check:
            if query.context_hint and resolve_hint(check, query.dataset_id, query.context_hint) != hint:
                name, args, hint = 'clarify', {'question':'이전 대상이 변경되었습니다. 대상을 다시 선택해주세요.'}, None
        if name == 'prepare_campaign':
            if not hint or hint['kind'] != 'segment':
                name, args = 'clarify', {'question':'캠페인 대상으로 사용할 세그먼트를 먼저 저장해주세요. 저장한 결과에서 캠페인 초안으로 이어갈 수 있습니다.'}
            elif not all(isinstance(value, str) for value in args.values()): raise ValueError('Invalid brief')
            elif not args['channel'] or not args['benefit']:
                name, args = 'clarify', {'question':'채널과 혜택을 알려주세요. 예: 이메일로 15% 할인 쿠폰, 다정한 말투로 만들어줘. 기본 초안은 전환율 목표 5%, A/B 50:50으로 제안하며 저장 전에 검토할 수 있습니다.'}
            else:
                from app.ai.schemas import CampaignSetup
                from app.ai.planning import plan
                if ''.join(args['benefit'].split()) not in ''.join(prompt.split()):
                    raise ValueError('Benefit must come from this request')
                setup = CampaignSetup(segment_revision_id=hint['revision_id'], **args)
                response = plan(database, settings, query.model_copy(update={'campaign_setup':setup}), request_id, provider)
                status = 'SUCCESS'
                return {**response, 'context_hint':hint, 'conversation_id':query.conversation_id}
        if name in ('preview_segment', 'create_segment_draft'):
            # Validate before opening the execution transaction. Retry malformed DSL once;
            # never weaken the public validator or send customer rows/error input to the model.
            original_tool = name
            for attempt in range(2):
                try:
                    if not isinstance(args.get('condition_json'), str) or len(args['condition_json']) > 16000:
                        raise ValueError('Invalid DSL')
                    condition_payload = {'dataset_id':query.dataset_id, 'condition':json.loads(args['condition_json']),
                        'reference_at':query.reference_at, 'data_version':version}
                    PreviewRequest.model_validate(condition_payload)
                    if name == 'create_segment_draft':
                        SegmentWrite.model_validate({**condition_payload, 'name':safe_prompt(args['name'])})
                    break
                except (ValueError, TypeError, ValidationError):
                    if attempt: raise
                    repair = {**context, 'condition_repair': {
                        'tool':original_tool,
                        'instruction':'조건 형식을 검증하지 못했습니다. 등록된 field/comparison만 사용하고 정수·금액·boolean 타입을 확인하세요. 그룹은 operator/conditions만, 단일 조건은 field/comparison/value만 포함하세요.'}}
                    retry_name, retry_args, retry_tokens = provider.plan(prompt, repair)
                    tokens += retry_tokens
                    if retry_name != original_tool or not isinstance(retry_args, dict) or set(retry_args) != allowed[original_tool]:
                        raise ValueError('Invalid repair tool')
                    args = retry_args
            with database.sessions() as check:
                if query.context_hint and resolve_hint(check, query.dataset_id, query.context_hint) != hint:
                    raise AppError('DATA_VERSION_CONFLICT', '대상이 변경되었습니다. 다시 요청해주세요.')
        with database.sessions() as session:
            if name == 'validate_campaign':
                if not validation_campaign: raise ValueError('Campaign context required')
                from app.services import policies
                parsed = ValidationRequest(dataset_id=query.dataset_id, campaign_version=query.validation_campaign_version,
                    reference_at=query.reference_at)
                result = policies.validate(session, query.validation_campaign_id, parsed, request_id, actor_type='AI')
                result['campaign_name'] = validation_campaign['name']
                kind, message = 'campaign_validation', ('정책 검수를 통과했습니다. 승인 여부는 캠페인 화면에서 결정해주세요.'
                    if result['passed'] else '정책 검수에서 제외 대상 또는 차단 사유를 확인했습니다.')
            elif name == 'get_metric':
                if args['metric'] not in METRICS: raise ValueError('Invalid metric')
                result = analytics.overview(session, query.model_copy(update={'data_version': version}))
                result['metrics'] = {args['metric']: result['metrics'][args['metric']]}
                kind, message = 'metric', '선택한 기간의 데이터셋 전체 지표입니다.'
            else:
                require_dataset(session, query.dataset_id, lock=True)
                if data_version(session, query.dataset_id) != version:
                    raise AppError('DATA_VERSION_CONFLICT', '데이터가 변경되었습니다. 다시 요청해주세요.')
                if name == 'clarify':
                    if not isinstance(args['question'], str) or len(args['question']) > 1000: raise ValueError('Invalid question')
                    result, kind, message = {}, 'clarification', safe_prompt(args['question'])
                elif name == 'compare_campaigns':
                    from app.services.performance import compare_campaigns
                    result = compare_campaigns(session, query.dataset_id, args, query.start, query.end, hint)
                    kind = 'campaign_comparison'
                    message = '조건에 맞는 완료 캠페인이 없습니다.' if not result['campaigns'] else '선택한 발송 기간의 완료 캠페인을 비교했습니다.'
                    ids = [str(row['campaign_id']) for row in result['campaigns']]
                    hint = {'kind':'campaign_list','campaign_ids':ids,'label':f'위 {len(ids)}개 캠페인 기준으로'} if ids else None
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
                'request_id': request_id, 'conversation_id':query.conversation_id, 'context_hint':hint}
    except (ValueError, TypeError, ValidationError):
        raise AppError('AI_INVALID_OUTPUT', 'AI 조건을 검증하지 못했습니다. 조건을 구체적으로 다시 입력해주세요.', 502) from None
    finally:
        with database.sessions.begin() as session:
            session.add(AIExecutionLog(dataset_id=query.dataset_id, request_id=request_id,
                conversation_id=query.conversation_id,
                provider=settings.ai_mode, model=settings.ai_model if settings.ai_mode == 'live' else 'fixture',
                status=status, tool_name=name if name in ('get_metric', 'preview_segment', 'create_segment_draft', 'clarify', 'validate_campaign', 'compare_campaigns', 'prepare_campaign') else None,
                elapsed_ms=int((time.monotonic() - started) * 1000), total_tokens=tokens))


def confirm(session, proposal_id, dataset_id, request_id):
    with session.begin():
        require_dataset(session, dataset_id, lock=True)
        proposal = session.scalar(select(AIActionProposal).where(AIActionProposal.id == proposal_id,
            AIActionProposal.dataset_id == dataset_id).with_for_update())
        if proposal is None: raise AppError('NOT_FOUND', '제안을 찾을 수 없습니다.', 404)
        if proposal.confirmed_at:
            if proposal.action_type != 'SEGMENT':
                from app.services.campaigns import detail
                return detail(session,dataset_id,proposal.campaign_id)
            result = segments.detail(session, dataset_id, proposal.segment_id)
            return {**result, 'context_hint':segment_hint(result)}
        if proposal.expires_at <= datetime.now(timezone.utc):
            raise AppError('AI_PROPOSAL_EXPIRED', '제안이 만료되었습니다. 다시 요청해주세요.')
        if payload_hash(proposal.payload) != proposal.payload_hash or UUID(proposal.payload['dataset_id']) != dataset_id:
            raise AppError('AI_PROPOSAL_CHANGED', '제안 내용이 변경되었습니다. 다시 요청해주세요.')
        if proposal.action_type in ('CAMPAIGN_CREATE','CAMPAIGN_COPY'):
            from app.ai.campaigns import apply
            return apply(session,proposal,request_id)
        if proposal.action_type == 'CAMPAIGN_FOLLOWUP':
            from app.ai.performance import apply_followup
            return apply_followup(session,proposal,request_id)
        result = segments.save(session, SegmentWrite.model_validate(proposal.payload), request_id,
                               managed_transaction=True, created_source='AI')
        proposal.segment_id = result['id']
        proposal.confirmed_at = datetime.now(timezone.utc)
        return {**result, 'context_hint':segment_hint(result)}
