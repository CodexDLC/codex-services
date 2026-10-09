# Booking chains

The public facade `codex_services.booking.slot_master.find_slots` accepts dictionaries and returns a JSON-compatible dictionary. This example runs with `codex-services` installed:

```python
from codex_services.booking.slot_master import find_slots

result = find_slots(
    request_data={
        "booking_date": "2026-10-12",
        "service_requests": [
            {"service_id": "cut", "duration_minutes": 60, "possible_resource_ids": ["m1"]},
        ],
    },
    resources_availability=[
        {"resource_id": "m1", "free_windows": [["2026-10-12T09:00:00", "2026-10-12T11:00:00"]]},
    ],
)
print([item["start_time"] for chain in result["solutions"] for item in chain["items"]])
```

`service_requests` must be nonempty, each duration positive, and each service needs at least one `possible_resource_ids` entry. The facade validates with Pydantic and may raise `ValidationError`; `solutions` can be empty. `group_size > 1` and `MULTI_DAY` raise `NotImplementedError`. Optional `scoring_weights` ranks solutions and `preferred_resource_ids` matters only when weights are supplied.

For typed integration, import `BookingEngineRequest`, `ServiceRequest`, `MasterAvailability`, `ChainFinder`, and `BookingMode` from `codex_services.booking.slot_master`. `ChainFinder(step_minutes=30).find(request, {availability.resource_id: availability})` returns an `EngineResult`; check `has_solutions` before using `best`. The DTOs are immutable. Use `find_nearest_slots(request_data, get_availability_fn, search_from=..., search_days=...)` when the application can provide per-day availability; it returns a result dictionary or `None`.

The library computes candidates from supplied availability. The consuming application owns ORM queries, timezone normalization, authorization, conflict checks, and booking writes. See package source `codex_services/booking/slot_master/api.py` and `dto.py` for version-specific fields.
