import csv
import io
from datetime import date
from html import escape

from bot.calendar_utils import month_name

WEEKDAYS = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]


def esc(value) -> str:
    return escape(str(value or ""), quote=False)


def _plural(n: int, one: str, few: str, many: str) -> str:
    n = abs(n) % 100
    if 11 <= n <= 14:
        return many
    last = n % 10
    if last == 1:
        return one
    if last in (2, 3, 4):
        return few
    return many


def _money(amount) -> str:
    return f"{amount:,.0f} руб." if amount else "0 руб."


def _end_short(end: str) -> str:
    if not end:
        return ""
    parts = end.split("-")
    return f"{int(parts[2])} {month_name(int(parts[1]))}"


def format_payment_line(dv, with_date: bool = True) -> str:
    line = f"• <b>{esc(dv['supplier_name'])}</b> — {_money(dv['amount'])}"
    if with_date and dv.get("deferral_end"):
        line += f" (до {_end_short(dv['deferral_end'])})"
    return line


def format_overdue_line(dv, today: str) -> str:
    days = (date.fromisoformat(today) - date.fromisoformat(dv["deferral_end"])).days
    overdue = _plural(days, "день", "дня", "дней")
    return f"🔴 <b>{esc(dv['supplier_name'])}</b> — {_money(dv['amount'])} (просрочено {days} {overdue})"


def build_daily_text(deliveries, overdue, upcoming, remind_days: int, today: date) -> str:
    d = today
    weekday = WEEKDAYS[d.weekday()]
    parts = [f"☀️ <b>Доброе утро!</b> — {d.day} {month_name(d.month)} ({weekday})"]

    if overdue:
        lines = [f"\n🔴 <b>Просрочено:</b>"]
        total = sum(ov["amount"] or 0 for ov in overdue)
        for ov in overdue:
            lines.append(format_overdue_line(ov, today.strftime("%Y-%m-%d")))
        lines.append(f"💳 Итого просрочено: <b>{_money(total)}</b>")
        parts.append("\n".join(lines))

    if deliveries:
        lines = [f"\n💰 <b>Сегодня нужно оплатить:</b>"]
        total = sum(dv["amount"] or 0 for dv in deliveries)
        for dv in deliveries:
            lines.append(format_payment_line(dv, with_date=False))
        lines.append(f"💳 Итого сегодня: <b>{_money(total)}</b>")
        parts.append("\n".join(lines))
    else:
        parts.append("\n🎉 На сегодня платежей нет.")

    if upcoming:
        lines = [f"\n⏳ <b>Скоро (в ближайшие {remind_days} дн.):</b>"]
        total = sum(dv["amount"] or 0 for dv in upcoming)
        for dv in upcoming:
            lines.append(format_payment_line(dv, with_date=True))
        lines.append(f"💳 Итого скоро: <b>{_money(total)}</b>")
        parts.append("\n".join(lines))

    return "\n".join(parts)


def build_weekly_text(week_deliveries, overdue, today: date) -> str:
    d = today
    parts = [f"📊 <b>Отчёт на неделю</b> — {d.day} {month_name(d.month)} {d.year}"]

    if overdue:
        lines = [f"\n🔴 <b>Просрочено:</b>"]
        total = sum(ov["amount"] or 0 for ov in overdue)
        for ov in overdue:
            lines.append(format_overdue_line(ov, today.strftime("%Y-%m-%d")))
        lines.append(f"💳 Итого просрочено: <b>{_money(total)}</b>")
        parts.append("\n".join(lines))
    else:
        parts.append("\n✅ Просроченных нет.")

    if week_deliveries:
        lines = [f"\n📅 <b>Платежи на неделю:</b>"]
        total = sum(dv["amount"] or 0 for dv in week_deliveries)
        for dv in week_deliveries:
            lines.append(format_payment_line(dv, with_date=True))
        lines.append(f"💳 Итого на неделю: <b>{_money(total)}</b>")
        parts.append("\n".join(lines))
    else:
        parts.append("\n🎉 На неделю платежей нет.")

    return "\n".join(parts)


def build_overdue_text(overdue, today: date) -> str:
    d = today
    weekday = WEEKDAYS[d.weekday()]
    header = f"⚠️ <b>Просроченные платежи</b> — {d.day} {month_name(d.month)} {d.year} ({weekday})"
    if not overdue:
        return f"{header}\n\n🎉 Просроченных платежей нет!"
    lines = [header, ""]
    total = sum(ov["amount"] or 0 for ov in overdue)
    for ov in overdue:
        lines.append(format_overdue_line(ov, today.strftime("%Y-%m-%d")))
    lines.append(f"\n💳 Итого просрочено: <b>{_money(total)}</b>")
    return "\n".join(lines)


def _csv_safe(value) -> str:
    s = str(value or "")
    if s and s[0] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + s
    return s


def build_export_csv(deliveries) -> bytes:
    buf = io.StringIO()
    writer = csv.writer(buf, delimiter=";")
    writer.writerow(["ID", "Поставщик", "Дата поставки", "Сумма, руб", "Оплачено", "Оплатить до"])
    for dv in deliveries:
        writer.writerow([
            dv["id"],
            _csv_safe(dv["supplier_name"]),
            dv["delivery_date"],
            dv["amount"] or "",
            "да" if dv["paid"] else "нет",
            dv.get("deferral_end", ""),
        ])
    return ("\ufeff" + buf.getvalue()).encode("utf-8")
