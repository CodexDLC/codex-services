"""
codex_services.booking.slot_master.modes
========================================
Operating modes for the slot-master booking engine.

Imports:
    from codex_services.booking.slot_master import BookingMode
"""

import sys
from enum import Enum

if sys.version_info >= (3, 11):  # pragma: no cover
    from enum import StrEnum  # pragma: no cover
else:

    class StrEnum(str, Enum):
        pass


class BookingMode(StrEnum):
    """
    Operating mode for ChainFinder.

    SINGLE_DAY:
        All services from the request must fit within a single day.
        The common mode — multiple services in one visit.

    MULTI_DAY:
        Each service can be scheduled for a different day (Stub).

    RESOURCE_LOCKED:
        Booking for a specific resource (e.g., from their personal page).
        The engine relies entirely on the provided resource constraints.

    Example:
        ```python
        mode = BookingMode.SINGLE_DAY
        ```
    """

    SINGLE_DAY = "single_day"
    MULTI_DAY = "multi_day"
    RESOURCE_LOCKED = "resource_locked"
