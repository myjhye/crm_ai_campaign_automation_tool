from sqlalchemy import select, func
from app.models.campaigns import (PolicySetting, ValidationRun, ValidationRecipient, Approval,
    CampaignDelivery, CampaignExclusion)
from app.models.customers import CustomerChannel
from app.models.segments import SegmentRevision

def setting(session,dataset_id,lock=False):
    query=select(PolicySetting).where(PolicySetting.dataset_id==dataset_id)
    return session.scalar(query.with_for_update() if lock else query)

def revision(session,dataset_id,revision_id):
    return session.scalar(select(SegmentRevision).where(SegmentRevision.dataset_id==dataset_id,SegmentRevision.id==revision_id))

def exclusion_revisions(session,campaign_id):
    return session.scalars(select(SegmentRevision).join(CampaignExclusion,CampaignExclusion.segment_revision_id==SegmentRevision.id).where(CampaignExclusion.campaign_id==campaign_id)).all()

def channels(session,dataset_id,customer_ids,channel):
    rows=session.scalars(select(CustomerChannel).where(CustomerChannel.dataset_id==dataset_id,CustomerChannel.customer_id.in_(customer_ids),CustomerChannel.channel==channel)).all()
    return {row.customer_id:row for row in rows}

def delivery_counts(session,dataset_id,customer_ids,channel,campaign_id,day_start,week_start,reference):
    rows=session.execute(select(CampaignDelivery.customer_id,
        func.count().filter(CampaignDelivery.campaign_id==campaign_id).label('duplicate'),
        func.count().filter(CampaignDelivery.sent_at>=day_start).label('daily'),
        func.count().filter(CampaignDelivery.sent_at>=week_start).label('weekly')).where(
        CampaignDelivery.dataset_id==dataset_id,CampaignDelivery.customer_id.in_(customer_ids),CampaignDelivery.channel==channel,
        CampaignDelivery.status=='SENT',CampaignDelivery.sent_at<reference).group_by(CampaignDelivery.customer_id)).all()
    return {row.customer_id:(row.duplicate,row.daily,row.weekly) for row in rows}

def latest_validation(session,dataset_id,campaign_id):
    return session.scalar(select(ValidationRun).where(ValidationRun.dataset_id==dataset_id,ValidationRun.campaign_id==campaign_id).order_by(ValidationRun.created_at.desc(),ValidationRun.id.desc()).limit(1))

def get_validation(session,dataset_id,run_id,lock=False):
    query=select(ValidationRun).where(ValidationRun.dataset_id==dataset_id,ValidationRun.id==run_id)
    return session.scalar(query.with_for_update() if lock else query)

def latest_approval(session,dataset_id,campaign_id):
    return session.scalar(select(Approval).where(Approval.dataset_id==dataset_id,Approval.campaign_id==campaign_id).order_by(Approval.created_at.desc(),Approval.id.desc()).limit(1))

def get_approval(session,dataset_id,approval_id,lock=False):
    query=select(Approval).where(Approval.dataset_id==dataset_id,Approval.id==approval_id)
    return session.scalar(query.with_for_update() if lock else query)
