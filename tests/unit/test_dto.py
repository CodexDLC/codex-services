"""Unit tests for booking DTOs."""

from datetime import date, datetime, timedelta

import pytest
from pydantic import ValidationError

from codex_services.booking.slot_master.dto import (
    BookingChainSolution,
    BookingEngineRequest,
    EngineResult,
    MasterAvailability,
    ServiceRequest,
    SingleServiceSolution,
    WaitlistEntry,
)
from codex_services.booking.slot_master.modes import BookingMode


def dt(h: int, m: int = 0, day: int = 10) -> datetime:
    return datetime(2024, 5, day, h, m)


def make_item(
    service_id: str = "s1",
    resource_id: str = "m1",
    start_h: int = 9,
    dur: int = 60,
    day: int = 10,
) -> SingleServiceSolution:
    start = dt(start_h, day=day)
    end = start + timedelta(minutes=dur)
    return SingleServiceSolution(
        service_id=service_id,
        resource_id=resource_id,
        start_time=start,
        end_time=end,
        gap_end_time=end,
    )


def make_chain(*items: SingleServiceSolution, score: float = 0.0) -> BookingChainSolution:
    return BookingChainSolution(items=list(items), score=score)


# ---------------------------------------------------------------------------
# ServiceRequest
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestServiceRequest:
    def test_valid_minimal(self) -> None:
        sr = ServiceRequest(service_id="1", duration_minutes=60, possible_resource_ids=["m1"])
        assert sr.service_id == "1"
        assert sr.min_gap_after_minutes == 0
        assert sr.parallel_group is None

    def test_total_block_minutes_no_gap(self) -> None:
        sr = ServiceRequest(service_id="1", duration_minutes=60, possible_resource_ids=["m1"])
        assert sr.total_block_minutes == 60

    def test_total_block_minutes_with_gap(self) -> None:
        sr = ServiceRequest(
            service_id="1",
            duration_minutes=60,
            min_gap_after_minutes=30,
            possible_resource_ids=["m1"],
        )
        assert sr.total_block_minutes == 90

    def test_duration_zero_raises(self) -> None:
        with pytest.raises(ValidationError):
            ServiceRequest(service_id="1", duration_minutes=0, possible_resource_ids=["m1"])

    def test_duration_negative_raises(self) -> None:
        with pytest.raises(ValidationError):
            ServiceRequest(service_id="1", duration_minutes=-10, possible_resource_ids=["m1"])

    def test_empty_resources_raises(self) -> None:
        with pytest.raises(ValidationError):
            ServiceRequest(service_id="1", duration_minutes=60, possible_resource_ids=[])

    def test_multiple_resources_allowed(self) -> None:
        sr = ServiceRequest(service_id="1", duration_minutes=60, possible_resource_ids=["m1", "m2", "m3"])
        assert len(sr.possible_resource_ids) == 3

    def test_parallel_group_set(self) -> None:
        sr = ServiceRequest(
            service_id="1",
            duration_minutes=60,
            possible_resource_ids=["m1"],
            parallel_group="group_a",
        )
        assert sr.parallel_group == "group_a"

    def test_frozen_immutable(self) -> None:
        sr = ServiceRequest(service_id="1", duration_minutes=60, possible_resource_ids=["m1"])
        with pytest.raises(ValidationError):
            sr.duration_minutes = 90  # type: ignore[misc]


# ---------------------------------------------------------------------------
# BookingEngineRequest
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestBookingEngineRequest:
    def _sr(self, duration: int = 60, gap: int = 0) -> ServiceRequest:
        return ServiceRequest(
            service_id="s1",
            duration_minutes=duration,
            min_gap_after_minutes=gap,
            possible_resource_ids=["m1"],
        )

    def test_total_duration_minutes(self) -> None:
        req = BookingEngineRequest(
            service_requests=[self._sr(60), self._sr(30)],
            booking_date=date(2024, 5, 10),
        )
        assert req.total_duration_minutes == 90

    def test_total_block_minutes_includes_gaps(self) -> None:
        req = BookingEngineRequest(
            service_requests=[self._sr(60, gap=10), self._sr(30)],
            booking_date=date(2024, 5, 10),
        )
        assert req.total_block_minutes == 100  # (60+10) + (30+0)

    def test_empty_services_raises(self) -> None:
        with pytest.raises(ValidationError):
            BookingEngineRequest(service_requests=[], booking_date=date(2024, 5, 10))

    def test_default_mode_single_day(self) -> None:
        req = BookingEngineRequest(
            service_requests=[self._sr()],
            booking_date=date(2024, 5, 10),
        )
        assert req.mode == BookingMode.SINGLE_DAY

    def test_overlap_allowed_default_false(self) -> None:
        req = BookingEngineRequest(
            service_requests=[self._sr()],
            booking_date=date(2024, 5, 10),
        )
        assert req.overlap_allowed is False

    def test_max_chain_duration_none_by_default(self) -> None:
        req = BookingEngineRequest(
            service_requests=[self._sr()],
            booking_date=date(2024, 5, 10),
        )
        assert req.max_chain_duration_minutes is None

    def test_frozen_immutable(self) -> None:
        req = BookingEngineRequest(
            service_requests=[self._sr()],
            booking_date=date(2024, 5, 10),
        )
        with pytest.raises(ValidationError):
            req.booking_date = date(2024, 6, 1)  # type: ignore[misc]


# ---------------------------------------------------------------------------
# MasterAvailability
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestMasterAvailability:
    def test_valid_with_windows(self) -> None:
        ma = MasterAvailability(resource_id="m1", free_windows=[(dt(9), dt(12))])
        assert ma.resource_id == "m1"
        assert len(ma.free_windows) == 1

    def test_empty_windows_allowed(self) -> None:
        ma = MasterAvailability(resource_id="m1", free_windows=[])
        assert ma.free_windows == []

    def test_start_after_end_raises(self) -> None:
        with pytest.raises(ValidationError):
            MasterAvailability(resource_id="m1", free_windows=[(dt(12), dt(9))])

    def test_start_equal_end_raises(self) -> None:
        with pytest.raises(ValidationError):
            MasterAvailability(resource_id="m1", free_windows=[(dt(9), dt(9))])

    def test_buffer_default_zero(self) -> None:
        ma = MasterAvailability(resource_id="m1", free_windows=[])
        assert ma.buffer_between_minutes == 0

    def test_multiple_valid_windows(self) -> None:
        ma = MasterAvailability(
            resource_id="m1",
            free_windows=[(dt(9), dt(12)), (dt(13), dt(18))],
        )
        assert len(ma.free_windows) == 2


# ---------------------------------------------------------------------------
# SingleServiceSolution
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestSingleServiceSolution:
    def test_duration_minutes_property(self) -> None:
        item = make_item(dur=90)
        assert item.duration_minutes == 90

    def test_duration_minutes_60(self) -> None:
        item = make_item(start_h=9, dur=60)
        assert item.duration_minutes == 60


# ---------------------------------------------------------------------------
# BookingChainSolution
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestBookingChainSolution:
    def test_starts_at_min_of_items(self) -> None:
        chain = make_chain(make_item(start_h=9), make_item(start_h=11))
        assert chain.starts_at == dt(9)

    def test_ends_at_max_of_items(self) -> None:
        chain = make_chain(make_item(start_h=9, dur=60), make_item(start_h=11, dur=60))
        assert chain.ends_at == dt(12)

    def test_span_minutes(self) -> None:
        chain = make_chain(make_item(start_h=9, dur=60), make_item(start_h=11, dur=60))
        assert chain.span_minutes == 180  # 12:00 - 9:00

    def test_span_single_item(self) -> None:
        chain = make_chain(make_item(start_h=9, dur=60))
        assert chain.span_minutes == 60

    def test_to_display_structure(self) -> None:
        chain = make_chain(make_item(service_id="haircut", resource_id="m1", start_h=9, dur=60))
        display = chain.to_display()
        assert "haircut" in display
        assert display["haircut"]["resource_id"] == "m1"
        assert display["haircut"]["start"] == "09:00"
        assert display["haircut"]["end"] == "10:00"

    def test_to_display_multiple_items(self) -> None:
        chain = make_chain(
            make_item(service_id="s1", start_h=9),
            make_item(service_id="s2", start_h=11),
        )
        display = chain.to_display()
        assert len(display) == 2

    def test_empty_items_raises(self) -> None:
        with pytest.raises(ValidationError):
            BookingChainSolution(items=[])

    def test_score_default_zero(self) -> None:
        chain = make_chain(make_item())
        assert chain.score == 0.0

    def test_frozen_immutable(self) -> None:
        chain = make_chain(make_item())
        with pytest.raises(ValidationError):
            chain.score = 99.0  # type: ignore[misc]


# ---------------------------------------------------------------------------
# EngineResult
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestEngineResult:
    def _make_chain(self, start_h: int, score: float = 0.0) -> BookingChainSolution:
        return make_chain(make_item(start_h=start_h), score=score)

    def test_has_solutions_true(self) -> None:
        r = EngineResult(mode=BookingMode.SINGLE_DAY, solutions=[self._make_chain(9)])
        assert r.has_solutions is True

    def test_has_solutions_false(self) -> None:
        r = EngineResult(mode=BookingMode.SINGLE_DAY, solutions=[])
        assert r.has_solutions is False

    def test_best_returns_first_solution(self) -> None:
        c1, c2 = self._make_chain(9), self._make_chain(10)
        r = EngineResult(mode=BookingMode.SINGLE_DAY, solutions=[c1, c2])
        assert r.best is c1

    def test_best_none_when_empty(self) -> None:
        r = EngineResult(mode=BookingMode.SINGLE_DAY, solutions=[])
        assert r.best is None

    def test_best_scored_returns_max_score(self) -> None:
        r = EngineResult(
            mode=BookingMode.SINGLE_DAY,
            solutions=[self._make_chain(9, score=5.0), self._make_chain(10, score=10.0)],
        )
        assert r.best_scored is r.solutions[1]

    def test_best_scored_none_when_empty(self) -> None:
        r = EngineResult(mode=BookingMode.SINGLE_DAY, solutions=[])
        assert r.best_scored is None

    def test_get_unique_start_times_sorted(self) -> None:
        r = EngineResult(
            mode=BookingMode.SINGLE_DAY,
            solutions=[self._make_chain(10), self._make_chain(9), self._make_chain(9)],
        )
        times = r.get_unique_start_times()
        assert times == ["09:00", "10:00"]

    def test_get_unique_start_times_empty(self) -> None:
        r = EngineResult(mode=BookingMode.SINGLE_DAY, solutions=[])
        assert r.get_unique_start_times() == []


# ---------------------------------------------------------------------------
# WaitlistEntry
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestWaitlistEntry:
    def _make_result(self, day: int = 15, start_h: int = 10) -> EngineResult:
        chain = make_chain(make_item(start_h=start_h, day=day))
        return EngineResult(mode=BookingMode.SINGLE_DAY, solutions=[chain])

    def test_from_engine_result_basic(self) -> None:
        result = self._make_result(day=15, start_h=10)
        entry = WaitlistEntry.from_engine_result(result, date(2024, 5, 10))
        assert entry is not None
        assert entry.available_date == date(2024, 5, 15)
        assert entry.available_time == "10:00"
        assert entry.days_from_request == 5

    def test_from_engine_result_empty_returns_none(self) -> None:
        result = EngineResult(mode=BookingMode.SINGLE_DAY, solutions=[])
        assert WaitlistEntry.from_engine_result(result, date(2024, 5, 10)) is None

    def test_days_from_request_same_day_is_zero(self) -> None:
        result = self._make_result(day=10, start_h=10)
        entry = WaitlistEntry.from_engine_result(result, date(2024, 5, 10))
        assert entry is not None
        assert entry.days_from_request == 0

    def test_solution_stored(self) -> None:
        result = self._make_result(day=15)
        entry = WaitlistEntry.from_engine_result(result, date(2024, 5, 10))
        assert entry is not None
        assert entry.solution is not None
        assert len(entry.solution.items) == 1


# ---------------------------------------------------------------------------
# __repr__ coverage
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestDTORepr:
    def test_service_request_repr(self) -> None:
        sr = ServiceRequest(service_id="s1", duration_minutes=60, possible_resource_ids=["m1"])
        assert "s1" in repr(sr)
        assert "60" in repr(sr)

    def test_booking_engine_request_repr(self) -> None:
        req = BookingEngineRequest(
            service_requests=[ServiceRequest(service_id="s1", duration_minutes=60, possible_resource_ids=["m1"])],
            booking_date=date(2024, 5, 10),
        )
        assert "2024-05-10" in repr(req)

    def test_master_availability_repr(self) -> None:
        avail = MasterAvailability(
            resource_id="m1",
            free_windows=[(datetime(2024, 5, 10, 9), datetime(2024, 5, 10, 18))],
        )
        assert "m1" in repr(avail)

    def test_single_service_solution_repr(self) -> None:
        sol = make_item()
        assert "s1" in repr(sol)
        assert "m1" in repr(sol)

    def test_booking_chain_solution_repr(self) -> None:
        chain = BookingChainSolution(items=[make_item()])
        assert "BookingChainSolution" in repr(chain)

    def test_engine_result_repr(self) -> None:
        result = EngineResult(mode=BookingMode.SINGLE_DAY, solutions=[])
        assert "single_day" in repr(result)

    def test_waitlist_entry_repr(self) -> None:
        chain = BookingChainSolution(items=[make_item(day=15)])
        entry = WaitlistEntry(
            available_date=date(2024, 5, 15),
            available_time="09:00",
            solution=chain,
            days_from_request=5,
        )
        assert "2024-05-15" in repr(entry)
