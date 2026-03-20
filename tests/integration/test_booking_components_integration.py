"""
Integration tests for booking engine components:
  - SlotCalculator (calculator.py)
  - BookingValidator (validators.py)
  - Custom exceptions (_shared/exceptions.py)
  - Shared base DTOs (_shared/dto.py)
"""

from datetime import date, datetime

import pytest

from codex_services.booking._shared.calculator import SlotCalculator
from codex_services.booking._shared.dto import BookingResult, BookingSolution, ResourceAvailability
from codex_services.booking._shared.exceptions import (
    BookingEngineError,
    ChainBuildError,
    InvalidBookingDateError,
    InvalidServiceDurationError,
    NoAvailabilityError,
    ResourceNotAvailableError,
    SlotAlreadyBookedError,
)
from codex_services.booking._shared.validators import BookingValidator
from codex_services.booking.slot_master import SingleServiceSolution

# ---------------------------------------------------------------------------
# SlotCalculator
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_calculator_invalid_step_raises() -> None:
    """SlotCalculator raises ValueError for step_minutes <= 0."""
    with pytest.raises(ValueError, match="step_minutes"):
        SlotCalculator(step_minutes=0)

    with pytest.raises(ValueError):
        SlotCalculator(step_minutes=-5)


@pytest.mark.integration
def test_calculator_find_slots_window_too_small() -> None:
    """find_slots_in_window returns [] when window is smaller than duration."""
    calc = SlotCalculator(step_minutes=30)
    slots = calc.find_slots_in_window(
        window_start=datetime(2024, 1, 1, 10, 0),
        window_end=datetime(2024, 1, 1, 10, 30),
        duration_minutes=60,
    )
    assert slots == []


@pytest.mark.integration
def test_calculator_find_slots_with_min_start() -> None:
    """find_slots_in_window respects min_start."""
    calc = SlotCalculator(step_minutes=30)
    slots = calc.find_slots_in_window(
        window_start=datetime(2024, 1, 1, 9, 0),
        window_end=datetime(2024, 1, 1, 13, 0),
        duration_minutes=60,
        min_start=datetime(2024, 1, 1, 11, 0),
    )
    assert all(s >= datetime(2024, 1, 1, 11, 0) for s in slots)
    assert len(slots) > 0


@pytest.mark.integration
def test_calculator_find_slots_with_grid_anchor() -> None:
    """find_slots_in_window aligns to grid_anchor."""
    calc = SlotCalculator(step_minutes=30)
    anchor = datetime(2024, 1, 1, 9, 0)
    slots = calc.find_slots_in_window(
        window_start=datetime(2024, 1, 1, 9, 0),
        window_end=datetime(2024, 1, 1, 12, 0),
        duration_minutes=60,
        grid_anchor=anchor,
    )
    # All starts should be on 30-min grid from 9:00
    for s in slots:
        minutes_from_anchor = int((s - anchor).total_seconds() / 60)
        assert minutes_from_anchor % 30 == 0


@pytest.mark.integration
def test_calculator_merge_free_windows_basic() -> None:
    """merge_free_windows subtracts busy intervals from the working day."""
    calc = SlotCalculator(step_minutes=30)
    work_start = datetime(2024, 1, 1, 9, 0)
    work_end = datetime(2024, 1, 1, 18, 0)
    busy = [(datetime(2024, 1, 1, 10, 0), datetime(2024, 1, 1, 11, 0))]

    windows = calc.merge_free_windows(work_start, work_end, busy)

    assert (datetime(2024, 1, 1, 9, 0), datetime(2024, 1, 1, 10, 0)) in windows
    assert (datetime(2024, 1, 1, 11, 0), datetime(2024, 1, 1, 18, 0)) in windows


@pytest.mark.integration
def test_calculator_merge_free_windows_with_break() -> None:
    """merge_free_windows respects break_interval."""
    calc = SlotCalculator(step_minutes=30)
    work_start = datetime(2024, 1, 1, 9, 0)
    work_end = datetime(2024, 1, 1, 18, 0)

    windows = calc.merge_free_windows(
        work_start,
        work_end,
        busy_intervals=[],
        break_interval=(datetime(2024, 1, 1, 13, 0), datetime(2024, 1, 1, 14, 0)),
    )
    assert len(windows) == 2
    assert windows[0] == (datetime(2024, 1, 1, 9, 0), datetime(2024, 1, 1, 13, 0))
    assert windows[1] == (datetime(2024, 1, 1, 14, 0), datetime(2024, 1, 1, 18, 0))


@pytest.mark.integration
def test_calculator_merge_free_windows_with_buffer() -> None:
    """merge_free_windows adds buffer after busy intervals."""
    calc = SlotCalculator(step_minutes=30)
    work_start = datetime(2024, 1, 1, 9, 0)
    work_end = datetime(2024, 1, 1, 18, 0)
    busy = [(datetime(2024, 1, 1, 10, 0), datetime(2024, 1, 1, 11, 0))]

    windows = calc.merge_free_windows(work_start, work_end, busy, buffer_minutes=10)
    # After 11:00 there's a 10 min buffer → next free window starts at 11:10
    assert any(w[0] == datetime(2024, 1, 1, 11, 10) for w in windows)


@pytest.mark.integration
def test_calculator_merge_free_windows_min_duration_filter() -> None:
    """merge_free_windows discards windows shorter than min_duration_minutes."""
    calc = SlotCalculator(step_minutes=30)
    work_start = datetime(2024, 1, 1, 9, 0)
    work_end = datetime(2024, 1, 1, 18, 0)
    # Two bookings close together, leaving a tiny gap between them
    busy = [
        (datetime(2024, 1, 1, 10, 0), datetime(2024, 1, 1, 11, 0)),
        (datetime(2024, 1, 1, 11, 10), datetime(2024, 1, 1, 12, 0)),
    ]

    windows = calc.merge_free_windows(work_start, work_end, busy, min_duration_minutes=30)
    # The 10-minute gap (11:00-11:10) must be filtered out
    for w_start, w_end in windows:
        duration = (w_end - w_start).total_seconds() / 60
        assert duration >= 30


@pytest.mark.integration
def test_calculator_merge_free_windows_empty_day() -> None:
    """merge_free_windows with no busy intervals returns full day."""
    calc = SlotCalculator(step_minutes=30)
    work_start = datetime(2024, 1, 1, 9, 0)
    work_end = datetime(2024, 1, 1, 18, 0)

    windows = calc.merge_free_windows(work_start, work_end, [])
    assert windows == [(work_start, work_end)]


@pytest.mark.integration
def test_calculator_merge_free_windows_overlapping_busy() -> None:
    """merge_free_windows merges overlapping busy intervals."""
    calc = SlotCalculator(step_minutes=30)
    work_start = datetime(2024, 1, 1, 9, 0)
    work_end = datetime(2024, 1, 1, 18, 0)
    busy = [
        (datetime(2024, 1, 1, 10, 0), datetime(2024, 1, 1, 12, 0)),
        (datetime(2024, 1, 1, 11, 0), datetime(2024, 1, 1, 13, 0)),
    ]

    windows = calc.merge_free_windows(work_start, work_end, busy)
    assert (datetime(2024, 1, 1, 9, 0), datetime(2024, 1, 1, 10, 0)) in windows
    assert (datetime(2024, 1, 1, 13, 0), datetime(2024, 1, 1, 18, 0)) in windows


@pytest.mark.integration
def test_calculator_find_gaps() -> None:
    """find_gaps returns windows meeting the minimum duration."""
    calc = SlotCalculator(step_minutes=30)
    free_windows = [
        (datetime(2024, 1, 1, 9, 0), datetime(2024, 1, 1, 10, 0)),  # 60 min
        (datetime(2024, 1, 1, 11, 0), datetime(2024, 1, 1, 11, 20)),  # 20 min — too short
        (datetime(2024, 1, 1, 14, 0), datetime(2024, 1, 1, 16, 0)),  # 120 min
    ]
    gaps = calc.find_gaps(free_windows, min_gap_minutes=60)

    assert len(gaps) == 2
    starts = [g[0] for g in gaps]
    assert datetime(2024, 1, 1, 9, 0) in starts
    assert datetime(2024, 1, 1, 14, 0) in starts
    # Duration field
    assert gaps[0][2] == 60
    assert gaps[1][2] == 120


@pytest.mark.integration
def test_calculator_find_gaps_empty() -> None:
    """find_gaps returns [] when no windows meet min_gap_minutes."""
    calc = SlotCalculator(step_minutes=30)
    gaps = calc.find_gaps(
        [(datetime(2024, 1, 1, 9, 0), datetime(2024, 1, 1, 9, 20))],
        min_gap_minutes=60,
    )
    assert gaps == []


@pytest.mark.integration
def test_calculator_split_window_by_service() -> None:
    """split_window_by_service returns two parts around the booked service."""
    calc = SlotCalculator(step_minutes=30)
    remaining = calc.split_window_by_service(
        window_start=datetime(2024, 1, 1, 9, 0),
        window_end=datetime(2024, 1, 1, 18, 0),
        service_start=datetime(2024, 1, 1, 11, 0),
        service_end=datetime(2024, 1, 1, 12, 0),
    )
    assert len(remaining) == 2
    assert remaining[0] == (datetime(2024, 1, 1, 9, 0), datetime(2024, 1, 1, 11, 0))
    assert remaining[1] == (datetime(2024, 1, 1, 12, 0), datetime(2024, 1, 1, 18, 0))


@pytest.mark.integration
def test_calculator_split_window_service_at_start() -> None:
    """split_window_by_service with service at window start returns only the tail."""
    calc = SlotCalculator(step_minutes=30)
    remaining = calc.split_window_by_service(
        window_start=datetime(2024, 1, 1, 9, 0),
        window_end=datetime(2024, 1, 1, 18, 0),
        service_start=datetime(2024, 1, 1, 9, 0),
        service_end=datetime(2024, 1, 1, 11, 0),
    )
    assert len(remaining) == 1
    assert remaining[0] == (datetime(2024, 1, 1, 11, 0), datetime(2024, 1, 1, 18, 0))


@pytest.mark.integration
def test_calculator_split_window_service_at_end() -> None:
    """split_window_by_service with service at window end returns only the head."""
    calc = SlotCalculator(step_minutes=30)
    remaining = calc.split_window_by_service(
        window_start=datetime(2024, 1, 1, 9, 0),
        window_end=datetime(2024, 1, 1, 18, 0),
        service_start=datetime(2024, 1, 1, 16, 0),
        service_end=datetime(2024, 1, 1, 18, 0),
    )
    assert len(remaining) == 1
    assert remaining[0] == (datetime(2024, 1, 1, 9, 0), datetime(2024, 1, 1, 16, 0))


# ---------------------------------------------------------------------------
# BookingValidator
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_validator_is_slot_free_no_conflict() -> None:
    """is_slot_free returns True when there's no overlap."""
    v = BookingValidator()
    assert (
        v.is_slot_free(
            slot_start=datetime(2024, 1, 1, 11, 0),
            slot_end=datetime(2024, 1, 1, 12, 0),
            busy_intervals=[(datetime(2024, 1, 1, 9, 0), datetime(2024, 1, 1, 11, 0))],
        )
        is True
    )


@pytest.mark.integration
def test_validator_is_slot_free_with_conflict() -> None:
    """is_slot_free returns False when there is an overlap."""
    v = BookingValidator()
    assert (
        v.is_slot_free(
            slot_start=datetime(2024, 1, 1, 10, 30),
            slot_end=datetime(2024, 1, 1, 11, 30),
            busy_intervals=[(datetime(2024, 1, 1, 10, 0), datetime(2024, 1, 1, 11, 0))],
        )
        is False
    )


@pytest.mark.integration
def test_validator_no_conflicts_single_resource_sequential() -> None:
    """no_conflicts is True for adjacent sequential slots on the same resource."""
    v = BookingValidator()
    solutions = [
        SingleServiceSolution(
            service_id="s1",
            resource_id="m1",
            start_time=datetime(2024, 1, 1, 9, 0),
            end_time=datetime(2024, 1, 1, 10, 0),
            gap_end_time=datetime(2024, 1, 1, 10, 0),
        ),
        SingleServiceSolution(
            service_id="s2",
            resource_id="m1",
            start_time=datetime(2024, 1, 1, 10, 0),
            end_time=datetime(2024, 1, 1, 11, 0),
            gap_end_time=datetime(2024, 1, 1, 11, 0),
        ),
    ]
    assert v.no_conflicts(solutions) is True


@pytest.mark.integration
def test_validator_no_conflicts_detects_overlap() -> None:
    """no_conflicts is False when same resource has overlapping slots."""
    v = BookingValidator()
    solutions = [
        SingleServiceSolution(
            service_id="s1",
            resource_id="m1",
            start_time=datetime(2024, 1, 1, 9, 0),
            end_time=datetime(2024, 1, 1, 10, 30),
            gap_end_time=datetime(2024, 1, 1, 10, 30),
        ),
        SingleServiceSolution(
            service_id="s2",
            resource_id="m1",
            start_time=datetime(2024, 1, 1, 10, 0),
            end_time=datetime(2024, 1, 1, 11, 0),
            gap_end_time=datetime(2024, 1, 1, 11, 0),
        ),
    ]
    assert v.no_conflicts(solutions) is False


@pytest.mark.integration
def test_validator_solution_fits_in_windows_true() -> None:
    """solution_fits_in_windows returns True when slot fits inside a window."""
    v = BookingValidator()
    sol = SingleServiceSolution(
        service_id="s1",
        resource_id="m1",
        start_time=datetime(2024, 1, 1, 10, 0),
        end_time=datetime(2024, 1, 1, 11, 0),
        gap_end_time=datetime(2024, 1, 1, 11, 0),
    )
    windows = [(datetime(2024, 1, 1, 9, 0), datetime(2024, 1, 1, 12, 0))]
    assert v.solution_fits_in_windows(sol, windows) is True


@pytest.mark.integration
def test_validator_solution_fits_in_windows_false() -> None:
    """solution_fits_in_windows returns False when slot goes outside a window."""
    v = BookingValidator()
    sol = SingleServiceSolution(
        service_id="s1",
        resource_id="m1",
        start_time=datetime(2024, 1, 1, 11, 30),
        end_time=datetime(2024, 1, 1, 12, 30),
        gap_end_time=datetime(2024, 1, 1, 12, 30),
    )
    windows = [(datetime(2024, 1, 1, 9, 0), datetime(2024, 1, 1, 12, 0))]
    assert v.solution_fits_in_windows(sol, windows) is False


# ---------------------------------------------------------------------------
# Shared base DTOs
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_resource_availability_invalid_window_raises() -> None:
    """ResourceAvailability raises ValueError when start >= end."""
    with pytest.raises(Exception):
        ResourceAvailability(
            resource_id="m1",
            free_windows=[(datetime(2024, 1, 1, 12, 0), datetime(2024, 1, 1, 9, 0))],
        )


@pytest.mark.integration
def test_resource_availability_repr() -> None:
    """ResourceAvailability repr includes resource_id."""
    avail = ResourceAvailability(resource_id="r42", free_windows=[])
    assert "r42" in repr(avail)


@pytest.mark.integration
def test_booking_solution_duration_minutes() -> None:
    """BookingSolution.duration_minutes calculated correctly."""
    sol = BookingSolution(
        resource_id="m1",
        start_time=datetime(2024, 1, 1, 10, 0),
        end_time=datetime(2024, 1, 1, 11, 30),
    )
    assert sol.duration_minutes == 90


@pytest.mark.integration
def test_booking_result_has_solutions_not_implemented() -> None:
    """BookingResult.has_solutions raises NotImplementedError."""
    result = BookingResult()
    with pytest.raises(NotImplementedError):
        _ = result.has_solutions


# ---------------------------------------------------------------------------
# Exception classes
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_booking_engine_error_default_message() -> None:
    """BookingEngineError uses default_message when no message passed."""
    err = BookingEngineError()
    assert "Booking system error" in str(err)
    assert isinstance(err, Exception)


@pytest.mark.integration
def test_booking_engine_error_custom_message() -> None:
    """BookingEngineError uses custom message when provided."""
    err = BookingEngineError("custom error")
    assert "custom error" in str(err)


@pytest.mark.integration
def test_no_availability_error_with_date() -> None:
    """NoAvailabilityError formats message with date."""
    err = NoAvailabilityError(booking_date=date(2024, 5, 10), service_ids=["s1", "s2"])
    msg = str(err)
    assert "10.05.2024" in msg
    assert err.booking_date == date(2024, 5, 10)
    assert err.service_ids == ["s1", "s2"]


@pytest.mark.integration
def test_no_availability_error_without_date() -> None:
    """NoAvailabilityError uses default message when no date provided."""
    err = NoAvailabilityError()
    assert "no available slots" in str(err).lower() or "unfortunately" in str(err).lower()
    assert err.booking_date is None


@pytest.mark.integration
def test_no_availability_error_custom_message() -> None:
    """NoAvailabilityError with explicit message uses it."""
    err = NoAvailabilityError(message="nothing here")
    assert "nothing here" in str(err)


@pytest.mark.integration
def test_invalid_service_duration_error_with_details() -> None:
    """InvalidServiceDurationError formats message with service_id and duration."""
    err = InvalidServiceDurationError(service_id="svc5", duration_minutes=0)
    msg = str(err)
    assert "svc5" in msg
    assert "0" in msg
    assert err.service_id == "svc5"
    assert err.duration_minutes == 0


@pytest.mark.integration
def test_invalid_service_duration_error_default() -> None:
    """InvalidServiceDurationError default message when no details."""
    err = InvalidServiceDurationError()
    assert "duration" in str(err).lower()


@pytest.mark.integration
def test_invalid_service_duration_error_custom_message() -> None:
    """InvalidServiceDurationError with custom message."""
    err = InvalidServiceDurationError(message="bad duration!")
    assert "bad duration!" in str(err)


@pytest.mark.integration
def test_invalid_booking_date_error_with_date_and_reason() -> None:
    """InvalidBookingDateError formats message with date and reason."""
    err = InvalidBookingDateError(booking_date=date(2020, 1, 1), reason="Date in the past")
    msg = str(err)
    assert "01.01.2020" in msg
    assert "past" in msg.lower()
    assert err.booking_date == date(2020, 1, 1)
    assert err.reason == "Date in the past"


@pytest.mark.integration
def test_invalid_booking_date_error_with_date_only() -> None:
    """InvalidBookingDateError with date but no reason."""
    err = InvalidBookingDateError(booking_date=date(2020, 3, 15))
    assert "15.03.2020" in str(err)


@pytest.mark.integration
def test_invalid_booking_date_error_default() -> None:
    """InvalidBookingDateError default message."""
    err = InvalidBookingDateError()
    assert "unavailable" in str(err).lower() or "selected" in str(err).lower()


@pytest.mark.integration
def test_invalid_booking_date_error_custom_message() -> None:
    """InvalidBookingDateError with custom message."""
    err = InvalidBookingDateError(message="closed that day")
    assert "closed" in str(err)


@pytest.mark.integration
def test_slot_already_booked_error_with_details() -> None:
    """SlotAlreadyBookedError formats message with slot_time and date."""
    err = SlotAlreadyBookedError(
        resource_id="m1",
        service_id="s1",
        booking_date=date(2024, 6, 1),
        slot_time="14:00",
    )
    msg = str(err)
    assert "14:00" in msg
    assert "01.06.2024" in msg
    assert err.resource_id == "m1"
    assert err.slot_time == "14:00"


@pytest.mark.integration
def test_slot_already_booked_error_default() -> None:
    """SlotAlreadyBookedError default message."""
    err = SlotAlreadyBookedError()
    assert "booked" in str(err).lower() or "slot" in str(err).lower()


@pytest.mark.integration
def test_slot_already_booked_error_custom_message() -> None:
    """SlotAlreadyBookedError with custom message."""
    err = SlotAlreadyBookedError(message="taken!")
    assert "taken!" in str(err)


@pytest.mark.integration
def test_chain_build_error_with_reason() -> None:
    """ChainBuildError formats message with reason."""
    err = ChainBuildError(failed_at_index=2, reason="max duration exceeded")
    msg = str(err)
    assert "max duration exceeded" in msg
    assert err.failed_at_index == 2
    assert err.reason == "max duration exceeded"


@pytest.mark.integration
def test_chain_build_error_default() -> None:
    """ChainBuildError default message."""
    err = ChainBuildError()
    assert "schedule" in str(err).lower() or "chain" in str(err).lower()


@pytest.mark.integration
def test_chain_build_error_custom_message() -> None:
    """ChainBuildError with custom message."""
    err = ChainBuildError(message="partial failure")
    assert "partial failure" in str(err)


@pytest.mark.integration
def test_resource_not_available_error_with_date() -> None:
    """ResourceNotAvailableError formats message with date."""
    err = ResourceNotAvailableError(resource_id="m3", booking_date=date(2024, 7, 4))
    msg = str(err)
    assert "04.07.2024" in msg
    assert err.resource_id == "m3"
    assert err.booking_date == date(2024, 7, 4)


@pytest.mark.integration
def test_resource_not_available_error_default() -> None:
    """ResourceNotAvailableError default message."""
    err = ResourceNotAvailableError()
    assert "unavailable" in str(err).lower() or "resource" in str(err).lower()


@pytest.mark.integration
def test_resource_not_available_error_custom_message() -> None:
    """ResourceNotAvailableError with custom message."""
    err = ResourceNotAvailableError(message="no such master")
    assert "no such master" in str(err)


@pytest.mark.integration
def test_all_exceptions_inherit_from_base() -> None:
    """All booking exceptions inherit from BookingEngineError."""
    exceptions = [
        NoAvailabilityError(),
        InvalidServiceDurationError(),
        InvalidBookingDateError(),
        SlotAlreadyBookedError(),
        ChainBuildError(),
        ResourceNotAvailableError(),
    ]
    for exc in exceptions:
        assert isinstance(exc, BookingEngineError)
        assert isinstance(exc, Exception)
