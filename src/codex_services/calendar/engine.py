"""
codex_services.calendar.engine
==============================
Universal calendar generator.
Framework-agnostic (does not depend on Django).
"""

import calendar
from datetime import date
from typing import Any

try:
    import holidays
except ImportError as exc:
    raise ImportError("CalendarEngine requires the 'calendar' extra: pip install codex-services[calendar]") from exc


class CalendarEngine:
    """
    Day matrix generator for a calendar.

    Used for rendering UI (website, bot).
    """

    @staticmethod
    def get_month_matrix(
        year: int,
        month: int,
        today: date,
        selected_date: date | None = None,
        holidays_subdiv: str = "ST",  # Default: Saxony-Anhalt
    ) -> list[dict[str, Any]]:
        """
        Generates a list of days for the calendar grid.

        Args:
            year: Year.
            month: Month.
            today: Current date (to determine past days).
            selected_date: Selected date (for 'active' status).
            holidays_subdiv: German region for holidays.

        Returns:
            List of dictionaries with day data.
        """
        de_holidays = holidays.country_holidays("DE", subdiv=holidays_subdiv, years=year)

        cal = calendar.Calendar(firstweekday=0)  # Mon - first day
        month_days = cal.itermonthdays(year, month)

        result: list[dict[str, Any]] = []
        for day_num in month_days:
            if day_num == 0:
                result.append({"num": "", "status": "empty"})
                continue

            calc_date = date(year, month, day_num)
            weekday = calc_date.weekday()

            # Base status
            status = "available"

            if calc_date < today or weekday == 6:
                status = "disabled"
            elif calc_date in de_holidays:
                status = "holiday"

            if selected_date and calc_date == selected_date:
                status = "active"

            day_data: dict[str, Any] = {
                "num": str(day_num),
                "date": calc_date.isoformat(),
                "status": status,
                "is_holiday": calc_date in de_holidays,
                "weekday": weekday,
            }
            result.append(day_data)

        return result

    @staticmethod
    def get_month_label(year: int, month: int, locale: str = "ru") -> str:
        """Returns the month name and year."""
        month_names_ru = {
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
        # Other languages (de, en) can be added if necessary
        name = month_names_ru.get(month, "")
        return f"{name} {year}"
