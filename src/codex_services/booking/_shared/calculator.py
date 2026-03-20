"""
codex_services.booking._shared.calculator
==========================================
Basic slot operations inside time windows.

This is "math without ORM" — works with datetime objects, does not know about Django.
Used inside ChainFinder, and can also be applied independently.

Imports:
    from codex_services.booking import SlotCalculator
"""

from datetime import datetime, timedelta


class SlotCalculator:
    """
    Slot generator inside a free time window (sliding window).

    Does not depend on ORM. Works with datetime objects.

    Examples:
        ```python
        calc = SlotCalculator(step_minutes=30)

        # Get all possible slots in a window from 9:00 to 12:00 for a 60 min service:
        slots = calc.find_slots_in_window(
            window_start=datetime(2024, 5, 10, 9, 0),
            window_end=datetime(2024, 5, 10, 12, 0),
            duration_minutes=60,
        )
        # -> [datetime(2024,5,10,9,0), datetime(2024,5,10,9,30), ...]
        ```

        ```python
        # Get free windows from a working day:
        windows = calc.merge_free_windows(
            work_start=datetime(2024,5,10,9,0),
            work_end=datetime(2024,5,10,18,0),
            busy_intervals=[(datetime(2024,5,10,10,0), datetime(2024,5,10,11,0))],
        )
        # -> [(9:00, 10:00), (11:10, 18:00)]
        ```
    """

    def __init__(self, step_minutes: int = 30) -> None:
        """
        Args:
            step_minutes: Grid slot step in minutes. Defaults to 30.
                          Determines the interval at which slots are offered.
        """
        if step_minutes <= 0:
            raise ValueError(f"step_minutes должен быть > 0, получен: {step_minutes}")
        self.step_minutes = step_minutes
        self._step_delta = timedelta(minutes=step_minutes)

    def find_slots_in_window(
        self,
        window_start: datetime,
        window_end: datetime,
        duration_minutes: int,
        min_start: datetime | None = None,
        grid_anchor: datetime | None = None,
    ) -> list[datetime]:
        """
        Returns a list of possible start times within the window.

        Algorithm: sliding window with a step of self.step_minutes.
        Each candidate is checked: does the service [slot, slot+duration]
        fit within the end of the window.

        Args:
            window_start: Start of the free time window.
            window_end: End of the free time window.
            duration_minutes: Duration of the service in minutes.
            min_start: Minimum acceptable start time (e.g., "no earlier than
                       15 minutes from the current time"). None = no limit.
            grid_anchor: Anchor for grid alignment (e.g., shifts start).
                         If provided, slots will be aligned to (grid_anchor + N * step).

        Returns:
            List of datetime — possible service start moments.
            Empty list if the service does not fit in the window.

        Example:
            # Window 9:00-11:00, service 60 min, step 30 min:
            # -> [9:00, 9:30, 10:00]  (10:30 + 60 min = 11:30, does not fit)
        """
        duration_delta = timedelta(minutes=duration_minutes)

        # Быстрая проверка: окно в принципе достаточно для услуги
        if window_end - window_start < duration_delta:
            return []

        slots: list[datetime] = []
        current = window_start

        # Если есть min_start — двигаем указатель к ближайшему шагу сетки
        if min_start and current < min_start:
            current = min_start

        # Если задан якорь — выравниваем текущую позицию по сетке относительно якоря
        # Если якоря нет — по умолчанию выравниваем по началу окна (обратная совместимость)
        anchor = grid_anchor or window_start
        current = self._align_to_grid(current, anchor)

        while current + duration_delta <= window_end:
            slots.append(current)
            current += self._step_delta

        return slots

    def merge_free_windows(
        self,
        work_start: datetime,
        work_end: datetime,
        busy_intervals: list[tuple[datetime, datetime]],
        break_interval: tuple[datetime, datetime] | None = None,
        buffer_minutes: int = 0,
        min_duration_minutes: int = 0,
    ) -> list[tuple[datetime, datetime]]:
        """
        Calculates a list of free windows from a working day.

        Subtracts from the interval [work_start, work_end]:
        - busy_intervals (booked appointments)
        - break_interval (resource's break)
        - buffer_minutes (buffer after each booked interval)

        Args:
            work_start: Start of the resource's working day.
            work_end: End of the resource's working day.
            busy_intervals: List of busy segments [(start, end), ...].
            break_interval: Resource's break (lunch), tuple (start, end) or None.
            buffer_minutes: Buffer in minutes added after each booked appointment.
            min_duration_minutes: Minimum window length. Windows shorter than this value
                                  are discarded as "junk".

        Returns:
            List of free windows [(start, end), ...] sorted by time.

        Example:
            ```python
            # Work day 9:00-18:00, booked 10:00-11:00, lunch 13:00-14:00
            windows = calc.merge_free_windows(
                work_start=dt(9,0), work_end=dt(18,0),
                busy_intervals=[(dt(10,0), dt(11,0))],
                break_interval=(dt(13,0), dt(14,0)),
                buffer_minutes=10,
            )
            # -> [(9:00, 10:00), (11:10, 13:00), (14:00, 18:00)]
            ```
        """
        buffer_delta = timedelta(minutes=buffer_minutes)

        # Collect all "busy" intervals: appointments + break
        blocked: list[tuple[datetime, datetime]] = []
        for b_start, b_end in busy_intervals:
            # Apply buffer after the booked appointment
            blocked.append((b_start, b_end + buffer_delta))

        if break_interval:
            blocked.append(break_interval)

        # Sort and merge overlapping intervals
        blocked = self._merge_intervals(blocked)

        # Calculate free windows
        free_windows: list[tuple[datetime, datetime]] = []
        current_ptr = work_start

        for b_start, b_end in blocked:
            # Cut off segments outside the working day
            b_start = max(b_start, work_start)
            b_end = min(b_end, work_end)

            if b_start > current_ptr:
                # Junk window filter
                if min_duration_minutes > 0:
                    duration = (b_start - current_ptr).total_seconds() / 60
                    if duration < min_duration_minutes:
                        current_ptr = max(current_ptr, b_end)
                        continue

                free_windows.append((current_ptr, b_start))

            current_ptr = max(current_ptr, b_end)

        # Remaining time after the last busy block
        if current_ptr < work_end:
            if min_duration_minutes > 0:
                duration = (work_end - current_ptr).total_seconds() / 60
                if duration >= min_duration_minutes:
                    free_windows.append((current_ptr, work_end))
            else:
                free_windows.append((current_ptr, work_end))

        return free_windows

    def find_gaps(
        self,
        free_windows: list[tuple[datetime, datetime]],
        min_gap_minutes: int,
    ) -> list[tuple[datetime, datetime, int]]:
        """
        Finds all free windows of minimum length in the resource's schedule.

        Used for:
            - Load analysis: how much free time the resource has
            - Notifications: resource is free for N minutes -> offer to user

        Args:
            free_windows: Free windows from ResourceAvailability.free_windows
            min_gap_minutes: Minimum window length in minutes.

        Returns:
            List (window_start, window_end, duration_minutes) — windows
            longer than min_gap_minutes, sorted by start time.

        Examples:
            ```python
            # Search for windows >= 60 minutes:
            gaps = calc.find_gaps(free_windows, min_gap_minutes=60)
            # -> [(9:00, 10:00, 60), (11:30, 14:00, 150), (16:00, 18:00, 120)]
            ```
        """
        result: list[tuple[datetime, datetime, int]] = []

        for w_start, w_end in free_windows:
            duration = int((w_end - w_start).total_seconds() / 60)
            if duration >= min_gap_minutes:
                result.append((w_start, w_end, duration))

        result.sort(key=lambda x: x[0])
        return result

    def split_window_by_service(
        self,
        window_start: datetime,
        window_end: datetime,
        service_start: datetime,
        service_end: datetime,
    ) -> list[tuple[datetime, datetime]]:
        """
        Splits a free window into parts around a booked service segment.

        Used for dynamic calculation: "if we put a service here —
        what windows will remain free for the next ones?"

        Args:
            window_start: Start of the free window.
            window_end: End of the free window.
            service_start: Start of the booked segment (must be inside the window).
            service_end: End of the booked segment (must be inside the window).

        Returns:
            List of remaining free windows (0, 1, or 2 elements).

        Example:
            # Window 9:00-18:00, service 11:00-12:00:
            split_window_by_service(9:00, 18:00, 11:00, 12:00)
            # -> [(9:00, 11:00), (12:00, 18:00)]

            # Service at the start of the window:
            split_window_by_service(9:00, 18:00, 9:00, 11:00)
            # -> [(11:00, 18:00)]
        """
        remaining: list[tuple[datetime, datetime]] = []

        # Part before the service
        if service_start > window_start:
            remaining.append((window_start, service_start))

        # Part after the service
        if service_end < window_end:
            remaining.append((service_end, window_end))

        return remaining

    # ---------------------------------------------------------------------------
    # Internal helper methods
    # ---------------------------------------------------------------------------

    def _merge_intervals(self, intervals: list[tuple[datetime, datetime]]) -> list[tuple[datetime, datetime]]:
        """
        Merges overlapping or adjacent intervals.
        Returns a sorted list of non-overlapping intervals.

        Internal method. Used in merge_free_windows.
        """
        if not intervals:
            return []

        sorted_intervals = sorted(intervals, key=lambda x: x[0])
        merged: list[tuple[datetime, datetime]] = [sorted_intervals[0]]

        for start, end in sorted_intervals[1:]:
            last_start, last_end = merged[-1]
            if start <= last_end:
                # Overlap — expand current block
                merged[-1] = (last_start, max(last_end, end))
            else:
                merged.append((start, end))

        return merged

    def _align_to_grid(self, target: datetime, grid_origin: datetime) -> datetime:
        """
        Aligns target to the nearest grid step relative to grid_origin.
        Returns the first grid moment >= target.

        Internal method. Used to align min_start to the grid.

        Example (step 30 min, origin 9:00, target 9:17):
            -> 9:30  (nearest step >= 9:17)
        """
        delta_seconds = (target - grid_origin).total_seconds()
        step_seconds = self._step_delta.total_seconds()

        if delta_seconds <= 0:
            return grid_origin

        # Number of full steps
        full_steps = int(delta_seconds / step_seconds)
        aligned = grid_origin + timedelta(seconds=full_steps * step_seconds)

        if aligned < target:
            aligned += self._step_delta

        return aligned
