"""Unit tests for CalendarEngine."""

from datetime import date

import pytest

from codex_services.calendar.engine import CalendarEngine


@pytest.mark.unit
class TestCalendarEngineGetMonthMatrix:
    def test_returns_list(self) -> None:
        result = CalendarEngine.get_month_matrix(2024, 5, today=date(2024, 5, 1))
        assert isinstance(result, list)
        assert len(result) > 0

    def test_empty_cells_for_padding(self) -> None:
        # May 1 2024 = Wednesday → 2 leading empty cells (Mon, Tue) + 2 trailing = 4 total
        result = CalendarEngine.get_month_matrix(2024, 5, today=date(2024, 5, 1))
        empty_cells = [d for d in result if d["status"] == "empty"]
        assert len(empty_cells) == 4

    def test_past_days_are_disabled(self) -> None:
        result = CalendarEngine.get_month_matrix(2024, 5, today=date(2024, 5, 15))
        day_1 = next(d for d in result if d.get("num") == "1")
        assert day_1["status"] == "disabled"

    def test_today_is_available(self) -> None:
        result = CalendarEngine.get_month_matrix(2024, 5, today=date(2024, 5, 10))
        day_10 = next(d for d in result if d.get("num") == "10")
        assert day_10["status"] == "available"

    def test_future_day_is_available(self) -> None:
        # May 16 2024 = Thursday, not a holiday → available
        result = CalendarEngine.get_month_matrix(2024, 5, today=date(2024, 5, 1))
        day_16 = next(d for d in result if d.get("num") == "16")
        assert day_16["status"] == "available"

    def test_selected_date_is_active(self) -> None:
        result = CalendarEngine.get_month_matrix(
            2024,
            5,
            today=date(2024, 5, 1),
            selected_date=date(2024, 5, 10),
        )
        day_10 = next(d for d in result if d.get("num") == "10")
        assert day_10["status"] == "active"

    def test_sunday_is_disabled(self) -> None:
        # May 5 2024 is a Sunday
        result = CalendarEngine.get_month_matrix(2024, 5, today=date(2024, 5, 1))
        day_5 = next(d for d in result if d.get("num") == "5")
        assert day_5["status"] == "disabled"

    def test_german_public_holiday_tagged(self) -> None:
        # May 1 2024 = Tag der Arbeit (German public holiday)
        result = CalendarEngine.get_month_matrix(2024, 5, today=date(2024, 4, 1))
        day_1 = next(d for d in result if d.get("num") == "1")
        assert day_1["is_holiday"] is True

    def test_holiday_status_set(self) -> None:
        # May 1 is not past (today=Apr 1), not Sunday → should be "holiday"
        result = CalendarEngine.get_month_matrix(2024, 5, today=date(2024, 4, 1))
        day_1 = next(d for d in result if d.get("num") == "1")
        assert day_1["status"] == "holiday"

    def test_day_data_has_required_keys(self) -> None:
        result = CalendarEngine.get_month_matrix(2024, 5, today=date(2024, 5, 1))
        real_days = [d for d in result if d.get("num") and d["num"] != ""]
        for day_data in real_days:
            assert "num" in day_data
            assert "date" in day_data
            assert "status" in day_data
            assert "is_holiday" in day_data
            assert "weekday" in day_data

    def test_empty_cell_has_empty_num(self) -> None:
        result = CalendarEngine.get_month_matrix(2024, 5, today=date(2024, 5, 1))
        empty_cells = [d for d in result if d["status"] == "empty"]
        for cell in empty_cells:
            assert cell["num"] == ""

    def test_correct_day_count_for_may(self) -> None:
        result = CalendarEngine.get_month_matrix(2024, 5, today=date(2024, 5, 1))
        real_days = [d for d in result if d.get("num") and d["num"] != ""]
        assert len(real_days) == 31

    def test_subdiv_parameter_accepted(self) -> None:
        # Different German state (Bavaria = BY)
        result = CalendarEngine.get_month_matrix(2024, 5, today=date(2024, 4, 1), holidays_subdiv="BY")
        assert isinstance(result, list)
        assert len(result) > 0


@pytest.mark.unit
class TestCalendarEngineGetMonthLabel:
    def test_russian_month_name(self) -> None:
        label = CalendarEngine.get_month_label(2024, 5, locale="ru")
        assert "Май" in label
        assert "2024" in label

    def test_all_russian_months(self) -> None:
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
            label = CalendarEngine.get_month_label(2024, month)
            assert name in label, f"Month {month}: expected '{name}' in '{label}'"

    def test_unknown_month_no_crash(self) -> None:
        label = CalendarEngine.get_month_label(2024, 13)
        assert "2024" in label

    def test_year_in_label(self) -> None:
        label = CalendarEngine.get_month_label(2099, 1)
        assert "2099" in label
