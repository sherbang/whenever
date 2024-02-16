# The MIT License (MIT)
#
# Copyright (c) Arie Bovenberg
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

# Maintainer's notes:
#
# - Why is everything in one file?
#   - Flat is better than nested
#   - It prevents circular imports since the classes 'know' about each other
#   - It's easier to vendor (i.e. copy-paste) this library if needed
# - There is some code duplication in this file. This is intentional:
#   - It makes it easier to understand the code
#   - It's sometimes necessary for the type checker
#   - It saves some overhead
from __future__ import annotations

__version__ = "0.4.0rc0"

import re
import sys
from abc import ABC, abstractmethod
from calendar import monthrange
from datetime import (
    date as _date,
    datetime as _datetime,
    timedelta as _timedelta,
    timezone as _timezone,
    tzinfo as _tzinfo,
)
from email.utils import format_datetime, parsedate_to_datetime
from operator import attrgetter
from typing import (
    TYPE_CHECKING,
    Callable,
    ClassVar,
    Literal,
    TypeVar,
    no_type_check,
    overload,
)

try:
    from typing import SPHINX_BUILD  # type: ignore[attr-defined]
except ImportError:
    SPHINX_BUILD = False

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover
    from backports.zoneinfo import (  # type: ignore[import-not-found,no-redef]
        ZoneInfo,
    )

__all__ = [
    "Date",
    "DateTime",
    "AwareDateTime",
    "UTCDateTime",
    "OffsetDateTime",
    "ZonedDateTime",
    "LocalDateTime",
    "NaiveDateTime",
    "Duration",
    "Period",
    "hours",
    "minutes",
    "DoesntExistInZone",
    "Ambiguous",
    "InvalidOffsetForZone",
    "InvalidFormat",
]


MONDAY, TUESDAY, WEDNESDAY, THURSDAY, FRIDAY, SATURDAY, SUNDAY = range(1, 8)


class NOT_SET:
    pass  # sentinel for when no value is passed


class Date:
    """A date without a time component

    Example
    -------

    >>> d = Date(2021, 1, 2)
    Date(2021-01-02)

    """

    __slots__ = ("_py_date",)

    def __init__(self, year: int, month: int, day: int) -> None:
        self._py_date = _date(year, month, day)

    @property
    def year(self) -> int:
        return self._py_date.year

    @property
    def month(self) -> int:
        return self._py_date.month

    @property
    def day(self) -> int:
        return self._py_date.day

    def canonical_format(self) -> str:
        """The date in canonical format.

        Example
        -------

        >>> d = Date(2021, 1, 2)
        >>> d.canonical_format()
        '2021-01-02'

        """
        return self._py_date.isoformat()

    __str__ = canonical_format

    def __repr__(self) -> str:
        return f"Date({self})"

    if not TYPE_CHECKING:  # pragma: no branch

        def __eq__(self, other: object) -> bool:
            """Compare for equality

            Example
            -------

            >>> d = Date(2021, 1, 2)
            >>> d == Date(2021, 1, 2)
            True
            >>> d == Date(2021, 1, 3)
            False

            """
            if not isinstance(other, Date):
                return NotImplemented
            return self._py_date == other._py_date

        __hash__ = property(attrgetter("_py_date.__hash__"))

    @classmethod
    def from_py_date(cls, d: _date, /) -> Date:
        """Create from a :class:`~datetime.date`

        Example
        -------

        >>> Date.from_py_date(date(2021, 1, 2))
        Date(2021-01-02)

        """
        self = _object_new(cls)
        self._py_date = d
        return self

    def add(
        self, years: int = 0, months: int = 0, weeks: int = 0, days: int = 0
    ) -> Date:
        """Add a components to a date.

        Components are added in the order of years, months, weeks, and days.

        Example
        -------

        >>> d = Date(2021, 1, 2)
        >>> d.add(years=1, months=2, days=3)
        Date(2022-03-05)

        >>> Date(2020, 2, 29).add(years=1)
        Date(2021-02-28)

        """
        year_overflow, month_new = divmod(self.month - 1 + months, 12)
        month_new += 1
        year_new = self.year + years + year_overflow
        day_new = min(self.day, monthrange(year_new, month_new)[1])
        return Date.from_py_date(
            _date(year_new, month_new, day_new) + _timedelta(days, weeks=weeks)
        )

    def day_of_week(self) -> int:
        """The day of the week, where 1 is Monday and 7 is Sunday

        Warning
        -------
        This method uses the ISO definition of the week, in contrast to
        the :meth:`~datetime.date.weekday` method.

        Example
        -------

        >>> from whenever import SATURDAY
        >>> Date(2021, 1, 2).day_of_week()
        6
        >>> Date(2021, 1, 2).day_of_week() == SATURDAY
        True

        """
        return self._py_date.isoweekday()


class Duration:
    """A duration consisting of a fixed time: hours, minutes, (micro)seconds

    The inputs are normalized, so 90 minutes becomes 1 hour and 30 minutes,
    for example.

    Examples
    --------

    >>> d = Duration(hours=1, minutes=30)
    Duration(01:30:00)
    >>> d.in_minutes()
    90.0

    """

    __slots__ = ("_total_ms",)

    def __init__(
        self,
        *,
        hours: float = 0,
        minutes: float = 0,
        seconds: float = 0,
        microseconds: int = 0,
    ) -> None:
        assert type(microseconds) is int  # catch this common mistake
        self._total_ms = (
            # Cast individual components to int to avoid floating point errors
            int(hours * 3_600_000_000)
            + int(minutes * 60_000_000)
            + int(seconds * 1_000_000)
            + microseconds
        )

    ZERO: ClassVar[Duration]
    """A duration of zero"""

    def in_hours(self) -> float:
        """The total duration in hours

        Example
        -------

        >>> d = Duration(hours=1, minutes=30)
        >>> d.in_hours()
        1.5

        """
        return self._total_ms / 3_600_000_000

    def in_minutes(self) -> float:
        """The total duration in minutes

        Example
        -------

        >>> d = Duration(hours=1, minutes=30, seconds=30)
        >>> d.in_minutes()
        90.5

        """
        return self._total_ms / 60_000_000

    def in_seconds(self) -> float:
        """The total duration in seconds

        Example
        -------

        >>> d = Duration(minutes=2, seconds=1, microseconds=500_000)
        >>> d.in_seconds()
        121.5

        """
        return self._total_ms / 1_000_000

    def in_microseconds(self) -> int:
        """The total duration in microseconds

        >>> d = Duration(seconds=2, microseconds=50)
        >>> d.in_microseconds()
        2_000_050

        """
        return self._total_ms

    def __eq__(self, other: object) -> bool:
        """Compare for equality

        Example
        -------

        >>> d = Duration(hours=1, minutes=30)
        >>> d == Duration(minutes=90)
        True
        >>> d == Duration(hours=2)
        False

        """
        if not isinstance(other, Duration):
            return NotImplemented
        return self._total_ms == other._total_ms

    def __hash__(self) -> int:
        return hash(self._total_ms)

    def __lt__(self, other: Duration) -> bool:
        if not isinstance(other, Duration):
            return NotImplemented
        return self._total_ms < other._total_ms

    def __le__(self, other: Duration) -> bool:
        if not isinstance(other, Duration):
            return NotImplemented
        return self._total_ms <= other._total_ms

    def __gt__(self, other: Duration) -> bool:
        if not isinstance(other, Duration):
            return NotImplemented
        return self._total_ms > other._total_ms

    def __ge__(self, other: Duration) -> bool:
        if not isinstance(other, Duration):
            return NotImplemented
        return self._total_ms >= other._total_ms

    def __bool__(self) -> bool:
        """True if the duration is non-zero

        Example
        -------

        >>> bool(Duration())
        False
        >>> bool(Duration(minutes=1))
        True

        """
        return bool(self._total_ms)

    def __add__(self, other: Duration) -> Duration:
        """Add two durations together

        Example
        -------

        >>> d = Duration(hours=1, minutes=30)
        >>> d + Duration(minutes=30)
        Duration(02:00:00)

        """
        if not isinstance(other, Duration):
            return NotImplemented
        return Duration(microseconds=self._total_ms + other._total_ms)

    def __sub__(self, other: Duration) -> Duration:
        """Subtract two durations

        Example
        -------

        >>> d = Duration(hours=1, minutes=30)
        >>> d - Duration(minutes=30)
        Duration(01:00:00)

        """
        if not isinstance(other, Duration):
            return NotImplemented
        return Duration(microseconds=self._total_ms - other._total_ms)

    def __mul__(self, other: float) -> Duration:
        """Multiply by a number

        Example
        -------

        >>> d = Duration(hours=1, minutes=30)
        >>> d * 2.5
        Duration(03:45:00)

        """
        if not isinstance(other, (int, float)):
            return NotImplemented
        return Duration(microseconds=int(self._total_ms * other))

    def __neg__(self) -> Duration:
        """Negate the duration

        Example
        -------

        >>> d = Duration(hours=1, minutes=30)
        >>> -d
        Duration(-01:30:00)

        """
        return Duration(microseconds=-self._total_ms)

    @overload
    def __truediv__(self, other: float) -> Duration: ...

    @overload
    def __truediv__(self, other: Duration) -> float: ...

    def __truediv__(self, other: float | Duration) -> Duration | float:
        """Divide by a number or another duration

        Example
        -------

        >>> d = Duration(hours=1, minutes=30)
        >>> d / 2
        Duration(00:45:00)
        >>> d / Duration(minutes=30)
        3.0

        """
        if isinstance(other, Duration):
            return self._total_ms / other._total_ms
        elif isinstance(other, (int, float)):
            return Duration(microseconds=int(self._total_ms / other))
        return NotImplemented

    def __abs__(self) -> Duration:
        """The absolute value of the duration

        Example
        -------

        >>> d = Duration(hours=-1, minutes=-30)
        >>> abs(d)
        Duration(01:30:00)

        """
        return Duration(microseconds=abs(self._total_ms))

    def canonical_format(self) -> str:
        """The duration in canonical format.

        The format is:

        .. code-block:: text

           HH:MM:SS(.ffffff)

        For example:

        .. code-block:: text

           01:24:45.0089

        """
        hrs, mins, secs, ms = abs(self).as_tuple()
        return (
            f"{'-'*(self._total_ms < 0)}{hrs:02}:{mins:02}:{secs:02}"
            + f".{ms:0>6}" * bool(ms)
        )

    @classmethod
    def from_canonical_format(cls, s: str, /) -> Duration:
        """Create from a canonical string representation.

        Inverse of :meth:`canonical_format`

        Example
        -------

        >>> Duration.from_canonical_format("01:30:00")
        Duration(01:30:00)

        Raises
        ------
        InvalidFormat
            If the string does not match this exact format.

        """
        if not (match := _match_duration(s)):
            raise InvalidFormat()
        sign, hours, mins, secs = match.groups()
        return cls(
            microseconds=(-1 if sign == "-" else 1)
            * (
                int(hours) * 3_600_000_000
                + int(mins) * 60_000_000
                + round(float(secs) * 1_000_000)
            )
        )

    __str__ = canonical_format

    def py_timedelta(self) -> _timedelta:
        """Convert to a :class:`~datetime.timedelta`

        Inverse of :meth:`from_py_timedelta`

        Example
        -------

        >>> d = Duration(hours=1, minutes=30)
        >>> d.py_timedelta()
        timedelta(seconds=5400)

        """
        return _timedelta(microseconds=self._total_ms)

    @classmethod
    def from_py_timedelta(cls, td: _timedelta, /) -> Duration:
        """Create from a :class:`~datetime.timedelta`

        Inverse of :meth:`py_timedelta`

        Example
        -------

        >>> Duration.from_py_timedelta(timedelta(seconds=5400))
        Duration(01:30:00)

        """
        return Duration(
            microseconds=td.microseconds,
            seconds=td.seconds,
            hours=td.days * 24,
        )

    def as_period(self) -> Period:
        """Convert to a :class:`Period`

        Example
        -------

        >>> d = Duration(minutes=90)
        >>> d.as_period()
        Period(PT1H30M)

        """
        h, m, s, ms = self.as_tuple()
        return Period(hours=h, minutes=m, seconds=s, microseconds=ms)

    def as_tuple(self) -> tuple[int, int, int, int]:
        """Convert to a tuple of (hours, minutes, seconds, microseconds)

        Example
        -------

        >>> d = Duration(hours=1, minutes=30, microseconds=5_000_090)
        >>> d.as_tuple()
        (1, 30, 5, 90)

        """
        hours, rem = divmod(abs(self._total_ms), 3_600_000_000)
        mins, rem = divmod(rem, 60_000_000)
        secs, ms = divmod(rem, 1_000_000)
        return (
            (hours, mins, secs, ms)
            if self._total_ms >= 0
            else (-hours, -mins, -secs, -ms)
        )

    def __repr__(self) -> str:
        return f"Duration({self})"


Duration.ZERO = Duration()


class Period:
    """A period of time, consisting of years, months, weeks, days, hours,
    minutes, seconds and microseconds.

    The canonical string format is:

    .. code-block:: text

        PnYnMnWnDTnHnMn(.ffffff)S

    For example:

    .. code-block:: text

        P1DT5H30M
        PT3H
        P2M
        P1Y2M-3W4DT5H6M7.0089S

    Note
    ----
    Aside from milliseconds, the fields are not normalized.
    For example, "90 minutes" is not converted to "1 hour and 30 minutes".

    """

    __slots__ = (
        "_years",
        "_months",
        "_weeks",
        "_days",
        "_hours",
        "_minutes",
        "_seconds",
        "_microseconds",
    )

    ZERO: ClassVar[Period]
    """A period of zero"""

    def __init__(
        self,
        *,
        years: int = 0,
        months: int = 0,
        weeks: int = 0,
        days: int = 0,
        hours: int = 0,
        minutes: int = 0,
        seconds: int = 0,
        microseconds: int = 0,
    ) -> None:
        self._years = years
        self._months = months
        self._weeks = weeks
        self._days = days
        self._hours = hours
        self._minutes = minutes
        seconds_extra, self._microseconds = divmod(microseconds, 1_000_000)
        self._seconds = seconds + seconds_extra

    @property
    def years(self) -> int:
        return self._years

    @property
    def months(self) -> int:
        return self._months

    @property
    def weeks(self) -> int:
        return self._weeks

    @property
    def days(self) -> int:
        return self._days

    @property
    def hours(self) -> int:
        return self._hours

    @property
    def minutes(self) -> int:
        return self._minutes

    @property
    def seconds(self) -> int:
        return self._seconds

    @property
    def microseconds(self) -> int:
        return self._microseconds

    def __eq__(self, other: object) -> bool:
        """Compare for equality of all fields

        Note
        ----
        Periods are equal if they have the same values for all fields.
        No normalization is done, so "one minute" is not equal to "60 seconds".

        Example
        -------

        >>> p = Period(hours=1, minutes=30)
        >>> p == Period(days=0, hours=1, minutes=30)
        True
        >>> # same duration, but different field values
        >>> p == Period(minutes=90)
        False
        """
        if not isinstance(other, Period):
            return NotImplemented
        return (
            self._years == other._years
            and self._months == other._months
            and self._weeks == other._weeks
            and self._days == other._days
            and self._hours == other._hours
            and self._minutes == other._minutes
            and self._seconds == other._seconds
            and self._microseconds == other._microseconds
        )

    def __hash__(self) -> int:
        return hash(
            (
                self._years,
                self._months,
                self._weeks,
                self._days,
                self._hours,
                self._minutes,
                self._seconds,
                self._microseconds,
            )
        )

    def __bool__(self) -> bool:
        """True if any field is non-zero

        Example
        -------

        >>> bool(Period())
        False
        >>> bool(Period(hours=-1))
        True

        """
        return bool(
            self._years
            or self._months
            or self._weeks
            or self._days
            or self._hours
            or self._minutes
            or self._seconds
            or self._microseconds
        )

    def canonical_format(self) -> str:
        """The period in canonical format.

        Example
        -------

        >>> p = Period(hours=1, minutes=30)
        >>> p.canonical_format()
        'PT1H30M'

        """
        if self._microseconds:
            seconds = (
                f"{self._seconds + self._microseconds / 1_000_000:f}".rstrip(
                    "0"
                )
            )
        else:
            seconds = str(self._seconds)
        date = (
            f"{self._years}Y" * bool(self._years),
            f"{self._months}M" * bool(self._months),
            f"{self._weeks}W" * bool(self._weeks),
            f"{self._days}D" * bool(self._days),
        )
        time = (
            f"{self._hours}H" * bool(self._hours),
            f"{self._minutes}M" * bool(self._minutes),
            f"{seconds}S" * bool(self._seconds or self._microseconds),
        )
        return "P" + (
            "".join((*date, "T" if any(time) else "", *time)) or "0D"
        )

    @classmethod
    def from_canonical_format(cls, s: str, /) -> Period:
        """Create from a canonical string representation.

        Inverse of :meth:`canonical_format`

        Example
        -------

        >>> Period.from_canonical_format("P1Y2M-3W4DT5H6M7.0089S")
        Period(P1Y2M-3W4DT5H6M7.0089S)

        Raises
        ------
        InvalidFormat
            If the string does not match this exact format.

        """
        if not (match := _match_period(s)) or s == "P":
            raise InvalidFormat()
        years, months, weeks, days, hours, minutes, seconds = match.groups()
        return cls(
            years=int(years or 0),
            months=int(months or 0),
            weeks=int(weeks or 0),
            days=int(days or 0),
            hours=int(hours or 0),
            minutes=int(minutes or 0),
            microseconds=int(float(seconds or "0") * 1_000_000),
        )

    __str__ = canonical_format

    if TYPE_CHECKING:

        def replace(
            self,
            *,
            years: int | NOT_SET = NOT_SET(),
            months: int | NOT_SET = NOT_SET(),
            weeks: int | NOT_SET = NOT_SET(),
            days: int | NOT_SET = NOT_SET(),
            hours: int | NOT_SET = NOT_SET(),
            minutes: int | NOT_SET = NOT_SET(),
            seconds: int | NOT_SET = NOT_SET(),
            microseconds: int | NOT_SET = NOT_SET(),
        ) -> Period: ...

    else:

        def replace(self, **kwargs) -> Period:
            """Create a new instance with the given fields replaced.

            Example
            -------

            >>> p = Period(years=1, months=2)
            >>> p.replace(years=2)
            Period(P2Y2M)

            """
            return Period(
                years=kwargs.get("years", self._years),
                months=kwargs.get("months", self._months),
                weeks=kwargs.get("weeks", self._weeks),
                days=kwargs.get("days", self._days),
                hours=kwargs.get("hours", self._hours),
                minutes=kwargs.get("minutes", self._minutes),
                seconds=kwargs.get("seconds", self._seconds),
                microseconds=kwargs.get("microseconds", self._microseconds),
            )

    def __repr__(self) -> str:
        return f"Period({self})"

    def __neg__(self) -> Period:
        """Negate each field of the period

        Example
        -------

        >>> p = Period(weeks=2, days=-3, hours=10)
        >>> -p
        Period(P-2W3DT-10H)

        """
        return Period(
            years=-self._years,
            months=-self._months,
            weeks=-self._weeks,
            days=-self._days,
            hours=-self._hours,
            minutes=-self._minutes,
            seconds=-self._seconds,
            microseconds=-self._microseconds,
        )

    def __mul__(self, other: int) -> Period:
        """Multiply each field by a round number

        Example
        -------

        >>> p = Period(weeks=2, hours=1, minutes=30)
        >>> p * 2
        Period(P4WT2H60M)

        """
        if not isinstance(other, int):
            return NotImplemented
        overflow_secs, micros = divmod(self._microseconds * other, 1_000_000)
        return Period(
            years=self._years * other,
            months=self._months * other,
            weeks=self._weeks * other,
            days=self._days * other,
            hours=self._hours * other,
            minutes=self._minutes * other,
            seconds=self._seconds * other + overflow_secs,
            microseconds=micros,
        )

    def __add__(self, other: Period | Duration) -> Period:
        """Add the fields of another period to this one

        Example
        -------

        >>> p = Period(weeks=2, hours=1, minutes=30)
        >>> p + Period(days=-4, minutes=15)
        Period(P2W-4DT1H45M)

        """

        if isinstance(other, Period):
            return Period(
                years=self._years + other._years,
                months=self._months + other._months,
                weeks=self._weeks + other._weeks,
                days=self._days + other._days,
                hours=self._hours + other._hours,
                minutes=self._minutes + other._minutes,
                seconds=self._seconds + other._seconds,
                microseconds=self._microseconds + other._microseconds,
            )
        elif isinstance(other, Duration):
            hrs, mins, secs, ms = other.as_tuple()
            return self.replace(
                hours=self._hours + hrs,
                minutes=self._minutes + mins,
                seconds=self._seconds + secs,
                microseconds=self._microseconds + ms,
            )

        else:
            return NotImplemented

    def __radd__(self, other: Duration) -> Period:
        if isinstance(other, Duration):
            return self + other
        return NotImplemented

    def __sub__(self, other: Period | Duration) -> Period:
        """Subtract the fields of another period from this one

        Example
        -------

        >>> p = Period(weeks=2, hours=1, minutes=30)
        >>> p - Period(days=-4, minutes=15)
        Period(P2W4DT1H15M)
        >>> p - Duration(minutes=15)
        Period(P2WT1H-15M)

        """
        if isinstance(other, Period):
            overflow_secs, micros = divmod(
                self._microseconds - other._microseconds, 1_000_000
            )
            return Period(
                years=self._years - other._years,
                months=self._months - other._months,
                weeks=self._weeks - other._weeks,
                days=self._days - other._days,
                hours=self._hours - other._hours,
                minutes=self._minutes - other._minutes,
                seconds=self._seconds - other._seconds + overflow_secs,
                microseconds=micros,
            )
        elif isinstance(other, Duration):
            return self + (-other)
        else:
            return NotImplemented

    def time_component(self) -> Duration:
        """The time component of the period

        Example
        -------

        >>> p = Period(days=30, minutes=90)
        >>> p.time_component()
        Duration(01:30:00)

        """
        return Duration(
            hours=self._hours,
            minutes=self._minutes,
            seconds=self._seconds,
            microseconds=self._microseconds,
        )

    def as_tuple(self) -> tuple[int, int, int, int, int, int, int, int]:
        """Convert to a tuple of (years, months, weeks, days, hours, minutes,
        seconds, microseconds)

        Example
        -------

        >>> p = Period(weeks=2, hours=1, minutes=30)
        >>> p.as_tuple()
        (0, 0, 2, 0, 1, 30, 0, 0)

        """
        return (
            self._years,
            self._months,
            self._weeks,
            self._days,
            self._hours,
            self._minutes,
            self._seconds,
            self._microseconds,
        )


Period.ZERO = Period()


_TDateTime = TypeVar("_TDateTime", bound="DateTime")


class DateTime(ABC):
    """Abstract base class for all datetime types"""

    __slots__ = ("_py_dt", "__weakref__")
    _py_dt: _datetime

    if TYPE_CHECKING or SPHINX_BUILD:

        @property
        def year(self) -> int: ...

        @property
        def month(self) -> int: ...

        @property
        def day(self) -> int: ...

        @property
        def hour(self) -> int: ...

        @property
        def minute(self) -> int: ...

        @property
        def second(self) -> int: ...

        @property
        def microsecond(self) -> int: ...

    else:
        # Defining properties this way is faster than declaring a `def`,
        # but the type checker doesn't like it.
        year = property(attrgetter("_py_dt.year"))
        month = property(attrgetter("_py_dt.month"))
        day = property(attrgetter("_py_dt.day"))
        hour = property(attrgetter("_py_dt.hour"))
        minute = property(attrgetter("_py_dt.minute"))
        second = property(attrgetter("_py_dt.second"))
        microsecond = property(attrgetter("_py_dt.microsecond"))

    def date(self) -> Date:
        """The date part of the datetime

        Example
        -------

        >>> d = UTCDateTime(2021, 1, 2, 3, 4, 5)
        >>> d.date()
        Date(2021-01-02)

        """
        return Date.from_py_date(self._py_dt.date())

    @abstractmethod
    def canonical_format(self, sep: Literal[" ", "T"] = "T") -> str:
        """Format as the canonical string representation. Each
        subclass has a different format. See the documentation for
        the subclass for more information.
        Inverse of :meth:`from_canonical_format`.
        """

    def __str__(self) -> str:
        """Same as :meth:`canonical_format` with ``sep=" "``"""
        return self.canonical_format(" ")

    @classmethod
    @abstractmethod
    def from_canonical_format(cls: type[_TDateTime], s: str, /) -> _TDateTime:
        """Create an instance from the canonical string representation,
        which is different for each subclass.

        Inverse of :meth:`__str__` and :meth:`canonical_format`.

        Note
        ----
        ``T`` may be replaced with a single space

        Raises
        ------
        InvalidFormat
            If the string does not match this exact format.
        """

    @classmethod
    @abstractmethod
    def from_py_datetime(cls: type[_TDateTime], d: _datetime, /) -> _TDateTime:
        """Create an instance from a :class:`~datetime.datetime` object.
        Inverse of :meth:`py_datetime`.

        Note
        ----
        The datetime is checked for validity, raising similar exceptions
        to the constructor.
        ``ValueError`` is raised if the datetime doesn't have the correct
        tzinfo matching the class. For example, :class:`ZonedDateTime`
        requires a :class:`~zoneinfo.ZoneInfo` tzinfo.

        Warning
        -------
        No exceptions are raised if the datetime is ambiguous.
        Its ``fold`` attribute is consulted to determine which
        the behavior on ambiguity.
        """

    def py_datetime(self) -> _datetime:
        """Get the underlying :class:`~datetime.datetime` object"""
        return self._py_dt

    if not TYPE_CHECKING and SPHINX_BUILD:  # pragma: no cover

        @abstractmethod
        def replace(self: _TDateTime, /, **kwargs) -> _TDateTime:
            """Construct a new instance with the given fields replaced.

            Arguments are the same as the constructor,
            but only keyword arguments are allowed.

            Note
            ----
            If you need to shift the datetime by a duration,
            use the addition and subtraction operators instead.
            These account for daylight saving time and other complications.

            Warning
            -------
            The same exceptions as the constructor may be raised.
            For local and zoned datetimes,
            you will need to pass ``disambiguate=`` to resolve ambiguities.

            Example
            -------

            >>> d = UTCDateTime(2020, 8, 15, 23, 12)
            >>> d.replace(year=2021)
            UTCDateTime(2021-08-15T23:12:00)

            >>> z = ZonedDateTime(2020, 8, 15, 23, 12, tz="Europe/London")
            >>> z.replace(year=2021, disambiguate="later")
            ZonedDateTime(2021-08-15T23:12:00+01:00)
            """

    @classmethod
    def _from_py_unchecked(
        cls: type[_TDateTime], d: _datetime, /
    ) -> _TDateTime:
        self = _object_new(cls)
        self._py_dt = d
        return self

    # We don't need to copy, because it's immutable
    def __copy__(self: _TDateTime) -> _TDateTime:
        return self

    def __deepcopy__(self: _TDateTime, _: object) -> _TDateTime:
        return self


class AwareDateTime(DateTime):
    """Abstract base class for all aware datetime types (:class:`UTCDateTime`,
    :class:`OffsetDateTime`, :class:`ZonedDateTime` and :class:`LocalDateTime`).
    """

    __slots__ = ()

    if TYPE_CHECKING or SPHINX_BUILD:

        def timestamp(self) -> float:
            """The UNIX timestamp for this datetime.

            Each subclass also defines an inverse ``from_timestamp`` method,
            which may require additional arguments.

            Example
            -------

            >>> UTCDateTime(1970, 1, 1).timestamp()
            0.0

            >>> ts = 1_123_000_000
            >>> UTCDateTime.from_timestamp(ts).timestamp() == ts
            True
            """
            return self._py_dt.timestamp()

    else:
        timestamp = property(attrgetter("_py_dt.timestamp"))

    @property
    @abstractmethod
    def offset(self) -> Duration:
        """The UTC offset of the datetime"""

    @abstractmethod
    def as_utc(self) -> UTCDateTime:
        """Convert into an equivalent UTCDateTime.
        The result will always represent the same moment in time.
        """

    @overload
    @abstractmethod
    def as_offset(self, /) -> OffsetDateTime: ...

    @overload
    @abstractmethod
    def as_offset(self, offset: Duration, /) -> OffsetDateTime: ...

    @abstractmethod
    def as_offset(self, offset: Duration | None = None, /) -> OffsetDateTime:
        """Convert into an equivalent OffsetDateTime.
        Optionally, specify the offset to use.
        The result will always represent the same moment in time.
        """

    def as_zoned(self, tz: str, /) -> ZonedDateTime:
        """Convert into an equivalent ZonedDateTime.
        The result will always represent the same moment in time.

        Raises
        ------
        ~zoneinfo.ZoneInfoNotFoundError
            If the timezone ID is not found in the IANA database.
        """
        return ZonedDateTime._from_py_unchecked(
            self._py_dt.astimezone(ZoneInfo(tz))
        )

    def as_local(self) -> LocalDateTime:
        """Convert into a an equivalent LocalDateTime.
        The result will always represent the same moment in time.
        """
        return LocalDateTime._from_py_unchecked(self._py_dt.astimezone())

    def naive(self) -> NaiveDateTime:
        """Convert into a naive datetime, dropping all timezone information

        As an inverse, :class:`NaiveDateTime` has methods
        :meth:`~NaiveDateTime.assume_utc`, :meth:`~NaiveDateTime.assume_offset`
        , :meth:`~NaiveDateTime.assume_zoned`, and :meth:`~NaiveDateTime.assume_local`
        which may require additional arguments.
        """
        return NaiveDateTime._from_py_unchecked(
            self._py_dt.replace(tzinfo=None)
        )

    # Hiding __eq__ from mypy ensures that --strict-equality works
    if not TYPE_CHECKING:  # pragma: no branch

        @abstractmethod
        def __eq__(self, other: object) -> bool:
            """Check if two datetimes represent at the same moment in time

            ``a == b`` is equivalent to ``a.as_utc() == b.as_utc()``

            Note
            ----

            If you want to exactly compare the values on their values
            instead of UTC equivalence, use :meth:`exact_eq` instead.

            Example
            -------

            >>> UTCDateTime(2020, 8, 15, hour=23) == UTCDateTime(2020, 8, 15, hour=23)
            True
            >>> OffsetDateTime(2020, 8, 15, hour=23, offset=hours(1)) == (
            ...     ZonedDateTime(2020, 8, 15, hour=18, tz="America/New_York")
            ... )
            True
            """

    @abstractmethod
    def __lt__(self, other: AwareDateTime) -> bool:
        """Compare two datetimes by when they occur in time

        ``a < b`` is equivalent to ``a.as_utc() < b.as_utc()``

        Example
        -------

        >>> OffsetDateTime(2020, 8, 15, hour=23, offset=hours(8)) < (
        ...     ZoneDateTime(2020, 8, 15, hour=20, tz="Europe/Amsterdam")
        ... )
        True
        """

    @abstractmethod
    def __le__(self, other: AwareDateTime) -> bool:
        """Compare two datetimes by when they occur in time

        ``a <= b`` is equivalent to ``a.as_utc() <= b.as_utc()``

        Example
        -------

        >>> OffsetDateTime(2020, 8, 15, hour=23, offset=hours(8)) <= (
        ...     ZoneDateTime(2020, 8, 15, hour=20, tz="Europe/Amsterdam")
        ... )
        True
        """

    @abstractmethod
    def __gt__(self, other: AwareDateTime) -> bool:
        """Compare two datetimes by when they occur in time

        ``a > b`` is equivalent to ``a.as_utc() > b.as_utc()``

        Example
        -------

        >>> OffsetDateTime(2020, 8, 15, hour=19, offset=hours(-8)) > (
        ...     ZoneDateTime(2020, 8, 15, hour=20, tz="Europe/Amsterdam")
        ... )
        True
        """

    @abstractmethod
    def __ge__(self, other: AwareDateTime) -> bool:
        """Compare two datetimes by when they occur in time

        ``a >= b`` is equivalent to ``a.as_utc() >= b.as_utc()``

        Example
        -------

        >>> OffsetDateTime(2020, 8, 15, hour=19, offset=hours(-8)) >= (
        ...     ZoneDateTime(2020, 8, 15, hour=20, tz="Europe/Amsterdam")
        ... )
        True
        """

    # Mypy doesn't like overloaded overrides, but we'd like to document
    # this 'abstract' behaviour anyway
    if not TYPE_CHECKING:  # pragma: no branch

        @abstractmethod
        def __sub__(self, other: AwareDateTime) -> Duration:
            """Calculate the duration between two datetimes

            ``a - b`` is equivalent to ``a.as_utc() - b.as_utc()``

            Example
            -------

            >>> d = UTCDateTime(2020, 8, 15, hour=23)
            >>> d - ZonedDateTime(2020, 8, 15, hour=20, tz="Europe/Amsterdam")
            Duration(05:00:00)
            """

    @abstractmethod
    def exact_eq(self: _TDateTime, other: _TDateTime, /) -> bool:
        """Compare objects by their values (instead of their UTC equivalence).
        Different types are never equal.

        Note
        ----
        If ``a.exact_eq(b)`` is true, then
        ``a == b`` is also true, but the converse is not necessarily true.

        Examples
        --------

        >>> a = OffsetDateTime(2020, 8, 15, hour=12, offset=hours(1))
        >>> b = OffsetDateTime(2020, 8, 15, hour=13, offset=hours(2))
        >>> a == b
        True  # equivalent UTC times
        >>> a.exact_eq(b)
        False  # different values (hour and offset)
        """


class UTCDateTime(AwareDateTime):
    """A UTC-only datetime. Useful for representing moments in time
    in an unambiguous way.

    In >95% of cases, you should use this class over the others. The other
    classes are most often useful at the boundaries of your application.

    Example
    -------

    >>> from whenever import UTCDateTime
    >>> py311_release_livestream = UTCDateTime(2022, 10, 24, hour=17)

    Note
    ----

    The canonical string format is:

    .. code-block:: text

        YYYY-MM-DDTHH:MM:SS(.ffffff)Z

    This format is both RFC 3339 and ISO 8601 compliant.

    Note
    ----

    The underlying :class:`~datetime.datetime` object is always timezone-aware
    and has a fixed :attr:`~datetime.UTC` tzinfo.
    """

    __slots__ = ()

    def __init__(
        self,
        year: int,
        month: int,
        day: int,
        hour: int = 0,
        minute: int = 0,
        second: int = 0,
        microsecond: int = 0,
    ) -> None:
        self._py_dt = _datetime(
            year, month, day, hour, minute, second, microsecond, _UTC
        )

    @classmethod
    def now(cls) -> UTCDateTime:
        """Create an instance from the current time"""
        return cls._from_py_unchecked(_datetime.now(_UTC))

    def canonical_format(self, sep: Literal[" ", "T"] = "T") -> str:
        return f"{self._py_dt.isoformat(sep)[:-6]}Z"

    @classmethod
    def from_canonical_format(cls, s: str, /) -> UTCDateTime:
        if not _match_utc_str(s):
            raise InvalidFormat()
        return cls._from_py_unchecked(_fromisoformat_utc(s))

    @classmethod
    def from_timestamp(cls, i: float, /) -> UTCDateTime:
        """Create an instance from a UNIX timestamp.
        The inverse of :meth:`~AwareDateTime.timestamp`.

        Example
        -------

        >>> UTCDateTime.from_timestamp(0) == UTCDateTime(1970, 1, 1)
        >>> d = UTCDateTime.from_timestamp(1_123_000_000.45)
        UTCDateTime(2004-08-02T16:26:40.45Z)
        >>> UTCDateTime.from_timestamp(d.timestamp()) == d
        True
        """
        return cls._from_py_unchecked(_fromtimestamp(i, _UTC))

    @classmethod
    def from_py_datetime(cls, d: _datetime, /) -> UTCDateTime:
        if d.tzinfo is not _UTC:
            raise ValueError(
                "Can only create UTCDateTime from UTC datetime, "
                f"got datetime with tzinfo={d.tzinfo!r}"
            )
        return cls._from_py_unchecked(d)

    offset = Duration.ZERO

    if TYPE_CHECKING:  # pragma: no branch
        # We could have used typing.Unpack, but that's only available
        # in Python 3.11+ or with typing_extensions.
        def replace(
            self,
            *,
            year: int | NOT_SET = NOT_SET(),
            month: int | NOT_SET = NOT_SET(),
            day: int | NOT_SET = NOT_SET(),
            hour: int | NOT_SET = NOT_SET(),
            minute: int | NOT_SET = NOT_SET(),
            second: int | NOT_SET = NOT_SET(),
            microsecond: int | NOT_SET = NOT_SET(),
        ) -> UTCDateTime: ...

    else:

        def replace(self, /, **kwargs) -> UTCDateTime:
            if not _no_tzinfo_or_fold(kwargs):
                raise TypeError("tzinfo and fold are not allowed arguments")
            return self._from_py_unchecked(self._py_dt.replace(**kwargs))

        # Defining properties this way is faster than declaring a `def`,
        # but the type checker doesn't like it.
        __hash__ = property(attrgetter("_py_dt.__hash__"))

        # Hiding __eq__ from mypy ensures that --strict-equality works
        def __eq__(self, other: object) -> bool:
            if not isinstance(
                other, (UTCDateTime, OffsetDateTime, LocalDateTime)
            ):
                return NotImplemented
            return self._py_dt == other._py_dt

    min: ClassVar[UTCDateTime]
    max: ClassVar[UTCDateTime]

    def exact_eq(self, other: UTCDateTime, /) -> bool:
        return self._py_dt == other._py_dt

    def __lt__(self, other: AwareDateTime) -> bool:
        if not isinstance(other, (UTCDateTime, OffsetDateTime, LocalDateTime)):
            return NotImplemented
        return self._py_dt < other._py_dt

    def __le__(self, other: AwareDateTime) -> bool:
        if not isinstance(other, (UTCDateTime, OffsetDateTime, LocalDateTime)):
            return NotImplemented
        return self._py_dt <= other._py_dt

    def __gt__(self, other: AwareDateTime) -> bool:
        if not isinstance(other, (UTCDateTime, OffsetDateTime, LocalDateTime)):
            return NotImplemented
        return self._py_dt > other._py_dt

    def __ge__(self, other: AwareDateTime) -> bool:
        if not isinstance(other, (UTCDateTime, OffsetDateTime, LocalDateTime)):
            return NotImplemented
        return self._py_dt >= other._py_dt

    def __add__(self, delta: Duration | Period) -> UTCDateTime:
        """Add a time amount to this datetime

        Example
        -------

        >>> d = UTCDateTime(2020, 8, 15, hour=23, minute=12)
        >>> d + Duration(hours=24, seconds=5)
        UTCDateTime(2020-08-16 23:12:05Z)

        >>> d + Period(years=1, days=2)
        UTCDateTime(2021-08-17 23:12:00Z)
        """
        if isinstance(delta, Duration):
            return self._from_py_unchecked(self._py_dt + delta.py_timedelta())
        elif isinstance(delta, Period):
            years, months, weeks, days, *_ = delta.as_tuple()
            date = self.date().add(years, months, weeks, days)
            return (
                self.replace(year=date.year, month=date.month, day=date.day)
                + delta.time_component()
            )
        return NotImplemented

    if TYPE_CHECKING:

        @overload
        def __sub__(self, other: AwareDateTime) -> Duration: ...

        @overload
        def __sub__(self, other: Duration | Period) -> UTCDateTime: ...

        def __sub__(
            self, other: AwareDateTime | Duration | Period
        ) -> UTCDateTime | Duration: ...

    else:

        def __sub__(
            self, other: Duration | Period | AwareDateTime
        ) -> UTCDateTime | Duration:
            """Subtract another datetime or time amount

            Example
            -------

            >>> d = UTCDateTime(2020, 8, 15, hour=23, minute=12)
            >>> d - Duration(hours=24, seconds=5)
            UTCDateTime(2020-08-14 23:11:55Z)
            >>> d - UTCDateTime(2020, 8, 14)
            Duration(47:12:00)
            >>> d - Period(months=2, days=3, minutes=5)
            UTCDateTime(2020-06-12 23:06:00Z)
            """
            if isinstance(other, AwareDateTime):
                return Duration.from_py_timedelta(self._py_dt - other._py_dt)
            elif isinstance(other, Duration):
                return self._from_py_unchecked(
                    self._py_dt - other.py_timedelta()
                )
            elif isinstance(other, Period):
                return self + -other
            return NotImplemented

    def as_utc(self) -> UTCDateTime:
        return self

    @overload
    def as_offset(self, /) -> OffsetDateTime: ...

    @overload
    def as_offset(self, offset: Duration, /) -> OffsetDateTime: ...

    def as_offset(self, offset: Duration | None = None, /) -> OffsetDateTime:
        return OffsetDateTime._from_py_unchecked(
            self._py_dt.astimezone(
                _timezone(offset.py_timedelta()) if offset else _zero_timezone
            )
        )

    @classmethod
    def strptime(cls, s: str, /, fmt: str) -> UTCDateTime:
        """Simple alias for
        ``UTCDateTime.from_py_datetime(datetime.strptime(s, fmt))``

        Example
        -------

        >>> UTCDateTime.strptime("2020-08-15+0000", "%Y-%m-%d%z")
        UTCDateTime(2020-08-15 00:00:00Z)
        >>> UTCDateTime.strptime("2020-08-15", "%Y-%m-%d")
        UTCDateTime(2020-08-15 00:00:00Z)

        Note
        ----
        The parsed ``tzinfo`` must be either :attr:`datetime.UTC`
        or ``None`` (in which case it's set to :attr:`datetime.UTC`).

        """
        parsed = _datetime.strptime(s, fmt)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=_UTC)
        elif parsed.tzinfo is not _UTC:
            raise ValueError(
                "Parsed datetime must have tzinfo=UTC or None, "
                f"got {parsed.tzinfo!r}"
            )
        return cls._from_py_unchecked(parsed)

    def rfc2822(self) -> str:
        """Format as an RFC 2822 string.

        The inverse of :meth:`from_rfc2822`.

        Example
        -------

        >>> UTCDateTime(2020, 8, 15, hour=23, minute=12).rfc2822()
        "Sat, 15 Aug 2020 23:12:00 GMT"
        """
        return format_datetime(self._py_dt, usegmt=True)

    @classmethod
    def from_rfc2822(cls, s: str, /) -> UTCDateTime:
        """Parse a UTC datetime in RFC 2822 format.

        The inverse of :meth:`rfc2822`.

        Example
        -------

        >>> UTCDateTime.from_rfc2822("Sat, 15 Aug 2020 23:12:00 GMT")
        UTCDateTime(2020-08-15 23:12:00Z)

        >>> # also valid:
        >>> UTCDateTime.from_rfc2822("Sat, 15 Aug 2020 23:12:00 +0000")
        >>> UTCDateTime.from_rfc2822("Sat, 15 Aug 2020 23:12:00 UT")

        >>> # Error: nonzero offset. Use OffsetDateTime.from_rfc2822() instead
        >>> UTCDateTime.from_rfc2822("Sat, 15 Aug 2020 23:12:00 +0200")


        Warning
        -------
        * Nonzero offsets will not be implicitly converted to UTC.
          Use :meth:`OffsetDateTime.from_rfc2822` if you'd like to
          parse an RFC 2822 string with a nonzero offset.
        * The offset ``-0000`` has special meaning in RFC 2822,
          and is not allowed here.
        """
        parsed = parsedate_to_datetime(s)
        # Nested ifs to keep happy path fast
        if parsed.tzinfo is not _UTC:
            if parsed.tzinfo is None:
                raise ValueError(
                    "RFC 2822 string with -0000 offset cannot be parsed as UTC"
                )
            raise ValueError(
                "RFC 2822 string can't have nonzero offset to be parsed as UTC"
            )
        return cls._from_py_unchecked(parsedate_to_datetime(s))

    def rfc3339(self) -> str:
        """Format as an RFC 3339 string

        For UTCDateTime, equivalent to :meth:`~DateTime.canonical_format`.
        Inverse of :meth:`from_rfc3339`.

        Example
        -------

        >>> UTCDateTime(2020, 8, 15, hour=23, minute=12).rfc3339()
        "2020-08-15T23:12:00Z"
        """
        return f"{self._py_dt.isoformat()[:-6]}Z"

    @classmethod
    def from_rfc3339(cls, s: str, /) -> UTCDateTime:
        """Parse a UTC datetime in RFC 3339 format.

        Inverse of :meth:`rfc3339`.

        Example
        -------

        >>> UTCDateTime.from_rfc3339("2020-08-15T23:12:00Z")
        UTCDateTime(2020-08-15 23:12:00Z)
        >>>
        >>> # also valid:
        >>> UTCDateTime.from_rfc3339("2020-08-15T23:12:00+00:00")
        >>> UTCDateTime.from_rfc3339("2020-08-15_23:12:00.34Z")
        >>> UTCDateTime.from_rfc3339("2020-08-15t23:12:00z")
        >>>
        >>> # not valid (nonzero offset):
        >>> UTCDateTime.from_rfc3339("2020-08-15T23:12:00+02:00")

        Warning
        -------
        Nonzero offsets will not be implicitly converted to UTC.
        Use :meth:`OffsetDateTime.from_rfc3339` if you'd like to
        parse an RFC 3339 string with a nonzero offset.
        """
        return cls._from_py_unchecked(_parse_utc_rfc3339(s))

    def __repr__(self) -> str:
        return f"UTCDateTime({self})"

    # a custom pickle implementation with a smaller payload
    def __reduce__(self) -> tuple[object, ...]:
        return (
            _unpkl_utc,
            self._py_dt.timetuple()[:6] + (self._py_dt.microsecond,),
        )


# A separate unpickling function allows us to make backwards-compatible changes
# to the pickling format in the future
@no_type_check
def _unpkl_utc(*args) -> UTCDateTime:
    return UTCDateTime(*args)


class OffsetDateTime(AwareDateTime):
    """A datetime with a fixed UTC offset.
    Useful for representing the local time at a specific location.

    Example
    -------

    >>> # 9 AM in Salt Lake City, with the UTC offset at the time
    >>> pycon23_start = OffsetDateTime(2023, 4, 21, hour=9, offset=-6)
    OffsetDateTime(2023-04-21 09:00:00-06:00)

    Note
    ----

    The canonical string format is:

    .. code-block:: text

        YYYY-MM-DDTHH:MM:SS(.ffffff)±HH:MM(:SS(.ffffff))

    For example:

    .. code-block:: text

        2020-08-15T12:08:30+01:00

    This format is both RFC 3339 and ISO 8601 compliant.

    Note
    ----

    The underlying :class:`~datetime.datetime` object is always timezone-aware
    and has a fixed :class:`datetime.timezone` tzinfo.
    """

    __slots__ = ()

    def __init__(
        self,
        year: int,
        month: int,
        day: int,
        hour: int = 0,
        minute: int = 0,
        second: int = 0,
        microsecond: int = 0,
        *,
        offset: int | Duration,
    ) -> None:
        self._py_dt = _datetime(
            year,
            month,
            day,
            hour,
            minute,
            second,
            microsecond,
            _timezone(
                _timedelta(hours=offset)
                if isinstance(offset, int)
                else offset.py_timedelta()
            ),
        )

    @classmethod
    def now(cls, offset: Duration) -> OffsetDateTime:
        """Create an instance at the current time with the given offset"""
        return cls._from_py_unchecked(
            _datetime.now(_timezone(offset.py_timedelta()))
        )

    def canonical_format(self, sep: Literal[" ", "T"] = "T") -> str:
        return self._py_dt.isoformat(sep)

    @classmethod
    def from_canonical_format(cls, s: str, /) -> OffsetDateTime:
        if not _match_offset_str(s):
            raise InvalidFormat()
        return cls._from_py_unchecked(_fromisoformat(s))

    @classmethod
    def from_timestamp(cls, i: float, /, offset: Duration) -> OffsetDateTime:
        """Create a OffsetDateTime from a UNIX timestamp.
        The inverse of :meth:`~AwareDateTime.timestamp`.

        Example
        -------

        >>> OffsetDateTime.from_timestamp(0, offset=hours(3))
        OffsetDateTime(1970-01-01 03:00:00+03:00)
        >>>d = OffsetDateTime.from_timestamp(1_123_000_000.45, offset=hours(-2))
        OffsetDateTime(2004-08-02 14:26:40.45-02:00)
        >>> OffsetDateTime.from_timestamp(d.timestamp(), d.offset) == d
        True
        """
        return cls._from_py_unchecked(
            _fromtimestamp(i, _timezone(offset.py_timedelta()))
        )

    @classmethod
    def from_py_datetime(cls, d: _datetime, /) -> OffsetDateTime:
        if not isinstance(d.tzinfo, _timezone):
            raise ValueError(
                "Datetime's tzinfo is not a datetime.timezone, "
                f"got tzinfo={d.tzinfo!r}"
            )
        return cls._from_py_unchecked(d)

    if TYPE_CHECKING:
        # We could have used typing.Unpack, but that's only available
        # in Python 3.11+ or with typing_extensions.
        def replace(
            self,
            *,
            year: int | NOT_SET = NOT_SET(),
            month: int | NOT_SET = NOT_SET(),
            day: int | NOT_SET = NOT_SET(),
            hour: int | NOT_SET = NOT_SET(),
            minute: int | NOT_SET = NOT_SET(),
            second: int | NOT_SET = NOT_SET(),
            microsecond: int | NOT_SET = NOT_SET(),
            offset: Duration | NOT_SET = NOT_SET(),
        ) -> OffsetDateTime: ...

    else:

        def replace(self, /, **kwargs) -> OffsetDateTime:
            if not _no_tzinfo_or_fold(kwargs):
                raise TypeError("tzinfo and fold are not allowed arguments")
            try:
                kwargs["tzinfo"] = _timezone(
                    kwargs.pop("offset").py_timedelta()
                )
            except KeyError:
                pass
            return self._from_py_unchecked(self._py_dt.replace(**kwargs))

        __hash__ = property(attrgetter("_py_dt.__hash__"))

        # Hiding __eq__ from mypy ensures that --strict-equality works
        def __eq__(self, other: object) -> bool:
            if not isinstance(
                other, (UTCDateTime, OffsetDateTime, LocalDateTime)
            ):
                return NotImplemented
            return self._py_dt == other._py_dt

    @property
    def offset(self) -> Duration:
        # We know that offset is never None, because we set it in __init__
        return Duration.from_py_timedelta(self._py_dt.utcoffset())  # type: ignore[arg-type]

    def exact_eq(self, other: OffsetDateTime, /) -> bool:
        # FUTURE: there's probably a faster way to do this
        return self == other and self.offset == other.offset

    def __lt__(self, other: AwareDateTime) -> bool:
        if not isinstance(other, (UTCDateTime, OffsetDateTime, LocalDateTime)):
            return NotImplemented
        return self._py_dt < other._py_dt

    def __le__(self, other: AwareDateTime) -> bool:
        if not isinstance(other, (UTCDateTime, OffsetDateTime, LocalDateTime)):
            return NotImplemented
        return self._py_dt <= other._py_dt

    def __gt__(self, other: AwareDateTime) -> bool:
        if not isinstance(other, (UTCDateTime, OffsetDateTime, LocalDateTime)):
            return NotImplemented
        return self._py_dt > other._py_dt

    def __ge__(self, other: AwareDateTime) -> bool:
        if not isinstance(other, (UTCDateTime, OffsetDateTime, LocalDateTime)):
            return NotImplemented
        return self._py_dt >= other._py_dt

    def __sub__(self, other: AwareDateTime) -> Duration:
        """Subtract another datetime to get the duration between them

        Example
        -------

        >>> d = UTCDateTime(2020, 8, 15, 23, 12)
        >>> d - Duration(hours=28, seconds=5)
        UTCDateTime(2020-08-14 19:11:55Z)

        >>> d - OffsetDateTime(2020, 8, 15, offset=hours(-5))
        Duration(18:12:00)
        """
        if isinstance(other, AwareDateTime):
            return Duration.from_py_timedelta(self._py_dt - other._py_dt)
        return NotImplemented

    def as_utc(self) -> UTCDateTime:
        return UTCDateTime._from_py_unchecked(self._py_dt.astimezone(_UTC))

    @overload
    def as_offset(self, /) -> OffsetDateTime: ...

    @overload
    def as_offset(self, offset: Duration, /) -> OffsetDateTime: ...

    def as_offset(self, offset: Duration | None = None, /) -> OffsetDateTime:
        return (
            self
            if offset is None
            else self._from_py_unchecked(
                self._py_dt.astimezone(_timezone(offset.py_timedelta()))
            )
        )

    @classmethod
    def strptime(cls, s: str, /, fmt: str) -> OffsetDateTime:
        """Simple alias for
        ``OffsetDateTime.from_py_datetime(datetime.strptime(s, fmt))``

        Example
        -------

        >>> OffsetDateTime.strptime("2020-08-15+0200", "%Y-%m-%d%z")
        OffsetDateTime(2020-08-15 00:00:00+02:00)

        Note
        ----
        The parsed ``tzinfo`` must be a fixed offset
        (:class:`~datetime.timezone` instance).
        This means you need to include the directive ``%z``, ``%Z``, or ``%:z``
        in the format string.
        """
        parsed = _datetime.strptime(s, fmt)
        # We only need to check for None, because the only other tzinfo
        # returned from strptime is a fixed offset
        if parsed.tzinfo is None:
            raise ValueError(
                "Parsed datetime must have an offset. "
                "Use %z, %Z, or %:z in the format string"
            )
        return cls._from_py_unchecked(parsed)

    def rfc2822(self) -> str:
        """Format as an RFC 2822 string.

        Inverse of :meth:`from_rfc2822`.

        Example
        -------

        >>> OffsetDateTime(2020, 8, 15, 23, 12, offset=hours(2)).rfc2822()
        "Sat, 15 Aug 2020 23:12:00 +0200"
        """
        return format_datetime(self._py_dt)

    @classmethod
    def from_rfc2822(cls, s: str, /) -> OffsetDateTime:
        """Parse an offset datetime in RFC 2822 format.

        Inverse of :meth:`rfc2822`.

        Example
        -------

        >>> OffsetDateTime.from_rfc2822("Sat, 15 Aug 2020 23:12:00 +0200")
        OffsetDateTime(2020-08-15 23:12:00+02:00)
        >>> # also valid:
        >>> OffsetDateTime.from_rfc2822("Sat, 15 Aug 2020 23:12:00 UT")
        >>> OffsetDateTime.from_rfc2822("Sat, 15 Aug 2020 23:12:00 GMT")
        >>> OffsetDateTime.from_rfc2822("Sat, 15 Aug 2020 23:12:00 MST")

        Warning
        -------
        The offset ``-0000`` has special meaning in RFC 2822,
        and is not allowed here.
        """
        parsed = parsedate_to_datetime(s)
        if parsed.tzinfo is None:
            raise ValueError(
                "RFC 2822 string with -0000 offset cannot be parsed as UTC"
            )
        return cls._from_py_unchecked(parsedate_to_datetime(s))

    def rfc3339(self) -> str:
        """Format as an RFC 3339 string

        For ``OffsetDateTime``, equivalent to :meth:`~DateTime.canonical_format`.
        Inverse of :meth:`from_rfc3339`.

        Example
        -------

        >>> OffsetDateTime(2020, 8, 15, hour=23, minute=12, offset=hours(4)).rfc3339()
        "2020-08-15T23:12:00+04:00"
        """
        return self._py_dt.isoformat()

    @classmethod
    def from_rfc3339(cls, s: str, /) -> OffsetDateTime:
        """Parse a UTC datetime in RFC 3339 format.

        Inverse of :meth:`rfc3339`.

        Example
        -------

        >>> OffsetDateTime.from_rfc3339("2020-08-15T23:12:00+02:00")
        OffsetDateTime(2020-08-15 23:12:00+02:00)
        >>> # also valid:
        >>> OffsetDateTime.from_rfc3339("2020-08-15T23:12:00Z")
        >>> OffsetDateTime.from_rfc3339("2020-08-15_23:12:00.23-12:00")
        >>> OffsetDateTime.from_rfc3339("2020-08-15t23:12:00z")
        """
        return cls._from_py_unchecked(_parse_rfc3339(s))

    def __repr__(self) -> str:
        return f"OffsetDateTime({self})"

    # a custom pickle implementation with a smaller payload
    def __reduce__(self) -> tuple[object, ...]:
        return (
            _unpkl_offset,
            self._py_dt.timetuple()[:6]
            + (
                self._py_dt.microsecond,
                self._py_dt.utcoffset().total_seconds(),  # type: ignore[union-attr]
            ),
        )


# A separate function is needed for unpickling, because the
# constructor doesn't accept positional offset argument as
# required by __reduce__.
# Also, it allows backwards-compatible changes to the pickling format.
def _unpkl_offset(
    year: int,
    month: int,
    day: int,
    hour: int,
    minute: int,
    second: int,
    microsecond: int,
    offset_secs: float,
) -> OffsetDateTime:
    return OffsetDateTime._from_py_unchecked(
        _datetime(
            year,
            month,
            day,
            hour,
            minute,
            second,
            microsecond,
            _timezone(_timedelta(seconds=offset_secs)),
        )
    )


class ZonedDateTime(AwareDateTime):
    """A datetime associated with a IANA timezone ID.
    Useful for representing the local time bound to a specific location.

    Example
    -------

    >>> from whenever import ZonedDateTime
    >>>
    >>> # always at 11:00 in London, regardless of the offset
    >>> changing_the_guard = ZonedDateTime(2024, 12, 8, hour=11, tz="Europe/London")
    >>>
    >>> # Explicitly resolve ambiguities when clocks are set backwards.
    >>> night_shift = ZonedDateTime(2023, 10, 29, 1, 15, tz="Europe/London", disambiguate="later")
    >>>
    >>> # ZoneInfoNotFoundError: no such timezone
    >>> ZonedDateTime(2024, 12, 8, hour=11, tz="invalid")
    >>>
    >>> # DoesntExistInZone: 2:15 AM does not exist on this day
    >>> ZonedDateTime(2023, 3, 26, 2, 15, tz="Europe/Amsterdam")

    Disambiguation
    --------------

    The ``disambiguate`` argument controls how ambiguous datetimes are handled:

    +------------------+-------------------------------------------------+
    | ``disambiguate`` | Behavior in case of ambiguity                   |
    +==================+=================================================+
    | ``"raise"``      | (default) Refuse to guess:                      |
    |                  | raise :exc:`~whenever.Ambiguous`                |
    |                  | or :exc:`~whenever.DoesntExistInZone` exception.|
    +------------------+-------------------------------------------------+
    | ``"earlier"``    | Choose the earlier of the two options           |
    +------------------+-------------------------------------------------+
    | ``"later"``      | Choose the later of the two options             |
    +------------------+-------------------------------------------------+
    | ``"compatible"`` | Choose "earlier" for backward transitions and   |
    |                  | "later" for forward transitions. This matches   |
    |                  | the behavior of other established libraries,    |
    |                  | and the industry standard RFC 5545.             |
    |                  | It corresponds to setting ``fold=0`` in the     |
    |                  | standard library.                               |
    +------------------+-------------------------------------------------+

    Warning
    -------

    The canonical string format is:

    .. code-block:: text

       YYYY-MM-DDTHH:MM:SS(.ffffff)±HH:MM(:SS(.ffffff))[TIMEZONE ID]

    For example:

    .. code-block:: text

       2020-08-15T23:12:00+01:00[Europe/London]

    The offset is included to disambiguate cases where the same
    local time occurs twice due to DST transitions.
    If the offset is invalid for the system timezone,
    parsing will raise :class:`InvalidOffsetForZone`.

    This format is similar to those `used by other languages <https://tc39.es/proposal-temporal/docs/strings.html#iana-time-zone-names>`_,
    but it is *not* RFC 3339 or ISO 8601 compliant
    (these standards don't support timezone IDs.)
    Use :meth:`~AwareDateTime.as_offset` first if you
    need RFC 3339 or ISO 8601 compliance.
    """

    __slots__ = ()

    def __init__(
        self,
        year: int,
        month: int,
        day: int,
        hour: int = 0,
        minute: int = 0,
        second: int = 0,
        microsecond: int = 0,
        *,
        tz: str,
        disambiguate: Disambiguate = "raise",
    ) -> None:
        self._py_dt = _resolve_ambuguity(
            _datetime(
                year,
                month,
                day,
                hour,
                minute,
                second,
                microsecond,
                zone := ZoneInfo(tz),
                fold=_as_fold(disambiguate),
            ),
            zone,
            disambiguate,
        )

    @classmethod
    def now(cls, tz: str) -> ZonedDateTime:
        """Create an instance from the current time in the given timezone"""
        return cls._from_py_unchecked(_datetime.now(ZoneInfo(tz)))

    def canonical_format(self, sep: Literal[" ", "T"] = "T") -> str:
        return (
            f"{self._py_dt.isoformat(sep)}"
            f"[{self._py_dt.tzinfo.key}]"  # type: ignore[union-attr]
        )

    @classmethod
    def from_canonical_format(cls, s: str, /) -> ZonedDateTime:
        if (match := _match_zoned_str(s)) is None:
            raise InvalidFormat()
        dt = _fromisoformat(match[1])
        offset = dt.utcoffset()
        dt = dt.replace(tzinfo=ZoneInfo(match[2]))
        if offset != dt.utcoffset():  # offset/zone mismatch: try other fold
            dt = dt.replace(fold=1)
            if dt.utcoffset() != offset:
                raise InvalidOffsetForZone()
        return cls._from_py_unchecked(dt)

    @classmethod
    def from_timestamp(cls, i: float, /, tz: str) -> ZonedDateTime:
        """Create an instace from a UNIX timestamp."""
        return cls._from_py_unchecked(_fromtimestamp(i, ZoneInfo(tz)))

    @classmethod
    def from_py_datetime(cls, d: _datetime, /) -> ZonedDateTime:
        if not isinstance(d.tzinfo, ZoneInfo):
            raise ValueError(
                "Can only create ZonedDateTime from ZoneInfo, "
                f"got datetime with tzinfo={d.tzinfo!r}"
            )
        if not _exists_in_tz(d):
            raise DoesntExistInZone.for_timezone(d, d.tzinfo)
        return cls._from_py_unchecked(d)

    if TYPE_CHECKING:
        # We could have used typing.Unpack, but that's only available
        # in Python 3.11+ or with typing_extensions.
        def replace(
            self,
            *,
            year: int | NOT_SET = NOT_SET(),
            month: int | NOT_SET = NOT_SET(),
            day: int | NOT_SET = NOT_SET(),
            hour: int | NOT_SET = NOT_SET(),
            minute: int | NOT_SET = NOT_SET(),
            second: int | NOT_SET = NOT_SET(),
            microsecond: int | NOT_SET = NOT_SET(),
            tz: str | NOT_SET = NOT_SET(),
            disambiguate: Disambiguate | NOT_SET = NOT_SET(),
        ) -> ZonedDateTime: ...

    else:

        def replace(self, /, disambiguate="raise", **kwargs) -> ZonedDateTime:
            if not _no_tzinfo_or_fold(kwargs):
                raise TypeError("tzinfo and/or fold are not allowed arguments")
            try:
                kwargs["tzinfo"] = ZoneInfo(kwargs.pop("tz"))
            except KeyError:
                pass
            return self._from_py_unchecked(
                _resolve_ambuguity(
                    self._py_dt.replace(fold=_as_fold(disambiguate), **kwargs),
                    kwargs.get("tzinfo", self._py_dt.tzinfo),
                    disambiguate,
                )
            )

    if TYPE_CHECKING or SPHINX_BUILD:  # pragma: no cover

        @property
        def tz(self) -> str:
            """The timezone ID"""
            ...

    else:
        tz = property(attrgetter("_py_dt.tzinfo.key"))

    @property
    def offset(self) -> Duration:
        return Duration.from_py_timedelta(self._py_dt.utcoffset())  # type: ignore[arg-type]

    def __hash__(self) -> int:
        return hash(self._py_dt.astimezone(_UTC))

    # Hiding __eq__ from mypy ensures that --strict-equality works.
    if not TYPE_CHECKING:  # pragma: no branch

        def __eq__(self, other: object) -> bool:
            if not isinstance(other, AwareDateTime):
                return NotImplemented

            # We can't rely on simple equality, because it isn't equal
            # between two datetimes with different timezones if one of the
            # datetimes needs fold to disambiguate it.
            # See peps.python.org/pep-0495/#aware-datetime-equality-comparison.
            # We want to avoid this legacy edge case, so we normalize to UTC.
            return self._py_dt.astimezone(_UTC) == other._py_dt.astimezone(
                _UTC
            )

    def exact_eq(self, other: ZonedDateTime, /) -> bool:
        return (
            self._py_dt.tzinfo is other._py_dt.tzinfo
            and self._py_dt.fold == other._py_dt.fold
            and self._py_dt == other._py_dt
        )

    def __lt__(self, other: AwareDateTime) -> bool:
        if not isinstance(other, AwareDateTime):
            return NotImplemented
        return self._py_dt.astimezone(_UTC) < other._py_dt

    def __le__(self, other: AwareDateTime) -> bool:
        if not isinstance(other, AwareDateTime):
            return NotImplemented
        return self._py_dt.astimezone(_UTC) <= other._py_dt

    def __gt__(self, other: AwareDateTime) -> bool:
        if not isinstance(other, AwareDateTime):
            return NotImplemented
        return self._py_dt.astimezone(_UTC) > other._py_dt

    def __ge__(self, other: AwareDateTime) -> bool:
        if not isinstance(other, AwareDateTime):
            return NotImplemented
        return self._py_dt.astimezone(_UTC) >= other._py_dt

    def __add__(self, delta: Duration | Period) -> ZonedDateTime:
        """Add an amount of time, accounting for timezone changes (e.g. DST).

        Example
        -------

        >>> d = ZonedDateTime(2023, 10, 28, 12, tz="Europe/Amsterdam", disambiguate="earlier")
        >>> # adding exact number of hours accounts for the DST transition
        >>> d + Duration(hours=24)
        ZonedDateTime(2023-10-29T11:00:00+01:00[Europe/Amsterdam])
        >>> # adding days keeps the same local time
        >>> d + Period(days=1)
        ZonedDateTime(2023-10-29T12:00:00+01:00[Europe/Amsterdam])

        Note
        ----
        Addition of :class:`~whenever.Period` follows RFC 5545
        (iCalendar) and the behavior of other established libraries:

        - Units are added from largest to smallest.
        - Adding days keeps the same local time. For example,
          scheduling a 11am event "a days later" will result in
          11am local time the next day, even if there was a DST transition.
          Scheduling it exactly 24 hours would have resulted in
          a different local time.
        - If the resulting time is amgiuous after shifting the date,
          the "compatible" disambiguation is used.
          This means that for gaps, time is skipped forward.
        """
        if isinstance(delta, Duration):
            return self._from_py_unchecked(
                (
                    self._py_dt.astimezone(_UTC) + delta.py_timedelta()
                ).astimezone(self._py_dt.tzinfo)
            )
        elif isinstance(delta, Period):
            years, months, weeks, days, *_ = delta.as_tuple()
            date_old = self.date()
            date_new = date_old.add(years, months, weeks, days)
            return (
                self
                if date_new == date_old
                else self.replace(
                    year=date_new.year,
                    month=date_new.month,
                    day=date_new.day,
                    disambiguate="compatible",
                )
            ) + delta.time_component()
        else:
            return NotImplemented

    if TYPE_CHECKING:

        @overload
        def __sub__(self, other: AwareDateTime) -> Duration: ...

        @overload
        def __sub__(self, other: Duration | Period) -> ZonedDateTime: ...

        def __sub__(
            self, other: AwareDateTime | Duration | Period
        ) -> AwareDateTime | Duration: ...

    else:

        def __sub__(
            self, other: Duration | Period | AwareDateTime
        ) -> AwareDateTime | Duration:
            """Subtract another datetime or duration"""
            if isinstance(other, AwareDateTime):
                return Duration.from_py_timedelta(
                    self._py_dt.astimezone(_UTC) - other._py_dt
                )
            elif isinstance(other, Duration):
                return self._from_py_unchecked(
                    (
                        self._py_dt.astimezone(_UTC) - other.py_timedelta()
                    ).astimezone(self._py_dt.tzinfo)
                )
            elif isinstance(other, Period):
                return self + -other
            return NotImplemented

    def is_ambiguous(self) -> bool:
        """Whether the local time is ambiguous, e.g. due to a DST transition.

        Example
        -------

        >>> ZonedDateTime(2020, 8, 15, 23, tz="Europe/London", disambiguate="later").ambiguous()
        False
        >>> ZonedDateTime(2023, 10, 29, 2, 15, tz="Europe/Amsterdam", disambiguate="later").ambiguous()
        True
        """
        return self._py_dt.astimezone(_UTC) != self._py_dt

    def as_utc(self) -> UTCDateTime:
        return UTCDateTime._from_py_unchecked(self._py_dt.astimezone(_UTC))

    @overload
    def as_offset(self, /) -> OffsetDateTime: ...

    @overload
    def as_offset(self, offset: Duration, /) -> OffsetDateTime: ...

    def as_offset(self, offset: Duration | None = None, /) -> OffsetDateTime:
        return OffsetDateTime._from_py_unchecked(
            self._py_dt.astimezone(
                # mypy doesn't know that offset is never None
                _timezone(self._py_dt.utcoffset())  # type: ignore[arg-type]
                if offset is None
                else _timezone(offset.py_timedelta())
            )
        )

    def as_zoned(self, tz: str, /) -> ZonedDateTime:
        return self._from_py_unchecked(self._py_dt.astimezone(ZoneInfo(tz)))

    def __repr__(self) -> str:
        return f"ZonedDateTime({self})"

    # a custom pickle implementation with a smaller payload
    def __reduce__(self) -> tuple[object, ...]:
        return (
            _unpkl_zoned,
            self._py_dt.timetuple()[:6]
            + (
                self._py_dt.microsecond,
                # We know that tzinfo is always a ZoneInfo, but mypy doesn't
                self._py_dt.tzinfo.key,  # type: ignore[union-attr]
                self._py_dt.fold,
            ),
        )


# A separate function is needed for unpickling, because the
# constructor doesn't accept positional tz and fold arguments as
# required by __reduce__.
# Also, it allows backwards-compatible changes to the pickling format.
def _unpkl_zoned(
    year: int,
    month: int,
    day: int,
    hour: int,
    minute: int,
    second: int,
    microsecond: int,
    tz: str,
    fold: Fold,
) -> ZonedDateTime:
    return ZonedDateTime._from_py_unchecked(
        _datetime(
            year,
            month,
            day,
            hour,
            minute,
            second,
            microsecond,
            ZoneInfo(tz),
            fold=fold,
        )
    )


class LocalDateTime(AwareDateTime):
    """Represents a time in the system timezone. Unlike OffsetDateTime,
    it knows about the system timezone and its DST transitions.

    Example
    -------

    >>> # 8:00 in the system timezone—Paris in this case
    >>> alarm = LocalDateTime(2024, 3, 31, hour=6)
    LocalDateTime(2024-03-31 06:00:00+02:00)
    ...
    >>> # Conversion based on Paris' offset
    >>> alarm.as_utc()
    UTCDateTime(2024-03-31 04:00:00)
    ...
    >>> # unlike OffsetDateTime, it knows about DST transitions
    >>> bedtime = alarm - hours(8)
    LocalDateTime(2024-03-30 21:00:00+01:00)

    Handling ambiguity
    ------------------

    The system timezone may have ambiguous datetimes,
    such as during a DST transition.
    The ``disambiguate`` argument controls how ambiguous datetimes are handled:

    +------------------+-------------------------------------------------+
    | ``disambiguate`` | Behavior in case of ambiguity                   |
    +==================+=================================================+
    | ``"raise"``      | (default) Refuse to guess:                      |
    |                  | raise :exc:`~whenever.Ambiguous`                |
    |                  | or :exc:`~whenever.DoesntExistInZone` exception.|
    +------------------+-------------------------------------------------+
    | ``"earlier"``    | Choose the earlier of the two options           |
    +------------------+-------------------------------------------------+
    | ``"later"``      | Choose the later of the two options             |
    +------------------+-------------------------------------------------+
    | ``"compatible"`` | Choose "earlier" for backward transitions and   |
    |                  | "later" for forward transitions. This matches   |
    |                  | the behavior of other established libraries,    |
    |                  | and the industry standard RFC 5545.             |
    |                  | It corresponds to setting ``fold=0`` in the     |
    |                  | standard library.                               |
    +------------------+-------------------------------------------------+

    Changes to the system timezone
    ------------------------------

    Instances have the fixed offset of the system timezone
    at the time of initialization.
    The system timezone may change afterwards,
    but instances of this type will not reflect that change.
    This is because:

    - There are several ways to deal with such a change:
      should the moment in time be preserved, or the local time on the clock?
    - Automatically reflecting that change would mean that the object could
      change at any time, depending on some global mutable state.
      This would make it harder to reason about and use.

    >>> # initialization where the system timezone is America/New_York
    >>> d = LocalDateTime(2020, 8, 15, hour=8)
    LocalDateTime(2020-08-15 08:00:00-04:00)
    ...
    >>> # we change the system timezone to Amsterdam
    >>> os.environ["TZ"] = "Europe/Amsterdam"
    >>> time.tzset()
    ...
    >>> d  # object remains unchanged
    LocalDateTime(2020-08-15 08:00:00-04:00)

    If you'd like to preserve the moment in time
    and calculate the new local time, simply call :meth:`~AwareDateTime.as_local`.

    >>> # same moment, but now with the clock time in Amsterdam
    >>> d.as_local()
    LocalDateTime(2020-08-15 14:00:00+02:00)

    On the other hand, if you'd like to preserve the local time on the clock
    and calculate the corresponding moment in time:

    >>> # take the wall clock time...
    >>> wall_clock = d.naive()
    NaiveDateTime(2020-08-15 08:00:00)
    >>> # ...and assume the system timezone (Amsterdam)
    >>> wall_clock.assume_local()
    LocalDateTime(2020-08-15 08:00:00+02:00)

    Note
    ----

    The canonical string format is:

    .. code-block:: text

       YYYY-MM-DDTHH:MM:SS(.ffffff)±HH:MM(:SS(.ffffff))

    This format is both RFC 3339 and ISO 8601 compliant.

    Note
    ----
    The underlying :class:`~datetime.datetime` object has
    a fixed :class:`~datetime.timezone` tzinfo.
    """

    __slots__ = ()

    def __init__(
        self,
        year: int,
        month: int,
        day: int,
        hour: int = 0,
        minute: int = 0,
        second: int = 0,
        microsecond: int = 0,
        *,
        disambiguate: Disambiguate = "raise",
    ) -> None:
        self._py_dt = _resolve_local_ambiguity(
            _datetime(
                year,
                month,
                day,
                hour,
                minute,
                second,
                microsecond,
                fold=_as_fold(disambiguate),
            ),
            disambiguate,
        )

    @classmethod
    def now(cls) -> LocalDateTime:
        """Create an instance from the current time"""
        return cls._from_py_unchecked(_datetime.now())

    def canonical_format(self, sep: Literal[" ", "T"] = "T") -> str:
        return self._py_dt.isoformat(sep)

    @classmethod
    def from_canonical_format(cls, s: str, /) -> LocalDateTime:
        if not _match_offset_str(s):
            raise InvalidFormat()
        return cls._from_py_unchecked(_fromisoformat(s))

    @classmethod
    def from_timestamp(cls, i: float, /) -> LocalDateTime:
        """Create an instace from a UNIX timestamp.
        The inverse of :meth:`~AwareDateTime.timestamp`.

        Example
        -------

        >>> # assuming system timezone is America/New_York
        >>> LocalDateTime.from_timestamp(0)
        LocalDateTime(1969-12-31T19:00:00-05:00)
        >>> LocalDateTime.from_timestamp(1_123_000_000.45)
        LocalDateTime(2005-08-12T12:26:40.45-04:00)
        >>> LocalDateTime.from_timestamp(d.timestamp()) == d
        True
        """
        return cls._from_py_unchecked(_fromtimestamp(i).astimezone())

    @classmethod
    def from_py_datetime(cls, d: _datetime, /) -> LocalDateTime:
        if not isinstance(d.tzinfo, _timezone):
            raise ValueError(
                "Can only create LocalDateTime from a fixed-offset datetime, "
                f"got datetime with tzinfo={d.tzinfo!r}."
            )
        return cls._from_py_unchecked(d)

    def __repr__(self) -> str:
        return f"LocalDateTime({self})"

    @property
    def offset(self) -> Duration:
        return Duration.from_py_timedelta(self._py_dt.utcoffset())  # type: ignore[arg-type]

    # TODO: include in canonical_format? Remove?
    @property
    def tzname(self) -> str | None:
        """The name of the timezone as provided by the system, if known.
        Examples: ``"EST"`` or ``"CET"``.

        .. attention::

           This is different from the IANA timezone ID.
           For example, ``"Europe/Paris"`` is the IANA tz ID
           that *observes* ``"CET"`` in the winter and ``"CEST"`` in the summer.

        """
        return self._py_dt.tzname()

    if not TYPE_CHECKING:  # pragma: no branch

        def __eq__(self, other: object) -> bool:
            if not isinstance(
                other, (UTCDateTime, OffsetDateTime, LocalDateTime)
            ):
                return NotImplemented
            return self._py_dt == other._py_dt

    def __lt__(self, other: AwareDateTime) -> bool:
        if not isinstance(other, (UTCDateTime, OffsetDateTime, LocalDateTime)):
            return NotImplemented
        return self._py_dt < other._py_dt

    def __le__(self, other: AwareDateTime) -> bool:
        if not isinstance(other, (UTCDateTime, OffsetDateTime, LocalDateTime)):
            return NotImplemented
        return self._py_dt <= other._py_dt

    def __gt__(self, other: AwareDateTime) -> bool:
        if not isinstance(other, (UTCDateTime, OffsetDateTime, LocalDateTime)):
            return NotImplemented
        return self._py_dt > other._py_dt

    def __ge__(self, other: AwareDateTime) -> bool:
        if not isinstance(other, (UTCDateTime, OffsetDateTime, LocalDateTime)):
            return NotImplemented
        return self._py_dt >= other._py_dt

    def exact_eq(self, other: LocalDateTime) -> bool:
        return (
            self._py_dt == other._py_dt
            and self._py_dt.tzinfo == other._py_dt.tzinfo
        )

    if TYPE_CHECKING:
        # We could have used typing.Unpack, but that's only available
        # in Python 3.11+ or with typing_extensions.
        def replace(
            self,
            *,
            year: int | NOT_SET = NOT_SET(),
            month: int | NOT_SET = NOT_SET(),
            day: int | NOT_SET = NOT_SET(),
            hour: int | NOT_SET = NOT_SET(),
            minute: int | NOT_SET = NOT_SET(),
            second: int | NOT_SET = NOT_SET(),
            microsecond: int | NOT_SET = NOT_SET(),
            disambiguate: Disambiguate | NOT_SET = NOT_SET(),
        ) -> LocalDateTime: ...

    else:

        def replace(self, /, disambiguate="raise", **kwargs) -> LocalDateTime:
            if not _no_tzinfo_or_fold(kwargs):
                raise TypeError("tzinfo and/or fold are not allowed arguments")
            d = self._py_dt.replace(
                tzinfo=None, fold=_as_fold(disambiguate), **kwargs
            )
            return self._from_py_unchecked(
                _resolve_local_ambiguity(d, disambiguate)
            )

        __hash__ = property(attrgetter("_py_dt.__hash__"))

    def __add__(self, other: Duration) -> LocalDateTime:
        """Add a duration to this datetime

        Example
        -------

        >>> d = LocalDateTime(2020, 8, 15, hour=23, minute=12, fold=0)
        >>> d + Duration(hours=24, seconds=5)
        LocalDateTime(2020-08-16 23:12:05)

        """
        if not isinstance(other, Duration):
            return NotImplemented
        return self._from_py_unchecked(
            (self._py_dt + other.py_timedelta()).astimezone()
        )

    if TYPE_CHECKING:

        @overload
        def __sub__(self, other: AwareDateTime) -> Duration: ...

        @overload
        def __sub__(self, other: Duration) -> LocalDateTime: ...

        def __sub__(
            self, other: AwareDateTime | Duration
        ) -> AwareDateTime | Duration: ...

    else:

        def __sub__(
            self, other: Duration | AwareDateTime
        ) -> AwareDateTime | Duration:
            """Subtract another datetime or duration

            Example
            -------

            >>> d = LocalDateTime(2020, 8, 15, hour=23, minute=12, fold=0)
            >>> d - Duration(hours=24, seconds=5)
            LocalDateTime(2020-08-14 23:11:55)

            """
            if isinstance(other, AwareDateTime):
                return Duration.from_py_timedelta(self._py_dt - other._py_dt)
            elif isinstance(other, Duration):
                return self._from_py_unchecked(
                    (self._py_dt - other.py_timedelta()).astimezone()
                )
            return NotImplemented

    def as_utc(self) -> UTCDateTime:
        return UTCDateTime._from_py_unchecked(self._py_dt.astimezone(_UTC))

    @overload
    def as_offset(self, /) -> OffsetDateTime: ...

    @overload
    def as_offset(self, offset: Duration, /) -> OffsetDateTime: ...

    def as_offset(self, offset: Duration | None = None, /) -> OffsetDateTime:
        return OffsetDateTime._from_py_unchecked(
            self._py_dt
            if offset is None
            else self._py_dt.astimezone(_timezone(offset.py_timedelta()))
        )

    def as_zoned(self, tz: str, /) -> ZonedDateTime:
        return ZonedDateTime._from_py_unchecked(
            self._py_dt.astimezone(ZoneInfo(tz))
        )

    def as_local(self) -> LocalDateTime:
        return self._from_py_unchecked(self._py_dt.astimezone())

    # a custom pickle implementation with a smaller payload
    def __reduce__(self) -> tuple[object, ...]:
        return (
            _unpkl_local,
            self._py_dt.timetuple()[:6]
            + (
                self._py_dt.microsecond,
                self._py_dt.utcoffset().total_seconds(),  # type: ignore[union-attr]
                self._py_dt.tzname(),
            ),
        )


# A separate function is needed for unpickling, because the
# constructor doesn't accept positional fold arguments as
# required by __reduce__.
# Also, it allows backwards-compatible changes to the pickling format.
def _unpkl_local(
    year: int,
    month: int,
    day: int,
    hour: int,
    minute: int,
    second: int,
    microsecond: int,
    offset_secs: float,
    tzname: str,
) -> LocalDateTime:
    # TODO: check rounding
    return LocalDateTime._from_py_unchecked(
        _datetime(
            year,
            month,
            day,
            hour,
            minute,
            second,
            microsecond,
            tzinfo=_timezone(_timedelta(seconds=offset_secs), tzname),
        )
    )


class NaiveDateTime(DateTime):
    """A plain datetime without timezone or offset.

    It can't be mixed with aware datetimes.
    Conversion to aware datetimes can only be done by
    explicitly assuming a timezone or offset.

    Examples of when to use this type:

    - You need to express a date and time as it would be observed locally
      on the "wall clock" or calendar.
    - You receive a date and time without any timezone information,
      and you need a type to represent this lack of information.
    - In the rare case you truly don't need to account for timezones,
      or Daylight Saving Time transitions. For example, when modeling
      time in a simulation game.

    Note
    ----

    The canonical string format is:

    .. code-block:: text

       YYYY-MM-DDTHH:MM:SS(.fff(fff))

    This format is ISO 8601 compliant, but not RFC 3339 compliant,
    because this requires a UTC offset.
    """

    def __init__(
        self,
        year: int,
        month: int,
        day: int,
        hour: int = 0,
        minute: int = 0,
        second: int = 0,
        microsecond: int = 0,
    ) -> None:
        self._py_dt = _datetime(
            year, month, day, hour, minute, second, microsecond
        )

    def canonical_format(self, sep: Literal[" ", "T"] = "T") -> str:
        return self._py_dt.isoformat(sep)

    @classmethod
    def from_canonical_format(cls, s: str, /) -> NaiveDateTime:
        if not _match_naive_str(s):
            raise InvalidFormat()
        return cls._from_py_unchecked(_fromisoformat(s))

    @classmethod
    def from_py_datetime(cls, d: _datetime, /) -> NaiveDateTime:
        if d.tzinfo is not None:
            raise ValueError(
                "Can only create NaiveDateTime from a naive datetime, "
                f"got datetime with tzinfo={d.tzinfo!r}"
            )
        return cls._from_py_unchecked(d)

    tzinfo: ClassVar[None] = None

    if TYPE_CHECKING:
        # We could have used typing.Unpack, but that's only available
        # in Python 3.11+ or with typing_extensions.
        def replace(
            self,
            *,
            year: int | NOT_SET = NOT_SET(),
            month: int | NOT_SET = NOT_SET(),
            day: int | NOT_SET = NOT_SET(),
            hour: int | NOT_SET = NOT_SET(),
            minute: int | NOT_SET = NOT_SET(),
            second: int | NOT_SET = NOT_SET(),
            microsecond: int | NOT_SET = NOT_SET(),
        ) -> NaiveDateTime: ...

    else:

        def replace(self, /, **kwargs) -> NaiveDateTime:
            if not _no_tzinfo_or_fold(kwargs):
                raise TypeError("tzinfo and fold are not allowed arguments")
            return self._from_py_unchecked(self._py_dt.replace(**kwargs))

        __hash__ = property(attrgetter("_py_dt.__hash__"))

        # Hiding __eq__ from mypy ensures that --strict-equality works
        def __eq__(self, other: object) -> bool:
            """Compare objects for equality.
            Only ever equal to other :class:`NaiveDateTime` instances with the
            same values.

            Warning
            -------
            To comply with the Python data model, this method can't
            raise a :exc:`TypeError` when comparing with other types.
            Although it seems to be the sensible response, it would result in
            `surprising behavior <https://stackoverflow.com/a/33417512>`_
            when using values as dictionary keys.

            Use mypy's ``--strict-equality`` flag to detect and prevent this.

            Example
            -------

            >>> NaiveDateTime(2020, 8, 15, 23) == NaiveDateTime(2020, 8, 15, 23)
            True
            >>> NaiveDateTime(2020, 8, 15, 23, 1) == NaiveDateTime(2020, 8, 15, 23)
            False
            >>> NaiveDateTime(2020, 8, 15) == UTCDateTime(2020, 8, 15)
            False  # Use mypy's --strict-equality flag to detect this.

            """
            if not isinstance(other, NaiveDateTime):
                return NotImplemented
            return self._py_dt == other._py_dt

    min: ClassVar[NaiveDateTime]
    max: ClassVar[NaiveDateTime]

    def __lt__(self, other: NaiveDateTime) -> bool:
        if not isinstance(other, NaiveDateTime):
            return NotImplemented
        return self._py_dt < other._py_dt

    def __le__(self, other: NaiveDateTime) -> bool:
        if not isinstance(other, NaiveDateTime):
            return NotImplemented
        return self._py_dt <= other._py_dt

    def __gt__(self, other: NaiveDateTime) -> bool:
        if not isinstance(other, NaiveDateTime):
            return NotImplemented
        return self._py_dt > other._py_dt

    def __ge__(self, other: NaiveDateTime) -> bool:
        if not isinstance(other, NaiveDateTime):
            return NotImplemented
        return self._py_dt >= other._py_dt

    def __add__(self, other: Duration | Period) -> NaiveDateTime:
        """Add a duration to this datetime

        Example
        -------

        >>> d = NaiveDateTime(2020, 8, 15, hour=23, minute=12)
        >>> d + Duration(hours=24, seconds=5)
        NaiveDateTime(2020-08-16 23:12:05)
        >>> d + Period(years=3, months=2, days=1)
        NaiveDateTime(2023-10-16 23:12:00)
        """
        if isinstance(other, Duration):
            return self._from_py_unchecked(self._py_dt + other.py_timedelta())
        elif isinstance(other, Period):
            years, months, weeks, days, *_ = other.as_tuple()
            date = self.date().add(years, months, weeks, days)
            return (
                self._from_py_unchecked(
                    self._py_dt.replace(
                        year=date.year, month=date.month, day=date.day
                    )
                )
                + other.time_component()
            )
        return NotImplemented

    if TYPE_CHECKING:

        @overload
        def __sub__(self, other: NaiveDateTime) -> Duration: ...

        @overload
        def __sub__(self, other: Duration | Period) -> NaiveDateTime: ...

        def __sub__(
            self, other: NaiveDateTime | Duration | Period
        ) -> NaiveDateTime | Duration: ...

    else:

        def __sub__(
            self, other: Duration | Period | NaiveDateTime
        ) -> NaiveDateTime | Duration:
            """Subtract another datetime or time amount

            Example
            -------

            >>> d = NaiveDateTime(2020, 8, 15, hour=23, minute=12)
            >>> d - Duration(hours=24, seconds=5)
            NaiveDateTime(2020-08-14 23:11:55)
            >>> d - NaiveDateTime(2020, 8, 14)
            Duration(47:12:00)
            >>> d - Period(years=3, months=2, days=1, minutes=5)
            NaiveDateTime(2017-06-14 23:07:00)
            """
            if isinstance(other, NaiveDateTime):
                return Duration.from_py_timedelta(self._py_dt - other._py_dt)
            elif isinstance(other, Duration):
                return self._from_py_unchecked(
                    self._py_dt - other.py_timedelta()
                )
            elif isinstance(other, Period):
                return self + -other
            return NotImplemented

    @classmethod
    def strptime(cls, s: str, /, fmt: str) -> NaiveDateTime:
        """Simple alias for
        ``NaiveDateTime.from_py_datetime(datetime.strptime(s, fmt))``

        Example
        -------

        >>> NaiveDateTime.strptime("2020-08-15", "%Y-%m-%d")
        NaiveDateTime(2020-08-15 00:00:00)

        Note
        ----
        The parsed ``tzinfo`` must be be ``None``.
        This means you can't include the directives ``%z``, ``%Z``, or ``%:z``
        in the format string.
        """
        parsed = _datetime.strptime(s, fmt)
        if parsed.tzinfo is not None:
            raise ValueError(
                "Parsed datetime can't have an offset. "
                "Do not use %z, %Z, or %:z in the format string"
            )
        return cls._from_py_unchecked(parsed)

    def assume_utc(self) -> UTCDateTime:
        """Assume the datetime is in UTC,
        creating a :class:`~whenever.UTCDateTime` instance.

        Example
        -------

        >>> NaiveDateTime(2020, 8, 15, 23, 12).assume_utc()
        UTCDateTime(2020-08-15 23:12:00Z)
        """
        return UTCDateTime._from_py_unchecked(self._py_dt.replace(tzinfo=_UTC))

    def assume_offset(self, offset: Duration, /) -> OffsetDateTime:
        """Assume the datetime is in the given offset,
        creating a :class:`~whenever.OffsetDateTime` instance.

        Example
        -------

        >>> NaiveDateTime(2020, 8, 15, 23, 12).assume_offset(hours(2))
        OffsetDateTime(2020-08-15 23:12:00+02:00)
        """
        return OffsetDateTime._from_py_unchecked(
            self._py_dt.replace(tzinfo=_timezone(offset.py_timedelta()))
        )

    def assume_zoned(
        self, tz: str, /, disambiguate: Disambiguate = "raise"
    ) -> ZonedDateTime:
        """Assume the datetime is in the given timezone,
        creating a :class:`~whenever.ZonedDateTime` instance.

        Example
        -------

        >>> NaiveDateTime(2020, 8, 15, 23, 12).assume_zoned("Europe/Amsterdam")
        ZonedDateTime(2020-08-15 23:12:00+02:00[Europe/Amsterdam])
        """
        return ZonedDateTime._from_py_unchecked(
            _resolve_ambuguity(
                self._py_dt.replace(
                    tzinfo=(zone := ZoneInfo(tz)), fold=_as_fold(disambiguate)
                ),
                zone,
                disambiguate,
            )
        )

    def assume_local(
        self, disambiguate: Disambiguate = "raise"
    ) -> LocalDateTime:
        """Assume the datetime is in the system timezone,
        creating a :class:`~whenever.LocalDateTime` instance.

        Example
        -------

        >>> # assuming system timezone is America/New_York
        >>> NaiveDateTime(2020, 8, 15, 23, 12).assume_local()
        LocalDateTime(2020-08-15 23:12:00-04:00)
        """
        return LocalDateTime._from_py_unchecked(
            _resolve_local_ambiguity(
                self._py_dt.replace(fold=_as_fold(disambiguate)),
                disambiguate,
            )
        )

    def rfc2822(self) -> str:
        """Format as an RFC 2822 string

        Example
        -------

        >>> NaiveDateTime(2020, 8, 15, 23, 12).rfc2822()
        "Sat, 15 Aug 2020 23:12:00 -0000"
        """
        return format_datetime(self._py_dt)

    @classmethod
    def from_rfc2822(cls, s: str, /) -> NaiveDateTime:
        """Parse an naive datetime in RFC 2822 format.

        Example
        -------

        >>> NaiveDateTime.from_rfc2822("Sat, 15 Aug 2020 23:12:00 -0000")
        NaiveDateTime(2020-08-15 23:12:00)
        >>> # Error: non-0000 offset
        >>> NaiveDateTime.from_rfc2822("Sat, 15 Aug 2020 23:12:00 GMT")
        >>> NaiveDateTime.from_rfc2822("Sat, 15 Aug 2020 23:12:00 +0000")
        >>> NaiveDateTime.from_rfc2822("Sat, 15 Aug 2020 23:12:00 -0100")

        Warning
        -------
        Only the offset ``-0000`` is allowed, since this has special meaning
        in RFC 2822.
        """
        parsed = parsedate_to_datetime(s)
        if parsed.tzinfo is not None:
            raise ValueError(
                "Only an RFC 2822 string with -0000 offset can be "
                "parsed as NaiveDateTime"
            )
        return cls._from_py_unchecked(parsedate_to_datetime(s))

    def __repr__(self) -> str:
        return f"NaiveDateTime({self})"

    # a custom pickle implementation with a smaller payload
    def __reduce__(self) -> tuple[object, ...]:
        return (
            _unpkl_naive,
            self._py_dt.timetuple()[:6] + (self._py_dt.microsecond,),
        )


# A separate unpickling function allows us to make backwards-compatible changes
# to the pickling format in the future
@no_type_check
def _unpkl_naive(*args) -> NaiveDateTime:
    return NaiveDateTime(*args)


class Ambiguous(Exception):
    """A datetime is unexpectedly ambiguous"""

    @staticmethod
    def for_timezone(d: _datetime, tz: _tzinfo) -> Ambiguous:
        return Ambiguous(
            f"{d.replace(tzinfo=None)} is ambiguous "
            f"in timezone {tz.key}"  # type:ignore[attr-defined]
        )

    @staticmethod
    def for_system_timezone(d: _datetime) -> Ambiguous:
        return Ambiguous(
            f"{d.replace(tzinfo=None)} is ambiguous in the system timezone"
        )


class DoesntExistInZone(Exception):
    """A datetime doesnt exist in a timezone, e.g. because of DST"""

    @staticmethod
    def for_timezone(d: _datetime, tz: _tzinfo) -> DoesntExistInZone:
        return DoesntExistInZone(
            f"{d.replace(tzinfo=None)} doesn't exist "
            f"in timezone {tz.key}"  # type:ignore[attr-defined]
        )

    @staticmethod
    def for_system_timezone(d: _datetime) -> DoesntExistInZone:
        return DoesntExistInZone(
            f"{d.replace(tzinfo=None)} doesn't exist in the system timezone"
        )


class InvalidOffsetForZone(ValueError):
    """A string has an invalid offset for the given zone"""


class InvalidFormat(ValueError):
    """A string has an invalid format"""


def _resolve_ambuguity(
    dt: _datetime, zone: ZoneInfo, disambiguate: Disambiguate
) -> _datetime:
    dt_utc = dt.astimezone(_UTC)
    # Non-existent times: they don't survive a UTC roundtrip
    if dt_utc.astimezone(zone) != dt:
        if disambiguate == "raise":
            raise DoesntExistInZone.for_timezone(dt, zone)
        elif disambiguate != "compatible":  # i.e. "earlier" or "later"
            # In gaps, the relationship between
            # fold and earlier/later is reversed
            dt = dt.replace(fold=not dt.fold)
        # perform the normalisation, shifting away from non-existent times
        dt = dt.astimezone(_UTC).astimezone(zone)
    # Ambiguous times: they're never equal to other timezones
    elif disambiguate == "raise" and dt_utc != dt:
        raise Ambiguous.for_timezone(dt, zone)
    return dt


# Whether the fold of a local time needs to be flipped in a gap
# was changed (fixed) in Python 3.12. See cpython/issues/83861
_requires_flip: Callable[[Disambiguate], bool]
if sys.version_info > (3, 12):
    _requires_flip = "compatible".__ne__
else:  # pragma: no cover
    _requires_flip = "compatible".__eq__


def _resolve_local_ambiguity(
    dt: _datetime, disambiguate: Disambiguate
) -> _datetime:
    norm = dt.astimezone(_UTC).astimezone()
    # Non-existent times: they don't survive a UTC roundtrip
    if norm.replace(tzinfo=None) != dt:
        if disambiguate == "raise":
            raise DoesntExistInZone.for_system_timezone(dt)
        elif _requires_flip(disambiguate):
            dt = dt.replace(fold=not dt.fold)
        # perform the normalisation, shifting away from non-existent times
        norm = dt.astimezone(_UTC).astimezone()
    # Ambiguous times: they're never equal to other timezones
    elif disambiguate == "raise" and norm != dt.replace(fold=1).astimezone(
        _UTC
    ):
        raise Ambiguous.for_system_timezone(dt)
    return norm


def _exists_in_tz(d: _datetime) -> bool:
    # non-existent datetimes don't survive a round-trip to UTC
    return d.astimezone(_UTC).astimezone(d.tzinfo) == d


# Helpers that pre-compute/lookup as much as possible
_UTC = _timezone.utc
_no_tzinfo_or_fold = {"tzinfo", "fold"}.isdisjoint
_object_new = object.__new__
# YYYY-MM-DD HH:MM:SS[.fff[fff]]
_DATETIME_RE = r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.(?:\d{3}|\d{6}))?"
# YYYY-MM-DD HH:MM:SS[.fff[fff]]±HH:MM[:SS[.ffffff]]
_OFFSET_RE = rf"{_DATETIME_RE}[+-]\d{{2}}:\d{{2}}(?::\d{{2}}(?:\.\d{{6}})?)?"
_match_utc_str = re.compile(rf"{_DATETIME_RE}Z").fullmatch
_match_naive_str = re.compile(_DATETIME_RE).fullmatch
_match_offset_str = re.compile(_OFFSET_RE).fullmatch
_match_zoned_str = re.compile(rf"({_OFFSET_RE})\[([^\]]+)\]").fullmatch
_fromisoformat = _datetime.fromisoformat
_fromtimestamp = _datetime.fromtimestamp
_zero_timezone = _timezone(_timedelta())
_match_utc_rfc3339 = re.compile(
    r"\d{4}-\d{2}-\d{2}.\d{2}:\d{2}:\d{2}(\.\d{1,6})?(?:[Zz]|[+-]00:00)"
).fullmatch
_match_rfc3339 = re.compile(
    r"\d{4}-\d{2}-\d{2}.\d{2}:\d{2}:\d{2}(\.\d{1,6})?(?:[Zz]|[+-]\d{2}:\d{2})"
).fullmatch
_match_period = re.compile(
    r"P(?:([-+]?\d+)Y)?(?:([-+]?\d+)M)?(?:([-+]?\d+)W)?(?:([-+]?\d+)D)?"
    r"(?:T(?:([-+]?\d+)H)?(?:([-+]?\d+)M)?(?:([-+]?\d+(?:\.\d{1,6})?)?S)?)?"
).fullmatch
_match_duration = re.compile(
    r"([-+]?)(\d{2,}):([0-5]\d):([0-5]\d(?:\.\d{1,6})?)"
).fullmatch
# Before Python 3.11, fromisoformat() is less capable
if sys.version_info < (3, 11):  # pragma: no cover

    def _fromisoformat_utc(s: str) -> _datetime:
        return _fromisoformat(s[:-1]).replace(tzinfo=_UTC)

    def _parse_rfc3339(s: str) -> _datetime:
        if not (m := _match_rfc3339(s)):
            raise ValueError()
        return _fromisoformat_extra(m, s)

    def _parse_utc_rfc3339(s: str) -> _datetime:
        if not (m := _match_utc_rfc3339(s)):
            raise ValueError()
        return _fromisoformat_extra(m, s)

    def _fromisoformat_extra(m: re.Match[str], s: str) -> _datetime:
        # handle fractions that aren't exactly 3 or 6 digits
        if (fraction := m.group(1)) and len(fraction) not in (7, 4):
            s = (
                s[:19]
                + fraction.ljust(7, "0")
                + s[19 + len(fraction) :]  # noqa
            )
        # handle Z suffix
        if s.endswith(("Z", "z")):
            s = s[:-1] + "+00:00"
        return _fromisoformat(s)

else:
    _fromisoformat_utc = _fromisoformat

    def _parse_utc_rfc3339(s: str) -> _datetime:
        if not _match_utc_rfc3339(s):
            raise ValueError()
        return _fromisoformat(s.upper())

    def _parse_rfc3339(s: str) -> _datetime:
        if not _match_rfc3339(s):
            raise ValueError()
        return _fromisoformat(s.upper())


UTCDateTime.min = UTCDateTime._from_py_unchecked(
    _datetime.min.replace(tzinfo=_UTC)
)
UTCDateTime.max = UTCDateTime._from_py_unchecked(
    _datetime.max.replace(tzinfo=_UTC)
)
NaiveDateTime.min = NaiveDateTime._from_py_unchecked(_datetime.min)
NaiveDateTime.max = NaiveDateTime._from_py_unchecked(_datetime.max)
Disambiguate = Literal["compatible", "earlier", "later", "raise"]
Fold = Literal[0, 1]
_as_fold: Callable[[Disambiguate], Fold] = {  # type: ignore[assignment]
    "compatible": 0,
    "earlier": 0,
    "later": 1,
    "raise": 0,
}.__getitem__


def hours(i: int, /) -> Duration:
    """Create a :class:`~Duration` with the given number of hours.
    ``hours(1) == Duration(hours=1)``
    """
    return Duration(hours=i)


def minutes(i: int, /) -> Duration:
    """Create a :class:`Duration` with the given number of minutes.
    ``minutes(1) == Duration(minutes=1)``
    """
    return Duration(minutes=i)
