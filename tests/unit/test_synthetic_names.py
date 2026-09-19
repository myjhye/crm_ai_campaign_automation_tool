from scripts.data.korean_names import GIVEN_NAMES, SURNAMES, synthetic_name


def test_name_parts_and_repeatability():
    assert 30 <= len(SURNAMES) <= 50
    assert 100 <= len(GIVEN_NAMES) <= 200
    names = [synthetic_name(f"customer-{i}", 42) for i in range(100)]
    assert names == [synthetic_name(f"customer-{i}", 42) for i in range(100)]
    assert len(set(names)) > 90
    assert all(name.isalpha() and 2 <= len(name) <= 4 for name in names)
    assert names != [synthetic_name(f"customer-{i}", 43) for i in range(100)]
