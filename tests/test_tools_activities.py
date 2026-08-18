from conftest import run_tool

RUN = {
    "activityId": 998877,
    "activityName": "Morning Run",
    "activityType": {"typeKey": "running"},
    "startTimeLocal": "2026-08-18T07:02:00",
    "distance": 10000,
    "duration": 3000,
    "movingDuration": 2950,
    "averageHR": 152,
    "maxHR": 176,
    "calories": 720,
    "elevationGain": 85,
    "aerobicTrainingEffect": 3.4,
}

RIDE = {
    "activityId": 112233,
    "activityName": "Evening Ride",
    "activityType": {"typeKey": "cycling"},
    "startTimeLocal": "2026-08-17T18:00:00",
    "distance": 40000,
    "duration": 4800,
    "averageSpeed": 8.33,
    "calories": 900,
}


class TestListing:
    async def test_lists_activities_with_their_ids(self, server, fake_garmin):
        fake_garmin({"get_activities_by_date": [RUN, RIDE]})
        text = await run_tool(server, "list_activities", period="last 30 days")
        assert "Morning Run (running)" in text
        assert "10.00 km" in text
        assert "id 998877" in text

    async def test_passes_the_sport_filter_to_garmin(self, server, fake_garmin):
        fake = fake_garmin({"get_activities_by_date": [RUN]})
        await run_tool(server, "list_activities", period="last 7 days", sport="Running")
        assert fake.calls[0][1][2] == "running"

    async def test_an_empty_sport_means_no_filter(self, server, fake_garmin):
        fake = fake_garmin({"get_activities_by_date": [RUN]})
        await run_tool(server, "list_activities", period="last 7 days")
        assert fake.calls[0][1][2] is None

    async def test_limit_caps_the_list_and_says_so(self, server, fake_garmin):
        fake_garmin({"get_activities_by_date": [RUN] * 40})
        text = await run_tool(server, "list_activities", period="last 30 days", limit=5)
        assert "40 activities" in text
        assert "showing the first 5" in text
        assert text.count("Morning Run") == 5

    async def test_nothing_recorded_says_so(self, server, fake_garmin):
        fake_garmin({"get_activities_by_date": []})
        text = await run_tool(server, "list_activities", period="last 7 days")
        assert "No activities" in text

    async def test_activities_on_a_single_day_query_that_day_twice(self, server, fake_garmin):
        fake = fake_garmin({"get_activities_by_date": [RUN]})
        await run_tool(server, "get_activities_on_day", day="2026-08-18")
        assert fake.calls[0][1][:2] == ("2026-08-18", "2026-08-18")


class TestDetails:
    async def test_a_run_is_described_with_pace(self, server, fake_garmin):
        fake_garmin({"get_activity": RUN})
        text = await run_tool(server, "get_activity_details", activity_id=998877)
        assert "Average pace: 5:00 /km" in text
        assert "Average heart rate: 152 bpm" in text
        assert "Elevation gain: 85 m" in text

    async def test_a_ride_is_described_with_speed_not_pace(self, server, fake_garmin):
        fake_garmin({"get_activity": RIDE})
        text = await run_tool(server, "get_activity_details", activity_id=112233)
        assert "Average speed: 30.0 km/h" in text
        assert "pace" not in text.lower()

    async def test_the_most_recent_activity(self, server, fake_garmin):
        fake_garmin({"get_last_activity": RUN})
        text = await run_tool(server, "get_last_activity")
        assert "Morning Run" in text

    async def test_an_account_with_no_activities(self, server, fake_garmin):
        fake_garmin({"get_last_activity": None})
        text = await run_tool(server, "get_last_activity")
        assert "No activities" in text

    async def test_summary_fields_are_merged_in(self, server, fake_garmin):
        # Some Garmin endpoints nest the numbers under summaryDTO.
        fake_garmin(
            {"get_activity": {"activityId": 1, "summaryDTO": {"distance": 5000, "duration": 1500}}}
        )
        text = await run_tool(server, "get_activity_details", activity_id=1)
        assert "5.00 km" in text


class TestSplits:
    async def test_renders_each_split(self, server, fake_garmin):
        fake_garmin(
            {
                "get_activity_splits": {
                    "lapDTOs": [
                        {"distance": 1000, "duration": 300, "averageHR": 148},
                        {"distance": 1000, "duration": 290, "averageHR": 155},
                    ]
                }
            }
        )
        text = await run_tool(server, "get_activity_splits", activity_id=1)
        assert "Split 1" in text
        assert "5:00 /km" in text
        assert "155 bpm" in text

    async def test_no_splits_says_so(self, server, fake_garmin):
        fake_garmin({"get_activity_splits": {}})
        text = await run_tool(server, "get_activity_splits", activity_id=1)
        assert "No splits" in text


class TestSummaryAndDevices:
    async def test_totals_across_the_period(self, server, fake_garmin):
        fake_garmin({"get_activities_by_date": [RUN, RIDE]})
        text = await run_tool(server, "get_date_range_summary", period="last 30 days")
        assert "Activities: 2" in text
        assert "50.00 km" in text
        assert "1 x running" in text
        assert "1 x cycling" in text

    async def test_devices_do_not_expose_a_full_serial_number(self, server, fake_garmin):
        fake_garmin(
            {"get_devices": [{"displayName": "Forerunner 965", "serialNumber": "3141592653"}]}
        )
        text = await run_tool(server, "get_devices")
        assert "Forerunner 965" in text
        assert "3141592653" not in text
        assert "...2653" in text

    async def test_personal_records_are_listed(self, server, fake_garmin):
        fake_garmin({"get_personal_record": [{"typeName": "Fastest 5K", "value": 1200}]})
        text = await run_tool(server, "get_personal_records")
        assert "Fastest 5K" in text
        assert "20m 0s" in text
