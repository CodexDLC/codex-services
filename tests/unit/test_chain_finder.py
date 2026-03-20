"""Unit tests for ChainFinder."""

from datetime import date, datetime

import pytest

from codex_services.booking.slot_master import ChainFinder
from codex_services.booking.slot_master.dto import (
    BookingEngineRequest,
    MasterAvailability,
    ServiceRequest,
)
from codex_services.booking.slot_master.modes import BookingMode


def dt(h: int, m: int = 0, day: int = 10) -> datetime:
    return datetime(2024, 5, day, h, m)


def make_avail(
    resource_id: str,
    windows: list[tuple[datetime, datetime]],
    buffer: int = 0,
) -> MasterAvailability:
    return MasterAvailability(
        resource_id=resource_id,
        free_windows=windows,
        buffer_between_minutes=buffer,
    )


def make_sr(
    service_id: str,
    duration: int,
    resources: list[str],
    gap: int = 0,
    group: str | None = None,
) -> ServiceRequest:
    return ServiceRequest(
        service_id=service_id,
        duration_minutes=duration,
        possible_resource_ids=resources,
        min_gap_after_minutes=gap,
        parallel_group=group,
    )


def make_req(
    services: list[ServiceRequest],
    booking_day: int = 10,
    mode: BookingMode = BookingMode.SINGLE_DAY,
    overlap: bool = False,
    max_duration: int | None = None,
    group_size: int = 1,
) -> BookingEngineRequest:
    return BookingEngineRequest(
        service_requests=services,
        booking_date=date(2024, 5, booking_day),
        mode=mode,
        overlap_allowed=overlap,
        max_chain_duration_minutes=max_duration,
        group_size=group_size,
    )


# ---------------------------------------------------------------------------
# Single service
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestChainFinderSingleService:
    def setup_method(self) -> None:
        self.finder = ChainFinder(step_minutes=30)

    def test_finds_slot_in_window(self) -> None:
        req = make_req([make_sr("s1", 60, ["m1"])])
        avail = {"m1": make_avail("m1", [(dt(9), dt(12))])}
        result = self.finder.find(req, avail)
        assert result.has_solutions
        assert result.solutions[0].items[0].service_id == "s1"
        assert result.solutions[0].items[0].resource_id == "m1"

    def test_no_resources_in_availability(self) -> None:
        req = make_req([make_sr("s1", 60, ["m1"])])
        result = self.finder.find(req, {})
        assert not result.has_solutions

    def test_window_too_short_no_slots(self) -> None:
        req = make_req([make_sr("s1", 120, ["m1"])])
        avail = {"m1": make_avail("m1", [(dt(9), dt(10))])}  # 60 min, need 120
        result = self.finder.find(req, avail)
        assert not result.has_solutions

    def test_max_solutions_limits_count(self) -> None:
        req = make_req([make_sr("s1", 30, ["m1"])])
        avail = {"m1": make_avail("m1", [(dt(9), dt(18))])}
        result = self.finder.find(req, avail, max_solutions=3)
        assert len(result.solutions) == 3

    def test_result_mode_matches_request(self) -> None:
        req = make_req([make_sr("s1", 60, ["m1"])], mode=BookingMode.RESOURCE_LOCKED)
        avail = {"m1": make_avail("m1", [(dt(9), dt(12))])}
        result = self.finder.find(req, avail)
        assert result.mode == BookingMode.RESOURCE_LOCKED

    def test_solutions_sorted_by_start_time(self) -> None:
        req = make_req([make_sr("s1", 60, ["m1"])])
        avail = {"m1": make_avail("m1", [(dt(9), dt(18))])}
        result = self.finder.find(req, avail)
        starts = [s.starts_at for s in result.solutions]
        assert starts == sorted(starts)

    def test_alternative_resources_tried(self) -> None:
        # m1 has no availability, m2 has it
        req = make_req([make_sr("s1", 60, ["m1", "m2"])])
        avail = {"m2": make_avail("m2", [(dt(9), dt(12))])}
        result = self.finder.find(req, avail)
        assert result.has_solutions
        assert result.solutions[0].items[0].resource_id == "m2"

    def test_buffer_between_bookings_respected(self) -> None:
        # Resource has buffer=30, window 9:00-12:00. Slots should not overlap with buffer.
        req = make_req([make_sr("s1", 60, ["m1"])])
        avail = {"m1": make_avail("m1", [(dt(9), dt(12))], buffer=30)}
        result = self.finder.find(req, avail)
        assert result.has_solutions


# ---------------------------------------------------------------------------
# Two services, sequential (overlap_allowed=False)
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestChainFinderTwoServicesSequential:
    def setup_method(self) -> None:
        self.finder = ChainFinder(step_minutes=30)

    def test_s2_starts_after_s1_ends(self) -> None:
        req = make_req(
            [make_sr("s1", 60, ["m1"]), make_sr("s2", 60, ["m2"])],
            overlap=False,
        )
        avail = {
            "m1": make_avail("m1", [(dt(9), dt(18))]),
            "m2": make_avail("m2", [(dt(9), dt(18))]),
        }
        result = self.finder.find(req, avail, max_solutions=5)
        assert result.has_solutions
        for chain in result.solutions:
            s1 = next(i for i in chain.items if i.service_id == "s1")
            s2 = next(i for i in chain.items if i.service_id == "s2")
            assert s2.start_time >= s1.end_time

    def test_same_resource_services_do_not_overlap(self) -> None:
        req = make_req(
            [make_sr("s1", 60, ["m1"]), make_sr("s2", 60, ["m1"])],
            overlap=False,
        )
        avail = {"m1": make_avail("m1", [(dt(9), dt(18))])}
        result = self.finder.find(req, avail, max_solutions=10)
        assert result.has_solutions
        for chain in result.solutions:
            items = sorted(chain.items, key=lambda i: i.start_time)
            assert items[1].start_time >= items[0].gap_end_time

    def test_gap_between_services_enforced(self) -> None:
        req = make_req(
            [make_sr("s1", 60, ["m1"], gap=30), make_sr("s2", 60, ["m2"])],
            overlap=False,
        )
        avail = {
            "m1": make_avail("m1", [(dt(9), dt(18))]),
            "m2": make_avail("m2", [(dt(9), dt(18))]),
        }
        result = self.finder.find(req, avail, max_solutions=5)
        assert result.has_solutions
        for chain in result.solutions:
            s1 = next(i for i in chain.items if i.service_id == "s1")
            s2 = next(i for i in chain.items if i.service_id == "s2")
            # overlap_allowed=False → s2 starts after s1.end_time (chain_ends_at).
            # gap_after blocks s1's own resource only, not a different resource (m2).
            assert s2.start_time >= s1.end_time

    def test_no_solution_if_window_too_tight(self) -> None:
        # m1 busy all day, m2 has only 30 min
        req = make_req([make_sr("s1", 60, ["m1"]), make_sr("s2", 60, ["m2"])])
        avail = {
            "m1": make_avail("m1", [(dt(9), dt(10))]),  # 60 min for s1
            "m2": make_avail("m2", [(dt(9), dt(9, 30))]),  # only 30 min — not enough for s2
        }
        result = self.finder.find(req, avail)
        assert not result.has_solutions


# ---------------------------------------------------------------------------
# Two services, parallel (overlap_allowed=True)
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestChainFinderTwoServicesParallel:
    def setup_method(self) -> None:
        self.finder = ChainFinder(step_minutes=30)

    def test_parallel_solutions_exist(self) -> None:
        req = make_req(
            [make_sr("s1", 60, ["m1"]), make_sr("s2", 60, ["m2"])],
            overlap=True,
        )
        avail = {
            "m1": make_avail("m1", [(dt(9), dt(12))]),
            "m2": make_avail("m2", [(dt(9), dt(12))]),
        }
        result = self.finder.find(req, avail, max_solutions=20)
        assert result.has_solutions
        # At least one solution where both start at the same time
        parallel = [c for c in result.solutions if c.items[0].start_time == c.items[1].start_time]
        assert len(parallel) > 0


# ---------------------------------------------------------------------------
# Parallel group
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestChainFinderParallelGroup:
    def setup_method(self) -> None:
        self.finder = ChainFinder(step_minutes=30)

    def test_parallel_group_forces_same_start(self) -> None:
        req = make_req(
            [
                make_sr("s1", 60, ["m1"], group="together"),
                make_sr("s2", 60, ["m2"], group="together"),
            ],
            overlap=True,
        )
        avail = {
            "m1": make_avail("m1", [(dt(9), dt(12))]),
            "m2": make_avail("m2", [(dt(9), dt(12))]),
        }
        result = self.finder.find(req, avail, max_solutions=10)
        assert result.has_solutions
        for chain in result.solutions:
            s1 = next(i for i in chain.items if i.service_id == "s1")
            s2 = next(i for i in chain.items if i.service_id == "s2")
            assert s1.start_time == s2.start_time

    def test_parallel_group_requires_both_resources_free(self) -> None:
        # m2 available only 11:00-12:00 → s2 forced to match s1's start, but m2 not free at 9:00
        req = make_req(
            [
                make_sr("s1", 60, ["m1"], group="together"),
                make_sr("s2", 60, ["m2"], group="together"),
            ],
            overlap=True,
        )
        avail = {
            "m1": make_avail("m1", [(dt(9), dt(12))]),
            "m2": make_avail("m2", [(dt(11), dt(12))]),  # only 11:00-12:00
        }
        result = self.finder.find(req, avail, max_solutions=10)
        assert result.has_solutions
        for chain in result.solutions:
            s1 = next(i for i in chain.items if i.service_id == "s1")
            s2 = next(i for i in chain.items if i.service_id == "s2")
            assert s1.start_time == s2.start_time == dt(11)


# ---------------------------------------------------------------------------
# max_chain_duration_minutes
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestChainFinderMaxChainDuration:
    def setup_method(self) -> None:
        self.finder = ChainFinder(step_minutes=30)

    def test_filters_chains_exceeding_limit(self) -> None:
        # m1 available 9:00-10:00, m2 available 11:00-12:00
        # s1 at 9:00-9:30 + s2 at 11:00-11:30 → span = 150 min > 90 → all cut off
        req = make_req(
            [make_sr("s1", 30, ["m1"]), make_sr("s2", 30, ["m2"])],
            overlap=False,
            max_duration=90,
        )
        avail = {
            "m1": make_avail("m1", [(dt(9), dt(10))]),
            "m2": make_avail("m2", [(dt(11), dt(12))]),
        }
        result = self.finder.find(req, avail, max_solutions=50)
        assert not result.has_solutions

    def test_allows_chains_within_limit(self) -> None:
        # same avail, but limit=200 → 150 ≤ 200 → solutions exist
        req = make_req(
            [make_sr("s1", 30, ["m1"]), make_sr("s2", 30, ["m2"])],
            overlap=False,
            max_duration=200,
        )
        avail = {
            "m1": make_avail("m1", [(dt(9), dt(10))]),
            "m2": make_avail("m2", [(dt(11), dt(12))]),
        }
        result = self.finder.find(req, avail, max_solutions=50)
        assert result.has_solutions
        for chain in result.solutions:
            assert chain.span_minutes <= 200


# ---------------------------------------------------------------------------
# NotImplementedError cases
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestChainFinderNotImplemented:
    def setup_method(self) -> None:
        self.finder = ChainFinder()

    def test_multi_day_raises(self) -> None:
        req = make_req([make_sr("s1", 60, ["m1"])], mode=BookingMode.MULTI_DAY)
        with pytest.raises(NotImplementedError):
            self.finder.find(req, {})

    def test_group_size_greater_than_one_raises(self) -> None:
        req = make_req([make_sr("s1", 60, ["m1"])], group_size=2)
        with pytest.raises(NotImplementedError):
            self.finder.find(req, {})


# ---------------------------------------------------------------------------
# find_nearest
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestChainFinderFindNearest:
    def setup_method(self) -> None:
        self.finder = ChainFinder(step_minutes=30)

    def test_finds_slot_on_next_available_day(self) -> None:
        req = make_req([make_sr("s1", 60, ["m1"])])

        def get_avail(d: date) -> dict[str, MasterAvailability]:
            if d == date(2024, 5, 11):
                return {"m1": make_avail("m1", [(datetime(2024, 5, 11, 9), datetime(2024, 5, 11, 12))])}
            return {}

        result = self.finder.find_nearest(req, get_avail, search_from=date(2024, 5, 10))
        assert result.has_solutions
        assert result.best is not None
        assert result.best.starts_at.date() == date(2024, 5, 11)

    def test_skips_empty_days(self) -> None:
        req = make_req([make_sr("s1", 60, ["m1"])])
        call_log: list[date] = []

        def get_avail(d: date) -> dict[str, MasterAvailability]:
            call_log.append(d)
            if d == date(2024, 5, 13):
                return {"m1": make_avail("m1", [(datetime(2024, 5, 13, 9), datetime(2024, 5, 13, 12))])}
            return {}

        result = self.finder.find_nearest(req, get_avail, search_from=date(2024, 5, 10))
        assert result.has_solutions
        # Days 10, 11, 12 were checked and skipped
        assert date(2024, 5, 10) in call_log
        assert date(2024, 5, 11) in call_log

    def test_returns_empty_when_nothing_found(self) -> None:
        req = make_req([make_sr("s1", 60, ["m1"])])
        result = self.finder.find_nearest(req, lambda d: {}, search_from=date(2024, 5, 10), search_days=5)
        assert not result.has_solutions
        assert result.mode == BookingMode.SINGLE_DAY

    def test_first_day_with_solutions_returned(self) -> None:
        req = make_req([make_sr("s1", 60, ["m1"])])
        days_checked: list[date] = []

        def get_avail(d: date) -> dict[str, MasterAvailability]:
            days_checked.append(d)
            # Both day 11 and 12 have availability
            return {
                "m1": make_avail("m1", [(datetime(d.year, d.month, d.day, 9), datetime(d.year, d.month, d.day, 12))])
            }

        result = self.finder.find_nearest(req, get_avail, search_from=date(2024, 5, 11))
        assert result.has_solutions
        # Should stop at day 11 (first day with solutions)
        assert result.best is not None
        assert result.best.starts_at.date() == date(2024, 5, 11)
        assert date(2024, 5, 12) not in days_checked


# ---------------------------------------------------------------------------
# Backtracking early exits (max_solutions / max_unique_starts)
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestChainFinderBacktrackEarlyExits:
    def setup_method(self) -> None:
        self.finder = ChainFinder(step_minutes=30)

    def test_max_solutions_cuts_recursion_mid_chain(self) -> None:
        # 2 services → after first complete chain, backtrack(1) fires 'solutions >= max' guard
        req = make_req([make_sr("s1", 30, ["m1"]), make_sr("s2", 30, ["m2"])], overlap=False)
        avail = {
            "m1": make_avail("m1", [(dt(9), dt(18))]),
            "m2": make_avail("m2", [(dt(9), dt(18))]),
        }
        result = self.finder.find(req, avail, max_solutions=1)
        assert len(result.solutions) == 1

    def test_max_solutions_in_parallel_forced_path(self) -> None:
        req = make_req(
            [
                make_sr("s1", 60, ["m1"], group="g"),
                make_sr("s2", 60, ["m2", "m3"], group="g"),
            ],
            overlap=True,
        )
        avail = {
            "m1": make_avail("m1", [(dt(9), dt(12))]),
            "m2": make_avail("m2", [(dt(9), dt(12))]),
            "m3": make_avail("m3", [(dt(9), dt(12))]),
        }
        result = self.finder.find(req, avail, max_solutions=1)
        assert len(result.solutions) == 1

    def test_max_unique_starts_in_parallel_forced_path(self) -> None:
        req = make_req(
            [
                make_sr("s1", 60, ["m1"], group="g"),
                make_sr("s2", 60, ["m2", "m3"], group="g"),
            ],
            overlap=True,
        )
        avail = {
            "m1": make_avail("m1", [(dt(9), dt(12))]),
            "m2": make_avail("m2", [(dt(9), dt(12))]),
            "m3": make_avail("m3", [(dt(9), dt(12))]),
        }
        result = self.finder.find(req, avail, max_solutions=50, max_unique_starts=1)
        starts = {s.starts_at.strftime("%H:%M") for s in result.solutions}
        assert len(starts) == 1

    def test_max_unique_starts_stops_slot_loop(self) -> None:
        req = make_req([make_sr("s1", 30, ["m1"])])
        avail = {"m1": make_avail("m1", [(dt(9), dt(18))])}
        result = self.finder.find(req, avail, max_solutions=100, max_unique_starts=2)
        starts = {s.starts_at.strftime("%H:%M") for s in result.solutions}
        assert len(starts) <= 2

    def test_max_unique_starts_deep_recursion(self) -> None:
        req = make_req(
            [make_sr("s1", 30, ["m1"]), make_sr("s2", 30, ["m2"]), make_sr("s3", 30, ["m3"])],
            overlap=False,
        )
        avail = {
            "m1": make_avail("m1", [(dt(9), dt(18))]),
            "m2": make_avail("m2", [(dt(9), dt(18))]),
            "m3": make_avail("m3", [(dt(9), dt(18))]),
        }
        result = self.finder.find(req, avail, max_solutions=100, max_unique_starts=1)
        starts = {s.starts_at.strftime("%H:%M") for s in result.solutions}
        assert len(starts) == 1


# ---------------------------------------------------------------------------
# Parallel group: forced start time conflict in chain
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestChainFinderForcedStartConflict:
    def setup_method(self) -> None:
        self.finder = ChainFinder(step_minutes=30)

    def test_parallel_group_same_resource_skips_conflict(self) -> None:
        req = make_req(
            [
                make_sr("s1", 60, ["m1"], group="together"),
                make_sr("s2", 60, ["m1", "m2"], group="together"),
            ],
            overlap=True,
        )
        avail = {
            "m1": make_avail("m1", [(dt(9), dt(12))]),
            "m2": make_avail("m2", [(dt(9), dt(12))]),
        }
        result = self.finder.find(req, avail, max_solutions=10)
        assert result.has_solutions
        for chain in result.solutions:
            s1 = next(i for i in chain.items if i.service_id == "s1")
            s2 = next(i for i in chain.items if i.service_id == "s2")
            assert s1.start_time == s2.start_time
            assert s1.resource_id != s2.resource_id


# ---------------------------------------------------------------------------
# Slot conflict in chain (overlap_allowed=True, same resource)
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestChainFinderSlotConflictInChain:
    def setup_method(self) -> None:
        self.finder = ChainFinder(step_minutes=30)

    def test_parallel_same_resource_skips_overlapping_slot(self) -> None:
        req = make_req(
            [make_sr("s1", 60, ["m1"]), make_sr("s2", 60, ["m1", "m2"])],
            overlap=True,
        )
        avail = {
            "m1": make_avail("m1", [(dt(9), dt(12))]),
            "m2": make_avail("m2", [(dt(9), dt(12))]),
        }
        result = self.finder.find(req, avail, max_solutions=5)
        assert result.has_solutions
        for chain in result.solutions:
            by_resource: dict[str, list] = {}
            for item in chain.items:
                by_resource.setdefault(item.resource_id, []).append(item)
            for items in by_resource.values():
                if len(items) > 1:
                    sorted_items = sorted(items, key=lambda i: i.start_time)
                    for i in range(len(sorted_items) - 1):
                        assert sorted_items[i + 1].start_time >= sorted_items[i].gap_end_time


# ---------------------------------------------------------------------------
# min_start parameter
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestChainFinderMinStart:
    def test_min_start_filters_early_slots(self) -> None:
        finder = ChainFinder(step_minutes=30, min_start=dt(10))
        req = make_req([make_sr("s1", 60, ["m1"])])
        avail = {"m1": make_avail("m1", [(dt(9), dt(18))])}
        result = finder.find(req, avail)
        assert result.has_solutions
        for chain in result.solutions:
            assert chain.starts_at >= dt(10)
