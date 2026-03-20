"""
codex_services.booking.slot_master.api
======================================
High-level facade for the slot-master booking engine.

Use this module if you work with plain Python dicts and don't need ORM integration.
For Django projects, see :mod:`codex_tools.adapters.django`.

Quick start::

    from codex_services.booking.slot_master.api import find_slots

    result = find_slots(
        request_data={
            "service_requests": [
                {
                    "service_id": "haircut",
                    "duration_minutes": 60,
                    "possible_resource_ids": ["1", "2"],
                }
            ],
            "booking_date": "2024-05-15",
        },
        resources_availability=[
            {
                "resource_id": "1",
                "free_windows": [
                    ["2024-05-15T09:00:00", "2024-05-15T18:00:00"],
                ],
            }
        ],
    )
    # result["solutions"] — list of booking chain dicts
    # result["solutions"][0]["items"][0]["start_time"] — ISO datetime string
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date
from typing import Any

from .chain_finder import ChainFinder
from .dto import BookingEngineRequest, EngineResult, MasterAvailability
from .scorer import BookingScorer, ScoringWeights


def _parse_availability(items: list[dict[str, Any]]) -> dict[str, MasterAvailability]:
    return {(m := MasterAvailability.model_validate(item)).resource_id: m for item in items}


def find_slots(
    request_data: dict[str, Any],
    resources_availability: list[dict[str, Any]],
    *,
    step_minutes: int = 30,
    max_solutions: int = 50,
    scoring_weights: dict[str, Any] | None = None,
    preferred_resource_ids: list[str] | None = None,
) -> dict[str, Any]:
    """Find available booking slots for one day.

    Validates input via Pydantic, runs :class:`ChainFinder`, optionally scores results.

    Args:
        request_data: Dict matching :class:`~codex_services.booking.slot_master.BookingEngineRequest`.
            Required: ``service_requests``, ``booking_date``.
        resources_availability: List of dicts matching
            :class:`~codex_services.booking.slot_master.MasterAvailability`.
            Each item must contain ``resource_id`` and ``free_windows``.
        step_minutes: Slot grid step in minutes. Defaults to 30.
        max_solutions: Max solutions returned by the engine. Defaults to 50.
        scoring_weights: Optional dict with :class:`~codex_services.booking.slot_master.scorer.ScoringWeights`
            fields to rank solutions. Supported keys: ``preferred_resource_bonus``,
            ``same_resource_bonus``, ``min_idle_bonus_per_hour``,
            ``early_slot_penalty_per_hour``.
        preferred_resource_ids: Resource IDs to boost in scoring.
            Only effective when ``scoring_weights`` is provided.

    Returns:
        Serialised :class:`~codex_services.booking.slot_master.EngineResult` dict.
        Key ``"solutions"`` is a list of booking chain dicts.
        Returns an empty list under ``"solutions"`` if no slots are available.

    Raises:
        pydantic.ValidationError: If ``request_data`` or ``resources_availability``
            do not match the expected schema.
        NotImplementedError: If the request uses an unsupported mode
            (e.g. MULTI_DAY or group bookings).

    Example::

        result = find_slots(
            request_data={
                "service_requests": [
                    {"service_id": "s1", "duration_minutes": 60,
                     "possible_resource_ids": ["m1"]},
                ],
                "booking_date": "2024-05-15",
            },
            resources_availability=[
                {"resource_id": "m1",
                 "free_windows": [["2024-05-15T09:00:00", "2024-05-15T18:00:00"]]},
            ],
        )
        for chain in result["solutions"]:
            print(chain["items"][0]["start_time"])
    """
    request = BookingEngineRequest.model_validate(request_data)
    availability = _parse_availability(resources_availability)

    result: EngineResult = ChainFinder(step_minutes).find(request, availability, max_solutions=max_solutions)

    if scoring_weights is not None:
        weights = ScoringWeights(**scoring_weights)
        scorer = BookingScorer(weights=weights, preferred_resource_ids=preferred_resource_ids)
        result = scorer.score(result)

    return result.model_dump(mode="json")


def find_nearest_slots(
    request_data: dict[str, Any],
    get_availability_fn: Callable[[date], list[dict[str, Any]]],
    *,
    search_from: date | None = None,
    search_days: int = 60,
    step_minutes: int = 30,
) -> dict[str, Any] | None:
    """Search for the nearest available booking slots across multiple days.

    Iterates days starting from *search_from* until a day with solutions is found.

    Args:
        request_data: Dict matching :class:`~codex_services.booking.slot_master.BookingEngineRequest`.
        get_availability_fn: Callable ``(date) -> list[dict]``. Called for each checked
            day. Each dict in the returned list must match
            :class:`~codex_services.booking.slot_master.MasterAvailability`.
        search_from: Start date (inclusive). Defaults to :func:`~datetime.date.today`.
        search_days: Max number of days to search. Defaults to 60.
        step_minutes: Slot grid step in minutes. Defaults to 30.

    Returns:
        Serialised :class:`~codex_services.booking.slot_master.EngineResult` dict for the first
        matching day, or ``None`` if no slots were found within *search_days*.

    Example::

        def get_availability(d):
            # return your per-day availability data as list of dicts
            return [...]

        result = find_nearest_slots(
            request_data={...},
            get_availability_fn=get_availability,
            search_from=date.today(),
        )
        if result:
            print(result["solutions"][0]["items"][0]["start_time"])
    """
    search_from = search_from or date.today()
    request = BookingEngineRequest.model_validate(request_data)

    def _get_avail(d: date) -> dict[str, MasterAvailability]:
        return _parse_availability(get_availability_fn(d))

    result = ChainFinder(step_minutes).find_nearest(
        request, _get_avail, search_from=search_from, search_days=search_days
    )

    return result.model_dump(mode="json") if result.has_solutions else None
