from datetime import date

import pytest

from garmin_mcp.dates import DateParseError, days_in_range, parse_date, parse_range

TODAY = date(2026, 8, 18)  # a Tuesday


class TestParseDate:
    def test_none_and_empty_mean_today(self):
        assert parse_date(None, today=TODAY) == "2026-08-18"
        assert parse_date("  ", today=TODAY) == "2026-08-18"

    @pytest.mark.parametrize(
        "phrase,expected",
        [
            ("today", "2026-08-18"),
            ("Yesterday", "2026-08-17"),
            ("tomorrow", "2026-08-19"),
            ("3 days ago", "2026-08-15"),
            ("1 week ago", "2026-08-11"),
            ("2026-01-05", "2026-01-05"),
        ],
    )
    def test_understands_everyday_phrases(self, phrase, expected):
        assert parse_date(phrase, today=TODAY) == expected

    def test_is_insensitive_to_case_and_spacing(self):
        assert parse_date("  3   DAYS   AGO ", today=TODAY) == "2026-08-15"

    def test_rejects_impossible_calendar_date(self):
        with pytest.raises(DateParseError):
            parse_date("2026-02-31", today=TODAY)

    def test_rejects_gibberish_with_a_helpful_message(self):
        with pytest.raises(DateParseError, match="Could not understand"):
            parse_date("whenever", today=TODAY)


class TestParseRange:
    def test_defaults_to_the_last_seven_days(self):
        assert parse_range(None, today=TODAY) == ("2026-08-12", "2026-08-18")

    def test_last_n_days_includes_today(self):
        # "last 7 days" is a 7-day window, not 8.
        start, end = parse_range("last 7 days", today=TODAY)
        assert (start, end) == ("2026-08-12", "2026-08-18")
        assert len(days_in_range(start, end)) == 7

    def test_this_week_starts_on_monday(self):
        assert parse_range("this week", today=TODAY) == ("2026-08-17", "2026-08-18")

    def test_this_month_starts_on_the_first(self):
        assert parse_range("this month", today=TODAY) == ("2026-08-01", "2026-08-18")

    def test_explicit_span(self):
        assert parse_range("2026-08-01 to 2026-08-05", today=TODAY) == ("2026-08-01", "2026-08-05")

    def test_reversed_span_is_corrected(self):
        assert parse_range("2026-08-05 to 2026-08-01", today=TODAY) == ("2026-08-01", "2026-08-05")

    def test_single_day_becomes_a_one_day_span(self):
        assert parse_range("yesterday", today=TODAY) == ("2026-08-17", "2026-08-17")

    def test_rejects_gibberish(self):
        with pytest.raises(DateParseError):
            parse_range("sometime soon", today=TODAY)


def test_days_in_range_is_inclusive():
    assert days_in_range("2026-08-01", "2026-08-03") == ["2026-08-01", "2026-08-02", "2026-08-03"]
