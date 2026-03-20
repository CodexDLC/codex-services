"""
codex_services.booking.slot_master.chain_finder
================================================
Main algorithm for finding slot chains for N services.

Framework-agnostic (does not depend on Django/ORM) -- works only with DTOs and datetime.
Acts as an orchestrator for SlotCalculator and BookingValidator.

Performance principle:
    Inside recursive search (backtracking) we use lightweight _SlotCandidate
    with __slots__ -- without Pydantic validation. Pydantic objects (SingleServiceSolution,
    BookingChainSolution) are created ONLY once for each found solution.
    This is critical with a large number of services and resources.

Imports:
    from codex_services.booking.slot_master import ChainFinder
"""

from collections.abc import Callable
from datetime import date, datetime, timedelta

from codex_services.booking._shared.calculator import SlotCalculator

from .dto import (
    BookingChainSolution,
    BookingEngineRequest,
    EngineResult,
    MasterAvailability,
    SingleServiceSolution,
)
from .modes import BookingMode


class _SlotCandidate:
    """
    Lightweight internal representation of a booked slot inside backtracking.

    Uses __slots__ for minimal memory consumption and fast access.
    Does NOT contain Pydantic validation -- only raw data.

    Converted to SingleServiceSolution (Pydantic) only for the final result.
    """

    __slots__ = (
        "service_id",
        "resource_id",
        "start_time",
        "end_time",
        "gap_end_time",
        "parallel_group",
    )

    def __init__(
        self,
        service_id: str,
        resource_id: str,
        start_time: datetime,
        end_time: datetime,
        gap_end_time: datetime,
        parallel_group: str | None = None,
    ) -> None:
        self.service_id = service_id
        self.resource_id = resource_id
        self.start_time = start_time
        self.end_time = end_time
        self.gap_end_time = gap_end_time
        self.parallel_group = parallel_group

    def to_solution(self) -> SingleServiceSolution:
        """Converts to Pydantic DTO for the final result."""
        return SingleServiceSolution(
            service_id=self.service_id,
            resource_id=self.resource_id,
            start_time=self.start_time,
            end_time=self.end_time,
            gap_end_time=self.gap_end_time,
        )


class ChainFinder:
    """
    Finds combinations of time slots for N services (booking chains).

    Core algorithm: recursive backtracking.
    Iterates over possible resources and their free windows for each service.
    Checks for the absence of conflicts with already assigned services in the chain.

    Examples:
        1 service, any free resource:
        ```python
        finder = ChainFinder(step_minutes=30)
        request = BookingEngineRequest(
            service_requests=[
                ServiceRequest(service_id="5", duration_minutes=60,
                               possible_resource_ids=["1", "2"])
            ],
            booking_date=date(2024, 5, 10),
            mode=BookingMode.SINGLE_DAY,
        )
        result = finder.find(request, resources_availability)
        # result.solutions -- list of BookingChainSolution
        # result.get_unique_start_times() -> ["09:00", "09:30", "10:00", ...]
        ```

        2 services on the same day:
        ```python
        request = BookingEngineRequest(
            service_requests=[svc_task_1, svc_task_2],
            booking_date=date(2024, 5, 10),
            mode=BookingMode.SINGLE_DAY,
        )
        result = finder.find(request, availability)
        ```

        Booking a specific resource (RESOURCE_LOCKED):
        ```python
        # Just pass possible_resource_ids=[locked_resource_id]
        # and mode=BookingMode.RESOURCE_LOCKED
        ```

    Args:
        step_minutes: Grid slot step (30 min by default).
        min_start: Minimum acceptable start time of the first service.
                   None = no restriction (e.g., in tests).
    """

    def __init__(
        self,
        step_minutes: int = 30,
        min_start: datetime | None = None,
    ) -> None:
        self.step_minutes = step_minutes
        self.min_start = min_start
        self._calc = SlotCalculator(step_minutes)

    def find(
        self,
        request: BookingEngineRequest,
        resources_availability: dict[str, MasterAvailability],
        max_solutions: int = 50,
        max_unique_starts: int | None = None,
    ) -> EngineResult:
        """
        Unified engine entry point. Delegates to the appropriate mode.

        Args:
            request: Input request with services, date, and mode.
            resources_availability: Dictionary {resource_id: MasterAvailability}.
                                    Usually prepared by an AvailabilityAdapter.
                                    Keys -- strings (resource identifiers).
            max_solutions: Maximum number of options the engine will return.
                           Does not affect correctness -- only completeness.
            max_unique_starts: Stop after finding N unique start times
                               (based on items[0].start_time).
                               None = no limit.
                               Example: max_unique_starts=8 -> only the closest 8 slots,
                               even if there are 16 in a day. Halves engine iterations.

        Returns:
            EngineResult with found solutions.
            solutions sorted by the start time of the first service.
        """
        # Fail Fast: Check for unsupported features
        if request.group_size > 1:
            raise NotImplementedError("Group bookings (group_size > 1) are not yet supported.")

        if request.mode == BookingMode.MULTI_DAY:
            raise NotImplementedError("MULTI_DAY booking mode is not yet implemented.")

        if request.mode in (BookingMode.SINGLE_DAY, BookingMode.RESOURCE_LOCKED):
            solutions = self._find_single_day(request, resources_availability, max_solutions, max_unique_starts)
        else:
            solutions = []  # pragma: no cover

        solutions.sort(key=lambda s: s.starts_at)
        return EngineResult(mode=request.mode, solutions=solutions)

    def find_nearest(
        self,
        request: BookingEngineRequest,
        get_availability_for_date: Callable[[date], dict[str, MasterAvailability]],
        search_from: date,
        search_days: int = 60,
        max_solutions_per_day: int = 1,
    ) -> EngineResult:
        """
        Searches for the first day with available slots in the search_days range.

        Used for:
            - Rebooking: resource is sick -> find a new date for N appointments
            - Waitlist: closest free slot to notify the client
            - MULTI_DAY planning: find the first day the chain fits

        Args:
            request: Request (booking_date will be replaced for each checked day).
            get_availability_for_date: callable(date) -> dict[str, MasterAvailability].
                                       Called for each checked day.
                                       Wraps DjangoAvailabilityAdapter in the Django layer.
            search_from: Date to start the search from (inclusive).
            search_days: Maximum days to check. Defaults to 60.
            max_solutions_per_day: How many solutions to look for per day.
                                   1 = fast mode (stop at the first one).

        Returns:
            EngineResult of the first day with solutions.
            If nothing found in search_days — EngineResult(solutions=[]).

        Example (Django layer):
            adapter = DjangoAvailabilityAdapter()
            resource_ids = [...]

            def get_avail(d):
                return adapter.build_resources_availability(resource_ids, d)

            result = finder.find_nearest(request, get_avail, search_from=date.today())
            if result.has_solutions:
                print(result.best.starts_at)  # date and time of the new slot
        """
        for offset in range(search_days):
            check_date = search_from + timedelta(days=offset)

            # Update date in the request (frozen=True -> model_copy)
            day_request = request.model_copy(update={"booking_date": check_date})

            availability = get_availability_for_date(check_date)
            if not availability:
                continue

            result = self.find(day_request, availability, max_solutions=max_solutions_per_day)
            if result.has_solutions:
                return result

        return EngineResult(mode=request.mode, solutions=[])

    # ---------------------------------------------------------------------------
    # SINGLE_DAY / RESOURCE_LOCKED mode
    # ---------------------------------------------------------------------------

    def _find_single_day(
        self,
        request: BookingEngineRequest,
        resources_availability: dict[str, MasterAvailability],
        max_solutions: int,
        max_unique_starts: int | None = None,
    ) -> list[BookingChainSolution]:
        """
        Search for a chain for the 'all services in one day' mode.

        Performance:
            Internally works with _SlotCandidate (__slots__) -- without Pydantic.
            Pydantic objects are created ONLY for final solutions.
            With 3 services x 3 resources x 20 slots -- up to 1800 iterations.

        Request parameters considered in this method:
            request.overlap_allowed:
                True  -> different resources work independently (can be parallel).
                False -> each subsequent service starts only after the previous one ends.
            request.max_chain_duration_minutes:
                If set — cuts off backtracking branches where the chain already exceeds the limit.
        """
        solutions: list[BookingChainSolution] = []
        chain: list[_SlotCandidate] = []
        seen_starts: set[str] = set()  # unique start times of the first service

        def backtrack(service_index: int) -> None:
            if len(solutions) >= max_solutions:
                return
            if max_unique_starts is not None and len(seen_starts) >= max_unique_starts:
                return

            if service_index >= len(request.service_requests):
                # Final check + conversion to Pydantic only here
                if self._no_conflicts_fast(chain):
                    solution = BookingChainSolution(items=[c.to_solution() for c in chain])
                    solutions.append(solution)
                    seen_starts.add(chain[0].start_time.strftime("%H:%M"))
                return

            service_req = request.service_requests[service_index]
            duration_delta = timedelta(minutes=service_req.duration_minutes)
            gap_delta = timedelta(minutes=service_req.min_gap_after_minutes)

            # --- Parallel Group Logic ---
            # If the current service has a parallel_group, look for a "partner" in the already assembled chain.
            # If found, the start time must strictly match.
            forced_start_time: datetime | None = None
            if service_req.parallel_group:
                for item in chain:
                    if item.parallel_group == service_req.parallel_group:
                        forced_start_time = item.start_time
                        break

            for resource_id in service_req.possible_resource_ids:
                availability = resources_availability.get(resource_id)
                if not availability:
                    continue

                # Busy intervals of this resource in the current chain
                resource_busy = [(c.start_time, c.gap_end_time) for c in chain if c.resource_id == resource_id]

                # If there is a forced_start_time, check only it
                if forced_start_time:
                    # Check if the resource is free at this specific time
                    slot_end = forced_start_time + duration_delta
                    gap_end = slot_end + gap_delta

                    # 1. Check resource's occupancy in the chain
                    if not self._is_slot_free_fast(forced_start_time, gap_end, resource_busy):
                        continue

                    # 2. Check if it falls into the resource's free windows
                    in_window = False
                    for w_start, w_end in availability.free_windows:
                        if w_start <= forced_start_time and w_end >= slot_end:
                            in_window = True
                            break

                    if not in_window:
                        continue

                    # If everything is ok - add and move on
                    chain.append(
                        _SlotCandidate(
                            service_id=service_req.service_id,
                            resource_id=resource_id,
                            start_time=forced_start_time,
                            end_time=slot_end,
                            gap_end_time=gap_end,
                            parallel_group=service_req.parallel_group,
                        )
                    )
                    backtrack(service_index + 1)
                    chain.pop()
                    continue  # Move to the next resource, no need to iterate over slots

                # --- Standard Logic (No forced start time) ---
                effective_min = self._effective_min_start(resource_busy, availability.buffer_between_minutes)

                # overlap_allowed=False: each service starts after the end of all previous ones
                if not request.overlap_allowed and chain:
                    chain_ends_at = max(c.end_time for c in chain)
                    if effective_min is None or effective_min < chain_ends_at:
                        effective_min = chain_ends_at

                # --- Anchor Logic ---
                # Use anchor only for the first service or if services are parallel.
                # For 2nd+ service in a sequential chain, anchor is None (tight fit).
                use_anchor = availability.work_start if (not chain or request.overlap_allowed) else None

                for window_start, window_end in availability.free_windows:
                    slots = self._calc.find_slots_in_window(
                        window_start=window_start,
                        window_end=window_end,
                        duration_minutes=service_req.duration_minutes,
                        min_start=effective_min,
                        grid_anchor=use_anchor,
                    )

                    for slot_start in slots:
                        if len(solutions) >= max_solutions:
                            return
                        if max_unique_starts is not None and len(seen_starts) >= max_unique_starts:
                            return

                        slot_end = slot_start + duration_delta
                        gap_end = slot_end + gap_delta

                        # Simple datetime comparison -- without Pydantic
                        if not self._is_slot_free_fast(slot_start, gap_end, resource_busy):  # pragma: no cover
                            continue  # pragma: no cover

                        # Check maximum chain duration
                        if request.max_chain_duration_minutes is not None and chain:
                            chain_start = min(c.start_time for c in chain)
                            prospective_span = int(
                                (max(slot_end, max(c.end_time for c in chain)) - chain_start).total_seconds() / 60
                            )
                            if prospective_span > request.max_chain_duration_minutes:
                                continue  # cut off branch - chain is too long

                        chain.append(
                            _SlotCandidate(
                                service_id=service_req.service_id,
                                resource_id=resource_id,
                                start_time=slot_start,
                                end_time=slot_end,
                                gap_end_time=gap_end,
                                parallel_group=service_req.parallel_group,
                            )
                        )
                        backtrack(service_index + 1)
                        chain.pop()

        backtrack(0)
        return solutions

    # ---------------------------------------------------------------------------
    # Fast internal checks (without Pydantic -- stdlib only)
    # ---------------------------------------------------------------------------

    @staticmethod
    def _is_slot_free_fast(
        slot_start: datetime,
        slot_end: datetime,
        busy_intervals: list[tuple[datetime, datetime]],
    ) -> bool:
        """Fast slot availability check. Without Pydantic."""
        return all(not (slot_start < b_end and slot_end > b_start) for b_start, b_end in busy_intervals)

    @staticmethod
    def _no_conflicts_fast(chain: list["_SlotCandidate"]) -> bool:
        """Final check of the chain for resource conflicts. Without Pydantic."""
        by_resource: dict[str, list[_SlotCandidate]] = {}
        for c in chain:
            if c.resource_id not in by_resource:
                by_resource[c.resource_id] = []
            by_resource[c.resource_id].append(c)

        for slots in by_resource.values():
            if len(slots) < 2:
                continue
            sorted_slots = sorted(slots, key=lambda s: s.start_time)
            for i in range(len(sorted_slots) - 1):
                if sorted_slots[i + 1].start_time < sorted_slots[i].gap_end_time:  # pragma: no cover
                    return False  # pragma: no cover

        return True

    def _effective_min_start(
        self,
        resource_busy: list[tuple[datetime, datetime]],
        buffer_minutes: int,
    ) -> datetime | None:
        """
        Minimum allowable start time for the resource.

        Considers:
            - self.min_start (global -- "no earlier than N mins from now")
            - End of the last booked slot + buffer between clients
        """
        candidates: list[datetime] = []

        if self.min_start:
            candidates.append(self.min_start)

        if resource_busy:
            last_end = max(end for _, end in resource_busy)
            candidates.append(last_end + timedelta(minutes=buffer_minutes))

        return max(candidates) if candidates else None
