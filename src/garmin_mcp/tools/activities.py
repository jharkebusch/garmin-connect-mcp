"""Recorded activity tools -- runs, rides, swims and everything else."""

from typing import Any

from ..dates import parse_date, parse_range
from ..format import (
    distance,
    duration,
    elevation,
    number,
    pace,
    pick,
    report,
    speed,
    timestamp,
)
from ..session import call, friendly, metric

# Sports where "how fast" is naturally a pace; everywhere else, a speed.
PACE_SPORTS = ("running", "walking", "hiking", "trail_running", "treadmill_running")


def _sport(activity: dict) -> str:
    kind = pick(activity, "activityType", default={}) or {}
    return str(pick(kind, "typeKey", default="other"))


def _headline(activity: dict, *, use_metric: bool) -> str:
    name = pick(activity, "activityName", default="Untitled")
    sport = _sport(activity).replace("_", " ")
    started = timestamp(pick(activity, "startTimeLocal", "startTimeGMT"))
    meters = pick(activity, "distance")
    seconds = pick(activity, "duration", "elapsedDuration")
    bits = [f"{name} ({sport})"]
    if started:
        bits.append(started)
    if meters:
        bits.append(str(distance(meters, metric=use_metric)))
    if seconds:
        bits.append(str(duration(seconds)))
    activity_id = pick(activity, "activityId")
    if activity_id is not None:
        bits.append(f"id {activity_id}")
    return " | ".join(bits)


def register(server: Any) -> None:
    @server.tool()
    @friendly
    async def list_activities(
        period: str = "last 30 days", sport: str = "", limit: int = 20
    ) -> str:
        """List recorded activities (runs, rides, swims, walks and so on) in a
        period. Use this to find an activity before asking for its details.

        Args:
            period: For example "last 30 days", "this month" or
                "2026-08-01 to 2026-08-18".
            sport: Optional filter, one of running, cycling, swimming, walking,
                hiking, strength_training, fitness_equipment, multi_sport, other.
                Leave empty for all sports.
            limit: Most activities to list. Defaults to 20.
        """
        start, end = parse_range(period)
        activity_type = sport.strip().lower() or None
        data = await call("get_activities_by_date", start, end, activity_type)
        if not isinstance(data, list) or not data:
            extra = f" for {activity_type}" if activity_type else ""
            return f"No activities{extra} recorded between {start} and {end}."
        use_metric = await metric()
        capped = data[: max(1, min(int(limit), 100))]
        lines = [f"- {_headline(item, use_metric=use_metric)}" for item in capped]
        header = f"{len(data)} activities from {start} to {end}"
        if len(capped) < len(data):
            header += f" (showing the first {len(capped)})"
        return "\n".join([header, "", *lines])

    @server.tool()
    @friendly
    async def get_activity_details(activity_id: int) -> str:
        """Full detail for one activity: distance, time, pace, heart rate,
        elevation, calories, cadence and training effect.

        Get the id from list_activities or get_last_activity first.

        Args:
            activity_id: The numeric id of the activity.
        """
        data = await call("get_activity", str(activity_id))
        return _render_activity(data, await metric())

    @server.tool()
    @friendly
    async def get_last_activity() -> str:
        """Full detail for the most recently recorded activity."""
        data = await call("get_last_activity")
        if not data:
            return "No activities have been recorded on this Garmin account yet."
        return _render_activity(data, await metric())

    @server.tool()
    @friendly
    async def get_activity_splits(activity_id: int) -> str:
        """Per-kilometre or per-mile splits for one activity, showing how pace
        and heart rate changed through the effort.

        Args:
            activity_id: The numeric id of the activity.
        """
        data = await call("get_activity_splits", str(activity_id))
        laps = pick(data, "lapDTOs", "splits", default=[]) or []
        if not laps:
            return f"No splits recorded for activity {activity_id}."
        use_metric = await metric()
        lines = []
        for index, lap in enumerate(laps, start=1):
            meters = pick(lap, "distance")
            seconds = pick(lap, "duration", "elapsedDuration")
            parts = [f"Split {index}"]
            if meters:
                parts.append(str(distance(meters, metric=use_metric)))
            if seconds:
                parts.append(str(duration(seconds)))
            lap_pace = pace(seconds, meters, metric=use_metric)
            if lap_pace:
                parts.append(lap_pace)
            heart = pick(lap, "averageHR")
            if heart:
                parts.append(f"{int(heart)} bpm")
            lines.append("- " + " | ".join(parts))
        return "\n".join([f"Splits for activity {activity_id}", "", *lines])

    @server.tool()
    @friendly
    async def get_personal_records() -> str:
        """Personal bests recorded by Garmin, such as fastest 5K, longest run
        and best times over standard distances.
        """
        data = await call("get_personal_record")
        records = data if isinstance(data, list) else pick(data, "personalRecords", default=[])
        if not records:
            return "No personal records found on this Garmin account."
        use_metric = await metric()
        lines = []
        for record in records:
            label = pick(record, "typeName", "activityType", default="Record")
            value = pick(record, "value")
            when = pick(record, "prStartTimeLocal", "startTimeLocal")
            shown = None
            if value is not None:
                # Garmin stores distance records in metres and time records in seconds.
                shown = (
                    str(distance(value, metric=use_metric))
                    if float(value) > 1000 and "distance" in str(label).lower()
                    else duration(value)
                )
            parts = [str(label)]
            if shown:
                parts.append(shown)
            stamp = timestamp(when)
            if stamp:
                parts.append(f"on {stamp}")
            lines.append("- " + " | ".join(parts))
        return "\n".join(["Personal records", "", *lines])

    @server.tool()
    @friendly
    async def get_date_range_summary(period: str = "last 30 days", sport: str = "") -> str:
        """Totals across a period: how many activities, total distance, total
        time and total calories. Good for "how much did I run last month".

        Args:
            period: For example "last 30 days", "this month" or "last week".
            sport: Optional sport filter such as running or cycling.
        """
        start, end = parse_range(period)
        activity_type = sport.strip().lower() or None
        data = await call("get_activities_by_date", start, end, activity_type)
        if not isinstance(data, list) or not data:
            extra = f" for {activity_type}" if activity_type else ""
            return f"No activities{extra} recorded between {start} and {end}."
        use_metric = await metric()
        total_meters = sum(float(pick(item, "distance") or 0) for item in data)
        total_seconds = sum(float(pick(item, "duration") or 0) for item in data)
        total_calories = sum(float(pick(item, "calories") or 0) for item in data)
        by_sport: dict[str, int] = {}
        for item in data:
            key = _sport(item).replace("_", " ")
            by_sport[key] = by_sport.get(key, 0) + 1
        breakdown = ", ".join(f"{count} x {name}" for name, count in sorted(by_sport.items()))
        rows = [
            ("Activities", number(len(data))),
            ("Breakdown", breakdown),
            ("Total distance", distance(total_meters, metric=use_metric) if total_meters else None),
            ("Total time", duration(total_seconds) if total_seconds else None),
            ("Total calories", number(total_calories, unit="kcal") if total_calories else None),
            (
                "Average pace",
                pace(total_seconds, total_meters, metric=use_metric)
                if activity_type in PACE_SPORTS
                else None,
            ),
        ]
        title = f"Summary from {start} to {end}"
        if activity_type:
            title += f" ({activity_type})"
        return report(title, rows)

    @server.tool()
    @friendly
    async def get_devices() -> str:
        """List the Garmin devices on this account and when each was last used."""
        data = await call("get_devices")
        if not isinstance(data, list) or not data:
            return "No Garmin devices found on this account."
        lines = []
        for device in data:
            name = pick(device, "displayName", "productDisplayName", default="Unknown device")
            software = pick(device, "softwareVersion")
            serial = pick(device, "serialNumber")
            parts = [str(name)]
            if software:
                parts.append(f"software {software}")
            if serial:
                # Only the tail, so a shared transcript does not leak a full serial.
                parts.append(f"serial ...{str(serial)[-4:]}")
            lines.append("- " + " | ".join(parts))
        return "\n".join(["Your Garmin devices", "", *lines])

    @server.tool()
    @friendly
    async def get_activities_on_day(day: str = "today") -> str:
        """List the activities recorded on one specific day.

        Args:
            day: For example "today", "yesterday" or "2026-08-18".
        """
        cdate = parse_date(day)
        data = await call("get_activities_by_date", cdate, cdate)
        if not isinstance(data, list) or not data:
            return f"No activities recorded on {cdate}."
        use_metric = await metric()
        lines = [f"- {_headline(item, use_metric=use_metric)}" for item in data]
        return "\n".join([f"Activities on {cdate}", "", *lines])


def _render_activity(data: dict, use_metric: bool) -> str:
    summary = pick(data, "summaryDTO", default={}) or {}
    merged = {**summary, **data} if isinstance(data, dict) else summary
    meters = pick(merged, "distance")
    seconds = pick(merged, "duration", "elapsedDuration")
    sport = _sport(merged)
    speed_row = (
        ("Average pace", pace(seconds, meters, metric=use_metric))
        if sport in PACE_SPORTS
        else ("Average speed", speed(pick(merged, "averageSpeed"), metric=use_metric))
    )
    rows = [
        ("Name", pick(merged, "activityName")),
        ("Sport", sport.replace("_", " ")),
        ("Started", timestamp(pick(merged, "startTimeLocal", "startTimeGMT"))),
        ("Distance", distance(meters, metric=use_metric)),
        ("Moving time", duration(pick(merged, "movingDuration"))),
        ("Total time", duration(seconds)),
        speed_row,
        ("Average heart rate", number(pick(merged, "averageHR"), unit="bpm")),
        ("Maximum heart rate", number(pick(merged, "maxHR"), unit="bpm")),
        ("Calories", number(pick(merged, "calories"), unit="kcal")),
        ("Elevation gain", elevation(pick(merged, "elevationGain"), metric=use_metric)),
        ("Elevation loss", elevation(pick(merged, "elevationLoss"), metric=use_metric)),
        (
            "Average cadence",
            number(
                pick(
                    merged,
                    "averageRunningCadenceInStepsPerMinute",
                    "averageBikingCadenceInRevPerMinute",
                ),
                unit="spm",
            ),
        ),
        ("Average power", number(pick(merged, "avgPower"), unit="W")),
        ("Aerobic training effect", number(pick(merged, "aerobicTrainingEffect"), digits=1)),
        ("Anaerobic training effect", number(pick(merged, "anaerobicTrainingEffect"), digits=1)),
        ("Perceived effort", number(pick(merged, "perceivedExertion"), unit="/10")),
    ]
    activity_id = pick(merged, "activityId")
    return report(f"Activity {activity_id}", rows, raw=merged)
