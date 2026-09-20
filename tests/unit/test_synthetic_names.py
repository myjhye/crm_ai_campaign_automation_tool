from datetime import datetime, timezone
from scripts.data.korean_names import GIVEN_NAMES, SURNAMES, synthetic_name
from scripts.seed_demo import SIZE_CONFIG, source_rows


def test_name_parts_and_repeatability():
    assert 30 <= len(SURNAMES) <= 50
    assert 100 <= len(GIVEN_NAMES) <= 200
    names = [synthetic_name(f"customer-{i}", 42) for i in range(100)]
    assert names == [synthetic_name(f"customer-{i}", 42) for i in range(100)]
    assert len(set(names)) > 90
    assert all(name.isalpha() and 2 <= len(name) <= 4 for name in names)
    assert names != [synthetic_name(f"customer-{i}", 43) for i in range(100)]


def test_medium_demo_shape_and_dormant_vip_population():
    assert SIZE_CONFIG['medium']['name'] == '체험용 중형 샘플 (고객 5,000명)'
    generated = {kind: rows for kind, rows in source_rows(42, datetime(2026, 9, 20, tzinfo=timezone.utc), 'medium')}
    assert {kind: len(generated[kind]) for kind in ('customers','products','orders','order_items','events')} == {
        'customers': 5_000, 'products': 300, 'orders': 15_000, 'order_items': 15_000, 'events': 100_000}
    dormant_orders = [row for row in generated['orders'] if int(row['customer_external_id'].split('-')[-1]) % 10 == 0]
    assert len({row['customer_external_id'] for row in dormant_orders}) == 500
