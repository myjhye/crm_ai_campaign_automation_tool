"""Rebuild resource context from scoped database records on every request."""
import re
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
def comparison_scope(prompt, suggested='dataset'):
    """Keep explicit scope words authoritative over a mistaken model scope choice."""
    if re.search(r'(전체|모든)\s*(캠페인|데이터셋)|\ball campaigns\b', prompt, re.I):
        return 'dataset'
    if re.search(r'(위|그|이|방금|이전)\s*캠페인|그\s*중|이\s*세그먼트|방금\s*(나온|본|조회한|비교한)\s*(결과|캠페인)|\b(these|those|above|previous) campaigns\b|\bamong them\b', prompt, re.I):
        return 'context'
    if re.search(r'이메일|푸시|문자|\b(EMAIL|PUSH|SMS)\b', prompt, re.I):
        return 'dataset'
    return suggested
