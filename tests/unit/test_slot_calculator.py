"""Unit tests for SlotCalculator."""

from datetime import datetime

import pytest

from codex_services.booking._shared.calculator import SlotCalculator


def dt(h: int, m: int = 0) -> datetime:
    return datetime(2024, 5, 10, h, m)


# ---------------------------------------------------------------------------
# Init
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestSlotCalculatorInit:
    def test_valid_step(self) -> None:
        calc = SlotCalculator(step_minutes=15)
        assert calc.step_minutes == 15

    def test_zero_step_raises(self) -> None:
        with pytest.raises(ValueError):
            SlotCalculator(step_minutes=0)

    def test_negative_step_raises(self) -> None:
        with pytest.raises(ValueError):
            SlotCalculator(step_minutes=-10)


# ---------------------------------------------------------------------------
# find_slots_in_window
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestFindSlotsInWindow:
    def setup_method(self) -> None:
        self.calc = SlotCalculator(step_minutes=30)

    def test_basic_slots(self) -> None:
        slots = self.calc.find_slots_in_window(dt(9), dt(12), 60)
        assert slots == [dt(9), dt(9, 30), dt(10), dt(10, 30), dt(11)]

    def test_window_too_short_returns_empty(self) -> None:
        slots = self.calc.find_slots_in_window(dt(9), dt(9, 30), 60)
        assert slots == []

    def test_exact_fit_one_slot(self) -> None:
        slots = self.calc.find_slots_in_window(dt(9), dt(10), 60)
        assert slots == [dt(9)]

    def test_min_start_aligns_to_grid(self) -> None:
        # min_start 9:17 → nearest grid step ≥ 9:17 is 9:30
        slots = self.calc.find_slots_in_window(dt(9), dt(12), 60, min_start=dt(9, 17))
        assert dt(9) not in slots
        assert slots[0] == dt(9, 30)

    def test_min_start_on_grid_boundary(self) -> None:
        slots = self.calc.find_slots_in_window(dt(9), dt(12), 60, min_start=dt(9, 30))
        assert dt(9) not in slots
        assert slots[0] == dt(9, 30)

    def test_min_start_beyond_window_empty(self) -> None:
        slots = self.calc.find_slots_in_window(dt(9), dt(10), 60, min_start=dt(11))
        assert slots == []

    def test_step_15_minutes(self) -> None:
        calc = SlotCalculator(step_minutes=15)
        slots = calc.find_slots_in_window(dt(9), dt(10), 30)
        assert slots == [dt(9), dt(9, 15), dt(9, 30)]

    def test_no_min_start_starts_from_window(self) -> None:
        slots = self.calc.find_slots_in_window(dt(10), dt(12), 60)
        assert slots[0] == dt(10)


# ---------------------------------------------------------------------------
# merge_free_windows
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestMergeFreeWindows:
    def setup_method(self) -> None:
        self.calc = SlotCalculator(step_minutes=30)

    def test_no_busy_returns_full_day(self) -> None:
        result = self.calc.merge_free_windows(dt(9), dt(18), [])
        assert result == [(dt(9), dt(18))]

    def test_busy_in_middle_splits_day(self) -> None:
        result = self.calc.merge_free_windows(dt(9), dt(18), [(dt(10), dt(11))])
        assert result == [(dt(9), dt(10)), (dt(11), dt(18))]

    def test_busy_at_start(self) -> None:
        result = self.calc.merge_free_windows(dt(9), dt(18), [(dt(9), dt(11))])
        assert result == [(dt(11), dt(18))]

    def test_busy_at_end(self) -> None:
        result = self.calc.merge_free_windows(dt(9), dt(18), [(dt(16), dt(18))])
        assert result == [(dt(9), dt(16))]

    def test_fully_busy_returns_empty(self) -> None:
        result = self.calc.merge_free_windows(dt(9), dt(18), [(dt(9), dt(18))])
        assert result == []

    def test_buffer_after_busy(self) -> None:
        result = self.calc.merge_free_windows(dt(9), dt(18), [(dt(10), dt(11))], buffer_minutes=10)
        assert result == [(dt(9), dt(10)), (dt(11, 10), dt(18))]

    def test_break_interval(self) -> None:
        result = self.calc.merge_free_windows(
            dt(9),
            dt(18),
            [(dt(10), dt(11))],
            break_interval=(dt(13), dt(14)),
        )
        assert result == [(dt(9), dt(10)), (dt(11), dt(13)), (dt(14), dt(18))]

    def test_overlapping_busy_merged(self) -> None:
        result = self.calc.merge_free_windows(dt(9), dt(18), [(dt(10), dt(12)), (dt(11), dt(13))])
        assert result == [(dt(9), dt(10)), (dt(13), dt(18))]

    def test_min_duration_filters_short_window(self) -> None:
        # busy 10:00-17:30 → 9:00-10:00 (60 min) and 17:30-18:00 (30 min)
        result = self.calc.merge_free_windows(
            dt(9),
            dt(18),
            [(dt(10), dt(17, 30))],
            min_duration_minutes=60,
        )
        assert result == [(dt(9), dt(10))]

    def test_two_busy_no_overlap(self) -> None:
        result = self.calc.merge_free_windows(dt(9), dt(18), [(dt(10), dt(11)), (dt(13), dt(14))])
        assert result == [(dt(9), dt(10)), (dt(11), dt(13)), (dt(14), dt(18))]

    def test_min_duration_filters_short_window_before_busy(self) -> None:
        # Gap before busy (9:00-9:15 = 15 min) is too short → filtered (lines 182-183)
        # Gap after busy (10:00-18:00) passes → included
        result = self.calc.merge_free_windows(
            dt(9),
            dt(18),
            [(dt(9, 15), dt(10))],
            min_duration_minutes=30,
        )
        assert result == [(dt(10), dt(18))]

    def test_min_duration_includes_tail_window(self) -> None:
        # Busy at start: no pre-busy window. Tail 10:00-18:00 = 480 min >= 60 → line 194 appends
        result = self.calc.merge_free_windows(
            dt(9),
            dt(18),
            [(dt(9), dt(10))],
            min_duration_minutes=60,
        )
        assert result == [(dt(10), dt(18))]


# ---------------------------------------------------------------------------
# find_gaps
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestFindGaps:
    def setup_method(self) -> None:
        self.calc = SlotCalculator(step_minutes=30)

    def test_finds_long_gap(self) -> None:
        gaps = self.calc.find_gaps([(dt(9), dt(12))], min_gap_minutes=60)
        assert len(gaps) == 1
        assert gaps[0] == (dt(9), dt(12), 180)

    def test_filters_short_gap(self) -> None:
        gaps = self.calc.find_gaps([(dt(9), dt(9, 30)), (dt(10), dt(12))], min_gap_minutes=60)
        assert len(gaps) == 1
        assert gaps[0][2] == 120

    def test_empty_windows_returns_empty(self) -> None:
        assert self.calc.find_gaps([], min_gap_minutes=60) == []

    def test_exact_min_gap_included(self) -> None:
        # exactly 60 min → included (>= check)
        gaps = self.calc.find_gaps([(dt(9), dt(10))], min_gap_minutes=60)
        assert len(gaps) == 1

    def test_one_below_min_excluded(self) -> None:
        gaps = self.calc.find_gaps([(dt(9), dt(9, 59))], min_gap_minutes=60)
        assert gaps == []


# ---------------------------------------------------------------------------
# split_window_by_service
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestSplitWindowByService:
    def setup_method(self) -> None:
        self.calc = SlotCalculator(step_minutes=30)

    def test_service_in_middle(self) -> None:
        result = self.calc.split_window_by_service(dt(9), dt(18), dt(11), dt(12))
        assert result == [(dt(9), dt(11)), (dt(12), dt(18))]

    def test_service_at_start(self) -> None:
        result = self.calc.split_window_by_service(dt(9), dt(18), dt(9), dt(11))
        assert result == [(dt(11), dt(18))]

    def test_service_at_end(self) -> None:
        result = self.calc.split_window_by_service(dt(9), dt(18), dt(16), dt(18))
        assert result == [(dt(9), dt(16))]

    def test_service_fills_entire_window(self) -> None:
        result = self.calc.split_window_by_service(dt(9), dt(18), dt(9), dt(18))
        assert result == []


# ---------------------------------------------------------------------------
# _align_to_grid
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestAlignToGrid:
    def setup_method(self) -> None:
        self.calc = SlotCalculator(step_minutes=30)

    def test_already_on_grid(self) -> None:
        assert self.calc._align_to_grid(dt(9, 30), dt(9)) == dt(9, 30)

    def test_between_steps_rounds_up(self) -> None:
        assert self.calc._align_to_grid(dt(9, 17), dt(9)) == dt(9, 30)

    def test_just_after_step(self) -> None:
        assert self.calc._align_to_grid(dt(9, 1), dt(9)) == dt(9, 30)

    def test_target_before_origin_returns_origin(self) -> None:
        assert self.calc._align_to_grid(dt(8, 50), dt(9)) == dt(9)

    def test_target_equals_origin(self) -> None:
        assert self.calc._align_to_grid(dt(9), dt(9)) == dt(9)

    def test_multi_step_offset(self) -> None:
        # target = 10:17, origin = 9:00, step = 30 → 10:30
        assert self.calc._align_to_grid(dt(10, 17), dt(9)) == dt(10, 30)
