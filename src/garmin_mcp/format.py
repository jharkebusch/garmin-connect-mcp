"""Turn raw Garmin JSON into short, readable text.

Garmin endpoints return large, deeply nested payloads full of nulls and
internal ids. Handing that to a model wastes the context window and reads
badly, so every tool renders a compact report through these helpers.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

METERS_PER_MILE = 1609.344
METERS_PER_FOOT = 0.3048
KG_PER_POUND = 0.45359237

# Garmin's own name for the imperial unit system.
STATUTE = "statute_us"


def is_metric(unit_system: str | None) -> bool:
    return (unit_system or "metric").lower() != STATUTE


def pick(payload: Any, *keys: str, default: Any = None) -> Any:
    """Return the first present, non-null value among ``keys``."""
    if not isinstance(payload, dict):
        return default
    for key in keys:
        value = payload.get(key)
        if value is not None:
            return value
    return default


def duration(seconds: float | None) -> str | None:
    """``3725`` -> ``1h 2m 5s``."""
    if seconds is None:
        return None
    total = int(round(float(seconds)))
    if total < 0:
        return None
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours}h {minutes}m {secs}s"
    if minutes:
        return f"{minutes}m {secs}s"
    return f"{secs}s"


def hours_minutes(seconds: float | None) -> str | None:
    """``27000`` -> ``7h 30m``. Used where seconds are noise, e.g. sleep."""
    if seconds is None:
        return None
    total = int(round(float(seconds)))
    if total < 0:
        return None
    hours, minutes = divmod(total // 60, 60)
    return f"{hours}h {minutes:02d}m"


def distance(meters: float | None, *, metric: bool = True) -> str | None:
    if meters is None:
        return None
    value = float(meters)
    if metric:
        return f"{value / 1000:.2f} km" if value >= 1000 else f"{value:.0f} m"
    miles = value / METERS_PER_MILE
    return f"{miles:.2f} mi" if miles >= 0.1 else f"{value / METERS_PER_FOOT:.0f} ft"


def elevation(meters: float | None, *, metric: bool = True) -> str | None:
    if meters is None:
        return None
    value = float(meters)
    return f"{value:.0f} m" if metric else f"{value / METERS_PER_FOOT:.0f} ft"


def pace(total_seconds: float | None, meters: float | None, *, metric: bool = True) -> str | None:
    """Average pace as ``m:ss /km`` or ``m:ss /mi``."""
    if not total_seconds or not meters or float(meters) <= 0:
        return None
    unit_meters = 1000.0 if metric else METERS_PER_MILE
    seconds_per_unit = float(total_seconds) / (float(meters) / unit_meters)
    if seconds_per_unit <= 0 or seconds_per_unit > 86400:
        return None
    minutes, secs = divmod(int(round(seconds_per_unit)), 60)
    return f"{minutes}:{secs:02d} /{'km' if metric else 'mi'}"


def speed(meters_per_second: float | None, *, metric: bool = True) -> str | None:
    if meters_per_second is None:
        return None
    value = float(meters_per_second) * 3.6
    return f"{value:.1f} km/h" if metric else f"{value / 1.609344:.1f} mph"


def weight(grams: float | None, *, metric: bool = True) -> str | None:
    """Garmin reports body weight in grams."""
    if grams is None:
        return None
    kilos = float(grams) / 1000.0
    return f"{kilos:.1f} kg" if metric else f"{kilos / KG_PER_POUND:.1f} lb"


def timestamp(value: Any, *, time_only: bool = False) -> str | None:
    """Format a Garmin timestamp, which may be epoch millis or an ISO string."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        # Garmin mixes seconds and milliseconds; anything this large is millis.
        seconds = float(value) / 1000.0 if abs(value) > 1e11 else float(value)
        try:
            moment = datetime.fromtimestamp(seconds, tz=UTC)
        except (OverflowError, OSError, ValueError):
            return None
        return moment.strftime("%H:%M" if time_only else "%Y-%m-%d %H:%M")
    text = str(value).strip()
    if not text:
        return None
    try:
        moment = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return text
    return moment.strftime("%H:%M" if time_only else "%Y-%m-%d %H:%M")


def number(value: Any, *, unit: str = "", digits: int = 0) -> str | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        rendered = f"{value:,.{digits}f}" if digits else f"{round(value):,}"
    else:
        rendered = str(value)
    return f"{rendered} {unit}".strip()


def prune(payload: Any, *, depth: int = 0) -> Any:
    """Recursively drop nulls, empty containers and long sample arrays."""
    if depth > 4:
        return None
    if isinstance(payload, dict):
        cleaned = {}
        for key, value in payload.items():
            trimmed = prune(value, depth=depth + 1)
            if trimmed not in (None, "", [], {}):
                cleaned[key] = trimmed
        return cleaned
    if isinstance(payload, list):
        # Per-second sample arrays are worthless to a language model and huge.
        if len(payload) > 12:
            return f"<{len(payload)} samples omitted>"
        cleaned_list = [prune(item, depth=depth + 1) for item in payload]
        return [item for item in cleaned_list if item not in (None, "", [], {})]
    return payload


def compact_json(payload: Any, *, limit: int = 1200) -> str:
    """Last-resort rendering when no known field matched.

    Garmin changes field names without warning; showing trimmed raw data beats
    telling the user there is nothing there when there is.
    """
    import json

    try:
        text = json.dumps(prune(payload), indent=2, default=str, sort_keys=True)
    except (TypeError, ValueError):
        text = str(payload)
    if len(text) > limit:
        text = text[:limit] + "\n... (truncated)"
    return text


def report(
    title: str,
    rows: list[tuple[str, Any]],
    *,
    footer: str | None = None,
    raw: Any = None,
) -> str:
    """Render ``label: value`` lines, dropping anything empty.

    Empty rows are dropped rather than shown as "None" so the model never
    reports a missing metric as a real zero. If nothing at all matched but
    Garmin did return something, fall back to trimmed raw data.
    """
    body = [f"{label}: {value}" for label, value in rows if value not in (None, "", [])]
    if not body:
        if raw:
            return f"{title}\n\nNo recognised fields, showing raw data:\n\n{compact_json(raw)}"
        return f"{title}\n\nNo data recorded."
    parts = [title, "", *body]
    if footer:
        parts += ["", footer]
    return "\n".join(parts)


def bullets(title: str, items: list[str], *, empty: str = "Nothing found.") -> str:
    if not items:
        return f"{title}\n\n{empty}"
    return "\n".join([title, "", *(f"- {item}" for item in items)])
