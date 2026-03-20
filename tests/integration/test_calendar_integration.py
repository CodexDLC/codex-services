"""
Integration tests for CalendarEngine (calendar/engine.py).
"""

from datetime import date

import pytest

from codex_services.calendar.engine import CalendarEngine


@pytest.mark.integration
def test_get_month_matrix_returns_list_of_dicts() -> None:
    """get_month_matrix returns a non-empty list of day dicts."""
    today = date(2024, 5, 1)
    matrix = CalendarEngine.get_month_matrix(year=2024, month=5, today=today)

    assert isinstance(matrix, list)
    assert len(matrix) > 0

    # Every entry has a 'status' key
    for day in matrix:
        assert "status" in day


@pytest.mark.integration
def test_get_month_matrix_empty_padding_cells() -> None:
    """Padding cells at the start have num='' and status='empty'."""
    today = date(2024, 1, 31)
    matrix = CalendarEngine.get_month_matrix(year=2024, month=1, today=today)
    empty_cells = [d for d in matrix if d["status"] == "empty"]
    # January 2024 starts on Monday (weekday=0), so no empty padding cells expected
    # But the structure should still be valid
    for cell in empty_cells:
        assert cell["num"] == ""


@pytest.mark.integration
def test_get_month_matrix_past_days_disabled() -> None:
    """Days before 'today' are marked as 'disabled'."""
    today = date(2024, 5, 15)
    matrix = CalendarEngine.get_month_matrix(year=2024, month=5, today=today)

    for day in matrix:
        if day["status"] == "empty":
            continue
        day_date = date.fromisoformat(day["date"])
        if day_date < today:
            assert day["status"] == "disabled"


@pytest.mark.integration
def test_get_month_matrix_sunday_disabled() -> None:
    """Sundays (weekday=6) are marked as 'disabled'."""
    today = date(2024, 1, 1)
    matrix = CalendarEngine.get_month_matrix(year=2024, month=5, today=today)

    for day in matrix:
        if day["status"] == "empty":
            continue
        if day.get("weekday") == 6:
            assert day["status"] == "disabled"


@pytest.mark.integration
def test_get_month_matrix_selected_date_active() -> None:
    """selected_date is marked as 'active'."""
    today = date(2024, 5, 1)
    selected = date(2024, 5, 20)
    matrix = CalendarEngine.get_month_matrix(year=2024, month=5, today=today, selected_date=selected)

    active_days = [d for d in matrix if d.get("status") == "active"]
    assert len(active_days) == 1
    assert active_days[0]["date"] == selected.isoformat()


@pytest.mark.integration
def test_get_month_matrix_holiday_status() -> None:
    """German public holidays are marked as 'holiday'."""
    # 2024-10-03 is German Unity Day (nationwide holiday)
    today = date(2024, 9, 1)
    matrix = CalendarEngine.get_month_matrix(year=2024, month=10, today=today, holidays_subdiv="BE")

    unity_day = [d for d in matrix if d.get("date") == "2024-10-03"]
    assert len(unity_day) == 1
    assert unity_day[0]["status"] == "holiday"
    assert unity_day[0]["is_holiday"] is True


@pytest.mark.integration
def test_get_month_matrix_is_holiday_field() -> None:
    """is_holiday field is a bool for all non-empty cells."""
    today = date(2024, 1, 1)
    matrix = CalendarEngine.get_month_matrix(year=2024, month=3, today=today)

    for day in matrix:
        if day["status"] == "empty":
            continue
        assert isinstance(day["is_holiday"], bool)


@pytest.mark.integration
def test_get_month_matrix_day_fields_complete() -> None:
    """Every non-empty day contains: num, date, status, is_holiday, weekday."""
    today = date(2024, 1, 1)
    matrix = CalendarEngine.get_month_matrix(year=2024, month=6, today=today)

    for day in matrix:
        if day["status"] == "empty":
            continue
        for field in ("num", "date", "status", "is_holiday", "weekday"):
            assert field in day, f"Missing field '{field}' in {day}"


@pytest.mark.integration
def test_get_month_matrix_different_subdivisions() -> None:
    """Different holiday subdivisions produce valid matrices."""
    today = date(2024, 1, 1)
    for subdiv in ("BY", "NW", "ST", "HH"):
        matrix = CalendarEngine.get_month_matrix(year=2024, month=12, today=today, holidays_subdiv=subdiv)
        assert len(matrix) > 0


@pytest.mark.integration
def test_get_month_label_russian_all_months() -> None:
    """get_month_label returns correct Russian names for all 12 months."""
    expected = {
        1: "Январь",
        2: "Февраль",
        3: "Март",
        4: "Апрель",
        5: "Май",
        6: "Июнь",
        7: "Июль",
        8: "Август",
        9: "Сентябрь",
        10: "Октябрь",
        11: "Ноябрь",
        12: "Декабрь",
    }
    for month, name in expected.items():
        label = CalendarEngine.get_month_label(year=2024, month=month)
        assert name in label
        assert "2024" in label


@pytest.mark.integration
def test_get_month_label_unknown_locale_returns_year() -> None:
    """get_month_label still returns the year for any locale."""
    label = CalendarEngine.get_month_label(year=2025, month=3, locale="de")
    assert "2025" in label


@pytest.mark.integration
def test_get_month_matrix_available_future_weekday() -> None:
    """Future non-holiday, non-Sunday weekdays are 'available'."""
    today = date(2024, 1, 1)
    # May 2024 — use a Monday in the future
    matrix = CalendarEngine.get_month_matrix(year=2024, month=5, today=today)

    available = [d for d in matrix if d.get("status") == "available"]
    assert len(available) > 0
    for d in available:
        assert d["is_holiday"] is False
        assert d.get("weekday") != 6
