"""codex_services.booking: Unified booking engine library.

Provides different booking strategies (slot_master, room, etc.)
with shared utilities and base DTOs.
"""

from codex_services.booking._shared.calculator import SlotCalculator
from codex_services.booking._shared.dto import (
    BookingRequest,
    BookingResult,
    BookingSolution,
    ResourceAvailability,
)
from codex_services.booking._shared.exceptions import BookingEngineError
from codex_services.booking._shared.interfaces import (
    AvailabilityProvider,
    BusySlotsProvider,
    ScheduleProvider,
)
from codex_services.booking._shared.validators import BookingValidator

__all__ = [
    # Base DTOs
    "ResourceAvailability",
    "BookingRequest",
    "BookingSolution",
    "BookingResult",
    # Shared utilities
    "SlotCalculator",
    "BookingValidator",
    # Interfaces
    "AvailabilityProvider",
    "BusySlotsProvider",
    "ScheduleProvider",
    # Base exception
    "BookingEngineError",
]
