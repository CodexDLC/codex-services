"""
codex_services.booking._shared.validators
==========================================
Validators for ensuring booking data correctness.

Used by ChainFinder to verify found solutions,
and can also be used independently in tests or the service layer.

Imports:
    from codex_services.booking import BookingValidator
"""

from datetime import datetime

from codex_services.booking._shared.dto import BookingSolution


class BookingValidator:
    """
    A set of correctness checks for booking data.
    Unaffected by the ORM — operates exclusively on DTOs.

    Used by:
        - ChainFinder: Ensuring found chains have no conflicts.
        - Adapter: Final verification before creating Appointment instances in the DB.
        - Tests: Isolated logic verification without Django.

    Example:
        v = BookingValidator()

        # Check if a slot is free:
        ok = v.is_slot_free(
            slot_start=datetime(2024,5,10,10,0),
            slot_end=datetime(2024,5,10,11,0),
            busy_intervals=[(datetime(2024,5,10,9,0), datetime(2024,5,10,9,30))],
        )
        # → True (no overlap)

        # Check entire chain for conflicts:
        ok = v.no_conflicts(solutions)
    """

    def is_slot_free(
        self,
        slot_start: datetime,
        slot_end: datetime,
        busy_intervals: list[tuple[datetime, datetime]],
    ) -> bool:
        """
        Verifies that the slot [slot_start, slot_end) does not overlap
        with any of the busy intervals.

        Uses a "half-open" interval — [start, end). If slot_end == busy_start,
        it is NOT considered a conflict (adjacent slots are allowed).

        Args:
            slot_start: Start of the slot to check.
            slot_end: End of the slot to check.
            busy_intervals: List of busy intervals [(start, end), ...].

        Returns:
            True if the slot is free. False if there is an overlap.

        Example:
            # Busy 10:00-11:00. Requesting 10:30-11:30 → conflict:
            is_slot_free(10:30, 11:30, [(10:00, 11:00)]) → False

            # Requesting 11:00-12:00 → OK (adjacent slots):
            is_slot_free(11:00, 12:00, [(10:00, 11:00)]) → True
        """
        return all(not (slot_start < busy_end and slot_end > busy_start) for busy_start, busy_end in busy_intervals)

    def no_conflicts(
        self,
        solutions: list[BookingSolution],
    ) -> bool:
        """
        Verifies that there are no resource conflicts within a set of solutions.
        A resource cannot be occupied by two services simultaneously.

        Groups solutions by resource_id and checks each group for overlaps.
        Used by ChainFinder after assembling the chain for final verification.

        Args:
            solutions: List of BookingSolution objects (found slots).

        Returns:
            True if no conflicts exist. False if at least one resource is double-booked.

        Example:
            no_conflicts([
                SingleServiceSolution(resource_id="1", start=9:00, gap_end=10:10),
                SingleServiceSolution(resource_id="1", start=10:10, gap_end=11:10),
            ])
            # → True (slots are adjacent, no overlap)
        """
        by_resource: dict[str, list[BookingSolution]] = {}
        for sol in solutions:
            by_resource.setdefault(sol.resource_id, []).append(sol)

        for _resource_id, resource_solutions in by_resource.items():
            if len(resource_solutions) < 2:
                continue
            sorted_sols = sorted(resource_solutions, key=lambda s: s.start_time)
            for i in range(len(sorted_sols) - 1):
                current = sorted_sols[i]
                next_sol = sorted_sols[i + 1]
                # For solutions with gap_end_time, use it; otherwise use end_time
                block_end = getattr(current, "gap_end_time", current.end_time)
                if next_sol.start_time < block_end:
                    return False

        return True

    def solution_fits_in_windows(
        self,
        solution: BookingSolution,
        free_windows: list[tuple[datetime, datetime]],
    ) -> bool:
        """
        Verifies that a solution's slot fits entirely inside one of the
        resource's free windows.

        Args:
            solution: Found slot for a single service.
            free_windows: Resource's free windows (from ResourceAvailability).

        Returns:
            True if the slot fits perfectly inside one of the given free windows.
        """
        block_end = getattr(solution, "gap_end_time", solution.end_time)
        return any(solution.start_time >= w_start and block_end <= w_end for w_start, w_end in free_windows)
