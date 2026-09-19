from datetime import datetime, timezone, timedelta
from uuid import UUID
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, func
from app.main import create_app
from app.core.config import Settings
from app.models.ai import AIActionProposal, AIExecutionLog
from app.models.segments import Segment
from scripts.seed_demo import seed_demo

pytestmark = pytest.mark.postgres
PROMPT = '60일 미구매, 누적 30만원 이상, 이메일 동의 고객을 저장할 초안으로 만들어줘'


@pytest.fixture
def ai_context(database):
    reference = datetime(2026, 9, 19, tzinfo=timezone.utc)
    with database.sessions.begin() as session:
        dataset, _ = seed_demo(session, seed=42, reference_at=reference)
        dataset_id = str(dataset.id)
    app = create_app(Settings(_env_file=None, database_url=None, ai_mode='mock'))
    app.state.database = database
    with TestClient(app) as client:
        yield client, app, {'dataset_id':dataset_id, 'from':'2026-08-19T00:00:00Z', 'to':reference.isoformat(), 'reference_at':reference.isoformat()}


def test_ai_metric_and_confirm_idempotency(ai_context, database):
    client, app, base = ai_context
    metric = client.post('/api/v1/ai/chat', json={**base, 'prompt':'활성 고객 수를 알려줘'})
    assert metric.status_code == 200, metric.text
    expected = client.get('/api/v1/dashboard/overview', params={k:v for k,v in base.items() if k != 'reference_at'}).json()
    assert metric.json()['data']['metrics']['active_customers'] == expected['metrics']['active_customers']
    response = client.post('/api/v1/ai/chat', json={**base,'prompt':PROMPT})
    assert response.status_code == 200, response.text
    data = response.json()['data']
    assert data['count'] == 10
    with database.sessions() as session: assert session.scalar(select(func.count()).select_from(Segment)) == 0
    path = f"/api/v1/ai/actions/{data['proposal_id']}/confirm"
    first = client.post(path, json={'dataset_id':base['dataset_id']})
    assert first.status_code == 200, first.text
    assert first.json()['created_source'] == 'AI'
    assert client.post(path,json={'dataset_id':base['dataset_id']}).json()['id'] == first.json()['id']
    with database.sessions() as session:
        assert session.scalar(select(func.count()).select_from(Segment)) == 1
        assert session.scalar(select(func.count()).select_from(AIExecutionLog)) == 2


def test_ai_expiry_tamper_and_bad_tool(ai_context, database):
    client, app, base = ai_context
    for mutation in ('expired', 'hash', 'version'):
        data = client.post('/api/v1/ai/chat',json={**base,'prompt':PROMPT}).json()['data']
        with database.sessions.begin() as session:
            row = session.get(AIActionProposal, UUID(data['proposal_id']))
            if mutation == 'expired': row.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
            elif mutation == 'hash': row.payload_hash = 'x' * 64
            else:
                from app.ai.orchestrator import payload_hash
                row.payload = {**row.payload, 'data_version':999}
                row.payload_hash = payload_hash(row.payload)
        assert client.post(f"/api/v1/ai/actions/{data['proposal_id']}/confirm",json={'dataset_id':base['dataset_id']}).status_code == 409
    class InvalidProvider:
        def plan(self, prompt, context): return 'execute_sql', {'sql':'DELETE'}, 0
    app.state.ai_provider = InvalidProvider()
    assert client.post('/api/v1/ai/chat',json={**base,'prompt':'test'}).status_code == 502
    assert client.post('/api/v1/ai/chat',json={**base,'prompt':'test@example.com'}).status_code == 422
    with database.sessions() as session: assert session.scalar(select(func.count()).select_from(Segment)) == 0


def test_ai_confirm_concurrency_and_rollback(ai_context, database, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from uuid import uuid4
    from app.ai.orchestrator import confirm
    from app.services import segments
    client, app, base = ai_context
    data = client.post('/api/v1/ai/chat',json={**base,'prompt':PROMPT}).json()['data']
    proposal_id, dataset_id = UUID(data['proposal_id']), UUID(base['dataset_id'])
    original = segments.record_change
    def fail(*args, **kwargs): raise RuntimeError('audit failure')
    monkeypatch.setattr(segments, 'record_change', fail)
    with database.sessions() as session:
        with pytest.raises(RuntimeError): confirm(session, proposal_id, dataset_id, uuid4())
    with database.sessions() as session:
        assert session.get(AIActionProposal, proposal_id).confirmed_at is None
        assert session.scalar(select(func.count()).select_from(Segment)) == 0
    monkeypatch.setattr(segments, 'record_change', original)
    def run():
        with database.sessions() as session: return confirm(session, proposal_id, dataset_id, uuid4())['id']
    with ThreadPoolExecutor(max_workers=2) as pool: ids = list(pool.map(lambda _:run(), range(2)))
    assert ids[0] == ids[1]


def test_changed_data_during_provider_wait_is_rejected(ai_context, database):
    from app.models.jobs import DatasetVersion
    client, app, base = ai_context
    class ChangingProvider:
        def plan(self, prompt, context):
            with database.sessions.begin() as session:
                session.add(DatasetVersion(dataset_id=UUID(base['dataset_id']), version=999, reason='test change'))
            return 'get_metric', {'metric':'active_customers'}, 0
    app.state.ai_provider = ChangingProvider()
    assert client.post('/api/v1/ai/chat',json={**base,'prompt':'test'}).status_code == 409
