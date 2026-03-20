"""
Integration testing for ChainFinder to verify the entire Booking Engine flow,
including custom mode evaluations and basic service resolving logic.
"""

from datetime import date, datetime

import pytest

from codex_services.booking.slot_master import (
    BookingEngineRequest,
    BookingMode,
    ChainFinder,
    MasterAvailability,
    ServiceRequest,
)


@pytest.mark.integration
def test_chain_finder_basic_integration() -> None:
    """
    Integration test:
    Verifies that ChainFinder successfully discovers valid booking slots
    using the SINGLE_DAY BookingMode.
    """
    request = BookingEngineRequest(
        service_requests=[
            ServiceRequest(service_id="s1", duration_minutes=60, possible_resource_ids=["m1"]),
        ],
        booking_date=date(2024, 1, 1),
        mode=BookingMode.SINGLE_DAY,
    )

    availability = {
        "m1": MasterAvailability(
            resource_id="m1",
            free_windows=[(datetime(2024, 1, 1, 10, 0), datetime(2024, 1, 1, 12, 0))],
        )
    }

    finder = ChainFinder(step_minutes=30)
    result = finder.find(request, availability)

    # Validate output structure and basic sanity logic
    assert result.has_solutions is True
    assert result.mode == BookingMode.SINGLE_DAY
    assert result.best is not None

    # Expected 3 variations of start grid steps within 2 hours for a 60min service:
    # 10:00-11:00, 10:30-11:30, 11:00-12:00
    assert len(result.solutions) == 3

    # Primary found slot validation
    first_item = result.best.items[0]
    assert first_item.service_id == "s1"
    assert first_item.resource_id == "m1"
    assert first_item.start_time == datetime(2024, 1, 1, 10, 0)
    assert first_item.end_time == datetime(2024, 1, 1, 11, 0)
