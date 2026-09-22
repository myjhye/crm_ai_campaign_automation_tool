"""Rebuild resource context from scoped database records on every request."""
from sqlalchemy import select
from app.models.segments import Segment, SegmentRevision
from app.models.campaigns import Campaign


def segment_hint(result):
    return {'kind': 'segment', 'id': str(result['id']), 'revision_id': str(result['revision_id']),
            'name': result['name'], 'label': f"{result['name']} 세그먼트 기준으로"}


def resolve_hint(session, dataset_id, hint):
    if hint is None:
        return None
    if hint.kind == 'segment':
        row = session.execute(select(Segment, SegmentRevision).join(SegmentRevision,
            (SegmentRevision.segment_id == Segment.id) & (SegmentRevision.dataset_id == Segment.dataset_id)).where(
            Segment.dataset_id == dataset_id, Segment.id == hint.id, Segment.archived_at.is_(None),
            SegmentRevision.id == hint.revision_id, SegmentRevision.version == Segment.version)).first()
        if row is None:
            return None
        segment, revision = row
        return {'kind': 'segment', 'id': str(segment.id), 'revision_id': str(revision.id),
                'name': revision.name, 'label': f'{revision.name} 세그먼트 기준으로'}
    ids = hint.campaign_ids
    if len(set(ids)) != len(ids):
        return None
    rows = session.scalars(select(Campaign).where(Campaign.dataset_id == dataset_id,
        Campaign.id.in_(ids), Campaign.archived_at.is_(None), Campaign.status == 'COMPLETED')).all()
    if len(rows) != len(ids):
        return None
    return {'kind': 'campaign_list', 'campaign_ids': [str(i) for i in ids],
            'label': f'위 {len(ids)}개 캠페인 기준으로'}


def segment_options(session, dataset_id):
    rows = session.execute(select(SegmentRevision.id, SegmentRevision.name).join(Segment,
        (SegmentRevision.segment_id == Segment.id) & (SegmentRevision.dataset_id == Segment.dataset_id)).where(
        Segment.dataset_id == dataset_id, Segment.archived_at.is_(None),
        SegmentRevision.version == Segment.version).order_by(Segment.id).limit(100)).all()
    return [{'revision_id': str(row.id), 'name': row.name} for row in rows]
