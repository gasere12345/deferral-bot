import json
import os
import tempfile
from datetime import date, timedelta
from unittest.mock import patch

import pytest

from bot.calendar_utils import (
    is_weekend,
    is_holiday,
    is_working_day,
    next_working_day,
    calc_deferral_end,
    month_range,
)


class TestIsWeekend:
    def test_saturday(self):
        assert is_weekend(date(2026, 7, 11))

    def test_sunday(self):
        assert is_weekend(date(2026, 7, 12))

    def test_monday(self):
        assert not is_weekend(date(2026, 7, 13))

    def test_friday(self):
        assert not is_weekend(date(2026, 7, 10))


class TestIsHoliday:
    def test_new_year(self):
        assert is_holiday(date(2026, 1, 1))

    def test_march_8(self):
        assert is_holiday(date(2026, 3, 8))

    def test_july_3(self):
        assert is_holiday(date(2026, 7, 3))

    def test_working_day_not_holiday(self):
        assert not is_holiday(date(2026, 7, 13))

    def test_ordinary_saturday_not_holiday(self):
        assert not is_holiday(date(2026, 7, 11))

    def test_new_year_2027(self):
        assert is_holiday(date(2027, 1, 1))

    def test_unknown_year_returns_empty(self):
        assert not is_holiday(date(2030, 7, 13))


class TestIsWorkingDay:
    def test_regular_monday(self):
        assert is_working_day(date(2026, 7, 13))

    def test_saturday_not_working(self):
        assert not is_working_day(date(2026, 7, 11))

    def test_holiday_not_working(self):
        assert not is_working_day(date(2026, 7, 3))

    def test_sunday_not_working(self):
        assert not is_working_day(date(2026, 7, 12))


class TestNextWorkingDay:
    def test_monday_after_sunday(self):
        d = date(2026, 7, 12)
        assert next_working_day(d) == date(2026, 7, 13)

    def test_skips_saturday_and_sunday(self):
        d = date(2026, 7, 10)
        result = next_working_day(d)
        assert result == date(2026, 7, 13)
        assert result.weekday() == 0

    def test_skips_holiday_july_3(self):
        d = date(2026, 7, 2)
        result = next_working_day(d)
        assert result == date(2026, 7, 6)

    def test_consecutive_calls_skip_weekend(self):
        d = date(2026, 7, 10)
        r1 = next_working_day(d)
        r2 = next_working_day(r1)
        assert r1 == date(2026, 7, 13)
        assert r2 == date(2026, 7, 14)


class TestCalcDeferralEnd:
    def test_simple_no_weekend(self):
        assert calc_deferral_end("2026-07-01", 5) == "2026-07-06"

    def test_with_weekend_skip(self):
        assert calc_deferral_end("2026-07-09", 3) == "2026-07-13"

    def test_with_holiday_skip(self):
        assert calc_deferral_end("2026-07-01", 2) == "2026-07-06"

    def test_zero_deferral_days(self):
        assert calc_deferral_end("2026-07-13", 0) == "2026-07-13"

    def test_manual_end_date_overrides(self):
        assert calc_deferral_end("2026-07-01", 5, manual_end_date="2026-07-20") == "2026-07-20"

    def test_manual_end_date_none(self):
        assert calc_deferral_end("2026-07-13", 3) == "2026-07-16"

    def test_deferral_ending_on_saturday(self):
        assert calc_deferral_end("2026-07-07", 5) == "2026-07-13"

    def test_deferral_ending_on_holiday(self):
        assert calc_deferral_end("2026-06-29", 4) == "2026-07-06"

    def test_long_deferral_crosses_weekends(self):
        result = calc_deferral_end("2026-07-01", 14)
        d = date(2026, 7, 15)
        assert result == d.strftime("%Y-%m-%d")

    def test_manual_end_date_empty_string(self):
        assert calc_deferral_end("2026-07-13", 3, manual_end_date="") == "2026-07-16"


class TestMonthRange:
    def test_january(self):
        assert month_range(2026, 1) == 31

    def test_february_non_leap(self):
        assert month_range(2025, 2) == 28

    def test_february_leap(self):
        assert month_range(2024, 2) == 29

    def test_december(self):
        assert month_range(2026, 12) == 31
