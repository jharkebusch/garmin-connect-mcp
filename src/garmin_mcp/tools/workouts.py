"""Planned workout tools -- the training templates stored in Garmin Connect.

These are workout *plans* you send to a watch, not recorded activities.
"""

from typing import Any

from ..dates import parse_date
from ..format import duration, pick, report
from ..session import GarminError, call, friendly

SPORTS = {
    "running": "RunningWorkout",
    "cycling": "CyclingWorkout",
    "walking": "WalkingWorkout",
    "swimming": "SwimmingWorkout",
    "hiking": "HikingWorkout",
}

STEP_BUILDERS = {
    "warmup": "create_warmup_step",
    "interval": "create_interval_step",
    "recovery": "create_recovery_step",
    "cooldown": "create_cooldown_step",
}


def register(server: Any) -> None:
    @server.tool()
    @friendly
    async def list_workouts(limit: int = 25) -> str:
        """List the saved workout plans in Garmin Connect.

        Args:
            limit: Most workouts to list. Defaults to 25.
        """
        data = await call("get_workouts", 0, max(1, min(int(limit), 100)))
        if not isinstance(data, list) or not data:
            return "There are no saved workouts on this Garmin account."
        lines = []
        for workout in data:
            name = pick(workout, "workoutName", default="Untitled")
            sport = pick(workout, "sportType", default={}) or {}
            sport_name = str(pick(sport, "sportTypeKey", default="")).replace("_", " ")
            estimated = duration(pick(workout, "estimatedDurationInSecs"))
            workout_id = pick(workout, "workoutId")
            parts = [str(name)]
            if sport_name:
                parts.append(sport_name)
            if estimated:
                parts.append(estimated)
            if workout_id is not None:
                parts.append(f"id {workout_id}")
            lines.append("- " + " | ".join(parts))
        return "\n".join(["Saved workouts", "", *lines])

    @server.tool()
    @friendly
    async def get_workout(workout_id: int) -> str:
        """Show the steps of one saved workout plan.

        Args:
            workout_id: The numeric id, from list_workouts.
        """
        data = await call("get_workout_by_id", workout_id)
        if not data:
            return f"No workout found with id {workout_id}."
        sport = pick(data, "sportType", default={}) or {}
        rows = [
            ("Name", pick(data, "workoutName")),
            ("Sport", str(pick(sport, "sportTypeKey", default="")).replace("_", " ")),
            ("Estimated duration", duration(pick(data, "estimatedDurationInSecs"))),
            ("Description", pick(data, "description")),
        ]
        steps = []
        for segment in pick(data, "workoutSegments", default=[]) or []:
            for step in pick(segment, "workoutSteps", default=[]) or []:
                kind = pick(step, "stepType", default={}) or {}
                label = str(pick(kind, "stepTypeKey", default="step")).replace("_", " ")
                value = pick(step, "endConditionValue")
                condition = pick(step, "endCondition", default={}) or {}
                unit = str(pick(condition, "conditionTypeKey", default=""))
                if value and unit == "time":
                    steps.append(f"{label} for {duration(value)}")
                elif value and unit == "distance":
                    steps.append(f"{label} for {float(value) / 1000:.2f} km")
                else:
                    steps.append(label)
        body = report(f"Workout {workout_id}", rows, raw=data)
        if steps:
            body += "\n\nSteps:\n" + "\n".join(f"{i}. {s}" for i, s in enumerate(steps, start=1))
        return body

    @server.tool()
    @friendly
    async def get_scheduled_workouts(period: str = "next 30 days") -> str:
        """Show workouts scheduled on the Garmin training calendar.

        Args:
            period: Currently informational; all upcoming scheduled workouts
                are returned.
        """
        data = await call("get_scheduled_workouts")
        items = data if isinstance(data, list) else pick(data, "calendarItems", default=[])
        if not items:
            return "There are no workouts scheduled on your Garmin calendar."
        lines = []
        for item in items:
            when = pick(item, "date", "scheduledDate", default="?")
            name = pick(item, "title", "workoutName", default="Workout")
            scheduled_id = pick(item, "id", "scheduleId")
            suffix = f" (scheduled id {scheduled_id})" if scheduled_id is not None else ""
            lines.append(f"- {when}: {name}{suffix}")
        return "\n".join(["Scheduled workouts", "", *lines])

    @server.tool()
    @friendly
    async def create_workout(
        name: str,
        sport: str = "running",
        warmup_minutes: float = 10,
        interval_minutes: float = 0,
        recovery_minutes: float = 0,
        repeats: int = 0,
        cooldown_minutes: float = 10,
    ) -> str:
        """Create a new time-based workout plan in Garmin Connect.

        Builds a warm-up, an optional repeated interval and recovery block, and
        a cool-down. Set interval_minutes and repeats to 0 for a steady session.

        Args:
            name: What to call the workout, for example "Tuesday intervals".
            sport: One of running, cycling, walking, swimming, hiking.
            warmup_minutes: Length of the warm-up. Use 0 to skip it.
            interval_minutes: Length of each hard interval. Use 0 for a steady session.
            recovery_minutes: Length of the easy recovery after each interval.
            repeats: How many times to repeat the interval and recovery pair.
            cooldown_minutes: Length of the cool-down. Use 0 to skip it.
        """
        sport_key = sport.strip().lower()
        if sport_key not in SPORTS:
            return f"'{sport}' is not a supported sport. Choose one of: {', '.join(SPORTS)}."
        if not name.strip():
            return "Please give the workout a name."

        try:
            from garminconnect import workout as workout_module
        except ImportError:  # pragma: no cover - pydantic ships with our dependencies
            raise GarminError(
                "Creating workouts needs the optional workout support. "
                "Re-run the installer to repair the installation."
            ) from None

        steps = []
        order = 1
        if warmup_minutes > 0:
            steps.append(workout_module.create_warmup_step(warmup_minutes * 60, order))
            order += 1
        if interval_minutes > 0 and repeats > 0:
            for _ in range(max(1, min(int(repeats), 30))):
                steps.append(workout_module.create_interval_step(interval_minutes * 60, order))
                order += 1
                if recovery_minutes > 0:
                    steps.append(workout_module.create_recovery_step(recovery_minutes * 60, order))
                    order += 1
        elif interval_minutes > 0:
            steps.append(workout_module.create_interval_step(interval_minutes * 60, order))
            order += 1
        if cooldown_minutes > 0:
            steps.append(workout_module.create_cooldown_step(cooldown_minutes * 60, order))
            order += 1
        if not steps:
            return "That workout would be empty. Give at least one part a length in minutes."

        total_seconds = int(sum(float(step.endConditionValue or 0) for step in steps))
        model = getattr(workout_module, SPORTS[sport_key])
        # Each sport model carries its own sportType default; read it from the
        # field rather than instantiating the model, which needs required fields.
        sport_type = model.model_fields["sportType"].default_factory()
        plan = model(
            workoutName=name.strip(),
            estimatedDurationInSecs=total_seconds,
            workoutSegments=[
                workout_module.WorkoutSegment(
                    segmentOrder=1,
                    sportType=sport_type,
                    workoutSteps=steps,
                )
            ],
        )
        result = await call(f"upload_{sport_key}_workout", plan)
        new_id = pick(result, "workoutId")
        return (
            f"Created the {sport_key} workout '{name.strip()}' "
            f"({duration(total_seconds)}, {len(steps)} steps) in Garmin Connect."
            + (f"\n\nIts id is {new_id}, so it can be scheduled onto a date." if new_id else "")
        )

    @server.tool()
    @friendly
    async def schedule_workout(workout_id: int, day: str) -> str:
        """Put an existing workout plan on the Garmin training calendar.

        Args:
            workout_id: The numeric id, from list_workouts or create_workout.
            day: The date to schedule it on, for example "tomorrow" or "2026-08-20".
        """
        cdate = parse_date(day)
        await call("schedule_workout", workout_id, cdate)
        return f"Scheduled workout {workout_id} for {cdate}. It will sync to your watch."
