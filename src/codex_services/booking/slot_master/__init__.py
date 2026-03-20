"""Booking engine — chain service scheduling with backtracking."""

from codex_services.booking._shared.exceptions import (
    BookingEngineError,
    ChainBuildError,
    InvalidBookingDateError,
    InvalidServiceDurationError,
    NoAvailabilityError,
    ResourceNotAvailableError,
    SlotAlreadyBookedError,
)
from codex_services.booking._shared.interfaces import AvailabilityProvider, BusySlotsProvider, ScheduleProvider

from .api import find_nearest_slots, find_slots
from .chain_finder import ChainFinder
from .dto import (
    BookingChainSolution,
    BookingEngineRequest,
    EngineResult,
    MasterAvailability,
    ServiceRequest,
    SingleServiceSolution,
    WaitlistEntry,
)
from .modes import BookingMode
from .scorer import BookingScorer, ScoringWeights

__all__ = [
    # High-level facade (dict-based API)
    "find_slots",
    "find_nearest_slots",
    # Engine
    "ChainFinder",
    "BookingScorer",
    "ScoringWeights",
    # Interfaces
    "AvailabilityProvider",
    "BusySlotsProvider",
    "ScheduleProvider",
    # Request / availability DTOs
    "BookingEngineRequest",
    "ServiceRequest",
    "MasterAvailability",
    "BookingMode",
    # Result DTOs
    "EngineResult",
    "BookingChainSolution",
    "SingleServiceSolution",
    "WaitlistEntry",
    # Exceptions
    "BookingEngineError",
    "NoAvailabilityError",
    "InvalidServiceDurationError",
    "InvalidBookingDateError",
    "ResourceNotAvailableError",
    "SlotAlreadyBookedError",
    "ChainBuildError",
]
