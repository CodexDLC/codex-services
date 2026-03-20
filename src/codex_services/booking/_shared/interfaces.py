"""
codex_services.booking._shared.interfaces
==========================================
Protocol contracts for booking-specific adapters.
Implement these protocols when building a new adapter for the booking engine.
"""

from __future__ import annotations

from datetime import date, datetime, time
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from codex_services.booking._shared.dto import ResourceAvailability


class ScheduleProvider(Protocol):
    """Provides working schedules for resources."""

    def get_working_hours(self, resource_id: str, target_date: date) -> tuple[time, time] | None:
        """Return (start, end) of working day or None if day off."""
        ...

    def get_break_interval(self, resource_id: str, target_date: date) -> tuple[datetime, datetime] | None:
        """Return (start, end) of break or None."""
        ...


class BusySlotsProvider(Protocol):
    """Provides busy time slots for resources."""

    def get_busy_intervals(
        self, resource_ids: list[str], target_date: date
    ) -> dict[str, list[tuple[datetime, datetime]]]:
        """Return {resource_id: [(start, end), ...]} of busy times."""
        ...


class AvailabilityProvider(Protocol):
    """
    Full availability provider — the main adapter contract.
    Implement this protocol for each framework adapter (Django, SQLAlchemy, etc.).
    """

    def build_resources_availability(
        self,
        resource_ids: list[str],
        target_date: date,
        cache_ttl: int = 300,
        exclude_appointment_ids: list[int] | None = None,
    ) -> dict[str, ResourceAvailability]:
        """Build availability for a single date. Return {resource_id: ResourceAvailability}."""
        ...

    def build_availability_batch(
        self,
        resource_ids: list[str],
        start_date: date,
        end_date: date,
    ) -> dict[date, dict[str, ResourceAvailability]]:
        """
        Build availability for a date range in a single batch.
        Must avoid N+1 queries — group appointments in memory.
        Return {date: {resource_id: ResourceAvailability}}.
        """
        ...
