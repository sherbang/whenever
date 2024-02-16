import pytest

from whenever import Duration, InvalidFormat, Period

from .common import AlwaysEqual, NeverEqual


class TestInit:

    def test_all_params(self):
        p = Period(
            years=1,
            months=2,
            weeks=3,
            days=4,
            hours=5,
            minutes=6,
            seconds=7,
            microseconds=8,
        )
        assert p.years == 1
        assert p.months == 2
        assert p.weeks == 3
        assert p.days == 4
        assert p.hours == 5
        assert p.minutes == 6
        assert p.seconds == 7
        assert p.microseconds == 8

    def test_defaults(self):
        p = Period()
        assert p.years == 0
        assert p.months == 0
        assert p.weeks == 0
        assert p.days == 0
        assert p.hours == 0
        assert p.minutes == 0
        assert p.seconds == 0
        assert p.microseconds == 0

    def test_overflow_microseconds(self):
        assert Period(microseconds=4_300_000) == Period(
            seconds=4, microseconds=300_000
        )


def test_immutable():
    p = Period(
        years=1,
        months=2,
        weeks=3,
        days=4,
        hours=5,
        minutes=6,
        seconds=7,
        microseconds=8,
    )

    with pytest.raises(AttributeError):
        p.years = 2  # type: ignore[misc]


def test_equality():
    p = Period(
        years=1,
        months=2,
        weeks=3,
        days=4,
        hours=5,
        minutes=6,
        seconds=7,
        microseconds=8,
    )
    same = Period(
        years=1,
        months=2,
        weeks=3,
        days=4,
        hours=5,
        minutes=6,
        seconds=7,
        microseconds=8,
    )
    same_total = Period(
        years=1,
        months=2,
        weeks=2,
        days=11,
        hours=5,
        minutes=6,
        seconds=7,
        microseconds=8,
    )
    different = Period(
        years=1,
        months=2,
        weeks=3,
        days=4,
        hours=5,
        minutes=6,
        seconds=7,
        microseconds=9,
    )
    assert p == same
    assert not p == same_total
    assert not p == different
    assert not p == NeverEqual()
    assert p == AlwaysEqual()
    assert not p != same
    assert p != same_total
    assert p != different
    assert p != NeverEqual()
    assert not p != AlwaysEqual()

    assert hash(p) == hash(same)
    assert hash(p) != hash(same_total)
    assert hash(p) != hash(different)


def test_zero():
    assert Period.ZERO == Period()


def test_bool():
    assert not Period()
    assert Period(days=1)
    assert Period(hours=1)
    assert Period(minutes=1)
    assert Period(seconds=1)
    assert Period(microseconds=1)


@pytest.mark.parametrize(
    "p, expect",
    [
        (Period(), "P0D"),
        (Period(years=-2), "P-2Y"),
        (Period(days=1), "P1D"),
        (Period(hours=1), "PT1H"),
        (Period(minutes=1), "PT1M"),
        (Period(seconds=1), "PT1S"),
        (Period(microseconds=1), "PT0.000001S"),
        (Period(microseconds=4300), "PT0.0043S"),
        (Period(weeks=1), "P1W"),
        (Period(months=1), "P1M"),
        (Period(years=1), "P1Y"),
        (
            Period(
                years=1,
                months=2,
                weeks=3,
                days=4,
                hours=5,
                minutes=6,
                seconds=7,
                microseconds=8,
            ),
            "P1Y2M3W4DT5H6M7.000008S",
        ),
        (
            Period(
                years=1,
                months=2,
                weeks=3,
                days=4,
                hours=5,
                minutes=6,
                seconds=7,
                microseconds=8,
            ),
            "P1Y2M3W4DT5H6M7.000008S",
        ),
        (Period(months=2, weeks=3, minutes=6, seconds=7), "P2M3WT6M7S"),
        (Period(microseconds=-45), "PT-0.000045S"),
        (
            Period(
                years=-3,
                months=2,
                weeks=3,
                minutes=-6,
                seconds=7,
                microseconds=-45,
            ),
            "P-3Y2M3WT-6M6.999955S",
        ),
    ],
)
def test_canonical_format(p, expect):
    assert p.canonical_format() == expect
    assert str(p) == expect


class TestFromCanonicalFormat:

    def test_empty(self):
        assert Period.from_canonical_format("P0D") == Period()
        assert Period.from_canonical_format("PT0S") == Period()

    @pytest.mark.parametrize(
        "input, expect",
        [
            ("P0D", Period()),
            ("PT0S", Period()),
            ("P2Y", Period(years=2)),
            ("P1M", Period(months=1)),
            ("P1W", Period(weeks=1)),
            ("P1D", Period(days=1)),
            ("PT1H", Period(hours=1)),
            ("PT1M", Period(minutes=1)),
            ("PT1S", Period(seconds=1)),
            ("PT0.000001S", Period(microseconds=1)),
            ("PT0.0043S", Period(microseconds=4300)),
        ],
    )
    def test_single_unit(self, input, expect):
        assert Period.from_canonical_format(input) == expect

    @pytest.mark.parametrize(
        "input, expect",
        [
            (
                "P1Y2M3W4DT5H6M7S",
                Period(
                    years=1,
                    months=2,
                    weeks=3,
                    days=4,
                    hours=5,
                    minutes=6,
                    seconds=7,
                ),
            ),
            (
                "P1Y2M3W4DT5H6M7.000008S",
                Period(
                    years=1,
                    months=2,
                    weeks=3,
                    days=4,
                    hours=5,
                    minutes=6,
                    seconds=7,
                    microseconds=8,
                ),
            ),
            ("P2M3WT6M7S", Period(months=2, weeks=3, minutes=6, seconds=7)),
            ("PT-0.000045S", Period(microseconds=-45)),
            (
                "P-3Y2M+3WT-6M6.999955S",
                Period(
                    years=-3,
                    months=2,
                    weeks=3,
                    minutes=-6,
                    seconds=7,
                    microseconds=-45,
                ),
            ),
            ("P-2MT-1M", Period(months=-2, minutes=-1)),
            (
                "P-2Y3W-0DT-0.999S",
                Period(years=-2, weeks=3, seconds=-1, microseconds=1_000),
            ),
        ],
    )
    def test_multiple_units(self, input, expect):
        assert Period.from_canonical_format(input) == expect

    def test_invalid(self):
        with pytest.raises(InvalidFormat):
            Period.from_canonical_format("P")

    def test_too_many_microseconds(self):
        with pytest.raises(InvalidFormat):
            Period.from_canonical_format("PT0.0000001S")


def test_repr():
    p = Period(
        years=1,
        months=2,
        weeks=3,
        days=4,
        hours=5,
        minutes=6,
        seconds=7,
        microseconds=8,
    )
    assert repr(p) == "Period(P1Y2M3W4DT5H6M7.000008S)"


def test_negate():
    p = Period(
        years=1,
        months=2,
        weeks=3,
        days=-4,
        hours=5,
        minutes=6,
        seconds=7,
        microseconds=-8,
    )
    assert -p == Period(
        years=-1,
        months=-2,
        weeks=-3,
        days=4,
        hours=-5,
        minutes=-6,
        seconds=-7,
        microseconds=8,
    )


def test_multiply():
    p = Period(
        years=1,
        months=2,
        weeks=3,
        days=4,
        hours=5,
        minutes=6,
        seconds=7,
        microseconds=800_000,
    )
    assert p * 2 == Period(
        years=2,
        months=4,
        weeks=6,
        days=8,
        hours=10,
        minutes=12,
        seconds=15,
        microseconds=600_000,
    )
    assert p * 0 == Period.ZERO

    with pytest.raises(TypeError, match="operand"):
        p * 1.5  # type: ignore[operator]

    with pytest.raises(TypeError, match="operand"):
        p * Ellipsis  # type: ignore[operator]


def test_replace():
    p = Period(
        years=1,
        months=2,
        weeks=3,
        days=4,
        hours=5,
        minutes=6,
        seconds=7,
        microseconds=800_000,
    )
    assert p.replace(years=2) == Period(
        years=2,
        months=2,
        weeks=3,
        days=4,
        hours=5,
        minutes=6,
        seconds=7,
        microseconds=800_000,
    )
    assert p.replace(months=3) == Period(
        years=1,
        months=3,
        weeks=3,
        days=4,
        hours=5,
        minutes=6,
        seconds=7,
        microseconds=800_000,
    )
    assert p.replace(weeks=4) == Period(
        years=1,
        months=2,
        weeks=4,
        days=4,
        hours=5,
        minutes=6,
        seconds=7,
        microseconds=800_000,
    )
    assert p.replace(days=5) == Period(
        years=1,
        months=2,
        weeks=3,
        days=5,
        hours=5,
        minutes=6,
        seconds=7,
        microseconds=800_000,
    )
    assert p.replace(hours=6) == Period(
        years=1,
        months=2,
        weeks=3,
        days=4,
        hours=6,
        minutes=6,
        seconds=7,
        microseconds=800_000,
    )
    assert p.replace(minutes=7) == Period(
        years=1,
        months=2,
        weeks=3,
        days=4,
        hours=5,
        minutes=7,
        seconds=7,
        microseconds=800_000,
    )
    assert p.replace(seconds=8) == Period(
        years=1,
        months=2,
        weeks=3,
        days=4,
        hours=5,
        minutes=6,
        seconds=8,
        microseconds=800_000,
    )
    assert p.replace(microseconds=900_000) == Period(
        years=1,
        months=2,
        weeks=3,
        days=4,
        hours=5,
        minutes=6,
        seconds=7,
        microseconds=900_000,
    )


def test_add():
    p = Period(
        years=1,
        months=2,
        weeks=3,
        days=4,
        hours=5,
        minutes=6,
        seconds=7,
        microseconds=800_000,
    )
    q = Period(
        years=-1,
        months=3,
        weeks=-1,
        minutes=0,
        seconds=1,
        microseconds=300_000,
    )
    assert p + q == Period(
        months=5,
        weeks=2,
        days=4,
        hours=5,
        minutes=6,
        seconds=9,
        microseconds=100_000,
    )
    assert p + q.replace(microseconds=-300_000) == Period(
        months=5,
        weeks=2,
        days=4,
        hours=5,
        minutes=6,
        seconds=8,
        microseconds=500_000,
    )

    with pytest.raises(TypeError, match="unsupported operand"):
        p + 32  # type: ignore[operator]

    with pytest.raises(TypeError, match="unsupported operand"):
        32 + p  # type: ignore[operator]


def test_add_duration():
    p = Period(
        years=1,
        months=2,
        weeks=3,
        days=4,
        hours=5,
        minutes=6,
        seconds=7,
        microseconds=800_000,
    )
    d = Duration(hours=1, minutes=2, seconds=3, microseconds=400_004)
    expect = Period(
        years=1,
        months=2,
        weeks=3,
        days=4,
        hours=6,
        minutes=8,
        seconds=11,
        microseconds=200_004,
    )
    assert p + d == expect
    assert d + p == expect


def test_subtract():
    p = Period(
        years=1,
        months=2,
        weeks=3,
        days=4,
        hours=5,
        minutes=6,
        seconds=7,
        microseconds=300_000,
    )
    q = Period(
        years=-1,
        months=2,
        weeks=-1,
        minutes=0,
        seconds=1,
        microseconds=800_000,
    )
    assert p - q == Period(
        years=2,
        weeks=4,
        days=4,
        hours=5,
        minutes=6,
        seconds=5,
        microseconds=500_000,
    )

    with pytest.raises(TypeError, match="unsupported operand"):
        p - 32  # type: ignore[operator]


def test_subtract_duration():
    p = Period(
        years=1,
        months=2,
        weeks=3,
        days=4,
        hours=5,
        minutes=6,
        seconds=7,
        microseconds=300_000,
    )
    assert p - Duration(
        hours=1, minutes=2, seconds=3, microseconds=400_004
    ) == Period(
        years=1,
        months=2,
        weeks=3,
        days=4,
        hours=4,
        minutes=4,
        seconds=3,
        microseconds=899_996,
    )


def test_time_component():
    p = Period(
        years=1,
        months=2,
        weeks=3,
        days=4,
        hours=5,
        minutes=6,
        seconds=7,
        microseconds=800_000,
    )
    assert p.time_component() == Duration(
        hours=5, minutes=6, seconds=7, microseconds=800_000
    )


def test_as_tuple():
    p = Period(
        years=1,
        months=2,
        weeks=3,
        days=4,
        hours=5,
        minutes=6,
        seconds=7,
        microseconds=800_000,
    )
    assert p.as_tuple() == (1, 2, 3, 4, 5, 6, 7, 800_000)
