"""Unit tests for booking API facade."""

from datetime import date

import pytest

from codex_services.booking.slot_master.api import find_nearest_slots, find_slots


def make_request_data(booking_date: str = "2024-05-10") -> dict:
    return {
        "service_requests": [
            {
                "service_id": "haircut",
                "duration_minutes": 60,
                "possible_resource_ids": ["m1"],
            }
        ],
        "booking_date": booking_date,
    }


def make_availability(
    resource_id: str = "m1",
    date_str: str = "2024-05-10",
    start_h: int = 9,
    end_h: int = 18,
) -> list[dict]:
    return [
        {
            "resource_id": resource_id,
            "free_windows": [
                [f"{date_str}T{start_h:02d}:00:00", f"{date_str}T{end_h:02d}:00:00"],
            ],
        }
    ]


@pytest.mark.unit
class TestFindSlots:
    def test_returns_dict(self) -> None:
        result = find_slots(make_request_data(), make_availability())
        assert isinstance(result, dict)
        assert "solutions" in result

    def test_finds_solutions(self) -> None:
        result = find_slots(make_request_data(), make_availability())
        assert len(result["solutions"]) > 0

    def test_no_availability_returns_empty(self) -> None:
        result = find_slots(make_request_data(), [])
        assert result["solutions"] == []

    def test_with_scoring_weights(self) -> None:
        result = find_slots(
            make_request_data(),
            make_availability(),
            scoring_weights={"preferred_resource_bonus": 5.0},
            preferred_resource_ids=["m1"],
        )
        assert isinstance(result, dict)
        assert len(result["solutions"]) > 0

    def test_max_solutions_respected(self) -> None:
        result = find_slots(make_request_data(), make_availability(), max_solutions=2)
        assert len(result["solutions"]) <= 2

    def test_solution_structure(self) -> None:
        result = find_slots(make_request_data(), make_availability())
        chain = result["solutions"][0]
        assert "items" in chain
        item = chain["items"][0]
        assert "start_time" in item
        assert "end_time" in item
        assert "resource_id" in item


@pytest.mark.unit
class TestFindNearestSlots:
    def test_returns_none_when_no_availability(self) -> None:
        def get_avail(d: date) -> list[dict]:
            return []

        result = find_nearest_slots(
            make_request_data(),
            get_avail,
            search_from=date(2024, 5, 10),
            search_days=3,
        )
        assert result is None

    def test_returns_result_when_availability_found(self) -> None:
        target_date = date(2024, 5, 10)

        def get_avail(d: date) -> list[dict]:
            if d == target_date:
                return make_availability(date_str=d.isoformat())
            return []

        result = find_nearest_slots(
            make_request_data(booking_date="2024-05-10"),
            get_avail,
            search_from=target_date,
            search_days=5,
        )
        assert result is not None
        assert "solutions" in result
        assert len(result["solutions"]) > 0

    def test_searches_across_days(self) -> None:
        available_date = date(2024, 5, 12)

        def get_avail(d: date) -> list[dict]:
            if d == available_date:
                return make_availability(date_str=d.isoformat())
            return []

        result = find_nearest_slots(
            make_request_data(booking_date="2024-05-10"),
            get_avail,
            search_from=date(2024, 5, 10),
            search_days=5,
        )
        assert result is not None
