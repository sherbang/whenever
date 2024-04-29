import pickle
import re
from copy import copy, deepcopy
from datetime import timedelta as py_timedelta

import pytest
from pytest import approx

from whenever import (
    TimeDelta,
    hours,
    microseconds,
    milliseconds,
    minutes,
    nanoseconds,
    seconds,
)

from .common import AlwaysEqual, AlwaysLarger, AlwaysSmaller, NeverEqual

MAX_HOURS = 9999 * 366 * 24


class TestInit:

    # TODO: a big fuzzing test for argument handling
    @pytest.mark.parametrize(
        "kwargs, expected_nanos",
        [
            (dict(), 0),
            # simplest cases
            (dict(hours=2), 2 * 3_600_000_000_000),
            (dict(minutes=3), 3 * 60_000_000_000),
            (dict(seconds=4), 4 * 1_000_000_000),
            (dict(milliseconds=5), 5 * 1_000_000),
            (dict(microseconds=6), 6 * 1_000),
            (dict(nanoseconds=7), 7),
            # all components
            (
                dict(
                    hours=1,
                    minutes=2,
                    seconds=90,
                    microseconds=4,
                    nanoseconds=5,
                    milliseconds=9,
                ),
                3_600_000_000_000
                + 2 * 60_000_000_000
                + 90 * 1_000_000_000
                + 9 * 1_000_000
                + 4 * 1_000
                + 5,
            ),
            # mixed signs
            (
                dict(hours=1, minutes=-2),
                3_600_000_000_000 - 2 * 60_000_000_000,
            ),
            (
                dict(hours=-1, milliseconds=2),
                -3_600_000_000_000 + 2 * 1_000_000,
            ),
            (dict(nanoseconds=1 << 66), 1 << 66),  # huge value outside i64
            # precision loss for floats
            (
                dict(microseconds=MAX_HOURS * 3_600_000_000 + 0.001),
                MAX_HOURS * 3_600_000_000_000,
            ),
            # no precision loss for integers
            (
                dict(hours=MAX_HOURS - 1),
                (MAX_HOURS - 1) * 3_600_000_000_000,
            ),
            (
                dict(minutes=MAX_HOURS * 60 - 1),
                MAX_HOURS * 3_600_000_000_000 - 60_000_000_000,
            ),
            (
                dict(seconds=MAX_HOURS * 3_600 - 1),
                MAX_HOURS * 3_600_000_000_000 - 1_000_000_000,
            ),
            (
                dict(milliseconds=MAX_HOURS * 3_600_000 - 1),
                MAX_HOURS * 3_600_000_000_000 - 1_000_000,
            ),
            (
                dict(microseconds=MAX_HOURS * 3_600_000_000 - 1),
                MAX_HOURS * 3_600_000_000_000 - 1_000,
            ),
            (
                dict(microseconds=-MAX_HOURS * 3_600_000_000 + 1),
                -MAX_HOURS * 3_600_000_000_000 + 1_000,
            ),
            (
                dict(nanoseconds=-MAX_HOURS * 3_600_000_000_000 + 1),
                -MAX_HOURS * 3_600_000_000_000 + 1,
            ),
            (
                dict(nanoseconds=MAX_HOURS * 3_600_000_000_000 - 1),
                MAX_HOURS * 3_600_000_000_000 - 1,
            ),
            # fractional values
            (dict(minutes=1.5), int(1.5 * 60_000_000_000)),
            (dict(seconds=1.5), int(1.5 * 1_000_000_000)),
        ],
    )
    def test_valid(self, kwargs, expected_nanos):
        d = TimeDelta(**kwargs)
        assert d.in_nanoseconds() == expected_nanos
        # the components are not accessible directly
        assert not hasattr(d, "hours")

    @pytest.mark.parametrize(
        "kwargs",
        [
            dict(hours=MAX_HOURS + 1),
            dict(hours=-MAX_HOURS - 1),
            dict(minutes=MAX_HOURS * 60 + 1),
            dict(minutes=-MAX_HOURS * 60 - 1),
            dict(seconds=MAX_HOURS * 3_600 + 1),
            dict(seconds=-MAX_HOURS * 3_600 - 1),
            dict(milliseconds=MAX_HOURS * 3_600_000 + 1),
            dict(milliseconds=-MAX_HOURS * 3_600_000 - 1),
            dict(microseconds=MAX_HOURS * 3_600_000_000 + 1),
            dict(microseconds=-MAX_HOURS * 3_600_000_000 - 1),
            dict(nanoseconds=MAX_HOURS * 3_600_000_000_000 + 1),
            dict(nanoseconds=-MAX_HOURS * 3_600_000_000_000 - 1),
            dict(hours=float("inf")),
            dict(minutes=float("inf")),
            dict(seconds=float("-inf")),
            dict(milliseconds=float("nan")),
        ],
    )
    def test_invalid_out_of_range(self, kwargs):
        with pytest.raises(ValueError, match="range"):
            TimeDelta(**kwargs)

    def test_invalid_kwargs(self):
        with pytest.raises(TypeError, match="foo"):
            TimeDelta(foo=1)  # type: ignore[call-arg]

        with pytest.raises(TypeError):
            TimeDelta(1)  # type: ignore[call-arg]

        with pytest.raises(TypeError):
            TimeDelta(**{1: 43})  # type: ignore[misc]


@pytest.mark.parametrize(
    "f, arg, expected",
    [
        (hours, 3.5, TimeDelta(hours=3.5)),
        (minutes, 3.5, TimeDelta(minutes=3.5)),
        (seconds, 3.5, TimeDelta(seconds=3.5)),
        (microseconds, 3.5, TimeDelta(microseconds=3.5)),
        (milliseconds, 3.5, TimeDelta(milliseconds=3.5)),
        (nanoseconds, 3, TimeDelta(nanoseconds=3)),
    ],
)
def test_factories(f, arg, expected):
    assert f(arg) == expected


def test_constants():
    assert TimeDelta.ZERO == TimeDelta()
    assert TimeDelta.MAX == TimeDelta(
        nanoseconds=9999 * 366 * 24 * 60 * 60 * 1_000_000_000
    )
    assert TimeDelta.MIN == -TimeDelta.MAX


def test_boolean():
    assert not TimeDelta(hours=0, minutes=0, seconds=0, microseconds=0)
    assert not TimeDelta(hours=1, minutes=-60)
    assert TimeDelta(microseconds=1)


def test_aggregations():
    d = TimeDelta(hours=1, minutes=2, seconds=0.003, nanoseconds=4)
    assert d.in_microseconds() == approx(
        3_600_000_000 + 2 * 60_000_000 + 3 * 1_000 + 0.004
    )
    assert d.in_milliseconds() == approx(3_600_000 + 2 * 60_000 + 3 + 4e-6)
    assert d.in_seconds() == approx(3600 + 2 * 60 + 0.003 + 4e-9)
    assert d.in_minutes() == approx(60 + 2 + 0.003 / 60 + 4 / 60_000_000_000)
    assert d.in_hours() == approx(
        1 + 2 / 60 + 0.003 / 3_600 + 4 / 3_600_000_000_000_000
    )
    assert d.in_days_of_24h() == approx(
        1 / 24
        + 2 / (24 * 60)
        + 0.003 / (24 * 3_600)
        + 4 / (24 * 3_600_000_000_000_000)
    )


def test_equality():
    d = TimeDelta(hours=1, minutes=2, seconds=3, microseconds=4)
    same = TimeDelta(hours=1, minutes=2, seconds=3, microseconds=4)
    same_total = TimeDelta(hours=0, minutes=62, seconds=3, microseconds=4)
    different = TimeDelta(hours=1, minutes=2, seconds=3, microseconds=5)
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
    d = TimeDelta(hours=1, minutes=2, seconds=3, microseconds=4)
    same = TimeDelta(hours=1, minutes=2, seconds=3, microseconds=4)
    same_total = TimeDelta(hours=0, minutes=62, seconds=3, microseconds=4)
    bigger = TimeDelta(hours=1, minutes=2, seconds=3, microseconds=5)
    smaller = TimeDelta(hours=1, minutes=2, seconds=3, microseconds=3)

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


# TODO: prefix with `PT`?
@pytest.mark.parametrize(
    "d, expected",
    [
        (
            TimeDelta(hours=1, minutes=2, seconds=3, microseconds=4),
            "01:02:03.000004",
        ),
        (
            TimeDelta(hours=1, minutes=-2, seconds=3, microseconds=-4),
            "00:58:02.999996",
        ),
        (
            TimeDelta(hours=1, minutes=2, seconds=3, microseconds=50_000),
            "01:02:03.05",
        ),
        (
            TimeDelta(hours=1, minutes=120, seconds=3),
            "03:00:03",
        ),
        (
            TimeDelta(),
            "00:00:00",
        ),
        (
            TimeDelta(hours=5),
            "05:00:00",
        ),
        (
            TimeDelta(hours=400),
            "400:00:00",
        ),
        (
            TimeDelta(minutes=-4),
            "-00:04:00",
        ),
    ],
)
def test_canonical_format(d, expected):
    assert d.canonical_format() == expected
    assert str(d) == expected


class TestFromCanonicalFormat:

    @pytest.mark.parametrize(
        "s, expected",
        [
            (
                "01:02:03.000004",
                TimeDelta(hours=1, minutes=2, seconds=3, microseconds=4),
            ),
            ("00:04:00", TimeDelta(minutes=4)),
            ("00:00:00", TimeDelta()),
            ("05:00:00", TimeDelta(hours=5)),
            ("400:00:00", TimeDelta(hours=400)),
            ("00:00:00.000000", TimeDelta()),
            ("00:00:00.999955", TimeDelta(microseconds=999_955)),
            ("00:00:00.99", TimeDelta(microseconds=990_000)),
            ("-00:04:00", TimeDelta(minutes=-4)),
            ("+00:04:00", TimeDelta(minutes=4)),
            ("-00:04:00.000000001", TimeDelta(minutes=-4, nanoseconds=-1)),
            ("4:00:00", TimeDelta(hours=4)),
        ],
    )
    def test_valid(self, s, expected):
        assert TimeDelta.from_canonical_format(s) == expected

    @pytest.mark.parametrize(
        "s",
        [
            "00:00:00.000000.000000",  # too many dots
            "00:00:00.0000.00",  # too many dots
            "00:00.00",  # invalid separator
            "00.00.00.0000",  # invalid separator
            "",  # empty
            "00:60:00",  # too large minutes
            "00:00:60",  # too large seconds
            "04:4:00",  # missing padding
            "05:-2:11",  # negative minutes
            "05:02:11.",  # invalid fraction
            "05:02:11.a",  # invalid fraction
            "05:02:11.1234567890",  # too long fraction
            "05",  # only hours
            "5:00",  # missing seconds
        ],
    )
    def test_invalid(self, s):
        with pytest.raises(
            ValueError,
            match="Invalid time delta format.*" + re.escape(repr(s)),
        ):
            TimeDelta.from_canonical_format(s)


@pytest.mark.parametrize(
    "d, expected",
    [
        (
            TimeDelta(hours=1, minutes=2, seconds=3, microseconds=4),
            "PT1H2M3.000004S",
        ),
        (
            TimeDelta(hours=1, minutes=-2, seconds=3, microseconds=-4),
            "PT58M2.999996S",
        ),
        (
            TimeDelta(hours=1, minutes=2, seconds=3, microseconds=50_000),
            "PT1H2M3.05S",
        ),
        (
            TimeDelta(hours=1, minutes=120, seconds=3),
            "PT3H3S",
        ),
        (
            TimeDelta(),
            "PT0S",
        ),
        (
            TimeDelta(microseconds=1),
            "PT0.000001S",
        ),
        (
            TimeDelta(microseconds=-1),
            "-PT0.000001S",
        ),
        (
            TimeDelta(seconds=2, microseconds=-3),
            "PT1.999997S",
        ),
        (
            TimeDelta(hours=5),
            "PT5H",
        ),
        (
            TimeDelta(hours=400),
            "PT400H",
        ),
        (
            TimeDelta(minutes=-4),
            "-PT4M",
        ),
    ],
)
def test_common_iso8601(d, expected):
    assert d.common_iso8601() == expected


class TestFromCommonIso8601:

    @pytest.mark.parametrize(
        "s, expected",
        [
            (
                "PT1H2M3.000004S",
                TimeDelta(hours=1, minutes=2, seconds=3, microseconds=4),
            ),
            (
                "PT58M2.999996S",
                TimeDelta(hours=1, minutes=-2, seconds=3, microseconds=-4),
            ),
            (
                "PT1H2M3.05S",
                TimeDelta(hours=1, minutes=2, seconds=3, microseconds=50_000),
            ),
            ("PT3H3S", TimeDelta(hours=1, minutes=120, seconds=3)),
            ("PT0S", TimeDelta()),
            ("PT0.000000001S", TimeDelta(nanoseconds=1)),
            ("PT450.000000001S", TimeDelta(seconds=450, nanoseconds=1)),
            ("PT0.000001S", TimeDelta(microseconds=1)),
            ("-PT0.000001S", TimeDelta(microseconds=-1)),
            ("PT1.999997S", TimeDelta(seconds=2, microseconds=-3)),
            ("PT5H", TimeDelta(hours=5)),
            ("PT400H", TimeDelta(hours=400)),
            ("-PT4M", TimeDelta(minutes=-4)),
            ("PT0S", TimeDelta()),
            ("PT3M", TimeDelta(minutes=3)),
            ("+PT3M", TimeDelta(minutes=3)),
            ("PT0M", TimeDelta()),
            ("PT0.000000000S", TimeDelta()),
            # extremely long but still valid
            (
                "PT0H0M000000000000000300000000000.000000000S",
                TimeDelta(seconds=300_000_000_000),
            ),
            # TODO: extreme number of seconds
        ],
    )
    def test_valid(self, s, expected):
        assert TimeDelta.from_common_iso8601(s) == expected

    @pytest.mark.parametrize(
        "s",
        [
            "P1D",  # date units
            "P1YT4M",  # date units
            "T1H",  # wrong prefix
            "PT4M3H",  # wrong order
            "PT1.5H",  # fractional hours
            "PT1H2M3.000004S9H",  # stuff after nanoseconds
            "PT1H2M3.000004S ",  # stuff after nanoseconds
            "PT34.S",  # missing fractions
            "PTS",  # no digits
            "PT4HS",  # no digits
            # way too many digits (there's a limit...)
            "PT000000000000000000000000000000000000000000000000000000000001S",
        ],
    )
    def test_invalid(self, s) -> None:
        with pytest.raises(
            ValueError,
            match=r"Invalid time delta format.*" + re.escape(repr(s)),
        ):
            TimeDelta.from_common_iso8601(s)

    @pytest.mark.parametrize(
        "s",
        [
            f"PT{10_000 * 366 * 24}H",  # too big value
            f"PT{10_000 * 366 * 24 * 3600}S",  # too big value
        ],
    )
    def test_too_large(self, s) -> None:
        with pytest.raises(ValueError, match="range"):
            TimeDelta.from_common_iso8601(s)


def test_addition():
    d = TimeDelta(hours=1, minutes=2, seconds=3, microseconds=4)
    assert d + TimeDelta() == d
    assert d + TimeDelta(hours=1) == TimeDelta(
        hours=2, minutes=2, seconds=3, microseconds=4
    )
    assert d + TimeDelta(minutes=-1) == TimeDelta(
        hours=1, minutes=1, seconds=3, microseconds=4
    )

    with pytest.raises(TypeError, match="unsupported operand"):
        d + Ellipsis  # type: ignore[operator]


def test_subtraction():
    d = TimeDelta(hours=1, minutes=2, seconds=3, microseconds=4)
    assert d - TimeDelta() == d
    assert d - TimeDelta(hours=1) == TimeDelta(
        hours=0, minutes=2, seconds=3, microseconds=4
    )
    assert d - TimeDelta(minutes=-1) == TimeDelta(
        hours=1, minutes=3, seconds=3, microseconds=4
    )

    with pytest.raises(TypeError, match="unsupported operand"):
        d - Ellipsis  # type: ignore[operator]


def test_multiply():
    d = TimeDelta(hours=1, minutes=2, seconds=3, microseconds=4)
    assert d * 2 == TimeDelta(hours=2, minutes=4, seconds=6, microseconds=8)
    assert d * 0.5 == TimeDelta(
        hours=0, minutes=31, seconds=1, microseconds=500_002
    )

    # allow very big ints if there's no overflow
    assert TimeDelta(nanoseconds=1) * (1 << 66) == TimeDelta(
        nanoseconds=1 << 66
    )
    assert TimeDelta(nanoseconds=1) * float(1 << 66) == TimeDelta(
        nanoseconds=1 << 66
    )

    # overflow
    with pytest.raises(ValueError, match="range"):
        d * 1_000_000_000

    with pytest.raises(TypeError, match="unsupported operand"):
        d * Ellipsis  # type: ignore[operator]


class TestDivision:

    def test_by_number(self):
        d = TimeDelta(hours=1, minutes=2, seconds=3, microseconds=4)
        assert d / 2 == TimeDelta(
            hours=0, minutes=31, seconds=1, microseconds=500_002
        )
        assert d / 0.5 == TimeDelta(
            hours=2, minutes=4, seconds=6, microseconds=8
        )
        assert TimeDelta.MAX / 1.0 == TimeDelta.MAX
        assert TimeDelta.MIN / 1.0 == TimeDelta.MIN

    def test_divide_by_duration(self):
        d = TimeDelta(hours=1, minutes=2, seconds=3, microseconds=4)
        assert d / TimeDelta(hours=1) == approx(
            1 + 2 / 60 + 3 / 3_600 + 4 / 3_600_000_000
        )
        assert TimeDelta.ZERO / TimeDelta.MAX == 0.0
        assert TimeDelta.ZERO / TimeDelta.MIN == 0.0
        assert TimeDelta.MAX / TimeDelta.MAX == 1.0
        assert TimeDelta.MIN / TimeDelta.MIN == 1.0
        assert TimeDelta.MAX / TimeDelta.MIN == -1.0
        assert TimeDelta.MIN / TimeDelta.MAX == -1.0

    def test_divide_by_zero(self):
        d = TimeDelta(hours=1, minutes=2, seconds=3, microseconds=4)
        with pytest.raises(ZeroDivisionError):
            d / TimeDelta()

        with pytest.raises(ZeroDivisionError):
            d / 0

        with pytest.raises(ZeroDivisionError):
            d / 0.0

    def test_invalid(self):
        d = TimeDelta(hours=1, minutes=2, seconds=3, microseconds=4)
        with pytest.raises(TypeError):
            d / "invalid"  # type: ignore[operator]


def test_negate():
    assert TimeDelta.ZERO == -TimeDelta.ZERO
    assert TimeDelta(
        hours=-1, minutes=2, seconds=-3, microseconds=4
    ) == -TimeDelta(hours=1, minutes=-2, seconds=3, microseconds=-4)


@pytest.mark.parametrize(
    "d",
    [
        TimeDelta(hours=1, minutes=2, seconds=3, microseconds=4),
        TimeDelta.ZERO,
        TimeDelta(hours=-2, minutes=-15),
    ],
)
def test_pos(d):
    assert d is +d


def test_py_timedelta():
    assert TimeDelta().py_timedelta() == py_timedelta(0)
    assert TimeDelta(
        hours=1, minutes=2, seconds=3, microseconds=4
    ).py_timedelta() == py_timedelta(
        hours=1, minutes=2, seconds=3, microseconds=4
    )
    assert TimeDelta(nanoseconds=-42_000).py_timedelta() == py_timedelta(
        microseconds=-42
    )

    # consistent truncation of sub-microsecond values
    assert TimeDelta(nanoseconds=-1).py_timedelta() == py_timedelta()
    assert TimeDelta(nanoseconds=-499).py_timedelta() == py_timedelta()
    assert TimeDelta(nanoseconds=-500).py_timedelta() == py_timedelta()
    assert TimeDelta(nanoseconds=-501).py_timedelta() == py_timedelta(
        microseconds=-1
    )
    assert TimeDelta(nanoseconds=1).py_timedelta() == py_timedelta()
    assert TimeDelta(nanoseconds=499).py_timedelta() == py_timedelta()
    assert TimeDelta(nanoseconds=500).py_timedelta() == py_timedelta(
        microseconds=1
    )
    assert TimeDelta(nanoseconds=501).py_timedelta() == py_timedelta(
        microseconds=1
    )


def test_from_py_timedelta():
    assert TimeDelta.from_py_timedelta(py_timedelta(0)) == TimeDelta.ZERO
    assert TimeDelta.from_py_timedelta(
        py_timedelta(weeks=8, hours=1, minutes=2, seconds=3, microseconds=4)
    ) == TimeDelta(hours=1 + 7 * 24 * 8, minutes=2, seconds=3, microseconds=4)


def test_tuple():
    d = TimeDelta(hours=1, minutes=2, seconds=-3, microseconds=4_060_000)
    hms = d.as_tuple()
    assert all(isinstance(x, int) for x in hms)
    assert hms == (1, 2, 1, 60_000_000)
    assert TimeDelta(hours=-2, minutes=-15).as_tuple() == (-2, -15, 0, 0)
    assert TimeDelta(nanoseconds=-4).as_tuple() == (0, 0, 0, -4)
    assert TimeDelta.ZERO.as_tuple() == (0, 0, 0, 0)


def test_abs():
    assert abs(TimeDelta()) == TimeDelta()
    assert abs(
        TimeDelta(hours=-1, minutes=-2, seconds=-3, microseconds=-4)
    ) == TimeDelta(hours=1, minutes=2, seconds=3, microseconds=4)
    assert abs(TimeDelta(hours=1)) == TimeDelta(hours=1)


def test_copy():
    d = TimeDelta(hours=1, minutes=2, seconds=3, microseconds=4)
    assert copy(d) is d
    assert deepcopy(d) is d


def test_pickling():
    d = TimeDelta(hours=1, minutes=2, seconds=3, microseconds=4)
    dumped = pickle.dumps(d)
    assert len(dumped) < len(pickle.dumps(d.py_timedelta())) + 10
    assert pickle.loads(dumped) == d

    assert pickle.loads(pickle.dumps(TimeDelta.MAX)) == TimeDelta.MAX
    assert pickle.loads(pickle.dumps(TimeDelta.MIN)) == TimeDelta.MIN


def test_compatible_unpickle():
    dumped = (
        b"\x80\x04\x95(\x00\x00\x00\x00\x00\x00\x00\x8c\x08whenever\x94\x8c\r_unpkl_t"
        b"delta\x94\x93\x94M\x8b\x0eM\xa0\x0f\x86\x94R\x94."
    )
    assert pickle.loads(dumped) == TimeDelta(
        hours=1, minutes=2, seconds=3, microseconds=4
    )
