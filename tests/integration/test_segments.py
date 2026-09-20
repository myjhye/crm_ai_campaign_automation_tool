from datetime import datetime, timezone, timedelta
from uuid import uuid4
from concurrent.futures import ThreadPoolExecutor
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, func
from app.main import create_app
from app.core.config import Settings
from app.models.datasets import Dataset
from app.models.segments import SegmentRevision, Segment
from app.models.customers import CustomerEvent
from scripts.seed_demo import seed_demo

pytestmark = pytest.mark.postgres
REFERENCE = datetime(2026,9,19,tzinfo=timezone.utc)

@pytest.fixture
def context(database):
    with database.sessions.begin() as session:
        dataset, _ = seed_demo(session, seed=42, reference_at=REFERENCE)
        session.add(Dataset(name='Other'))
        dataset_id = dataset.id
    app = create_app(Settings(_env_file=None, database_url=None)); app.state.database = database
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client, {'dataset_id':str(dataset_id), 'reference_at':REFERENCE.isoformat()}


def condition(field='order_count', comparison='GTE', value=1):
    return {'field':field,'comparison':comparison,'value':value}


def test_preview_nulls_groups_and_profile(context):
    client, base = context
    missing = {'field':'days_since_last_purchase','comparison':'IS_NULL'}
    def preview(node):
        response = client.post('/api/v1/segments/preview', json={**base,'condition':node})
        assert response.status_code == 200, response.text
        return response.json()
    all_rows = preview(condition(value=0))
    assert all_rows['count'] == 300 and all_rows['warnings'] == ['BROAD_SEGMENT']
    assert all_rows['profile']['average_purchase_amount'] is not None
    no_purchase = preview(missing)
    purchased = preview({'field':'days_since_last_purchase','comparison':'IS_NOT_NULL'})
    assert no_purchase['count'] + purchased['count'] == 300
    both = preview({'operator':'OR','conditions':[condition(),condition()]})
    assert both['count'] == purchased['count']
    empty = preview(condition('total_purchase_amount','GTE','999999999.00'))
    assert empty['count'] == 0 and empty['warnings'] == ['EMPTY_SEGMENT']
    assert empty['profile']['average_purchase_amount'] is None
    vip = preview({'operator':'AND','conditions':[condition('days_since_last_purchase','GTE',60), condition('total_purchase_amount','GTE','300000'),condition('email_consent','EQ',True)]})
    assert vip['count'] > 0 and vip['count'] < 300
    assert preview(condition('preferred_category','EQ','no-such-category'))['count'] == 0
    assert client.post('/api/v1/segments/preview',json={**base,'condition':condition(), 'data_version':999}).status_code == 409


def test_revision_conflict_archive_and_scope(context, database):
    client, base = context
    payload = {**base,'condition':condition(),'name':'VIP'}
    created = client.post('/api/v1/segments',json=payload)
    assert created.status_code == 201, created.text
    row = created.json(); path = '/api/v1/segments/' + row['id']
    changed = client.put(path,json={**payload,'name':'Updated','version':1})
    assert changed.status_code == 200, changed.text
    assert changed.json()['revision_id'] != row['revision_id']
    assert client.put(path,json={**payload,'version':1}).status_code == 409
    assert client.get(path,params={'dataset_id':str(uuid4())}).status_code == 404
    archived = client.request('DELETE',path,json={'dataset_id':base['dataset_id'],'version':2})
    assert archived.status_code == 200, archived.text
    assert client.get('/api/v1/segments',params={'dataset_id':base['dataset_id']}).json()['total'] == 0
    assert client.get(path,params={'dataset_id':base['dataset_id']}).json()['archived_at']
    with database.sessions() as session:
        assert session.scalar(select(func.count()).select_from(SegmentRevision)) == 2
        assert session.scalar(select(SegmentRevision).where(SegmentRevision.version==1)).name == 'VIP'


def test_event_subquery_does_not_duplicate_customers(context, database):
    client, base = context
    with database.sessions.begin() as session:
        from app.models.customers import Customer
        customer = session.scalar(select(Customer).where(Customer.dataset_id == base['dataset_id']))
        for i in range(3):
            session.add(CustomerEvent(dataset_id=customer.dataset_id,customer_id=customer.id,external_id=f'extra-open-{i}',event_type='EMAIL_OPEN',event_at=REFERENCE-timedelta(days=1)))
        session.add(CustomerEvent(dataset_id=customer.dataset_id,customer_id=customer.id,external_id='future-open',event_type='EMAIL_OPEN',event_at=REFERENCE+timedelta(days=1)))
    result = client.post('/api/v1/segments/preview',json={**base,'condition':condition('email_opens_30d','EQ',3)})
    assert result.status_code == 200, result.text
    assert result.json()['count'] == 1


def test_save_audit_failure_rolls_back(context, database, monkeypatch):
    from app.services import segments
    client, base = context
    def fail(*args, **kwargs): raise RuntimeError('audit failure')
    monkeypatch.setattr(segments,'record_change',fail)
    assert client.post('/api/v1/segments',json={**base,'condition':condition(),'name':'Rollback'}).status_code == 500
    with database.sessions() as session:
        assert session.scalar(select(func.count()).select_from(Segment)) == 0


def test_exact_money_and_elapsed_day_boundaries(context, database):
    from app.models.customers import Customer, Order
    client, base = context
    with database.sessions.begin() as session:
        customer = Customer(dataset_id=base['dataset_id'],external_id='boundary',name='Boundary',signup_at=REFERENCE-timedelta(days=100))
        session.add(customer); session.flush()
        session.add(Order(dataset_id=customer.dataset_id,customer_id=customer.id,external_id='boundary-order',purchased_at=REFERENCE-timedelta(days=60),status='COMPLETED',amount='12345.67'))
    for operator, days, expected in [('GTE',60,1),('GT',60,0),('LTE',59,0),('EQ',60,1)]:
        node = {'operator':'AND','conditions':[condition('total_purchase_amount','EQ','12345.67'),condition('days_since_last_purchase',operator,days)]}
        response = client.post('/api/v1/segments/preview',json={**base,'condition':node})
        assert response.status_code == 200, response.text
        assert response.json()['count'] == expected


def test_concurrent_segment_edits_only_one_revision_wins(context, database):
    from app.services.segments import save
    from app.schemas.segments import SegmentUpdate
    from app.core.errors import AppError
    client, base = context
    created = client.post('/api/v1/segments',json={**base,'condition':condition(),'name':'Concurrent'}).json()
    def update(name):
        with database.sessions() as session:
            try:
                save(session, SegmentUpdate(**base,condition=condition(),name=name,version=1),uuid4(),created['id'])
                return 200
            except AppError as error: return error.status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(update,['First','Second'])) == [200,409]
    with database.sessions() as session:
        assert session.scalar(select(func.count()).select_from(SegmentRevision)) == 2
