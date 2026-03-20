"""Unit tests for BookingValidator."""

from datetime import datetime

import pytest

from codex_services.booking._shared.validators import BookingValidator
from codex_services.booking.slot_master.dto import SingleServiceSolution


def dt(h: int, m: int = 0) -> datetime:
    return datetime(2024, 5, 10, h, m)


def make_solution(resource_id: str, start_h: int, end_h: int, gap_h: int | None = None) -> SingleServiceSolution:
    gap_end = dt(gap_h) if gap_h is not None else dt(end_h)
    return SingleServiceSolution(
        service_id="svc1",
        resource_id=resource_id,
        start_time=dt(start_h),
        end_time=dt(end_h),
        gap_end_time=gap_end,
    )


@pytest.mark.unit
class TestIsSlotFree:
    def setup_method(self) -> None:
        self.v = BookingValidator()

    def test_free_slot_no_busy(self) -> None:
        assert self.v.is_slot_free(dt(10), dt(11), []) is True

    def test_free_slot_before_busy(self) -> None:
        assert self.v.is_slot_free(dt(9), dt(10), [(dt(10), dt(11))]) is True

    def test_free_slot_after_busy(self) -> None:
        assert self.v.is_slot_free(dt(11), dt(12), [(dt(10), dt(11))]) is True

    def test_overlap_start(self) -> None:
        assert self.v.is_slot_free(dt(9, 30), dt(10, 30), [(dt(10), dt(11))]) is False

    def test_overlap_end(self) -> None:
        assert self.v.is_slot_free(dt(10, 30), dt(11, 30), [(dt(10), dt(11))]) is False

    def test_overlap_full_contains(self) -> None:
        assert self.v.is_slot_free(dt(10), dt(11), [(dt(9), dt(12))]) is False

    def test_adjacent_end_equals_busy_start(self) -> None:
        # [9:00, 10:00) adjacent to busy [10:00, 11:00) → OK
        assert self.v.is_slot_free(dt(9), dt(10), [(dt(10), dt(11))]) is True

    def test_multiple_busy_all_free(self) -> None:
        busy = [(dt(8), dt(9)), (dt(11), dt(12))]
        assert self.v.is_slot_free(dt(9), dt(11), busy) is True

    def test_multiple_busy_one_overlap(self) -> None:
        busy = [(dt(8), dt(9)), (dt(10), dt(11))]
        assert self.v.is_slot_free(dt(9), dt(10, 30), busy) is False


@pytest.mark.unit
class TestNoConflicts:
    def setup_method(self) -> None:
        self.v = BookingValidator()

    def test_empty_solutions(self) -> None:
        assert self.v.no_conflicts([]) is True

    def test_single_solution(self) -> None:
        sol = make_solution("m1", 10, 11)
        assert self.v.no_conflicts([sol]) is True

    def test_different_resources_no_conflict(self) -> None:
        sol1 = make_solution("m1", 10, 11)
        sol2 = make_solution("m2", 10, 11)
        assert self.v.no_conflicts([sol1, sol2]) is True

    def test_same_resource_adjacent_ok(self) -> None:
        sol1 = make_solution("m1", 10, 11, gap_h=11)
        sol2 = make_solution("m1", 11, 12, gap_h=12)
        assert self.v.no_conflicts([sol1, sol2]) is True

    def test_same_resource_conflict(self) -> None:
        sol1 = make_solution(
            "m1",
            10,
            11,
            gap_h=11,
        )
        # sol2 starts at 10:30 but sol1 gap_end is 11:00 → conflict
        sol2 = SingleServiceSolution(
            service_id="svc2",
            resource_id="m1",
            start_time=dt(10, 30),
            end_time=dt(11, 30),
            gap_end_time=dt(11, 30),
        )
        assert self.v.no_conflicts([sol1, sol2]) is False

    def test_same_resource_gap_conflict(self) -> None:
        # gap_end_time includes buffer — next slot starts during buffer → conflict
        sol1 = make_solution("m1", 10, 11, gap_h=11)
        # Overlap: sol2 starts at 10:45, before gap_end 11:00
        sol2 = SingleServiceSolution(
            service_id="svc2",
            resource_id="m1",
            start_time=dt(10, 45),
            end_time=dt(11, 45),
            gap_end_time=dt(11, 45),
        )
        assert self.v.no_conflicts([sol1, sol2]) is False


@pytest.mark.unit
class TestSolutionFitsInWindows:
    def setup_method(self) -> None:
        self.v = BookingValidator()

    def test_fits_perfectly(self) -> None:
        sol = make_solution("m1", 10, 11)
        windows = [(dt(9), dt(12))]
        assert self.v.solution_fits_in_windows(sol, windows) is True

    def test_fits_exact_boundaries(self) -> None:
        sol = make_solution("m1", 10, 11)
        windows = [(dt(10), dt(11))]
        assert self.v.solution_fits_in_windows(sol, windows) is True

    def test_does_not_fit_start_before_window(self) -> None:
        sol = make_solution("m1", 9, 10)
        windows = [(dt(10), dt(12))]
        assert self.v.solution_fits_in_windows(sol, windows) is False

    def test_does_not_fit_end_after_window(self) -> None:
        sol = make_solution("m1", 11, 12)
        windows = [(dt(9), dt(11))]
        assert self.v.solution_fits_in_windows(sol, windows) is False

    def test_fits_in_second_window(self) -> None:
        sol = make_solution("m1", 14, 15)
        windows = [(dt(9), dt(12)), (dt(13), dt(17))]
        assert self.v.solution_fits_in_windows(sol, windows) is True

    def test_empty_windows(self) -> None:
        sol = make_solution("m1", 10, 11)
        assert self.v.solution_fits_in_windows(sol, []) is False
