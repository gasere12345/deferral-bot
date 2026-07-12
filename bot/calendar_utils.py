import json
import os
from datetime import date, timedelta, datetime


HOLIDAYS_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "holidays_rb.json")


def _load_holidays(year: int) -> set:
    with open(HOLIDAYS_FILE) as f:
        data = json.load(f)
    return set(data.get(str(year), []))


def is_weekend(d: date) -> bool:
    return d.weekday() >= 5


def is_holiday(d: date) -> bool:
    holidays = _load_holidays(d.year)
    return d.strftime("%Y-%m-%d") in holidays


def is_working_day(d: date) -> bool:
    return not is_weekend(d) and not is_holiday(d)


def next_working_day(d: date) -> date:
    d += timedelta(days=1)
    while not is_working_day(d):
        d += timedelta(days=1)
    return d


def calc_deferral_end(delivery_date_str: str, deferral_days: int) -> str:
    d = datetime.strptime(delivery_date_str, "%Y-%m-%d").date()
    end_date = d + timedelta(days=deferral_days)
    if not is_working_day(end_date):
        end_date = next_working_day(end_date)
    return end_date.strftime("%Y-%m-%d")


def get_month_days(year: int, month: int) -> list:
    import calendar
    return calendar.monthcalendar(year, month)


def month_range(year: int, month: int):
    import calendar
    _, days_in_month = calendar.monthrange(year, month)
    return days_in_month
