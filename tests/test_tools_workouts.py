from conftest import run_tool


class TestListing:
    async def test_lists_saved_workouts(self, server, fake_garmin):
        fake_garmin(
            {
                "get_workouts": [
                    {
                        "workoutId": 555,
                        "workoutName": "Tuesday intervals",
                        "sportType": {"sportTypeKey": "running"},
                        "estimatedDurationInSecs": 3600,
                    }
                ]
            }
        )
        text = await run_tool(server, "list_workouts")
        assert "Tuesday intervals" in text
        assert "id 555" in text
        assert "1h 0m 0s" in text

    async def test_no_workouts_says_so(self, server, fake_garmin):
        fake_garmin({"get_workouts": []})
        assert "no saved workouts" in await run_tool(server, "list_workouts")

    async def test_shows_the_steps_of_one_workout(self, server, fake_garmin):
        fake_garmin(
            {
                "get_workout_by_id": {
                    "workoutName": "Easy run",
                    "sportType": {"sportTypeKey": "running"},
                    "workoutSegments": [
                        {
                            "workoutSteps": [
                                {
                                    "stepType": {"stepTypeKey": "warmup"},
                                    "endCondition": {"conditionTypeKey": "time"},
                                    "endConditionValue": 600,
                                },
                                {
                                    "stepType": {"stepTypeKey": "interval"},
                                    "endCondition": {"conditionTypeKey": "distance"},
                                    "endConditionValue": 5000,
                                },
                            ]
                        }
                    ],
                }
            }
        )
        text = await run_tool(server, "get_workout", workout_id=1)
        assert "1. warmup for 10m 0s" in text
        assert "2. interval for 5.00 km" in text

    async def test_scheduled_workouts_are_listed(self, server, fake_garmin):
        fake_garmin({"get_scheduled_workouts": [{"date": "2026-08-20", "title": "Long run"}]})
        text = await run_tool(server, "get_scheduled_workouts")
        assert "2026-08-20: Long run" in text


class TestCreate:
    async def test_builds_an_interval_session_with_the_right_steps(self, server, fake_garmin):
        fake = fake_garmin({"upload_running_workout": {"workoutId": 4242}})
        text = await run_tool(
            server,
            "create_workout",
            name="Tuesday intervals",
            sport="running",
            warmup_minutes=10,
            interval_minutes=3,
            recovery_minutes=2,
            repeats=4,
            cooldown_minutes=10,
        )
        method, args, _ = fake.calls[0]
        assert method == "upload_running_workout"
        plan = args[0]
        steps = plan.workoutSegments[0].workoutSteps
        # warmup + (interval + recovery) x 4 + cooldown
        assert len(steps) == 10
        assert plan.estimatedDurationInSecs == (10 + (3 + 2) * 4 + 10) * 60
        assert "4242" in text

    async def test_a_steady_session_has_no_intervals(self, server, fake_garmin):
        fake = fake_garmin({"upload_cycling_workout": {"workoutId": 1}})
        await run_tool(
            server,
            "create_workout",
            name="Steady ride",
            sport="cycling",
            warmup_minutes=10,
            interval_minutes=0,
            repeats=0,
            cooldown_minutes=5,
        )
        steps = fake.calls[0][1][0].workoutSegments[0].workoutSteps
        assert len(steps) == 2

    async def test_step_order_is_sequential(self, server, fake_garmin):
        fake = fake_garmin({"upload_running_workout": {"workoutId": 1}})
        await run_tool(
            server,
            "create_workout",
            name="Session",
            interval_minutes=1,
            recovery_minutes=1,
            repeats=3,
        )
        steps = fake.calls[0][1][0].workoutSegments[0].workoutSteps
        assert [s.stepOrder for s in steps] == list(range(1, len(steps) + 1))

    async def test_an_unsupported_sport_is_refused(self, server, fake_garmin):
        fake = fake_garmin({})
        text = await run_tool(server, "create_workout", name="Yoga", sport="yoga")
        assert "not a supported sport" in text
        assert fake.calls == []

    async def test_an_empty_workout_is_refused(self, server, fake_garmin):
        fake = fake_garmin({})
        text = await run_tool(
            server,
            "create_workout",
            name="Nothing",
            warmup_minutes=0,
            interval_minutes=0,
            cooldown_minutes=0,
        )
        assert "would be empty" in text
        assert fake.calls == []

    async def test_a_blank_name_is_refused(self, server, fake_garmin):
        fake = fake_garmin({})
        assert "give the workout a name" in await run_tool(server, "create_workout", name="   ")
        assert fake.calls == []

    async def test_repeats_are_capped_so_a_typo_cannot_explode(self, server, fake_garmin):
        fake = fake_garmin({"upload_running_workout": {"workoutId": 1}})
        await run_tool(server, "create_workout", name="Many", interval_minutes=1, repeats=5000)
        steps = fake.calls[0][1][0].workoutSegments[0].workoutSteps
        assert len(steps) <= 32


class TestSchedule:
    async def test_schedules_on_a_parsed_date(self, server, fake_garmin):
        fake = fake_garmin({"schedule_workout": {}})
        text = await run_tool(server, "schedule_workout", workout_id=555, day="2026-08-20")
        assert fake.calls[0][1] == (555, "2026-08-20")
        assert "2026-08-20" in text

    async def test_an_unparseable_date_is_explained_not_raised(self, server, fake_garmin):
        fake = fake_garmin({"schedule_workout": {}})
        text = await run_tool(server, "schedule_workout", workout_id=555, day="whenever")
        assert "Could not understand" in text
        assert fake.calls == []
