from app.domain.analytics.rfm import scores


def test_rfm_boundaries_and_no_purchase():
    assert scores(None, 0, 0)["reason"] == "NO_PURCHASE"
    assert [scores(days, 1, 0)["recency"] for days in (7, 8, 30, 31, 60, 61, 90, 91)] == [5, 4, 4, 3, 3, 2, 2, 1]
    assert [scores(1, count, 0)["frequency"] for count in (1, 2, 3, 4, 5, 9, 10)] == [1, 2, 3, 3, 4, 4, 5]
    assert [scores(1, 1, amount)["monetary"] for amount in (49999, 50000, 100000, 300000, 500000)] == [1, 2, 3, 4, 5]
