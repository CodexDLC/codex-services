"""
codex_services.booking._shared.exceptions
==========================================
Custom exceptions for the booking engine.

Hierarchy:
    BookingEngineError (base)
    ├── NoAvailabilityError      — no free slots for the request
    ├── InvalidServiceDurationError — incorrect service duration
    ├── InvalidBookingDateError  — incorrect/invalid date
    ├── ResourceNotAvailableError — specific resource is not available
    ├── SlotAlreadyBookedError   — race condition: slot was booked by another user
    └── ChainBuildError          — chain was partially assembled but not completed

Usage in the service layer:
    from codex_services.booking._shared.exceptions import NoAvailabilityError

    try:
        result = finder.find(request, availability)
        if not result.has_solutions:
            raise NoAvailabilityError(
                date=request.booking_date,
                service_ids=[s.service_id for s in request.service_requests],
            )
    except NoAvailabilityError as e:
        # Django view will catch and return a user-friendly message
        return render(request, "booking/no_slots.html", {"error": str(e)})

Imports:
    from codex_services.booking._shared.exceptions import (
        BookingEngineError,
        NoAvailabilityError,
        InvalidServiceDurationError,
        InvalidBookingDateError,
        ResourceNotAvailableError,
    )
"""

from datetime import date


class BookingEngineError(Exception):
    """
    Base exception of the booking engine.

    All other exceptions inherit from it.
    A Django view can catch BookingEngineError for unified handling
    of all engine errors.

    Example:
        try:
            result = service.book(...)
        except BookingEngineError as e:
            messages.error(request, str(e))
            return redirect("booking:wizard")
    """

    default_message: str = "Booking system error"

    def __init__(self, message: str | None = None) -> None:
        super().__init__(message or self.default_message)


class NoAvailabilityError(BookingEngineError):
    """
    The engine found no schedule options for the request.

    Raised when ChainFinder.find() returns an empty EngineResult.
    Translated to a user-friendly message in the Django view.

    Attributes:
        booking_date: Date searched for.
        service_ids: List of service IDs from the request.

    Example:
        raise NoAvailabilityError(
            booking_date=date(2024, 5, 10),
            service_ids=["5", "12"],
        )
        # str(e) -> "No free slots on 10.05.2024 for the selected services."
    """

    default_message = "Unfortunately, there are no available slots for these services on the selected date."

    def __init__(
        self,
        booking_date: date | None = None,
        service_ids: list[str] | None = None,
        message: str | None = None,
    ) -> None:
        self.booking_date = booking_date
        self.service_ids = service_ids or []

        if message:
            final_message = message
        elif booking_date:
            date_str = booking_date.strftime("%d.%m.%Y")
            final_message = f"No free slots on {date_str} for the selected services. Please try choosing another date."
        else:
            final_message = self.default_message

        super().__init__(final_message)


class InvalidServiceDurationError(BookingEngineError):
    """
    Incorrect service duration.

    Raised if duration_minutes <= 0 or exceeds the explicit maximum.

    Attributes:
        service_id: ID of the problematic service.
        duration_minutes: The passed duration value.

    Example:
        raise InvalidServiceDurationError(service_id="5", duration_minutes=0)
        # str(e) -> "Service 5: incorrect duration 0 min."
    """

    default_message = "Incorrect service duration."

    def __init__(
        self,
        service_id: str | None = None,
        duration_minutes: int | None = None,
        message: str | None = None,
    ) -> None:
        self.service_id = service_id
        self.duration_minutes = duration_minutes

        if message:
            final_message = message
        elif service_id is not None and duration_minutes is not None:
            final_message = (
                f"Service {service_id}: incorrect duration {duration_minutes} min. Duration must be greater than 0."
            )
        else:
            final_message = self.default_message

        super().__init__(final_message)


class InvalidBookingDateError(BookingEngineError):
    """
    Booking date is invalid.

    Example reasons:
        - Date in the past
        - Date beyond max_advance_days
        - Salon is closed on this day

    Attributes:
        booking_date: Problematic date.
        reason: Human-readable explanation.

    Example:
        raise InvalidBookingDateError(
            booking_date=date(2020, 1, 1),
            reason="Date in the past",
        )
    """

    default_message = "The selected date is unavailable for booking."

    def __init__(
        self,
        booking_date: date | None = None,
        reason: str | None = None,
        message: str | None = None,
    ) -> None:
        self.booking_date = booking_date
        self.reason = reason

        if message:
            final_message = message
        elif booking_date and reason:
            date_str = booking_date.strftime("%d.%m.%Y")
            final_message = f"Date {date_str} is unavailable: {reason}."
        elif booking_date:
            date_str = booking_date.strftime("%d.%m.%Y")
            final_message = f"Date {date_str} is unavailable for booking."
        else:
            final_message = self.default_message

        super().__init__(final_message)


class SlotAlreadyBookedError(BookingEngineError):
    """
    Slot was free during display but became booked by the time of confirmation.

    Race condition: client A and client B are viewing the same slot simultaneously.
    A clicks "Book" first -> B receives this error.

    Attributes:
        resource_id: Resource ID.
        service_id: Service ID.
        booking_date: Booking date.
        slot_time: Selected time (string "HH:MM").

    Example:
        raise SlotAlreadyBookedError(
            resource_id="3",
            service_id="5",
            booking_date=date(2024, 5, 10),
            slot_time="14:00",
        )
        # str(e) -> "Slot 14:00 on 10.05.2024 was booked. Please choose another time."
    """

    default_message = "The selected slot was booked. Please choose another time."

    def __init__(
        self,
        resource_id: str | None = None,
        service_id: str | None = None,
        booking_date: date | None = None,
        slot_time: str | None = None,
        message: str | None = None,
    ) -> None:
        self.resource_id = resource_id
        self.service_id = service_id
        self.booking_date = booking_date
        self.slot_time = slot_time

        if message:
            final_message = message
        elif slot_time and booking_date:
            date_str = booking_date.strftime("%d.%m.%Y")
            final_message = (
                f"Slot {slot_time} on {date_str} was booked while you were processing. Please choose another time."
            )
        else:
            final_message = self.default_message

        super().__init__(final_message)


class ChainBuildError(BookingEngineError):
    """
    The engine could not assemble a chain for all services in the request.

    Differs from NoAvailabilityError: here the chain was PARTIALLY assembled,
    but not to the end (constraint violation, incompatible services, etc.).

    Used when:
        - max_chain_duration_minutes is exceeded
        - Services are incompatible (future: excludes/tags)
        - group_size > available parallel slots

    Attributes:
        failed_at_index: Index of the service (in service_requests) where assembly failed.
        reason: Technical reason (for logs).

    Example:
        raise ChainBuildError(
            failed_at_index=2,
            reason="max_chain_duration_minutes=180 exceeded at service 'Coloring'",
        )
    """

    default_message = "Could not find a schedule for all selected services."

    def __init__(
        self,
        failed_at_index: int | None = None,
        reason: str | None = None,
        message: str | None = None,
    ) -> None:
        self.failed_at_index = failed_at_index
        self.reason = reason

        if message:
            final_message = message
        elif reason:
            final_message = f"Could not assemble the chain: {reason}."
        else:
            final_message = self.default_message

        super().__init__(final_message)


class ResourceNotAvailableError(BookingEngineError):
    """
    Specific resource is not available for booking.

    Used in RESOURCE_LOCKED mode when the selected resource
    does not work on this day or their schedule is empty.

    Attributes:
        resource_id: Resource's ID.
        booking_date: Date attempted to book.

    Example:
        raise ResourceNotAvailableError(resource_id="3", booking_date=date(2024,5,10))
        # str(e) -> "Resource unavailable on 10.05.2024."
    """

    default_message = "The selected resource is unavailable on this date."

    def __init__(
        self,
        resource_id: str | None = None,
        booking_date: date | None = None,
        message: str | None = None,
    ) -> None:
        self.resource_id = resource_id
        self.booking_date = booking_date

        if message:
            final_message = message
        elif booking_date:
            date_str = booking_date.strftime("%d.%m.%Y")
            final_message = f"Resource unavailable on {date_str}. Please try another date."
        else:
            final_message = self.default_message

        super().__init__(final_message)
