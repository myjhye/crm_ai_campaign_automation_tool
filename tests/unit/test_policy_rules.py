from app.domain.policies.rules import ordered_reasons, rule_results

def test_policy_reasons_keep_all_and_priority():
    reasons=ordered_reasons(withdrawn=True,consent=False,contact=None,valid=False,hard_bounce=True,
        excluded=True,duplicate=True,daily=2,weekly=5,daily_limit=1,weekly_limit=3)
    assert reasons == ['WITHDRAWN','NO_CONSENT','INVALID_CONTACT','EXCLUDED_SEGMENT','DUPLICATE_CAMPAIGN','DAILY_LIMIT','WEEKLY_LIMIT']
    rows=rule_results({'WITHDRAWN':2})
    assert rows[0]['affected_count']==2 and rows[0]['passed'] is False
    assert rows[1]['passed'] is True
