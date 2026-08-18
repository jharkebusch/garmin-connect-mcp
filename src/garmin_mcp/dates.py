"""Turn everyday date phrases into the YYYY-MM-DD strings Garmin expects.

Non-technical users say "last week", not "2026-08-10". Claude passes whatever
the user said straight through, so every tool accepts these phrases.
"""

from __future__ import annotations

import re
from datetime import date, timedelta

_RELATIVE_DAYS = {
    "today": 0,
    "now": 0,
    "yesterday": -1,
    "tomorrow": 1,
}

_UNIT_DAYS = {
    "day": 1,
    "week": 7,
    "month": 30,
    "year": 365,
}

_N_AGO = re.compile(r"^(\d+)\s+(day|week|month|year)s?\s+ago$")
_LAST_N = re.compile(r"^(?:last|past|previous)\s+(\d+)\s+(day|week|month|year)s?$")
_LAST_ONE = re.compile(r"^(?:last|past|previous)\s+(day|week|month|year)$")
_THIS_ONE = re.compile(r"^(?:this|current)\s+(week|month|year)$")
_ISO = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")


class DateParseError(ValueError):
    """Raised when a date phrase cannot be understood."""


def _normalise(text: str) -> str:
    return " ".join(str(text).strip().lower().split())


def parse_date(text: str | None, *, today: date | None = None) -> str:
    """Parse a single day into ``YYYY-MM-DD``.

    Accepts ISO dates plus phrases like ``today``, ``yesterday`` and
    ``3 days ago``. ``None`` or an empty string means today.
    """
    today = today or date.today()
    if text is None:
        return today.isoformat()

    value = _normalise(text)
    if not value:
        return today.isoformat()

    if value in _RELATIVE_DAYS:
        return (today + timedelta(days=_RELATIVE_DAYS[value])).isoformat()

    iso = _ISO.match(value)
    if iso:
        year, month, day = (int(part) for part in iso.groups())
        try:
            return date(year, month, day).isoformat()
        except ValueError as exc:
            raise DateParseError(f"'{text}' is not a real calendar date.") from exc

    ago = _N_AGO.match(value)
    if ago:
        amount, unit = int(ago.group(1)), ago.group(2)
        return (today - timedelta(days=amount * _UNIT_DAYS[unit])).isoformat()

    raise DateParseError(
        f"Could not understand the date '{text}'. "
        "Try 'today', 'yesterday', '3 days ago', or a date like 2026-08-18."
    )


def parse_range(text: str | None, *, today: date | None = None) -> tuple[str, str]:
    """Parse a span of days into an inclusive ``(start, end)`` pair.

    Accepts phrases like ``last 7 days``, ``this week``, ``last month`` and
    ``2026-08-01 to 2026-08-18``. ``None`` defaults to the last 7 days.
    """
    today = today or date.today()
    if text is None:
        return (today - timedelta(days=6)).isoformat(), today.isoformat()

    value = _normalise(text)
    if not value:
        return (today - timedelta(days=6)).isoformat(), today.isoformat()

    for separator in (" to ", " through ", " until ", ".."):
        if separator in value:
            left, right = value.split(separator, 1)
            start = parse_date(left, today=today)
            end = parse_date(right, today=today)
            if start > end:
                start, end = end, start
            return start, end

    if value in _RELATIVE_DAYS:
        single = parse_date(value, today=today)
        return single, single

    if _ISO.match(value):
        single = parse_date(value, today=today)
        return single, single

    last_n = _LAST_N.match(value)
    if last_n:
        amount, unit = int(last_n.group(1)), last_n.group(2)
        days = amount * _UNIT_DAYS[unit]
        # "last 7 days" reads as a 7-day window ending today, today included.
        return (today - timedelta(days=days - 1)).isoformat(), today.isoformat()

    last_one = _LAST_ONE.match(value)
    if last_one:
        days = _UNIT_DAYS[last_one.group(1)]
        return (today - timedelta(days=days - 1)).isoformat(), today.isoformat()

    this_one = _THIS_ONE.match(value)
    if this_one:
        unit = this_one.group(1)
        if unit == "week":
            start = today - timedelta(days=today.weekday())
        elif unit == "month":
            start = today.replace(day=1)
        else:
            start = today.replace(month=1, day=1)
        return start.isoformat(), today.isoformat()

    ago = _N_AGO.match(value)
    if ago:
        single = parse_date(value, today=today)
        return single, single

    raise DateParseError(
        f"Could not understand the date range '{text}'. "
        "Try 'last 7 days', 'this month', or '2026-08-01 to 2026-08-18'."
    )


def days_in_range(start: str, end: str) -> list[str]:
    """Every date from ``start`` to ``end`` inclusive, as ISO strings."""
    first = date.fromisoformat(start)
    last = date.fromisoformat(end)
    return [
        (first + timedelta(days=offset)).isoformat() for offset in range((last - first).days + 1)
    ]
