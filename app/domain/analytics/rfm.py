"""Versioned fixed RFM thresholds. Equal values always receive equal scores."""
RULE_VERSION = "rfm-fixed-v1"

def scores(days, count, amount):
    if count == 0:
        return {"version": RULE_VERSION, "recency": 0, "frequency": 0, "monetary": 0, "reason": "NO_PURCHASE"}
    return {"version": RULE_VERSION,
            "recency": 5 if days <= 7 else 4 if days <= 30 else 3 if days <= 60 else 2 if days <= 90 else 1,
            "frequency": 5 if count >= 10 else 4 if count >= 5 else 3 if count >= 3 else 2 if count >= 2 else 1,
            "monetary": 5 if amount >= 500000 else 4 if amount >= 300000 else 3 if amount >= 100000 else 2 if amount >= 50000 else 1,
            "reason": None}
