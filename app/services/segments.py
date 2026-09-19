import hashlib
import json
from decimal import Decimal
from datetime import datetime, timezone
from app.core.errors import AppError
from app.models.segments import Segment, SegmentRevision
from app.repositories import segments as repository
from app.repositories.imports import data_version
from app.services.datasets import require_dataset
from app.services.audit import record_change
from app.domain.segments.human_readable import describe
from app.domain.segments.dsl import Condition


def digest(condition):
    return hashlib.sha256(json.dumps(condition.canonical(), sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()


def preview(session, request):
    # Dataset lock synchronizes data-version reads with import/seed mutations.
    require_dataset(session, request.dataset_id, lock=True)
    version = data_version(session, request.dataset_id)
    if request.data_version is not None and request.data_version != version:
        raise AppError('DATA_VERSION_CONFLICT', '데이터가 변경되었습니다. 다시 미리보기 해주세요.')
    count, total, average, opened, categories = repository.preview(session, request)
    return {'dataset_id': request.dataset_id, 'count': count, 'total': total, 'percentage': round(count / total * 100, 2) if total else None,
        'condition': request.condition.canonical(), 'description': describe(request.condition), 'condition_hash': digest(request.condition),
        'reference_at': request.reference_at, 'data_version': version,
        'warnings': (['EMPTY_SEGMENT'] if count == 0 else []) + (['BROAD_SEGMENT'] if total and count / total > .8 else []),
        'profile': {'average_purchase_amount': format(average.quantize(Decimal('0.01')), 'f') if average is not None else None,
            'categories': [{'category': category, 'count': number} for category, number in categories],
            'email_open_customers_30d': opened, 'email_open_customer_rate_30d': round(opened / count * 100, 2) if count else None,
            'campaign_response_rate': {'status': 'not_ready', 'value': None}, 'age_distribution': {'status': 'not_available', 'value': None}},
        'channel_state': 'current', 'eligibility_checked': False}


def ai_profile(result, minimum=5):
    if result['count'] < minimum: return {'status': 'insufficient_population'}
    profile = dict(result['profile'])
    profile['categories'] = [row for row in profile['categories'] if row['count'] >= minimum]
    return profile


def representation(segment, revision):
    return {'id': segment.id, 'dataset_id': segment.dataset_id, 'name': segment.name, 'version': segment.version,
        'archived_at': segment.archived_at, 'revision_id': revision.id, 'condition': revision.condition_json,
        'description': describe(Condition.model_validate(revision.condition_json)), 'reference_at': revision.reference_at,
        'data_version': revision.data_version, 'condition_hash': revision.condition_hash, 'created_source': revision.created_source}


def require_segment(session, dataset_id, segment_id, lock=False):
    row = repository.get(session, dataset_id, segment_id, lock)
    if row is None: raise AppError('NOT_FOUND', '세그먼트를 찾을 수 없습니다.', 404)
    return row


def detail(session, dataset_id, segment_id):
    require_dataset(session, dataset_id)
    segment = require_segment(session, dataset_id, segment_id)
    return representation(segment, repository.revision(session, segment))


def list_segments(session, query):
    require_dataset(session, query.dataset_id)
    rows, total = repository.list_page(session, query)
    return {'items': [representation(segment, revision) for segment, revision in rows], 'total': total, 'page': query.page, 'page_size': query.page_size}


def save(session, request, request_id, segment_id=None):
    with session.begin():
        result = preview(session, request)
        if segment_id is None:
            segment = Segment(dataset_id=request.dataset_id, name=request.name)
            session.add(segment); session.flush()
            previous = None
        else:
            segment = require_segment(session, request.dataset_id, segment_id, True)
            if segment.archived_at or segment.version != request.version:
                raise AppError('VERSION_CONFLICT', '세그먼트가 변경되거나 보관되었습니다. 최신 내용을 불러오세요.')
            previous = segment.version
            segment.version += 1
            segment.name = request.name
        revision = SegmentRevision(dataset_id=request.dataset_id, segment_id=segment.id, version=segment.version, name=segment.name,
            condition_json=request.condition.canonical(), reference_at=request.reference_at, data_version=result['data_version'], condition_hash=result['condition_hash'], created_source='VISITOR')
        session.add(revision); session.flush()
        record_change(session, dataset_id=request.dataset_id, resource_id=segment.id, actor_type='VISITOR', action='SEGMENT_CREATED' if previous is None else 'SEGMENT_UPDATED', request_id=request_id, previous_version=previous, new_version=segment.version)
        return representation(segment, revision)


def archive(session, request, segment_id, request_id):
    with session.begin():
        require_dataset(session, request.dataset_id, lock=True)
        segment = require_segment(session, request.dataset_id, segment_id, True)
        if segment.version != request.version or segment.archived_at:
            raise AppError('VERSION_CONFLICT', '세그먼트가 변경되거나 이미 보관되었습니다.')
        previous = segment.version
        segment.version += 1
        segment.archived_at = datetime.now(timezone.utc)
        record_change(session, dataset_id=request.dataset_id, resource_id=segment.id, actor_type='VISITOR', action='SEGMENT_ARCHIVED', request_id=request_id, previous_version=previous, new_version=segment.version)
        return representation(segment, repository.revision(session, segment))
