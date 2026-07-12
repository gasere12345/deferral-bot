import calendar
import json
import os
from datetime import date, timedelta, datetime


HOLIDAYS_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "holidays_rb.json")
_HOLIDAYS_CACHE: dict[int, set] = {}


def _load_holidays(year: int) -> set:
    if year not in _HOLIDAYS_CACHE:
        with open(HOLIDAYS_FILE) as f:
            data = json.load(f)
        _HOLIDAYS_CACHE[year] = set(data.get(str(year), []))
    return _HOLIDAYS_CACHE[year]


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


def calc_deferral_end(delivery_date_str: str, deferral_days: int, manual_end_date: str = None) -> str:
    if manual_end_date:
        return manual_end_date
    d = datetime.strptime(delivery_date_str, "%Y-%m-%d").date()
    end_date = d + timedelta(days=max(0, deferral_days - 1))
    if not is_working_day(end_date):
        end_date = next_working_day(end_date)
    return end_date.strftime("%Y-%m-%d")


MONTH_NAMES = ["", "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
               "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"]


def month_name(m: int) -> str:
    return MONTH_NAMES[m] if 1 <= m <= 12 else ""


def get_month_days(year: int, month: int) -> list:
    return calendar.monthcalendar(year, month)


def month_range(year: int, month: int):
    _, days_in_month = calendar.monthrange(year, month)
    return days_in_month
