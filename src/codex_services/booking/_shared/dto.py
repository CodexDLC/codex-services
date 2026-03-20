"""
codex_services.booking._shared.dto
===================================
Base DTOs shared across all booking types.

Each booking type (slot_master, room, etc.) inherits from these
and adds domain-specific fields.
"""

from datetime import date, datetime

from codex_core.core.base_dto import BaseDTO
from pydantic import Field, model_validator


class ResourceAvailability(BaseDTO):
    """
    Base availability of a resource (executor, room, equipment, etc.).

    Fields:
        resource_id (str): Unique identifier of the resource.
        free_windows (list[tuple[datetime, datetime]]): Available time windows.
            Each tuple is (start, end) where start < end.
    """

    resource_id: str
    free_windows: list[tuple[datetime, datetime]] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_windows_order(self) -> "ResourceAvailability":
        """Validate that each free window is chronologically correct."""
        for start, end in self.free_windows:
            if start >= end:
                raise ValueError(f"Resource {self.resource_id}: start={start} >= end={end}")
        return self

    def __repr__(self) -> str:
        return f"<ResourceAvailability resource={self.resource_id} windows={len(self.free_windows)}>"


class BookingRequest(BaseDTO):
    """
    Base booking request.

    Fields:
        booking_date (date): Target date for the booking.
    """

    booking_date: date


class BookingSolution(BaseDTO):
    """
    Base result — one booked slot.

    Fields:
        resource_id (str): Assigned resource identifier.
        start_time (datetime): Scheduled start time.
        end_time (datetime): Scheduled end time.
    """

    resource_id: str
    start_time: datetime
    end_time: datetime

    @property
    def duration_minutes(self) -> int:
        """Calculate actual duration in minutes."""
        return int((self.end_time - self.start_time).total_seconds() / 60)


class BookingResult(BaseDTO):
    """
    Base result — list of solutions.

    Concrete booking types override the `solutions` field with a specific type.
    """

    @property
    def has_solutions(self) -> bool:
        """Return True if at least one solution was found."""
        raise NotImplementedError("Subclasses must implement has_solutions")
