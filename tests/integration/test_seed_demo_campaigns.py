from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select, func

from app.core.config import Settings
from app.models.campaigns import Campaign, CampaignRun, CampaignDelivery, CampaignEvent, Approval
from app.models.customers import Customer, Order
from app.services.performance import campaign_rows, compare_campaigns
from app.services.simulations import latest_run
from scripts.seed_demo import seed_demo
from scripts.seed_demo_campaigns import seed_campaigns, sent_at, COMBINATIONS

pytestmark = pytest.mark.postgres


def test_seed_campaigns_pipeline_idempotence_and_periods(database):
    reference=datetime(2026,9,20,tzinfo=timezone.utc)
    settings=Settings(_env_file=None)
    with database.sessions.begin() as session:
        dataset,_=seed_demo(session,seed=42,reference_at=reference)
        dataset_id=dataset.id
        from app.services.jobs import enqueue
        unrelated=enqueue(session,dataset_id=dataset_id,kind='not-a-seed-job',key='leave-alone',payload={})
        unrelated_id=unrelated.id
    ids=seed_campaigns(database,settings,dataset_id)
    assert len(set(ids))==12
    with database.sessions() as session:
        from app.models.jobs import Job
        assert session.get(Job,unrelated_id).status=='PENDING'
        assert session.scalar(select(func.count()).select_from(Customer).where(Customer.dataset_id==dataset_id))==1050
        rows=session.scalars(select(Campaign).where(Campaign.id.in_(ids))).all()
        assert {row.status for row in rows}=={'COMPLETED'}
        assert {row.channel for row in rows}=={'EMAIL','PUSH','SMS'}
        assert session.scalar(select(func.count()).select_from(Approval).where(Approval.dataset_id==dataset_id,Approval.status=='APPROVED'))==12
        runs=session.scalars(select(CampaignRun).where(CampaignRun.campaign_id.in_(ids))).all()
        assert len(runs)==12 and all(row.sent_count>0 for row in runs)
        for index,campaign_id in enumerate(ids):
            run=next(row for row in runs if row.campaign_id==campaign_id)
            at=sent_at(reference,index)
            assert run.started_at==at and run.finished_at==at+timedelta(seconds=4)
            deliveries=session.scalars(select(CampaignDelivery).where(CampaignDelivery.run_id==run.id,CampaignDelivery.status=='SENT')).all()
            assert all(row.sent_at==at for row in deliveries)
            events=session.scalars(select(CampaignEvent).where(CampaignEvent.run_id==run.id)).all()
            assert events and all(at<=row.event_at<=run.finished_at for row in events)
            orders=session.scalars(select(Order).where(Order.id.in_([row.order_id for row in events if row.order_id]))).all()
            assert orders and all(row.purchased_at==at+timedelta(seconds=3) for row in orders)
        counts=[len(campaign_rows(session,dataset_id,reference-timedelta(days=hi),reference-timedelta(days=lo)))
                for hi,lo in ((32,29),(16,13),(3,0))]
        assert counts==[4,4,4]
        reports=campaign_rows(session,dataset_id,reference-timedelta(days=32),reference)
        assert len(reports)==12
        args={'sort':'conversion_rate','order':'desc','limit':3,
              'filter':{'status':'COMPLETED','channel':'ANY','segment_revision_id':'','from':'','to':''}}
        comparison=compare_campaigns(session,dataset_id,args,reference-timedelta(days=20),reference)
        assert len(comparison['campaigns'])==3
        before={row.id:(row.sent_count,row.failed_count,row.finished_at) for row in runs}
        order_count=session.scalar(select(func.count()).select_from(Order).where(Order.dataset_id==dataset_id))
    assert seed_campaigns(database,settings,dataset_id)==ids
    with database.sessions() as session:
        after={row.id:(row.sent_count,row.failed_count,row.finished_at) for row in session.scalars(select(CampaignRun).where(CampaignRun.campaign_id.in_(ids)))}
        assert after==before
        assert session.scalar(select(func.count()).select_from(Order).where(Order.dataset_id==dataset_id))==order_count


def test_seed_outcomes_are_stable_across_fresh_copies(database):
    reference=datetime(2026,9,20,tzinfo=timezone.utc)
    outcomes=[]
    for key in ('first-copy','second-copy'):
        with database.sessions.begin() as session:
            dataset,_=seed_demo(session,seed=42,reference_at=reference,dataset_key=key)
            dataset_id=dataset.id
        ids=seed_campaigns(database,Settings(_env_file=None),dataset_id)
        with database.sessions() as session:
            # Customer UUIDs differ between copies; seeding scores must use external IDs.
            runs=[latest_run(session,dataset_id,campaign_id) for campaign_id in ids]
            outcomes.append([(run['sent_count'],run['failed_count'],run['variant_summary'],run['event_summary']) for run in runs])
    assert outcomes[0]==outcomes[1]


def test_campaign_seed_refuses_non_demo(database):
    from app.models.datasets import Dataset
    with database.sessions.begin() as session:
        row=Dataset(name='User upload',source='UPLOADED',reference_at=datetime(2026,9,20,tzinfo=timezone.utc))
        session.add(row); session.flush(); dataset_id=row.id
    with pytest.raises(ValueError,match='DEMO/ANALYSIS'):
        seed_campaigns(database,Settings(_env_file=None),dataset_id)
