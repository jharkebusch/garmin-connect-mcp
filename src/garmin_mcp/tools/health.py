"""Daily health and wellness tools.

Deliberately no ``from __future__ import annotations`` here: MCP builds each
tool's JSON schema from the live annotations, so they must stay real objects.
"""

from contextlib import suppress
from typing import Any

from ..dates import parse_date, parse_range
from ..format import (
    duration,
    hours_minutes,
    number,
    pick,
    report,
    timestamp,
    weight,
)
from ..session import GarminError, call, friendly, metric


def register(server: Any) -> None:
    @server.tool()
    @friendly
    async def get_daily_summary(day: str = "today") -> str:
        """Overall summary of one day: steps, calories, resting heart rate, stress,
        body battery, intensity minutes and sleep length.

        Start here when the user asks "how was my day" or "how am I doing today".

        Args:
            day: A day such as "today", "yesterday", "3 days ago" or "2026-08-18".
        """
        cdate = parse_date(day)
        data = await call("get_user_summary", cdate)
        use_metric = await metric()
        distance_m = pick(data, "totalDistanceMeters", "distanceMeters")
        rows = [
            ("Steps", number(pick(data, "totalSteps"))),
            ("Step goal", number(pick(data, "dailyStepGoal", "stepGoal"))),
            (
                "Distance",
                None
                if distance_m is None
                else (
                    f"{distance_m / 1000:.2f} km"
                    if use_metric
                    else f"{distance_m / 1609.344:.2f} mi"
                ),
            ),
            ("Total calories", number(pick(data, "totalKilocalories"), unit="kcal")),
            ("Active calories", number(pick(data, "activeKilocalories"), unit="kcal")),
            ("Floors climbed", number(pick(data, "floorsAscended"))),
            ("Resting heart rate", number(pick(data, "restingHeartRate"), unit="bpm")),
            ("Lowest heart rate", number(pick(data, "minHeartRate"), unit="bpm")),
            ("Highest heart rate", number(pick(data, "maxHeartRate"), unit="bpm")),
            ("Average stress", number(pick(data, "averageStressLevel"), unit="/100")),
            ("Body battery now", number(pick(data, "bodyBatteryMostRecentValue"))),
            ("Body battery high", number(pick(data, "bodyBatteryHighestValue"))),
            ("Body battery low", number(pick(data, "bodyBatteryLowestValue"))),
            (
                "Moderate intensity minutes",
                number(pick(data, "moderateIntensityMinutes"), unit="min"),
            ),
            (
                "Vigorous intensity minutes",
                number(pick(data, "vigorousIntensityMinutes"), unit="min"),
            ),
            ("Sleep", hours_minutes(pick(data, "sleepingSeconds"))),
            ("Average SpO2", number(pick(data, "averageSpo2"), unit="%")),
        ]
        return report(f"Daily summary for {cdate}", rows, raw=data)

    @server.tool()
    @friendly
    async def get_sleep(day: str = "last night") -> str:
        """Sleep for one night: total time, deep/light/REM/awake breakdown,
        sleep score, resting heart rate and breathing.

        Args:
            day: The night's date. "last night" and "today" both mean the most
                recent night. Also accepts "yesterday" or "2026-08-18".
        """
        cdate = parse_date("today" if str(day).strip().lower() == "last night" else day)
        data = await call("get_sleep_data", cdate)
        summary = pick(data, "dailySleepDTO", default={}) or {}
        scores = pick(summary, "sleepScores", default={}) or {}
        overall = pick(scores, "overall", default={}) or {}
        rows = [
            ("Time asleep", hours_minutes(pick(summary, "sleepTimeSeconds"))),
            ("Deep sleep", hours_minutes(pick(summary, "deepSleepSeconds"))),
            ("Light sleep", hours_minutes(pick(summary, "lightSleepSeconds"))),
            ("REM sleep", hours_minutes(pick(summary, "remSleepSeconds"))),
            ("Awake", hours_minutes(pick(summary, "awakeSleepSeconds"))),
            ("Sleep score", number(pick(overall, "value"), unit="/100")),
            ("Quality", pick(overall, "qualifierKey")),
            ("Went to sleep", timestamp(pick(summary, "sleepStartTimestampGMT"), time_only=True)),
            ("Woke up", timestamp(pick(summary, "sleepEndTimestampGMT"), time_only=True)),
            (
                "Resting heart rate",
                number(
                    pick(data, "restingHeartRate") or pick(summary, "restingHeartRate"), unit="bpm"
                ),
            ),
            ("Average SpO2", number(pick(data, "averageSpO2Value", "averageSpO2"), unit="%")),
            (
                "Average breathing rate",
                number(pick(data, "avgSleepRespirationValue"), unit="breaths/min", digits=1),
            ),
            ("Average stress during sleep", number(pick(summary, "avgSleepStress"), digits=0)),
        ]
        return report(f"Sleep for the night of {cdate}", rows, raw=data)

    @server.tool()
    @friendly
    async def get_steps(period: str = "last 7 days") -> str:
        """Daily step counts over a period, with the total and daily average.

        Args:
            period: For example "last 7 days", "this month", "last week",
                or "2026-08-01 to 2026-08-18".
        """
        start, end = parse_range(period)
        data = await call("get_daily_steps", start, end)
        if not isinstance(data, list) or not data:
            return f"No step data recorded between {start} and {end}."
        lines = []
        total = 0
        counted = 0
        for entry in data:
            steps = pick(entry, "totalSteps", "steps")
            when = pick(entry, "calendarDate", "statisticsStartDate", default="?")
            goal = pick(entry, "stepGoal", "totalStepGoal")
            if steps is None:
                continue
            total += int(steps)
            counted += 1
            suffix = f" (goal {int(goal):,})" if goal else ""
            lines.append(f"- {when}: {int(steps):,} steps{suffix}")
        if not counted:
            return f"No step data recorded between {start} and {end}."
        average = total // counted
        header = f"Steps from {start} to {end}"
        return "\n".join(
            [header, "", *lines, "", f"Total: {total:,} steps", f"Daily average: {average:,} steps"]
        )

    @server.tool()
    @friendly
    async def get_heart_rate(day: str = "today") -> str:
        """Heart rate for one day: resting, lowest, highest and the seven-day
        average resting heart rate.

        Args:
            day: For example "today", "yesterday" or "2026-08-18".
        """
        cdate = parse_date(day)
        data = await call("get_heart_rates", cdate)
        rows = [
            ("Resting heart rate", number(pick(data, "restingHeartRate"), unit="bpm")),
            ("Lowest", number(pick(data, "minHeartRate"), unit="bpm")),
            ("Highest", number(pick(data, "maxHeartRate"), unit="bpm")),
            (
                "7-day average resting",
                number(pick(data, "lastSevenDaysAvgRestingHeartRate"), unit="bpm"),
            ),
        ]
        return report(f"Heart rate for {cdate}", rows, raw=data)

    @server.tool()
    @friendly
    async def get_hrv(day: str = "today") -> str:
        """Heart rate variability (HRV) for one night, with Garmin's status and
        the personal baseline range. HRV is a recovery and stress indicator.

        Args:
            day: For example "today", "yesterday" or "2026-08-18".
        """
        cdate = parse_date(day)
        data = await call("get_hrv_data", cdate)
        if not data:
            return f"No HRV recorded for {cdate}. HRV needs a compatible watch worn overnight."
        summary = pick(data, "hrvSummary", default={}) or {}
        baseline = pick(summary, "baseline", default={}) or {}
        rows = [
            ("Last night average", number(pick(summary, "lastNightAvg"), unit="ms")),
            ("Highest 5-minute value", number(pick(summary, "lastNight5MinHigh"), unit="ms")),
            ("Status", pick(summary, "status")),
            ("What Garmin says", pick(summary, "feedbackPhrase")),
            (
                "Baseline balanced range",
                None
                if not baseline.get("balancedLow")
                else f"{baseline.get('balancedLow')}-{baseline.get('balancedUpper')} ms",
            ),
        ]
        return report(f"HRV for the night of {cdate}", rows, raw=data)

    @server.tool()
    @friendly
    async def get_stress(day: str = "today") -> str:
        """Stress levels for one day: average and highest, plus how the day split
        between rest, low, medium and high stress.

        Args:
            day: For example "today", "yesterday" or "2026-08-18".
        """
        cdate = parse_date(day)
        data = await call("get_all_day_stress", cdate)
        aggregator = pick(data, "bodyBatteryValueDescriptorDTOList")
        rows = [
            (
                "Average stress",
                number(pick(data, "avgStressLevel", "averageStressLevel"), unit="/100"),
            ),
            ("Highest stress", number(pick(data, "maxStressLevel"), unit="/100")),
            ("Time at rest", duration(pick(data, "restStressDuration"))),
            ("Time at low stress", duration(pick(data, "lowStressDuration"))),
            ("Time at medium stress", duration(pick(data, "mediumStressDuration"))),
            ("Time at high stress", duration(pick(data, "highStressDuration"))),
        ]
        if aggregator is None and all(value is None for _, value in rows):
            data = await call("get_stress_data", cdate)
            rows = [
                ("Average stress", number(pick(data, "avgStressLevel"), unit="/100")),
                ("Highest stress", number(pick(data, "maxStressLevel"), unit="/100")),
            ]
        return report(f"Stress for {cdate}", rows, raw=data)

    @server.tool()
    @friendly
    async def get_body_battery(period: str = "last 7 days") -> str:
        """Body Battery energy levels, showing how much was charged and drained
        each day. Higher is more energy available.

        Args:
            period: For example "last 7 days", "this week" or "2026-08-01 to 2026-08-18".
        """
        start, end = parse_range(period)
        data = await call("get_body_battery", start, end)
        if not isinstance(data, list) or not data:
            return f"No Body Battery data recorded between {start} and {end}."
        lines = []
        for entry in data:
            when = pick(entry, "date", "calendarDate", default="?")
            charged = pick(entry, "charged")
            drained = pick(entry, "drained")
            parts = []
            if charged is not None:
                parts.append(f"charged +{int(charged)}")
            if drained is not None:
                parts.append(f"drained -{abs(int(drained))}")
            lines.append(f"- {when}: {', '.join(parts) if parts else 'no data'}")
        return "\n".join([f"Body Battery from {start} to {end}", "", *lines])

    @server.tool()
    @friendly
    async def get_training_readiness(day: str = "today") -> str:
        """Garmin's training readiness score: how prepared the body is to train
        hard today, and which factors are helping or hurting.

        Args:
            day: For example "today", "yesterday" or "2026-08-18".
        """
        cdate = parse_date(day)
        data = await call("get_training_readiness", cdate)
        entry = data[0] if isinstance(data, list) and data else data
        if not entry:
            return f"No training readiness score for {cdate}. It needs a compatible Garmin watch."
        rows = [
            ("Readiness score", number(pick(entry, "score"), unit="/100")),
            ("Level", pick(entry, "level")),
            ("What Garmin says", pick(entry, "feedbackLong", "feedbackShort")),
            ("Sleep score contribution", number(pick(entry, "sleepScore"))),
            (
                "Recovery time left",
                None
                if pick(entry, "recoveryTime") is None
                else hours_minutes(pick(entry, "recoveryTime") * 60),
            ),
            ("HRV factor", number(pick(entry, "hrvFactorPercent"), unit="%")),
            ("Acute training load", number(pick(entry, "acuteLoad"))),
        ]
        return report(f"Training readiness for {cdate}", rows, raw=entry)

    @server.tool()
    @friendly
    async def get_vo2max_and_fitness(day: str = "today") -> str:
        """VO2 max (aerobic fitness), fitness age and training status.

        Args:
            day: For example "today" or "2026-08-18".
        """
        cdate = parse_date(day)
        data = await call("get_max_metrics", cdate)
        entry = data[0] if isinstance(data, list) and data else data
        generic = pick(entry, "generic", default={}) or {}
        cycling = pick(entry, "cycling", default={}) or {}
        rows = [
            (
                "VO2 max (running)",
                number(pick(generic, "vo2MaxPreciseValue", "vo2MaxValue"), digits=1),
            ),
            (
                "VO2 max (cycling)",
                number(pick(cycling, "vo2MaxPreciseValue", "vo2MaxValue"), digits=1),
            ),
            ("Fitness age", number(pick(generic, "fitnessAge"))),
        ]
        # Training status is a bonus on top of VO2 max; not every device records
        # it, so a failure here must not cost the user the metrics we do have.
        with suppress(GarminError):
            status = await call("get_training_status", cdate)
            most_recent = pick(status, "mostRecentTrainingStatus", default={}) or {}
            rows.append(("Training status", pick(most_recent, "trainingStatusFeedbackPhrase")))
        return report(f"Fitness metrics for {cdate}", rows, raw=entry)

    @server.tool()
    @friendly
    async def get_weight_history(period: str = "last 30 days") -> str:
        """Recorded body weight over a period, with the change from first to last.

        Args:
            period: For example "last 30 days", "this month" or
                "2026-01-01 to 2026-08-18".
        """
        start, end = parse_range(period)
        data = await call("get_weigh_ins", start, end)
        use_metric = await metric()
        summaries = pick(data, "dailyWeightSummaries", default=[]) or []
        entries = []
        for summary in summaries:
            grams = pick(summary, "latestWeight", default={})
            grams = pick(grams, "weight") if isinstance(grams, dict) else None
            if grams is None:
                grams = pick(summary, "weight", "minWeight")
            when = pick(summary, "summaryDate", "calendarDate", default="?")
            if grams is not None:
                entries.append((when, float(grams)))
        if not entries:
            return f"No weight recorded between {start} and {end}."
        entries.sort()
        lines = [f"- {when}: {weight(grams, metric=use_metric)}" for when, grams in entries]
        change = entries[-1][1] - entries[0][1]
        direction = "up" if change > 0 else "down" if change < 0 else "unchanged"
        change_text = weight(abs(change), metric=use_metric)
        footer = (
            f"Change over this period: {direction}"
            if change == 0
            else f"Change over this period: {direction} {change_text}"
        )
        return "\n".join([f"Weight from {start} to {end}", "", *lines, "", footer])

    @server.tool()
    @friendly
    async def log_weight(kilograms: float, day: str = "today") -> str:
        """Record a body weight measurement in Garmin Connect.

        Args:
            kilograms: The weight in kilograms, for example 74.5.
            day: When it was measured. Defaults to today.
        """
        if kilograms <= 0 or kilograms > 500:
            return (
                "That weight does not look right. "
                "Please give a value in kilograms, for example 74.5."
            )
        cdate = parse_date(day)
        await call("add_weigh_in", kilograms, "kg", f"{cdate}T12:00:00")
        use_metric = await metric()
        shown = weight(kilograms * 1000, metric=use_metric)
        return f"Recorded a weight of {shown} in Garmin Connect for {cdate}."

    @server.tool()
    @friendly
    async def log_hydration(milliliters: float, day: str = "today") -> str:
        """Add drunk water to the hydration log in Garmin Connect.

        Args:
            milliliters: How much water to add, in millilitres. 250 is a glass.
            day: Which day to add it to. Defaults to today.
        """
        if milliliters == 0:
            return "Please give an amount of water in millilitres, for example 250."
        cdate = parse_date(day)
        await call("add_hydration_data", float(milliliters), None, cdate)
        return f"Added {int(milliliters)} ml of water to your Garmin hydration log for {cdate}."
