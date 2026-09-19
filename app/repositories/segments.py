from sqlalchemy import select, func
from app.models.segments import Segment, SegmentRevision
from app.repositories.analytics import customer_snapshot
from app.domain.segments.compiler import expressions, compile_condition


def preview(session, request):
    snapshot = customer_snapshot(request.dataset_id, request.reference_at)
    fields = expressions(snapshot, request.dataset_id, request.reference_at)
    selected = select(snapshot.c.id, snapshot.c.total_purchase_amount, fields['preferred_category'].label('category'), fields['email_opens_30d'].label('opens')).where(compile_condition(request.condition, fields)).cte('selected_customers')
    total = session.scalar(select(func.count()).select_from(snapshot))
    count, average, opened = session.execute(select(func.count(), func.avg(selected.c.total_purchase_amount), func.count().filter(selected.c.opens > 0)).select_from(selected)).one()
    categories = session.execute(select(selected.c.category, func.count()).where(selected.c.category.is_not(None)).group_by(selected.c.category).order_by(func.count().desc(), selected.c.category).limit(5)).all()
    return count, total, average, opened, categories


def get(session, dataset_id, segment_id, lock=False):
    query = select(Segment).where(Segment.dataset_id == dataset_id, Segment.id == segment_id)
    return session.scalar(query.with_for_update() if lock else query)


def revision(session, segment):
    return session.scalar(select(SegmentRevision).where(SegmentRevision.segment_id == segment.id, SegmentRevision.version <= segment.version).order_by(SegmentRevision.version.desc()).limit(1))


def list_page(session, query):
    where = (Segment.dataset_id == query.dataset_id, Segment.archived_at.is_(None))
    total = session.scalar(select(func.count()).select_from(Segment).where(*where))
    rows = session.execute(select(Segment, SegmentRevision).join(SegmentRevision, (SegmentRevision.segment_id == Segment.id) & (SegmentRevision.version == Segment.version)).where(*where).order_by(Segment.created_at.desc(), Segment.id).offset(query.offset).limit(query.page_size)).all()
    return rows, total
