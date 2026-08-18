from conftest import run_tool

from garmin_mcp.session import GarminError

SLEEP = {
    "dailySleepDTO": {
        "sleepTimeSeconds": 27000,
        "deepSleepSeconds": 5400,
        "lightSleepSeconds": 16200,
        "remSleepSeconds": 5400,
        "awakeSleepSeconds": 900,
        "sleepStartTimestampGMT": "2026-08-17T22:30:00",
        "sleepEndTimestampGMT": "2026-08-18T06:15:00",
        "sleepScores": {"overall": {"value": 82, "qualifierKey": "good"}},
        "avgSleepStress": 18,
    },
    "restingHeartRate": 48,
    "averageSpO2Value": 96,
}

SUMMARY = {
    "totalSteps": 12345,
    "dailyStepGoal": 10000,
    "totalDistanceMeters": 9200,
    "totalKilocalories": 2450,
    "activeKilocalories": 780,
    "restingHeartRate": 48,
    "averageStressLevel": 27,
    "bodyBatteryMostRecentValue": 62,
    "sleepingSeconds": 27000,
}


class TestSleep:
    async def test_reports_the_stage_breakdown(self, server, fake_garmin):
        fake_garmin({"get_sleep_data": SLEEP})
        text = await run_tool(server, "get_sleep", day="2026-08-18")
        assert "Time asleep: 7h 30m" in text
        assert "Deep sleep: 1h 30m" in text
        assert "Sleep score: 82 /100" in text
        assert "Quality: good" in text

    async def test_last_night_is_accepted_as_a_date(self, server, fake_garmin):
        fake = fake_garmin({"get_sleep_data": SLEEP})
        await run_tool(server, "get_sleep", day="last night")
        assert fake.calls[0][0] == "get_sleep_data"

    async def test_a_night_with_no_data_is_not_reported_as_zero(self, server, fake_garmin):
        fake_garmin({"get_sleep_data": {}})
        text = await run_tool(server, "get_sleep", day="2026-08-18")
        assert "No data recorded." in text
        assert "0h" not in text


class TestDailySummary:
    async def test_renders_the_headline_numbers(self, server, fake_garmin):
        fake_garmin({"get_user_summary": SUMMARY})
        text = await run_tool(server, "get_daily_summary", day="today")
        assert "Steps: 12,345" in text
        assert "Distance: 9.20 km" in text
        assert "Resting heart rate: 48 bpm" in text

    async def test_uses_miles_for_an_imperial_account(self, server, fake_garmin):
        fake_garmin({"get_user_summary": SUMMARY}, unit="statute_us")
        text = await run_tool(server, "get_daily_summary", day="today")
        assert "5.72 mi" in text
        assert "km" not in text

    async def test_absent_metrics_are_omitted_entirely(self, server, fake_garmin):
        fake_garmin({"get_user_summary": {"totalSteps": 100}})
        text = await run_tool(server, "get_daily_summary", day="today")
        assert "Steps: 100" in text
        assert "Body battery" not in text


class TestSteps:
    async def test_totals_and_averages_the_period(self, server, fake_garmin):
        fake_garmin(
            {
                "get_daily_steps": [
                    {"calendarDate": "2026-08-16", "totalSteps": 10000, "stepGoal": 9000},
                    {"calendarDate": "2026-08-17", "totalSteps": 12000},
                    {"calendarDate": "2026-08-18", "totalSteps": 8000},
                ]
            }
        )
        text = await run_tool(server, "get_steps", period="last 3 days")
        assert "Total: 30,000 steps" in text
        assert "Daily average: 10,000 steps" in text
        assert "(goal 9,000)" in text

    async def test_empty_period_says_so(self, server, fake_garmin):
        fake_garmin({"get_daily_steps": []})
        text = await run_tool(server, "get_steps", period="last 7 days")
        assert "No step data" in text


class TestOtherHealthTools:
    async def test_hrv_includes_the_baseline_range(self, server, fake_garmin):
        fake_garmin(
            {
                "get_hrv_data": {
                    "hrvSummary": {
                        "lastNightAvg": 62,
                        "status": "BALANCED",
                        "baseline": {"balancedLow": 55, "balancedUpper": 75},
                    }
                }
            }
        )
        text = await run_tool(server, "get_hrv", day="today")
        assert "Last night average: 62 ms" in text
        assert "55-75 ms" in text

    async def test_hrv_explains_when_the_watch_recorded_nothing(self, server, fake_garmin):
        fake_garmin({"get_hrv_data": None})
        text = await run_tool(server, "get_hrv", day="today")
        assert "compatible watch" in text

    async def test_training_readiness_reads_the_first_entry(self, server, fake_garmin):
        fake_garmin(
            {
                "get_training_readiness": [
                    {"score": 74, "level": "READY", "feedbackShort": "Good to go"}
                ]
            }
        )
        text = await run_tool(server, "get_training_readiness", day="today")
        assert "Readiness score: 74 /100" in text
        assert "Level: READY" in text

    async def test_body_battery_shows_charge_and_drain(self, server, fake_garmin):
        fake_garmin({"get_body_battery": [{"date": "2026-08-18", "charged": 55, "drained": -40}]})
        text = await run_tool(server, "get_body_battery", period="last 7 days")
        assert "charged +55" in text
        assert "drained -40" in text

    async def test_vo2max_survives_a_failing_training_status(self, server, fake_garmin):
        # Training status is a bonus lookup; losing it must not cost the user
        # the metrics that did come back.
        fake_garmin(
            {
                "get_max_metrics": [{"generic": {"vo2MaxPreciseValue": 52.4, "fitnessAge": 31}}],
                "get_training_status": GarminError("device does not report this"),
            }
        )
        text = await run_tool(server, "get_vo2max_and_fitness", day="today")
        assert "VO2 max (running): 52.4" in text
        assert "Fitness age: 31" in text
        assert "Training status" not in text

    async def test_vo2max_includes_training_status_when_available(self, server, fake_garmin):
        fake_garmin(
            {
                "get_max_metrics": [{"generic": {"vo2MaxPreciseValue": 52.4}}],
                "get_training_status": {
                    "mostRecentTrainingStatus": {"trainingStatusFeedbackPhrase": "PRODUCTIVE"}
                },
            }
        )
        text = await run_tool(server, "get_vo2max_and_fitness", day="today")
        assert "Training status: PRODUCTIVE" in text

    async def test_weight_history_reports_the_change(self, server, fake_garmin):
        fake_garmin(
            {
                "get_weigh_ins": {
                    "dailyWeightSummaries": [
                        {"summaryDate": "2026-08-01", "latestWeight": {"weight": 76000}},
                        {"summaryDate": "2026-08-18", "latestWeight": {"weight": 74500}},
                    ]
                }
            }
        )
        text = await run_tool(server, "get_weight_history", period="this month")
        assert "76.0 kg" in text
        assert "down 1.5 kg" in text


class TestWrites:
    async def test_logging_a_weight_sends_kilograms(self, server, fake_garmin):
        fake = fake_garmin({"add_weigh_in": {}})
        text = await run_tool(server, "log_weight", kilograms=74.5, day="2026-08-18")
        assert fake.calls[0][0] == "add_weigh_in"
        assert fake.calls[0][1][:2] == (74.5, "kg")
        assert "74.5 kg" in text

    async def test_an_absurd_weight_is_refused_without_calling_garmin(self, server, fake_garmin):
        fake = fake_garmin({})
        text = await run_tool(server, "log_weight", kilograms=900)
        assert "does not look right" in text
        assert fake.calls == []

    async def test_logging_hydration_reports_the_amount(self, server, fake_garmin):
        fake = fake_garmin({"add_hydration_data": {}})
        text = await run_tool(server, "log_hydration", milliliters=250, day="today")
        assert fake.calls[0][0] == "add_hydration_data"
        assert "250 ml" in text
