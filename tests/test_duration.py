from datetime import timedelta

import pytest
from pytest import approx

from whenever import Duration, InvalidFormat, Period

from .common import AlwaysEqual, AlwaysLarger, AlwaysSmaller, NeverEqual


class TestInit:

    def test_basics(self):
        d = Duration(hours=1, minutes=2, seconds=3, microseconds=4)
        # the components are not accessible directly
        assert not hasattr(d, "hours")

    def test_defaults(self):
        d = Duration()
        assert d.in_microseconds() == 0


@pytest.mark.parametrize(
    "kwargs, expected",
    [
        (dict(), Duration()),
        (dict(hours=1), Duration(microseconds=3_600_000_000)),
        (dict(minutes=1), Duration(microseconds=60_000_000)),
        (dict(seconds=1), Duration(microseconds=1_000_000)),
        (
            dict(minutes=90, microseconds=-3_600_000_000),
            Duration(minutes=30),
        ),
    ],
)
def test_normalization(kwargs, expected):
    assert Duration(**kwargs) == expected


def test_fractional():
    assert Duration(minutes=1.5) == Duration(seconds=90)


def test_avoids_floating_point_errors():
    assert Duration(hours=10_000_001.0, microseconds=1) == Duration(
        microseconds=int(10_000_001 * 3_600_000_000) + 1
    )


def test_zero():
    assert Duration().ZERO == Duration()
    assert Duration.ZERO == Duration(
        hours=0, minutes=0, seconds=0, microseconds=0
    )


def test_boolean():
    assert not Duration(hours=0, minutes=0, seconds=0, microseconds=0)
    assert not Duration(hours=1, minutes=-60)
    assert Duration(microseconds=1)


def test_aggregations():
    d = Duration(hours=1, minutes=2, seconds=3, microseconds=4)
    assert d.in_hours() == approx(1 + 2 / 60 + 3 / 3_600 + 4 / 3_600_000_000)
    assert d.in_minutes() == approx(60 + 2 + 3 / 60 + 4 / 60_000_000)
    assert d.in_seconds() == approx(3600 + 2 * 60 + 3 + 4 / 1_000_000)
    assert (
        d.in_microseconds()
        == 3_600_000_000 + 2 * 60_000_000 + 3 * 1_000_000 + 4
    )


def test_equality():
    d = Duration(hours=1, minutes=2, seconds=3, microseconds=4)
    same = Duration(hours=1, minutes=2, seconds=3, microseconds=4)
    same_total = Duration(hours=0, minutes=62, seconds=3, microseconds=4)
    different = Duration(hours=1, minutes=2, seconds=3, microseconds=5)
    assert d == same
    assert d == same_total
    assert not d == different
    assert not d == NeverEqual()
    assert d == AlwaysEqual()
    assert not d != same
    assert not d != same_total
    assert d != different
    assert d != NeverEqual()
    assert not d != AlwaysEqual()

    assert hash(d) == hash(same)
    assert hash(d) == hash(same_total)
    assert hash(d) != hash(different)


def test_comparison():
    d = Duration(hours=1, minutes=2, seconds=3, microseconds=4)
    same = Duration(hours=1, minutes=2, seconds=3, microseconds=4)
    same_total = Duration(hours=0, minutes=62, seconds=3, microseconds=4)
    bigger = Duration(hours=1, minutes=2, seconds=3, microseconds=5)
    smaller = Duration(hours=1, minutes=2, seconds=3, microseconds=3)

    assert d <= same
    assert d <= same_total
    assert d <= bigger
    assert not d <= smaller
    assert d <= AlwaysLarger()
    assert not d <= AlwaysSmaller()

    assert not d < same
    assert not d < same_total
    assert d < bigger
    assert not d < smaller
    assert d < AlwaysLarger()
    assert not d < AlwaysSmaller()

    assert d >= same
    assert d >= same_total
    assert not d >= bigger
    assert d >= smaller
    assert not d >= AlwaysLarger()
    assert d >= AlwaysSmaller()

    assert not d > same
    assert not d > same_total
    assert not d > bigger
    assert d > smaller
    assert not d > AlwaysLarger()
    assert d > AlwaysSmaller()


@pytest.mark.parametrize(
    "d, expected",
    [
        (
            Duration(hours=1, minutes=2, seconds=3, microseconds=4),
            "01:02:03.000004",
        ),
        (
            Duration(hours=1, minutes=-2, seconds=3, microseconds=-4),
            "00:58:02.999996",
        ),
        (
            Duration(hours=1, minutes=120, seconds=3),
            "03:00:03",
        ),
        (
            Duration(),
            "00:00:00",
        ),
        (
            Duration(hours=5),
            "05:00:00",
        ),
        (
            Duration(hours=400),
            "400:00:00",
        ),
        (
            Duration(minutes=-4),
            "-00:04:00",
        ),
    ],
)
def test_canonical_format(d, expected):
    assert d.canonical_format() == expected


class TestFromCanonicalFormat:

    @pytest.mark.parametrize(
        "s, expected",
        [
            (
                "01:02:03.000004",
                Duration(hours=1, minutes=2, seconds=3, microseconds=4),
            ),
            ("00:04:00", Duration(minutes=4)),
            ("00:00:00", Duration()),
            ("05:00:00", Duration(hours=5)),
            ("400:00:00", Duration(hours=400)),
            ("00:00:00.000000", Duration()),
            ("00:00:00.999955", Duration(microseconds=999_955)),
            ("-00:04:00", Duration(minutes=-4)),
            ("+00:04:00", Duration(minutes=4)),
        ],
    )
    def test_valid(self, s, expected):
        assert Duration.from_canonical_format(s) == expected

    @pytest.mark.parametrize(
        "s",
        ["00:60:00", "00:00:60"],
    )
    def test_invalid_too_large(self, s):
        with pytest.raises(InvalidFormat):
            Duration.from_canonical_format(s)

    @pytest.mark.parametrize(
        "s",
        [
            "00:00:00.000000.000000",
            "00:00:00.0000.00" "00:00.00.0000",
            "00.00.00.0000",
            "+0000:00",
        ],
    )
    def test_invalid_seperators(self, s):
        with pytest.raises(InvalidFormat):
            Duration.from_canonical_format(s)


def test_addition():
    d = Duration(hours=1, minutes=2, seconds=3, microseconds=4)
    assert d + Duration() == d
    assert d + Duration(hours=1) == Duration(
        hours=2, minutes=2, seconds=3, microseconds=4
    )
    assert d + Duration(minutes=-1) == Duration(
        hours=1, minutes=1, seconds=3, microseconds=4
    )

    with pytest.raises(TypeError, match="unsupported operand"):
        d + Ellipsis  # type: ignore[operator]


def test_subtraction():
    d = Duration(hours=1, minutes=2, seconds=3, microseconds=4)
    assert d - Duration() == d
    assert d - Duration(hours=1) == Duration(
        hours=0, minutes=2, seconds=3, microseconds=4
    )
    assert d - Duration(minutes=-1) == Duration(
        hours=1, minutes=3, seconds=3, microseconds=4
    )

    with pytest.raises(TypeError, match="unsupported operand"):
        d - Ellipsis  # type: ignore[operator]


def test_multiply():
    d = Duration(hours=1, minutes=2, seconds=3, microseconds=4)
    assert d * 2 == Duration(hours=2, minutes=4, seconds=6, microseconds=8)
    assert d * 0.5 == Duration(
        hours=0, minutes=31, seconds=1, microseconds=500_002
    )

    with pytest.raises(TypeError, match="unsupported operand"):
        d * Ellipsis  # type: ignore[operator]


class TestDivision:

    def test_by_number(self):
        d = Duration(hours=1, minutes=2, seconds=3, microseconds=4)
        assert d / 2 == Duration(
            hours=0, minutes=31, seconds=1, microseconds=500_002
        )
        assert d / 0.5 == Duration(
            hours=2, minutes=4, seconds=6, microseconds=8
        )

    def test_divide_by_duration(self):
        d = Duration(hours=1, minutes=2, seconds=3, microseconds=4)
        assert d / Duration(hours=1) == approx(
            1 + 2 / 60 + 3 / 3_600 + 4 / 3_600_000_000
        )

    def test_divide_by_zero(self):
        d = Duration(hours=1, minutes=2, seconds=3, microseconds=4)
        with pytest.raises(ZeroDivisionError):
            d / Duration()

        with pytest.raises(ZeroDivisionError):
            d / 0

    def test_invalid(self):
        d = Duration(hours=1, minutes=2, seconds=3, microseconds=4)
        with pytest.raises(TypeError):
            d / "invalid"  # type: ignore[operator]


def test_negate():
    assert Duration.ZERO == -Duration.ZERO
    assert Duration(
        hours=-1, minutes=2, seconds=-3, microseconds=4
    ) == -Duration(hours=1, minutes=-2, seconds=3, microseconds=-4)


def test_py_timedelta():
    assert Duration().py_timedelta() == timedelta(0)
    assert Duration(
        hours=1, minutes=2, seconds=3, microseconds=4
    ).py_timedelta() == timedelta(
        hours=1, minutes=2, seconds=3, microseconds=4
    )


def test_from_timedelta():
    assert Duration.from_py_timedelta(timedelta(0)) == Duration()
    assert Duration.from_py_timedelta(
        timedelta(weeks=8, hours=1, minutes=2, seconds=3, microseconds=4)
    ) == Duration(hours=1 + 7 * 24 * 8, minutes=2, seconds=3, microseconds=4)


@pytest.mark.parametrize(
    "d, expected",
    [
        (Duration(), Period()),
        (Duration(hours=1), Period(hours=1)),
        (Duration(minutes=1), Period(minutes=1)),
        (Duration(seconds=1), Period(seconds=1)),
        (Duration(microseconds=1), Period(microseconds=1)),
        (
            Duration(hours=1, minutes=2, seconds=3, microseconds=4),
            Period(hours=1, minutes=2, seconds=3, microseconds=4),
        ),
    ],
)
def test_as_period(d, expected):
    assert d.as_period() == expected


def test_tuple():
    d = Duration(hours=1, minutes=2, seconds=-3, microseconds=4_060_000)
    hms = d.as_tuple()
    assert all(isinstance(x, int) for x in hms)
    assert hms == (1, 2, 1, 60_000)
    assert Duration(hours=-2, minutes=-15).as_tuple() == (-2, -15, 0, 0)
    assert Duration.ZERO.as_tuple() == (0, 0, 0, 0)


def test_abs():
    assert abs(Duration()) == Duration()
    assert abs(
        Duration(hours=-1, minutes=-2, seconds=-3, microseconds=-4)
    ) == Duration(hours=1, minutes=2, seconds=3, microseconds=4)
    assert abs(Duration(hours=1)) == Duration(hours=1)
