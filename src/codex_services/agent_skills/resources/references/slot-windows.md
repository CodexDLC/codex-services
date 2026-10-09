# Slot windows

`SlotCalculator` is exported from `codex_services.booking`. It works on `datetime` values supplied by the application and has no persistence or ORM integration.

```python
from datetime import datetime
from codex_services.booking import SlotCalculator

day = datetime(2026, 10, 12)
at = lambda hour, minute=0: day.replace(hour=hour, minute=minute)
calculator = SlotCalculator(step_minutes=30)
free = calculator.merge_free_windows(
    work_start=at(9),
    work_end=at(12),
    busy_intervals=[(at(10), at(11))],
    buffer_minutes=10,
)
starts = [start for begin, end in free for start in calculator.find_slots_in_window(begin, end, 30)]
print(starts)
```

`step_minutes` must be positive. `find_slots_in_window` can apply `min_start` and align candidates to a `grid_anchor`; without an anchor the window start is the grid origin. `merge_free_windows` can also subtract one `break_interval` and filter short windows with `min_duration_minutes`. Keep datetime awareness consistent and prepare valid working/busy intervals before calling it. See `codex_services/booking/_shared/calculator.py` for the installed version.
