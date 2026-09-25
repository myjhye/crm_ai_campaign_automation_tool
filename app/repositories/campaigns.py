from sqlalchemy import select, func, delete
from app.models.campaigns import Campaign, CampaignVariant, CampaignExclusion
from app.models.segments import SegmentRevision


def get(session, dataset_id, campaign_id, lock=False, include_archived=False):
    query = select(Campaign).where(Campaign.dataset_id == dataset_id, Campaign.id == campaign_id)
    if not include_archived: query = query.where(Campaign.archived_at.is_(None))
    return session.scalar(query.with_for_update() if lock else query)


def revisions(session, dataset_id, ids):
    return session.scalars(select(SegmentRevision).where(SegmentRevision.dataset_id == dataset_id, SegmentRevision.id.in_(ids))).all()


def page(session, query):
    where = [Campaign.dataset_id == query.dataset_id, Campaign.archived_at.is_(None)]
    if query.q.strip():
        where.append(Campaign.name.icontains(query.q.strip(), autoescape=True))
    if query.status:
        where.append(Campaign.status == query.status)
    total = session.scalar(select(func.count()).select_from(Campaign).where(*where))
    rows = session.scalars(select(Campaign).where(*where).order_by(Campaign.created_at.desc(), Campaign.id).offset(query.offset).limit(query.page_size)).all()
    return rows, total


def children(session, campaign):
    variants = session.scalars(select(CampaignVariant).where(CampaignVariant.campaign_id == campaign.id).order_by(CampaignVariant.variant_name)).all()
    exclusions = session.scalars(select(CampaignExclusion.segment_revision_id).where(CampaignExclusion.campaign_id == campaign.id)).all()
    return variants, exclusions


def replace_children(session, campaign, request):
    # Keep variant IDs stable while editing; later deliveries will reference them.
    existing = {v.variant_name:v for v in session.scalars(select(CampaignVariant).where(CampaignVariant.campaign_id == campaign.id))}
    for item in request.variants:
        variant = existing.get(item.variant_name)
        if variant is None:
            variant = CampaignVariant(dataset_id=campaign.dataset_id, campaign_id=campaign.id)
            session.add(variant)
        for key, value in item.model_dump().items(): setattr(variant, key, value)
    session.execute(delete(CampaignExclusion).where(CampaignExclusion.campaign_id == campaign.id))
    session.add_all([CampaignExclusion(dataset_id=campaign.dataset_id, campaign_id=campaign.id, segment_revision_id=id) for id in request.exclusion_revision_ids])
