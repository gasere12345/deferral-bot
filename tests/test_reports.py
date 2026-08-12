from datetime import date

from bot.reports import (
    build_daily_text,
    build_weekly_text,
    build_overdue_text,
    build_export_csv,
    format_overdue_line,
    fmt_money,
    esc,
)


def _dv(id, name, amount, end):
    return {
        "id": id,
        "supplier_name": name,
        "delivery_date": "2026-07-01",
        "amount": amount,
        "paid": 0,
        "deferral_end": end,
    }


class TestDailyText:
    def test_today_and_no_overdue_no_upcoming(self):
        text = build_daily_text(
            [_dv(1, "A", 100.0, "2026-07-10")], [], [], 3, date(2026, 7, 10)
        )
        assert "Доброе утро" in text
        assert "Сегодня нужно оплатить" in text
        assert "A" in text
        assert "Итого сегодня" in text
        assert "Просрочено" not in text
        assert "Скоро" not in text

    def test_no_today_but_overdue(self):
        overdue = [_dv(1, "B", 200.0, "2026-07-08")]
        text = build_daily_text([], overdue, [], 3, date(2026, 7, 10))
        assert "Просрочено" in text
        assert "B" in text
        assert "просрочено 2 дня" in text
        assert "Итого просрочено" in text
        assert "На сегодня платежей нет" in text

    def test_upcoming_section(self):
        upcoming = [_dv(1, "C", 300.0, "2026-07-13")]
        text = build_daily_text([], [], upcoming, 3, date(2026, 7, 10))
        assert "Скоро" in text
        assert "C" in text
        assert "до 13 Июль" in text

    def test_all_empty_calm_day(self):
        text = build_daily_text([], [], [], 3, date(2026, 7, 10))
        assert "На сегодня платежей нет." in text
        assert "Просрочено" not in text


class TestOverdueText:
    def test_empty(self):
        text = build_overdue_text([], date(2026, 7, 10))
        assert "Просроченных платежей нет!" in text

    def test_with_overdue(self):
        overdue = [_dv(1, "A", 500.0, "2026-07-05")]
        text = build_overdue_text(overdue, date(2026, 7, 10))
        assert "Просроченные платежи" in text
        assert "A" in text
        assert "просрочено 5 дней" in text
        assert "Итого просрочено: <b>500 BYN</b>" in text

    def test_overdue_line_plural(self):
        assert "просрочено 1 день" in format_overdue_line(_dv(1, "A", 1, "2026-07-09"), "2026-07-10")
        assert "просрочено 2 дня" in format_overdue_line(_dv(1, "A", 1, "2026-07-08"), "2026-07-10")
        assert "просрочено 6 дней" in format_overdue_line(_dv(1, "A", 1, "2026-07-04"), "2026-07-10")


class TestWeeklyText:
    def test_week_report(self):
        week = [_dv(1, "A", 100.0, "2026-07-12")]
        overdue = [_dv(2, "B", 50.0, "2026-07-05")]
        text = build_weekly_text(week, overdue, date(2026, 7, 10))
        assert "Отчёт на неделю" in text
        assert "Просрочено" in text
        assert "Платежи на неделю" in text
        assert "Итого на неделю" in text

    def test_week_no_overdue(self):
        text = build_weekly_text([], [], date(2026, 7, 10))
        assert "Просроченных нет" in text
        assert "На неделю платежей нет" in text


class TestExportCsv:
    def test_csv_bytes_with_bom_and_rows(self):
        deliveries = [_dv(1, "Sup", 1500.0, "2026-07-15"), _dv(2, "Sup2", None, "2026-07-16")]
        deliveries[1]["paid"] = 1
        data = build_export_csv(deliveries)
        assert isinstance(data, bytes)
        text = data.decode("utf-8-sig")
        assert "Поставщик" in text
        assert "Sup" in text
        assert "нет" in text
        assert "да" in text
        assert "1500.0" in text

    def test_csv_formula_injection_guarded(self):
        deliveries = [_dv(1, "=SUM(A1)", 100.0, "2026-07-15")]
        data = build_export_csv(deliveries)
        text = data.decode("utf-8-sig")
        assert "'=SUM(A1)" in text
        assert "1;=SUM" not in text

    def test_esc_escapes_html(self):
        assert esc('ООО "Рога & Копыта"') == 'ООО "Рога &amp; Копыта"'
        assert esc("<b>x</b>") == "&lt;b&gt;x&lt;/b&gt;"
        assert esc("простой") == "простой"


class TestFmtMoney:
    def test_whole_rubles(self):
        assert fmt_money(1500) == "1,500 BYN"
        assert fmt_money(1500.0) == "1,500 BYN"

    def test_kopecks_preserved(self):
        assert fmt_money(999.99) == "999.99 BYN"
        assert fmt_money(1234.5) == "1,234.50 BYN"

    def test_none_and_zero(self):
        assert fmt_money(None) == "0 BYN"
        assert fmt_money(0) == "0 BYN"
