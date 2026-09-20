from app.core.errors import AppError
from app.models.campaigns import Campaign
from app.repositories import campaigns as repository
from app.services.datasets import require_dataset
from app.services.audit import record_change
from app.domain.campaigns.copy_policy import CURRENT_VERSION
from contextlib import nullcontext
from datetime import datetime, timezone

FIELDS = ('name','objective','channel','benefit','brand_tone','primary_kpi','target_value','planned_at','coupon_expires_at','segment_revision_id')


def summary(row):
    return {'id':row.id, 'dataset_id':row.dataset_id, 'version':row.version, 'status':row.status,
        'policy_version':row.policy_version, **{key:getattr(row,key) for key in FIELDS}, 'target_value':format(row.target_value, 'f')}


def representation(session, row):
    variants, exclusions = repository.children(session,row)
    return {**summary(row), 'exclusion_revision_ids':exclusions,
        'variants':[{'id':v.id, **{key:getattr(v,key) for key in ('variant_name','subject','body','hypothesis','allocation_bp')}} for v in variants]}


def detail(session, dataset_id, campaign_id):
    require_dataset(session,dataset_id)
    row = repository.get(session,dataset_id,campaign_id)
    if row is None: raise AppError('NOT_FOUND','캠페인을 찾을 수 없습니다.',404)
    return representation(session,row)


def list_campaigns(session, query):
    require_dataset(session,query.dataset_id)
    rows,total = repository.page(session,query)
    return {'items':[summary(row) for row in rows], 'total':total, 'page':query.page, 'page_size':query.page_size}


def save(session, request, request_id, campaign_id=None, *, managed_transaction=False):
    with nullcontext() if managed_transaction else session.begin():
        if sum(v.allocation_bp for v in request.variants) != 10000:
            raise AppError('INVALID_ALLOCATION','A/B 비율 합계는 100%여야 합니다.',422)
        require_dataset(session,request.dataset_id,lock=True)
        ids = [request.segment_revision_id,*request.exclusion_revision_ids]
        if len(repository.revisions(session,request.dataset_id,ids)) != len(ids):
            raise AppError('SEGMENT_NOT_FOUND','같은 데이터셋의 세그먼트 버전을 선택해주세요.',404)
        previous = None
        if campaign_id:
            row = repository.get(session,request.dataset_id,campaign_id,lock=True)
            if row is None: raise AppError('NOT_FOUND','캠페인을 찾을 수 없습니다.',404)
            if row.version != request.version or row.status != 'DRAFT':
                raise AppError('VERSION_CONFLICT','캠페인이 변경되었거나 편집할 수 없는 상태입니다. 최신 내용을 불러오세요.')
            previous = row.version
            row.version += 1
        else:
            row = Campaign(dataset_id=request.dataset_id)
            session.add(row)
        for key in FIELDS: setattr(row,key,getattr(request,key))
        row.policy_version = CURRENT_VERSION
        session.flush()
        repository.replace_children(session,row,request)
        session.flush()
        record_change(session,dataset_id=row.dataset_id,resource_id=row.id,actor_type='VISITOR',
            action='CAMPAIGN_CREATED' if previous is None else 'CAMPAIGN_UPDATED',request_id=request_id,previous_version=previous,new_version=row.version)
        return representation(session,row)


def archive(session, request, campaign_id, request_id):
    with session.begin():
        require_dataset(session,request.dataset_id,lock=True)
        row=repository.get(session,request.dataset_id,campaign_id,lock=True)
        if row is None: raise AppError('NOT_FOUND','캠페인을 찾을 수 없습니다.',404)
        if row.status!='DRAFT' or row.version!=request.version:
            raise AppError('VERSION_CONFLICT','작성 중인 최신 캠페인만 삭제할 수 있습니다.')
        previous=row.version; row.version+=1; row.archived_at=datetime.now(timezone.utc)
        record_change(session,dataset_id=row.dataset_id,resource_id=row.id,actor_type='VISITOR',action='CAMPAIGN_ARCHIVED',request_id=request_id,previous_version=previous,new_version=row.version)
        return {'id':row.id,'archived':True,'version':row.version}
