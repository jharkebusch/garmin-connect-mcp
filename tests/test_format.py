from garmin_mcp import format as fmt


class TestDuration:
    def test_splits_into_hours_minutes_seconds(self):
        assert fmt.duration(3725) == "1h 2m 5s"

    def test_omits_hours_when_under_one(self):
        assert fmt.duration(125) == "2m 5s"

    def test_seconds_only(self):
        assert fmt.duration(45) == "45s"

    def test_missing_stays_missing(self):
        assert fmt.duration(None) is None

    def test_hours_minutes_pads_minutes(self):
        assert fmt.hours_minutes(27000) == "7h 30m"


class TestDistance:
    def test_metres_below_a_kilometre(self):
        assert fmt.distance(800) == "800 m"

    def test_kilometres_above(self):
        assert fmt.distance(10500) == "10.50 km"

    def test_miles_when_imperial(self):
        assert fmt.distance(1609.344, metric=False) == "1.00 mi"

    def test_feet_for_short_imperial_distances(self):
        assert fmt.distance(30, metric=False) == "98 ft"


class TestPace:
    def test_pace_per_kilometre(self):
        # 10 km in 50 minutes is 5:00 per km.
        assert fmt.pace(3000, 10000) == "5:00 /km"

    def test_pace_per_mile(self):
        assert fmt.pace(3000, 10000, metric=False) == "8:03 /mi"

    def test_zero_distance_has_no_pace(self):
        assert fmt.pace(3000, 0) is None

    def test_missing_inputs_have_no_pace(self):
        assert fmt.pace(None, 10000) is None


class TestWeightAndSpeed:
    def test_weight_converts_grams_to_kilograms(self):
        assert fmt.weight(74500) == "74.5 kg"

    def test_weight_in_pounds(self):
        assert fmt.weight(74500, metric=False) == "164.2 lb"

    def test_speed_converts_to_kilometres_per_hour(self):
        assert fmt.speed(10) == "36.0 km/h"


class TestNumber:
    def test_adds_thousand_separators(self):
        assert fmt.number(12345) == "12,345"

    def test_appends_a_unit(self):
        assert fmt.number(72, unit="bpm") == "72 bpm"

    def test_keeps_requested_decimals(self):
        assert fmt.number(48.27, digits=1) == "48.3"

    def test_missing_stays_missing(self):
        assert fmt.number(None) is None


class TestPick:
    def test_returns_the_first_present_key(self):
        assert fmt.pick({"b": 2}, "a", "b") == 2

    def test_skips_nulls(self):
        assert fmt.pick({"a": None, "b": 5}, "a", "b") == 5

    def test_falls_back_to_default(self):
        assert fmt.pick({}, "a", default="x") == "x"

    def test_tolerates_a_non_dict(self):
        assert fmt.pick(None, "a", default="x") == "x"


class TestReport:
    def test_drops_empty_rows(self):
        text = fmt.report("Title", [("Steps", "100"), ("Sleep", None), ("Stress", "")])
        assert "Steps: 100" in text
        assert "Sleep" not in text
        assert "Stress" not in text

    def test_says_so_when_there_is_nothing(self):
        assert "No data recorded." in fmt.report("Title", [("A", None)])

    def test_falls_back_to_raw_data_when_no_field_matched(self):
        # Garmin renames fields without warning; showing trimmed raw data beats
        # claiming there is no data.
        text = fmt.report("Title", [("A", None)], raw={"somethingNew": 42})
        assert "somethingNew" in text
        assert "No data recorded." not in text


class TestPrune:
    def test_removes_nulls_and_empties(self):
        assert fmt.prune({"a": 1, "b": None, "c": [], "d": {}}) == {"a": 1}

    def test_collapses_long_sample_arrays(self):
        result = fmt.prune({"samples": list(range(500))})
        assert result["samples"] == "<500 samples omitted>"

    def test_keeps_short_lists(self):
        assert fmt.prune({"x": [1, 2, 3]}) == {"x": [1, 2, 3]}

    def test_compact_json_is_truncated(self):
        text = fmt.compact_json({"k": "v" * 5000}, limit=200)
        assert len(text) < 300
        assert "truncated" in text


class TestTimestamp:
    def test_parses_iso_strings(self):
        assert fmt.timestamp("2026-08-18T22:15:00") == "2026-08-18 22:15"

    def test_time_only(self):
        assert fmt.timestamp("2026-08-18T22:15:00", time_only=True) == "22:15"

    def test_handles_epoch_milliseconds(self):
        assert fmt.timestamp(1755555600000) is not None

    def test_missing_stays_missing(self):
        assert fmt.timestamp(None) is None


def test_is_metric_defaults_to_metric():
    assert fmt.is_metric(None) is True
    assert fmt.is_metric("metric") is True
    assert fmt.is_metric("statute_us") is False
