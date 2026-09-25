"""Seed historical portfolio campaigns through the normal approval and worker pipeline.

Only DEMO/ANALYSIS datasets are accepted. Existing resources are never overwritten.
Dates are relative to dataset.reference_at, not the moving wall clock.
"""
import argparse
import hashlib
import time
from datetime import timedelta, timezone, datetime
from uuid import UUID, NAMESPACE_URL, uuid5

from sqlalchemy import select, text, func

from app.core.config import Settings
from app.db.session import Database
from app.models.datasets import Dataset, AuditLog
from app.models.customers import Customer, CustomerChannel, Order
from app.models.jobs import DatasetVersion
from app.models.campaigns import Campaign
from app.schemas.segments import SegmentWrite
from app.schemas.campaign import CampaignWrite
from app.schemas.policies import ValidationRequest, ApprovalRequest, ApprovalDecision
from app.schemas.simulations import SimulateSendRequest
from app.services import segments, campaigns, policies, simulations
from app.services.datasets import require_dataset
from app.workers.runner import run_once
from scripts.data.korean_names import synthetic_name

VERSION = 'portfolio-campaigns-v1'


def leaf(field, comparison, value):
    return dict(field=field, comparison=comparison, value=value)


def both(*conditions):
    return dict(operator='AND', conditions=list(conditions))


SEGMENTS = {
    '휴면 VIP': both(leaf('days_since_last_purchase', 'GTE', 60), leaf('total_purchase_amount', 'GTE', '300000')),
    '신규 미구매': both(leaf('days_since_signup', 'LTE', 30), leaf('order_count', 'EQ', 0)),
    '이메일 미동의': leaf('email_consent', 'EQ', False),
    '장바구니 이탈': both(leaf('cart_events', 'GTE', 1), leaf('purchase_events', 'EQ', 0)),
    '반복 구매자': leaf('order_count', 'GTE', 3),
    '모바일 이탈': both(leaf('mobile_landing_events', 'GTE', 1), leaf('purchase_events', 'EQ', 0)),
}

# Four campaigns per time bucket. Distinct hours avoid cross-campaign attribution ties.
COMBINATIONS = (
    ('휴면 VIP', 'EMAIL', '재구매 유도', 30),
    ('휴면 VIP', 'PUSH', '재구매 유도', 30),
    ('이메일 미동의', 'PUSH', '재동의 유도', 30),
    ('휴면 VIP', 'SMS', '재구매 유도', 30),
    ('장바구니 이탈', 'EMAIL', '구매 완료 유도', 14),
    ('장바구니 이탈', 'PUSH', '구매 완료 유도', 14),
    ('반복 구매자', 'SMS', '리텐션 강화', 14),
    ('모바일 이탈', 'PUSH', '재방문 유도', 14),
    ('신규 미구매', 'EMAIL', '첫 구매 유도', 2),
    ('신규 미구매', 'SMS', '첫 구매 유도', 2),
    ('신규 미구매', 'PUSH', '첫 구매 유도', 1),
    ('반복 구매자', 'EMAIL', '리텐션 강화', 1),
)

# Append-only: existing v1 audit/idempotency keys and campaigns stay unchanged.
EXTRA_COMBINATIONS = (
    ('휴면 VIP', 'EMAIL', '재구매 유도', 10),
    ('휴면 VIP', 'PUSH', '재구매 유도', 10),
    ('휴면 VIP', 'SMS', '재구매 유도', 10),
    ('이메일 미동의', 'PUSH', '재동의 유도', 10),
    ('장바구니 이탈', 'EMAIL', '구매 완료 유도', 7),
    ('장바구니 이탈', 'PUSH', '구매 완료 유도', 7),
    ('반복 구매자', 'SMS', '리텐션 강화', 7),
    ('모바일 이탈', 'PUSH', '재방문 유도', 7),
    ('반복 구매자', 'EMAIL', '리텐션 강화', 4),
    ('신규 미구매', 'EMAIL', '첫 구매 유도', 4),
    ('신규 미구매', 'SMS', '첫 구매 유도', 4),
    ('신규 미구매', 'PUSH', '첫 구매 유도', 4),
)
ALL_COMBINATIONS = COMBINATIONS + EXTRA_COMBINATIONS


def sent_at(reference, index):
    return reference - timedelta(days=ALL_COMBINATIONS[index][3], hours=index % 4)


def marker(session, dataset_id, key):
    return session.scalar(select(AuditLog).where(AuditLog.dataset_id == dataset_id, AuditLog.event_key == key))


def mark(session, dataset_id, key, resource_id, details=None):
    session.add(AuditLog(dataset_id=dataset_id, resource_id=resource_id, event_key=key,
                         actor_type='SYSTEM', action='DEMO_CAMPAIGNS_SEEDED', details=details or {}))


def prepare_population(database, dataset_id, seed, reference):
    """Add missing historical scenarios; never change existing customers or consent."""
    key=f'{VERSION}:population:{seed}'
    with database.sessions.begin() as session:
        require_dataset(session,dataset_id,lock=True)
        if marker(session, dataset_id, key):
            return
        # Original customers all joined 365 days ago, and original non-consent customers
        # also opted out of PUSH. Original VIP orders are only 75 days old: they are not
        # dormant yet at reference-30d. Dedicated synthetic cohorts fill these gaps.
        for group, count, age in (('new', 300, 10), ('push_only', 150, 180), ('historical_vip', 300, 365)):
            for number in range(count):
                external=f'{VERSION}:{seed}:{group}:{number}'
                customer_id=uuid5(NAMESPACE_URL, f'{dataset_id}:{external}')
                session.add(Customer(id=customer_id, dataset_id=dataset_id, external_id=external,
                    name=synthetic_name(external, seed), signup_at=reference-timedelta(days=age), status='ACTIVE'))
                session.flush()
                for channel in ('EMAIL', 'PUSH', 'SMS'):
                    contact={'EMAIL':f'portfolio-{group}-{seed}-{number}@example.invalid',
                             'PUSH':f'synthetic:{external}', 'SMS':f'0100000{number:04d}'}[channel]
                    session.add(CustomerChannel(dataset_id=dataset_id, customer_id=customer_id, channel=channel,
                        consent=group!='push_only' or channel=='PUSH', contact=contact, is_valid=True,
                        hard_bounce=False, consent_changed_at=reference-timedelta(days=age)))
                if group=='historical_vip':
                    for order_index in range(3):
                        session.add(Order(id=uuid5(customer_id, f'order:{order_index}'), dataset_id=dataset_id,
                            customer_id=customer_id, external_id=f'{external}:order:{order_index}',
                            purchased_at=reference-timedelta(days=120+order_index), status='COMPLETED',
                            amount=150000, source='UPLOADED'))
        version=(session.scalar(select(func.max(DatasetVersion.version)).where(DatasetVersion.dataset_id==dataset_id)) or 0)+1
        session.add(DatasetVersion(dataset_id=dataset_id, version=version, reason=key))
        mark(session, dataset_id, key, dataset_id, {'synthetic_customers_added':750})


def campaign_payload(dataset_id, revision_id, item, at):
    name, channel, objective, _ = item
    benefit={'EMAIL':'15% 할인 쿠폰', 'PUSH':'3000원 적립금', 'SMS':'무료배송'}[channel]
    return CampaignWrite(dataset_id=dataset_id, segment_revision_id=revision_id,
        name=f'{name} · {objective}', objective=objective, channel=channel, benefit=benefit,
        brand_tone='다정하고 간결하게', primary_kpi='conversion_rate', target_value='5.00', planned_at=at,
        variants=[dict(variant_name=variant, subject='' if channel=='SMS' else
                       (f'{benefit}으로 다시 만나요' if variant=='A' else '다시 만나서 반가워요'),
                       body=f'{benefit}으로 편하게 둘러보세요.' if variant=='A' else f'오랜만이에요. {benefit}과 함께 다시 만나요.',
                       hypothesis='혜택 우선 접근의 반응을 확인한다.' if variant=='A' else '관계 우선 접근의 반응을 확인한다.',
                       allocation_bp=5000) for variant in ('A','B')])


def ensure_campaign(database, dataset_id, seed, index, reference):
    item=ALL_COMBINATIONS[index]; name=item[0]; at=sent_at(reference,index)
    key=f'{VERSION}:{seed}:campaign:{index}'
    with database.sessions.begin() as session:
        require_dataset(session,dataset_id,lock=True)
        existing=marker(session,dataset_id,key)
        if existing:
            row=session.get(Campaign,existing.resource_id)
            if row is None or row.archived_at:
                raise ValueError(f'Seed campaign {index} was removed/archived; refusing to recreate it')
            return row.id
        segment_key=f'{VERSION}:{seed}:segment:{name}'
        saved=marker(session,dataset_id,segment_key)
        if saved:
            segment=segments.detail(session,dataset_id,saved.resource_id)
        else:
            request=SegmentWrite(dataset_id=dataset_id,name=name,condition=SEGMENTS[name],reference_at=at)
            preview=segments.preview(session,request)
            if not preview['count']:
                raise ValueError(f'{name}: no customers at {at.isoformat()}; use a medium demo dataset')
            segment=segments.save(session,request,None,managed_transaction=True)
            mark(session,dataset_id,segment_key,segment['id'])
        payload=campaign_payload(dataset_id,segment['revision_id'],item,at)
        if index>=len(COMBINATIONS):
            payload.name+=f' · {at.astimezone(timezone(timedelta(hours=9))):%m/%d} 재실험'
        campaign=campaigns.save(session,payload,None,managed_transaction=True)
        mark(session,dataset_id,key,campaign['id'],{'seed':seed,'sent_at':at.isoformat(),'combination':index})
        return campaign['id']


def complete_campaign(database,settings,dataset_id,campaign_id,seed,index,reference,timeout,external_worker):
    """Resume committed stages after interruption; never manufacture COMPLETED status."""
    with database.sessions() as session:
        current=policies.review(session,dataset_id,campaign_id)
    campaign=current['campaign']; at=sent_at(reference,index)
    if campaign['status']=='COMPLETED':
        with database.sessions() as session:
            run=simulations.latest_run(session,dataset_id,campaign_id)
        if not run or run['status']!='COMPLETED' or run['sent_count']==0:
            raise ValueError('Existing completed seed campaign has no successful simulation')
        return 'skipped'
    if campaign['status']=='REVIEW' and current['validation']['expires_at']<=datetime.now(timezone.utc):
        from app.schemas.policies import ResumeEditing
        with database.sessions() as session:
            campaign=policies.resume(session,campaign_id,ResumeEditing(dataset_id=dataset_id,
                campaign_version=campaign['version']),None)
    if campaign['status']=='DRAFT':
        with database.sessions() as session:
            validation=policies.validate(session,campaign_id,ValidationRequest(dataset_id=dataset_id,
                campaign_version=campaign['version'],reference_at=at),None,actor_type='SYSTEM')
        if not validation['passed']:
            raise ValueError(f"{campaign['name']}: validation blocked: {validation['blockers']}")
        with database.sessions() as session:
            current=policies.request_approval(session,campaign_id,ApprovalRequest(dataset_id=dataset_id,
                campaign_version=campaign['version'],validation_run_id=validation['id']),None)
        campaign=current['campaign']
    if campaign['status']=='REVIEW':
        with database.sessions() as session:
            current=policies.decide(session,campaign_id,ApprovalDecision(dataset_id=dataset_id,
                campaign_version=campaign['version'],approval_id=current['approval']['id'],
                comment='합성 데이터 포트폴리오 시드 승인'),None,True)
        campaign=current['campaign']
    if campaign['status']=='APPROVED':
        with database.sessions() as session:
            simulations.simulate(session,campaign_id,SimulateSendRequest(dataset_id=dataset_id,
                campaign_version=campaign['version']),f'{VERSION}:{seed}:{index}',None,
                seed_at=at,seed_value=f'{VERSION}:{seed}:{index}')
    deadline=time.monotonic()+timeout
    while time.monotonic()<deadline:
        with database.sessions() as session:
            run=simulations.latest_run(session,dataset_id,campaign_id)
        if run and run['status']=='COMPLETED':
            if run['sent_count']==0:
                raise ValueError('Completed with no deliveries; inspect eligibility before demonstrating')
            return 'created'
        if run and run['status']=='FAILED':
            raise ValueError(f'Worker failed for campaign {campaign_id}; inspect the job before retrying')
        if not external_worker and run:
            run_once(database,settings,job_id=run['job_id'])
        time.sleep(.1 if not external_worker else 1)
    raise TimeoutError(f'Worker timeout for {campaign_id}; rerun with the same seed to resume')


def seed_campaigns(database,settings,dataset_id,seed=42,timeout=120,external_worker=False,expanded=False):
    lock_key=int.from_bytes(hashlib.sha256(f'{VERSION}:{dataset_id}'.encode()).digest()[:8],'big',signed=True)
    # Session-level lock spans service commits and polling; a second seeder fails fast.
    with database.engine.connect() as lock:
        acquired=lock.scalar(text('SELECT pg_try_advisory_lock(:key)'),{'key':lock_key})
        lock.commit()
        if not acquired:
            raise ValueError('Another campaign seeder is already running for this dataset')
        try:
            with database.sessions() as session:
                dataset=session.get(Dataset,dataset_id)
                if dataset is None or dataset.source!='DEMO' or dataset.purpose!='ANALYSIS' or dataset.reference_at is None:
                    raise ValueError('A DEMO/ANALYSIS dataset with reference_at is required')
                reference=dataset.reference_at
                if reference>datetime.now(timezone.utc):
                    raise ValueError('Dataset reference_at must not be in the future')
            prepare_population(database,dataset_id,seed,reference)
            result=[]
            combinations=ALL_COMBINATIONS if expanded else COMBINATIONS
            for index,item in enumerate(combinations):
                campaign_id=ensure_campaign(database,dataset_id,seed,index,reference)
                outcome=complete_campaign(database,settings,dataset_id,campaign_id,seed,index,reference,timeout,external_worker)
                result.append(campaign_id)
                print(f'{index+1}/{len(combinations)} {outcome}: {item[0]} / {item[1]} / {sent_at(reference,index).isoformat()} / {campaign_id}',flush=True)
            print(f'Completed {len(combinations)} campaigns. Reports period: {(reference-timedelta(days=32)).date()} through {reference.date()}',flush=True)
            return result
        finally:
            lock.execute(text('SELECT pg_advisory_unlock(:key)'),{'key':lock_key})
            lock.commit()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset-id',type=UUID,required=True)
    parser.add_argument('--seed',type=int,default=42)
    parser.add_argument('--expanded',action='store_true',help='Add 12 repeated scenarios at 10, 7 and 4 days before reference (24 total)')
    parser.add_argument('--timeout',type=int,default=120,help='Worker timeout per campaign in seconds')
    parser.add_argument('--external-worker',action='store_true',help='Poll an already running worker instead of processing the queue locally')
    args=parser.parse_args()
    if args.timeout<=0:
        parser.error('--timeout must be positive')
    settings=Settings()
    if not settings.database_url:
        parser.error('DATABASE_URL required')
    database=Database(settings.database_url.get_secret_value())
    try:
        seed_campaigns(database,settings,args.dataset_id,args.seed,args.timeout,args.external_worker,args.expanded)
    finally:
        database.dispose()


if __name__=='__main__':
    main()
