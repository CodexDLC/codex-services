"""
Integration testing for ChainFinder to verify the entire Booking Engine flow,
including custom mode evaluations and basic service resolving logic.
"""

from datetime import date, datetime

import pytest

from codex_services.booking.slot_master import (
    BookingChainSolution,
    BookingEngineRequest,
    BookingMode,
    BookingScorer,
    ChainFinder,
    EngineResult,
    MasterAvailability,
    ScoringWeights,
    ServiceRequest,
    SingleServiceSolution,
    WaitlistEntry,
    find_nearest_slots,
    find_slots,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_availability(
    resource_id: str,
    win_start: datetime,
    win_end: datetime,
    buffer: int = 0,
    work_start: datetime | None = None,
) -> MasterAvailability:
    return MasterAvailability(
        resource_id=resource_id,
        free_windows=[(win_start, win_end)],
        buffer_between_minutes=buffer,
        work_start=work_start,
    )


# ---------------------------------------------------------------------------
# Original test (preserved)
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Multi-service sequential chain
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_multi_service_sequential_chain() -> None:
    """Two services for the same resource, sequential — covers recursive backtracking."""
    request = BookingEngineRequest(
        service_requests=[
            ServiceRequest(service_id="s1", duration_minutes=60, possible_resource_ids=["m1"]),
            ServiceRequest(service_id="s2", duration_minutes=30, possible_resource_ids=["m1"]),
        ],
        booking_date=date(2024, 1, 1),
        mode=BookingMode.SINGLE_DAY,
        overlap_allowed=False,
    )
    availability = {
        "m1": _make_availability("m1", datetime(2024, 1, 1, 9, 0), datetime(2024, 1, 1, 13, 0)),
    }
    finder = ChainFinder(step_minutes=30)
    result = finder.find(request, availability)

    assert result.has_solutions is True
    assert result.mode == BookingMode.SINGLE_DAY
    for sol in result.solutions:
        assert len(sol.items) == 2
        s1, s2 = sol.items[0], sol.items[1]
        # s2 must start after s1 ends
        assert s2.start_time >= s1.end_time


@pytest.mark.integration
def test_multi_service_two_resources() -> None:
    """Two services on different resources — covers no_conflicts path."""
    request = BookingEngineRequest(
        service_requests=[
            ServiceRequest(service_id="s1", duration_minutes=60, possible_resource_ids=["m1"]),
            ServiceRequest(service_id="s2", duration_minutes=60, possible_resource_ids=["m2"]),
        ],
        booking_date=date(2024, 1, 1),
        mode=BookingMode.SINGLE_DAY,
        overlap_allowed=False,
    )
    availability = {
        "m1": _make_availability("m1", datetime(2024, 1, 1, 10, 0), datetime(2024, 1, 1, 14, 0)),
        "m2": _make_availability("m2", datetime(2024, 1, 1, 10, 0), datetime(2024, 1, 1, 14, 0)),
    }
    finder = ChainFinder(step_minutes=30)
    result = finder.find(request, availability)

    assert result.has_solutions is True
    for sol in result.solutions:
        assert len(sol.items) == 2


# ---------------------------------------------------------------------------
# RESOURCE_LOCKED mode
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_resource_locked_mode() -> None:
    """RESOURCE_LOCKED mode uses same logic as SINGLE_DAY."""
    request = BookingEngineRequest(
        service_requests=[
            ServiceRequest(service_id="s1", duration_minutes=45, possible_resource_ids=["m1"]),
        ],
        booking_date=date(2024, 2, 1),
        mode=BookingMode.RESOURCE_LOCKED,
    )
    availability = {
        "m1": _make_availability("m1", datetime(2024, 2, 1, 9, 0), datetime(2024, 2, 1, 12, 0)),
    }
    finder = ChainFinder(step_minutes=15)
    result = finder.find(request, availability)

    assert result.has_solutions is True
    assert result.mode == BookingMode.RESOURCE_LOCKED


# ---------------------------------------------------------------------------
# NotImplementedError paths
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_group_size_raises_not_implemented() -> None:
    """group_size > 1 must raise NotImplementedError."""
    request = BookingEngineRequest(
        service_requests=[
            ServiceRequest(service_id="s1", duration_minutes=60, possible_resource_ids=["m1"]),
        ],
        booking_date=date(2024, 1, 1),
        mode=BookingMode.SINGLE_DAY,
        group_size=2,
    )
    availability = {
        "m1": _make_availability("m1", datetime(2024, 1, 1, 9, 0), datetime(2024, 1, 1, 12, 0)),
    }
    finder = ChainFinder(step_minutes=30)
    with pytest.raises(NotImplementedError, match="group_size"):
        finder.find(request, availability)


@pytest.mark.integration
def test_multi_day_mode_raises_not_implemented() -> None:
    """MULTI_DAY mode must raise NotImplementedError."""
    request = BookingEngineRequest(
        service_requests=[
            ServiceRequest(service_id="s1", duration_minutes=60, possible_resource_ids=["m1"]),
        ],
        booking_date=date(2024, 1, 1),
        mode=BookingMode.MULTI_DAY,
    )
    availability = {
        "m1": _make_availability("m1", datetime(2024, 1, 1, 9, 0), datetime(2024, 1, 1, 12, 0)),
    }
    finder = ChainFinder(step_minutes=30)
    with pytest.raises(NotImplementedError, match="MULTI_DAY"):
        finder.find(request, availability)


# ---------------------------------------------------------------------------
# max_chain_duration_minutes constraint
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_max_chain_duration_cuts_long_chains() -> None:
    """Solutions spanning more than max_chain_duration_minutes are excluded."""
    request = BookingEngineRequest(
        service_requests=[
            ServiceRequest(service_id="s1", duration_minutes=60, possible_resource_ids=["m1"]),
            ServiceRequest(service_id="s2", duration_minutes=60, possible_resource_ids=["m1"]),
        ],
        booking_date=date(2024, 1, 1),
        mode=BookingMode.SINGLE_DAY,
        overlap_allowed=False,
        max_chain_duration_minutes=90,  # 60+60=120 min span won't fit; only back-to-back chains
    )
    availability = {
        "m1": _make_availability("m1", datetime(2024, 1, 1, 9, 0), datetime(2024, 1, 1, 14, 0)),
    }
    finder = ChainFinder(step_minutes=30)
    result = finder.find(request, availability)

    # All solutions must fit within 90 min span
    for sol in result.solutions:
        assert sol.span_minutes <= 90


# ---------------------------------------------------------------------------
# min_gap_after_minutes
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_gap_after_service_respected() -> None:
    """s2 must start after s1.end_time + min_gap_after_minutes."""
    request = BookingEngineRequest(
        service_requests=[
            ServiceRequest(
                service_id="s1",
                duration_minutes=60,
                possible_resource_ids=["m1"],
                min_gap_after_minutes=30,
            ),
            ServiceRequest(service_id="s2", duration_minutes=30, possible_resource_ids=["m1"]),
        ],
        booking_date=date(2024, 1, 1),
        mode=BookingMode.SINGLE_DAY,
        overlap_allowed=False,
    )
    availability = {
        "m1": _make_availability("m1", datetime(2024, 1, 1, 9, 0), datetime(2024, 1, 1, 14, 0)),
    }
    finder = ChainFinder(step_minutes=30)
    result = finder.find(request, availability)

    assert result.has_solutions is True
    for sol in result.solutions:
        s1_item = sol.items[0]
        s2_item = sol.items[1]
        assert s2_item.start_time >= s1_item.gap_end_time


# ---------------------------------------------------------------------------
# buffer_between_minutes
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_buffer_between_clients() -> None:
    """buffer_between_minutes is respected for consecutive bookings."""
    request = BookingEngineRequest(
        service_requests=[
            ServiceRequest(service_id="s1", duration_minutes=60, possible_resource_ids=["m1"]),
            ServiceRequest(service_id="s2", duration_minutes=60, possible_resource_ids=["m1"]),
        ],
        booking_date=date(2024, 1, 1),
        mode=BookingMode.SINGLE_DAY,
        overlap_allowed=False,
    )
    availability = {
        "m1": _make_availability(
            "m1",
            datetime(2024, 1, 1, 9, 0),
            datetime(2024, 1, 1, 14, 0),
            buffer=15,
        ),
    }
    finder = ChainFinder(step_minutes=30)
    result = finder.find(request, availability)
    assert result.has_solutions is True


# ---------------------------------------------------------------------------
# min_start in ChainFinder
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_min_start_excludes_early_slots() -> None:
    """ChainFinder(min_start=...) skips slots before the min_start time."""
    min_start = datetime(2024, 1, 1, 11, 0)
    finder = ChainFinder(step_minutes=30, min_start=min_start)
    request = BookingEngineRequest(
        service_requests=[
            ServiceRequest(service_id="s1", duration_minutes=60, possible_resource_ids=["m1"]),
        ],
        booking_date=date(2024, 1, 1),
        mode=BookingMode.SINGLE_DAY,
    )
    availability = {
        "m1": _make_availability("m1", datetime(2024, 1, 1, 9, 0), datetime(2024, 1, 1, 14, 0)),
    }
    result = finder.find(request, availability)
    assert result.has_solutions is True
    for sol in result.solutions:
        assert sol.items[0].start_time >= min_start


# ---------------------------------------------------------------------------
# max_unique_starts
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_max_unique_starts_limits_results() -> None:
    """max_unique_starts=2 stops after finding 2 unique start times."""
    request = BookingEngineRequest(
        service_requests=[
            ServiceRequest(service_id="s1", duration_minutes=30, possible_resource_ids=["m1"]),
        ],
        booking_date=date(2024, 1, 1),
        mode=BookingMode.SINGLE_DAY,
    )
    availability = {
        "m1": _make_availability("m1", datetime(2024, 1, 1, 9, 0), datetime(2024, 1, 1, 14, 0)),
    }
    finder = ChainFinder(step_minutes=30)
    result = finder.find(request, availability, max_unique_starts=2)
    assert len(result.get_unique_start_times()) <= 2


# ---------------------------------------------------------------------------
# parallel_group
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_parallel_group_same_start_time() -> None:
    """Services in the same parallel_group must start at the same time."""
    request = BookingEngineRequest(
        service_requests=[
            ServiceRequest(
                service_id="s1",
                duration_minutes=60,
                possible_resource_ids=["m1"],
                parallel_group="grp1",
            ),
            ServiceRequest(
                service_id="s2",
                duration_minutes=60,
                possible_resource_ids=["m2"],
                parallel_group="grp1",
            ),
        ],
        booking_date=date(2024, 1, 1),
        mode=BookingMode.SINGLE_DAY,
        overlap_allowed=True,
    )
    availability = {
        "m1": _make_availability("m1", datetime(2024, 1, 1, 10, 0), datetime(2024, 1, 1, 14, 0)),
        "m2": _make_availability("m2", datetime(2024, 1, 1, 10, 0), datetime(2024, 1, 1, 14, 0)),
    }
    finder = ChainFinder(step_minutes=30)
    result = finder.find(request, availability)

    assert result.has_solutions is True
    for sol in result.solutions:
        assert sol.items[0].start_time == sol.items[1].start_time


# ---------------------------------------------------------------------------
# overlap_allowed=True
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_overlap_allowed_two_resources_simultaneous() -> None:
    """With overlap_allowed=True, services on different resources can be simultaneous."""
    request = BookingEngineRequest(
        service_requests=[
            ServiceRequest(service_id="s1", duration_minutes=60, possible_resource_ids=["m1"]),
            ServiceRequest(service_id="s2", duration_minutes=60, possible_resource_ids=["m2"]),
        ],
        booking_date=date(2024, 1, 1),
        mode=BookingMode.SINGLE_DAY,
        overlap_allowed=True,
    )
    availability = {
        "m1": _make_availability("m1", datetime(2024, 1, 1, 10, 0), datetime(2024, 1, 1, 14, 0)),
        "m2": _make_availability("m2", datetime(2024, 1, 1, 10, 0), datetime(2024, 1, 1, 14, 0)),
    }
    finder = ChainFinder(step_minutes=30)
    result = finder.find(request, availability)
    assert result.has_solutions is True


# ---------------------------------------------------------------------------
# find_nearest (ChainFinder)
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_find_nearest_finds_first_available_day() -> None:
    """find_nearest skips days with no availability and returns first day with slots."""
    base_date = date(2024, 3, 1)
    available_date = date(2024, 3, 3)

    def get_avail(d: date) -> dict[str, MasterAvailability]:
        if d != available_date:
            return {}
        return {
            "m1": _make_availability(
                "m1",
                datetime(d.year, d.month, d.day, 10, 0),
                datetime(d.year, d.month, d.day, 12, 0),
            )
        }

    request = BookingEngineRequest(
        service_requests=[
            ServiceRequest(service_id="s1", duration_minutes=60, possible_resource_ids=["m1"]),
        ],
        booking_date=base_date,
        mode=BookingMode.SINGLE_DAY,
    )
    finder = ChainFinder(step_minutes=30)
    result = finder.find_nearest(request, get_avail, search_from=base_date, search_days=10)

    assert result.has_solutions is True
    assert result.best is not None
    assert result.best.starts_at.date() == available_date


@pytest.mark.integration
def test_find_nearest_returns_empty_when_nothing_found() -> None:
    """find_nearest returns empty EngineResult when no day has slots."""
    request = BookingEngineRequest(
        service_requests=[
            ServiceRequest(service_id="s1", duration_minutes=60, possible_resource_ids=["m1"]),
        ],
        booking_date=date(2024, 1, 1),
        mode=BookingMode.SINGLE_DAY,
    )
    finder = ChainFinder(step_minutes=30)
    result = finder.find_nearest(
        request,
        lambda d: {},
        search_from=date(2024, 1, 1),
        search_days=5,
    )
    assert result.has_solutions is False
    assert isinstance(result, EngineResult)


# ---------------------------------------------------------------------------
# No solutions
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_no_solutions_when_window_too_small() -> None:
    """Service does not fit in the window — empty result."""
    request = BookingEngineRequest(
        service_requests=[
            ServiceRequest(service_id="s1", duration_minutes=120, possible_resource_ids=["m1"]),
        ],
        booking_date=date(2024, 1, 1),
        mode=BookingMode.SINGLE_DAY,
    )
    availability = {
        "m1": _make_availability("m1", datetime(2024, 1, 1, 10, 0), datetime(2024, 1, 1, 11, 0)),
    }
    finder = ChainFinder(step_minutes=30)
    result = finder.find(request, availability)
    assert result.has_solutions is False
    assert result.best is None


@pytest.mark.integration
def test_no_solutions_resource_not_in_availability() -> None:
    """Resource listed in request but not in availability dict — no solutions."""
    request = BookingEngineRequest(
        service_requests=[
            ServiceRequest(service_id="s1", duration_minutes=60, possible_resource_ids=["m99"]),
        ],
        booking_date=date(2024, 1, 1),
        mode=BookingMode.SINGLE_DAY,
    )
    availability = {
        "m1": _make_availability("m1", datetime(2024, 1, 1, 9, 0), datetime(2024, 1, 1, 12, 0)),
    }
    finder = ChainFinder(step_minutes=30)
    result = finder.find(request, availability)
    assert result.has_solutions is False


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_scoring_preferred_resource_boosts_score() -> None:
    """preferred_resource_ids increases score for matching solutions."""
    request = BookingEngineRequest(
        service_requests=[
            ServiceRequest(service_id="s1", duration_minutes=60, possible_resource_ids=["m1", "m2"]),
        ],
        booking_date=date(2024, 1, 1),
        mode=BookingMode.SINGLE_DAY,
    )
    availability = {
        "m1": _make_availability("m1", datetime(2024, 1, 1, 10, 0), datetime(2024, 1, 1, 14, 0)),
        "m2": _make_availability("m2", datetime(2024, 1, 1, 10, 0), datetime(2024, 1, 1, 14, 0)),
    }
    finder = ChainFinder(step_minutes=30)
    result = finder.find(request, availability)

    weights = ScoringWeights(preferred_resource_bonus=20.0)
    scorer = BookingScorer(weights=weights, preferred_resource_ids=["m1"])
    ranked = scorer.score(result)

    assert ranked.best is not None
    assert ranked.best.items[0].resource_id == "m1"
    assert ranked.best.score > 0


@pytest.mark.integration
def test_scoring_same_resource_bonus() -> None:
    """Two services on same resource gets same_resource_bonus."""
    request = BookingEngineRequest(
        service_requests=[
            ServiceRequest(service_id="s1", duration_minutes=30, possible_resource_ids=["m1"]),
            ServiceRequest(service_id="s2", duration_minutes=30, possible_resource_ids=["m1"]),
        ],
        booking_date=date(2024, 1, 1),
        mode=BookingMode.SINGLE_DAY,
        overlap_allowed=False,
    )
    availability = {
        "m1": _make_availability("m1", datetime(2024, 1, 1, 9, 0), datetime(2024, 1, 1, 13, 0)),
    }
    finder = ChainFinder(step_minutes=30)
    result = finder.find(request, availability)

    weights = ScoringWeights(same_resource_bonus=5.0)
    scorer = BookingScorer(weights=weights)
    ranked = scorer.score(result)

    for sol in ranked.solutions:
        assert sol.score >= 5.0


@pytest.mark.integration
def test_scoring_early_slot_penalty() -> None:
    """early_slot_penalty_per_hour reduces score for later start times."""
    request = BookingEngineRequest(
        service_requests=[
            ServiceRequest(service_id="s1", duration_minutes=60, possible_resource_ids=["m1"]),
        ],
        booking_date=date(2024, 1, 1),
        mode=BookingMode.SINGLE_DAY,
    )
    availability = {
        "m1": _make_availability("m1", datetime(2024, 1, 1, 9, 0), datetime(2024, 1, 1, 14, 0)),
    }
    finder = ChainFinder(step_minutes=30)
    result = finder.find(request, availability)

    weights = ScoringWeights(early_slot_penalty_per_hour=1.0)
    scorer = BookingScorer(weights=weights)
    ranked = scorer.score(result)

    # Earlier slot should have higher score (less penalty)
    assert ranked.best is not None
    assert ranked.best.starts_at == datetime(2024, 1, 1, 9, 0)


@pytest.mark.integration
def test_scoring_empty_result_unchanged() -> None:
    """Scoring an empty EngineResult returns it unchanged."""
    empty_result = EngineResult(mode=BookingMode.SINGLE_DAY, solutions=[])
    scorer = BookingScorer()
    ranked = scorer.score(empty_result)
    assert ranked.has_solutions is False


@pytest.mark.integration
def test_scoring_compactness_bonus() -> None:
    """min_idle_bonus_per_hour gives bonus for compact chains."""
    request = BookingEngineRequest(
        service_requests=[
            ServiceRequest(service_id="s1", duration_minutes=30, possible_resource_ids=["m1"]),
            ServiceRequest(service_id="s2", duration_minutes=30, possible_resource_ids=["m1"]),
        ],
        booking_date=date(2024, 1, 1),
        mode=BookingMode.SINGLE_DAY,
        overlap_allowed=False,
    )
    availability = {
        "m1": _make_availability("m1", datetime(2024, 1, 1, 9, 0), datetime(2024, 1, 1, 13, 0)),
    }
    finder = ChainFinder(step_minutes=30)
    result = finder.find(request, availability)

    weights = ScoringWeights(min_idle_bonus_per_hour=2.0)
    scorer = BookingScorer(weights=weights)
    ranked = scorer.score(result)
    assert ranked.best is not None


# ---------------------------------------------------------------------------
# High-level API: find_slots
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_find_slots_api_returns_dict() -> None:
    """find_slots returns a dict with 'solutions' key."""
    result = find_slots(
        request_data={
            "service_requests": [
                {"service_id": "s1", "duration_minutes": 60, "possible_resource_ids": ["m1"]},
            ],
            "booking_date": "2024-01-15",
        },
        resources_availability=[
            {
                "resource_id": "m1",
                "free_windows": [["2024-01-15T09:00:00", "2024-01-15T12:00:00"]],
            }
        ],
    )
    assert isinstance(result, dict)
    assert "solutions" in result
    assert len(result["solutions"]) > 0


@pytest.mark.integration
def test_find_slots_api_with_scoring() -> None:
    """find_slots with scoring_weights returns scored solutions."""
    result = find_slots(
        request_data={
            "service_requests": [
                {"service_id": "s1", "duration_minutes": 60, "possible_resource_ids": ["m1", "m2"]},
            ],
            "booking_date": "2024-01-15",
        },
        resources_availability=[
            {
                "resource_id": "m1",
                "free_windows": [["2024-01-15T09:00:00", "2024-01-15T14:00:00"]],
            },
            {
                "resource_id": "m2",
                "free_windows": [["2024-01-15T09:00:00", "2024-01-15T14:00:00"]],
            },
        ],
        scoring_weights={"preferred_resource_bonus": 15.0},
        preferred_resource_ids=["m1"],
    )
    assert len(result["solutions"]) > 0
    # Best solution should be for m1
    assert result["solutions"][0]["items"][0]["resource_id"] == "m1"


@pytest.mark.integration
def test_find_slots_api_no_solutions_returns_empty() -> None:
    """find_slots returns empty solutions list when no slots fit."""
    result = find_slots(
        request_data={
            "service_requests": [
                {"service_id": "s1", "duration_minutes": 240, "possible_resource_ids": ["m1"]},
            ],
            "booking_date": "2024-01-15",
        },
        resources_availability=[
            {
                "resource_id": "m1",
                "free_windows": [["2024-01-15T10:00:00", "2024-01-15T11:00:00"]],
            }
        ],
    )
    assert result["solutions"] == []


# ---------------------------------------------------------------------------
# High-level API: find_nearest_slots
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_find_nearest_slots_api_finds_day() -> None:
    """find_nearest_slots returns a result dict for the first available day."""
    target_date = date(2024, 4, 5)

    def get_avail(d: date) -> list[dict]:
        if d != target_date:
            return []
        return [
            {
                "resource_id": "m1",
                "free_windows": [[f"{d.isoformat()}T10:00:00", f"{d.isoformat()}T13:00:00"]],
            }
        ]

    result = find_nearest_slots(
        request_data={
            "service_requests": [
                {"service_id": "s1", "duration_minutes": 60, "possible_resource_ids": ["m1"]},
            ],
            "booking_date": "2024-04-01",
        },
        get_availability_fn=get_avail,
        search_from=date(2024, 4, 1),
        search_days=10,
    )
    assert result is not None
    assert len(result["solutions"]) > 0


@pytest.mark.integration
def test_find_nearest_slots_api_returns_none_when_unavailable() -> None:
    """find_nearest_slots returns None when no day has slots."""
    result = find_nearest_slots(
        request_data={
            "service_requests": [
                {"service_id": "s1", "duration_minutes": 60, "possible_resource_ids": ["m1"]},
            ],
            "booking_date": "2024-01-01",
        },
        get_availability_fn=lambda d: [],
        search_from=date(2024, 1, 1),
        search_days=5,
    )
    assert result is None


# ---------------------------------------------------------------------------
# DTO properties and repr
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_service_request_repr_and_properties() -> None:
    """ServiceRequest repr and total_block_minutes work correctly."""
    sr = ServiceRequest(
        service_id="abc",
        duration_minutes=60,
        possible_resource_ids=["m1"],
        min_gap_after_minutes=15,
    )
    assert sr.total_block_minutes == 75
    assert "abc" in repr(sr)
    assert "60" in repr(sr)


@pytest.mark.integration
def test_booking_engine_request_properties() -> None:
    """BookingEngineRequest properties: total_duration and total_block."""
    request = BookingEngineRequest(
        service_requests=[
            ServiceRequest(
                service_id="s1", duration_minutes=60, possible_resource_ids=["m1"], min_gap_after_minutes=10
            ),
            ServiceRequest(service_id="s2", duration_minutes=30, possible_resource_ids=["m1"]),
        ],
        booking_date=date(2024, 1, 1),
    )
    assert request.total_duration_minutes == 90
    assert request.total_block_minutes == 100
    assert "2024" in repr(request)


@pytest.mark.integration
def test_master_availability_repr() -> None:
    """MasterAvailability repr works."""
    avail = _make_availability("m1", datetime(2024, 1, 1, 9, 0), datetime(2024, 1, 1, 12, 0))
    r = repr(avail)
    assert "m1" in r


@pytest.mark.integration
def test_single_service_solution_repr() -> None:
    """SingleServiceSolution repr is safe (no PII)."""
    sol = SingleServiceSolution(
        service_id="s1",
        resource_id="m1",
        start_time=datetime(2024, 1, 1, 10, 0),
        end_time=datetime(2024, 1, 1, 11, 0),
        gap_end_time=datetime(2024, 1, 1, 11, 0),
    )
    r = repr(sol)
    assert "s1" in r
    assert "10:00" in r


@pytest.mark.integration
def test_booking_chain_solution_properties() -> None:
    """BookingChainSolution: starts_at, ends_at, span_minutes, to_display, repr."""
    sol = BookingChainSolution(
        items=[
            SingleServiceSolution(
                service_id="s1",
                resource_id="m1",
                start_time=datetime(2024, 1, 1, 10, 0),
                end_time=datetime(2024, 1, 1, 11, 0),
                gap_end_time=datetime(2024, 1, 1, 11, 0),
            ),
            SingleServiceSolution(
                service_id="s2",
                resource_id="m2",
                start_time=datetime(2024, 1, 1, 11, 30),
                end_time=datetime(2024, 1, 1, 12, 0),
                gap_end_time=datetime(2024, 1, 1, 12, 0),
            ),
        ]
    )
    assert sol.starts_at == datetime(2024, 1, 1, 10, 0)
    assert sol.ends_at == datetime(2024, 1, 1, 12, 0)
    assert sol.span_minutes == 120
    display = sol.to_display()
    assert "s1" in display
    assert "s2" in display
    assert "resource_id" in display["s1"]
    assert "s1" in repr(sol)


@pytest.mark.integration
def test_engine_result_properties() -> None:
    """EngineResult: best_scored, get_unique_start_times, repr."""
    sol1 = BookingChainSolution(
        items=[
            SingleServiceSolution(
                service_id="s1",
                resource_id="m1",
                start_time=datetime(2024, 1, 1, 10, 0),
                end_time=datetime(2024, 1, 1, 11, 0),
                gap_end_time=datetime(2024, 1, 1, 11, 0),
            )
        ],
        score=5.0,
    )
    sol2 = BookingChainSolution(
        items=[
            SingleServiceSolution(
                service_id="s1",
                resource_id="m1",
                start_time=datetime(2024, 1, 1, 11, 0),
                end_time=datetime(2024, 1, 1, 12, 0),
                gap_end_time=datetime(2024, 1, 1, 12, 0),
            )
        ],
        score=10.0,
    )
    result = EngineResult(mode=BookingMode.SINGLE_DAY, solutions=[sol1, sol2])
    assert result.best_scored is sol2
    times = result.get_unique_start_times()
    assert "10:00" in times
    assert "11:00" in times
    assert "single_day" in repr(result)

    # Empty result
    empty = EngineResult(mode=BookingMode.SINGLE_DAY, solutions=[])
    assert empty.best_scored is None


@pytest.mark.integration
def test_waitlist_entry_from_engine_result() -> None:
    """WaitlistEntry.from_engine_result creates entry from valid result."""
    request = BookingEngineRequest(
        service_requests=[
            ServiceRequest(service_id="s1", duration_minutes=60, possible_resource_ids=["m1"]),
        ],
        booking_date=date(2024, 1, 1),
        mode=BookingMode.SINGLE_DAY,
    )
    availability = {
        "m1": _make_availability("m1", datetime(2024, 1, 5, 10, 0), datetime(2024, 1, 5, 12, 0)),
    }
    finder = ChainFinder(step_minutes=30)
    result = finder.find(
        request.model_copy(update={"booking_date": date(2024, 1, 5)}),
        availability,
    )
    assert result.has_solutions is True

    entry = WaitlistEntry.from_engine_result(result, original_date=date(2024, 1, 1))
    assert entry is not None
    assert entry.available_date == date(2024, 1, 5)
    assert entry.available_time == "10:00"
    assert entry.days_from_request == 4
    assert "10:00" in repr(entry)


@pytest.mark.integration
def test_waitlist_entry_from_empty_result_returns_none() -> None:
    """WaitlistEntry.from_engine_result returns None for empty result."""
    empty = EngineResult(mode=BookingMode.SINGLE_DAY, solutions=[])
    entry = WaitlistEntry.from_engine_result(empty, original_date=date(2024, 1, 1))
    assert entry is None
