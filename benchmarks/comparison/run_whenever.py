# See Makefile for how to run this
import pyperf

runner = pyperf.Runner()

# runner.timeit(
#     "parse + convert + add",
#     "OffsetDateTime.from_rfc3339('2020-04-05 22:04:00-04:00')"
#     ".as_zoned('Europe/Amsterdam')"
#     ".add(days=30)",
#     "from whenever import OffsetDateTime",
# )

runner.timeit(
    "new date",
    "Date(2020, 2, 29)",
    "from whenever import Date",
)

runner.timeit(
    "date add",
    "d.add(years=-4, months=59, weeks=-7, days=3)",
    setup="from whenever import Date; d = Date(1987, 3, 31)",
)

runner.timeit(
    "date diff",
    "d1 - d2",
    setup="from whenever import Date; d1 = Date(2020, 2, 29); d2 = Date(2025, 2, 28)",
)

runner.timeit(
    "parse date",
    "f('2020-02-29')",
    setup="from whenever import Date; f = Date.from_canonical_format",
)

runner.timeit(
    "parse date delta",
    "f('P5Y2M4D')",
    setup="from whenever import DateDelta; f = DateDelta.from_canonical_format",
)

runner.timeit(
    "change tz",
    "dt.as_zoned('America/New_York')",
    setup="from whenever import ZonedDateTime; dt = ZonedDateTime(2020, 3, 20, 12, 30, 45, tz='Europe/Amsterdam')",
)
