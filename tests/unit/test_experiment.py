from app.domain.analytics.experiment import compare, minimum_sample, ratio, wilson


def test_ratio_distinguishes_zero_denominator_from_zero_percent():
    assert ratio(0, 0)['status'] == 'no_denominator'
    assert ratio(0, 10) == {'status': 'available', 'numerator': 0, 'denominator': 10, 'value': 0.0}


def test_wilson_interval_contains_observed_rate():
    interval = wilson(20, 100)
    assert interval['low'] < 20 < interval['high']


def test_demo_mde_reduces_required_sample_from_conservative_twenty_percent_lift():
    assert minimum_sample(0.05) == 1471


def test_experiment_holds_until_observation_and_sample_are_sufficient():
    result = compare(2, 20, 4, 20, False)
    assert result['status'] == 'HOLD'
    assert 'OBSERVATION_OPEN' in result['reasons']
    assert 'INSUFFICIENT_SAMPLE' in result['reasons']


def test_demo_decision_threshold_is_separate_from_power_sample():
    result = compare(3, 40, 1, 43, True)
    assert result['minimum_sample_per_variant'] == 30
    assert result['power_sample_per_variant'] > result['minimum_sample_per_variant']
    assert 'INSUFFICIENT_SAMPLE' not in result['reasons']
    assert result['reasons'] == ['NO_SIGNIFICANT_DIFFERENCE']


def test_relative_uplift_is_null_when_baseline_is_zero():
    result = compare(0, 5000, 100, 5000, True)
    assert result['relative_uplift_percent'] is None


def test_guardrail_prevents_winner_declaration():
    result = compare(100, 5000, 200, 5000, True, guardrail_worse=True)
    assert result['status'] == 'HOLD'
    assert result['winner'] is None
    assert 'GUARDRAIL_WORSE' in result['reasons']
