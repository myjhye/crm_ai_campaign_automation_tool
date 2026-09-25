from datetime import datetime, timedelta, timezone
from uuid import uuid4
import pytest
from pydantic import ValidationError
from app.schemas.segments import SegmentWrite
from app.schemas.simulations import SimulateSendRequest
from scripts.seed_demo_campaigns import SEGMENTS, COMBINATIONS, ALL_COMBINATIONS, campaign_payload, sent_at


def test_templates_and_time_buckets():
    reference=datetime(2026,9,20,tzinfo=timezone.utc)
    dataset_id=uuid4()
    assert len(SEGMENTS)==6 and len(COMBINATIONS)==12
    for name,condition in SEGMENTS.items():
        SegmentWrite(dataset_id=dataset_id,name=name,condition=condition,reference_at=reference)
    for index,item in enumerate(COMBINATIONS):
        payload=campaign_payload(dataset_id,uuid4(),item,sent_at(reference,index))
        assert sum(row.allocation_bp for row in payload.variants)==10000
        assert all(payload.benefit in row.body for row in payload.variants)
        assert payload.channel!='SMS' or all(row.subject=='' for row in payload.variants)
    assert sum(reference-timedelta(days=32)<=sent_at(reference,i)<reference-timedelta(days=29) for i in range(12))==4
    assert sum(reference-timedelta(days=16)<=sent_at(reference,i)<reference-timedelta(days=13) for i in range(12))==4
    assert sum(reference-timedelta(days=3)<=sent_at(reference,i)<reference for i in range(12))==4
    assert len(ALL_COMBINATIONS)==24
    assert ALL_COMBINATIONS[:12]==COMBINATIONS
    assert sum(item[1]=='EMAIL' for item in ALL_COMBINATIONS)==8
    for index,item in enumerate(ALL_COMBINATIONS):
        campaign_payload(dataset_id,uuid4(),item,sent_at(reference,index))


def test_backdating_is_not_exposed_in_http_payload():
    with pytest.raises(ValidationError):
        SimulateSendRequest(dataset_id=uuid4(),campaign_version=3,seed_at='2026-09-01T00:00:00Z',seed_value=42)
