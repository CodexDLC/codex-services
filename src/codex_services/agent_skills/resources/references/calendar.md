# Calendar grids

Install `codex-services[calendar]` to use `CalendarEngine`; importing it without the `holidays` dependency raises an `ImportError`. It returns day dictionaries for UI rendering, not availability from your booking database.

```python
from datetime import date
from codex_services.calendar import CalendarEngine

days = CalendarEngine.get_month_matrix(2026, 10, today=date(2026, 10, 1), holidays_subdiv="ST")
print([day for day in days if day["status"] == "available"][:3])
```

The grid starts on Monday. Empty padding cells contain only `num` and `status`; real days include `date`, `is_holiday`, and `weekday`. Past dates and Sundays are disabled, German holidays use the supplied subdivision, and `selected_date` overrides status to `active`. `get_month_label` currently returns Russian month names regardless of its `locale` argument; handle other localization in the application. See `codex_services/calendar/engine.py` for the installed version.
