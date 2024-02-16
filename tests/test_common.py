from whenever import Duration, hours, minutes


def test_duration_aliases():
    assert hours(1) == Duration(hours=1)
    assert minutes(1) == Duration(minutes=1)
