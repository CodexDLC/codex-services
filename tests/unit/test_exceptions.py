"""Unit tests for booking exceptions."""

from datetime import date

import pytest

from codex_services.booking._shared.exceptions import (
    BookingEngineError,
    ChainBuildError,
    InvalidBookingDateError,
    InvalidServiceDurationError,
    NoAvailabilityError,
    ResourceNotAvailableError,
    SlotAlreadyBookedError,
)


@pytest.mark.unit
class TestBookingEngineError:
    def test_default_message(self) -> None:
        e = BookingEngineError()
        assert "Booking system error" in str(e)

    def test_custom_message(self) -> None:
        e = BookingEngineError("custom error")
        assert str(e) == "custom error"


@pytest.mark.unit
class TestNoAvailabilityError:
    def test_default_message(self) -> None:
        e = NoAvailabilityError()
        assert "no available slots" in str(e).lower() or "unfortunately" in str(e).lower()

    def test_with_booking_date(self) -> None:
        e = NoAvailabilityError(booking_date=date(2024, 5, 10))
        assert "10.05.2024" in str(e)

    def test_with_custom_message(self) -> None:
        e = NoAvailabilityError(message="custom msg")
        assert str(e) == "custom msg"

    def test_stores_attributes(self) -> None:
        e = NoAvailabilityError(booking_date=date(2024, 5, 10), service_ids=["s1", "s2"])
        assert e.booking_date == date(2024, 5, 10)
        assert e.service_ids == ["s1", "s2"]

    def test_service_ids_default_empty(self) -> None:
        e = NoAvailabilityError()
        assert e.service_ids == []

    def test_is_booking_engine_error(self) -> None:
        assert isinstance(NoAvailabilityError(), BookingEngineError)


@pytest.mark.unit
class TestInvalidServiceDurationError:
    def test_default_message(self) -> None:
        e = InvalidServiceDurationError()
        assert "duration" in str(e).lower()

    def test_with_service_and_duration(self) -> None:
        e = InvalidServiceDurationError(service_id="s5", duration_minutes=0)
        assert "s5" in str(e)
        assert "0" in str(e)

    def test_with_custom_message(self) -> None:
        e = InvalidServiceDurationError(message="bad duration")
        assert str(e) == "bad duration"

    def test_stores_attributes(self) -> None:
        e = InvalidServiceDurationError(service_id="s1", duration_minutes=-5)
        assert e.service_id == "s1"
        assert e.duration_minutes == -5

    def test_partial_args_falls_back_to_default(self) -> None:
        e = InvalidServiceDurationError(service_id="s1")  # no duration_minutes
        assert "duration" in str(e).lower()


@pytest.mark.unit
class TestInvalidBookingDateError:
    def test_default_message(self) -> None:
        e = InvalidBookingDateError()
        assert "unavailable" in str(e).lower()

    def test_with_date_and_reason(self) -> None:
        e = InvalidBookingDateError(booking_date=date(2020, 1, 1), reason="Date in the past")
        assert "01.01.2020" in str(e)
        assert "Date in the past" in str(e)

    def test_with_date_only(self) -> None:
        e = InvalidBookingDateError(booking_date=date(2024, 5, 10))
        assert "10.05.2024" in str(e)

    def test_with_custom_message(self) -> None:
        e = InvalidBookingDateError(message="bad date")
        assert str(e) == "bad date"

    def test_stores_attributes(self) -> None:
        e = InvalidBookingDateError(booking_date=date(2024, 5, 10), reason="closed")
        assert e.booking_date == date(2024, 5, 10)
        assert e.reason == "closed"


@pytest.mark.unit
class TestSlotAlreadyBookedError:
    def test_default_message(self) -> None:
        e = SlotAlreadyBookedError()
        assert "booked" in str(e).lower()

    def test_with_slot_and_date(self) -> None:
        e = SlotAlreadyBookedError(slot_time="14:00", booking_date=date(2024, 5, 10))
        assert "14:00" in str(e)
        assert "10.05.2024" in str(e)

    def test_with_custom_message(self) -> None:
        e = SlotAlreadyBookedError(message="already taken")
        assert str(e) == "already taken"

    def test_stores_attributes(self) -> None:
        e = SlotAlreadyBookedError(resource_id="m1", service_id="s1", booking_date=date(2024, 5, 10), slot_time="10:00")
        assert e.resource_id == "m1"
        assert e.service_id == "s1"


@pytest.mark.unit
class TestChainBuildError:
    def test_default_message(self) -> None:
        e = ChainBuildError()
        assert "schedule" in str(e).lower() or "chain" in str(e).lower()

    def test_with_reason(self) -> None:
        e = ChainBuildError(reason="max duration exceeded")
        assert "max duration exceeded" in str(e)

    def test_with_custom_message(self) -> None:
        e = ChainBuildError(message="chain failed")
        assert str(e) == "chain failed"

    def test_stores_attributes(self) -> None:
        e = ChainBuildError(failed_at_index=2, reason="timeout")
        assert e.failed_at_index == 2
        assert e.reason == "timeout"


@pytest.mark.unit
class TestResourceNotAvailableError:
    def test_default_message(self) -> None:
        e = ResourceNotAvailableError()
        assert "unavailable" in str(e).lower()

    def test_with_date(self) -> None:
        e = ResourceNotAvailableError(booking_date=date(2024, 5, 10))
        assert "10.05.2024" in str(e)

    def test_with_custom_message(self) -> None:
        e = ResourceNotAvailableError(message="no resource")
        assert str(e) == "no resource"

    def test_stores_attributes(self) -> None:
        e = ResourceNotAvailableError(resource_id="m3", booking_date=date(2024, 5, 10))
        assert e.resource_id == "m3"
        assert e.booking_date == date(2024, 5, 10)

    def test_is_booking_engine_error(self) -> None:
        assert isinstance(ResourceNotAvailableError(), BookingEngineError)
