"""
codex_services.booking.slot_master.dto
======================================
Pydantic v2 DTO (Data Transfer Objects) for the slot-master booking engine.

All models are immutable (frozen=True via BaseDTO) — the engine does not mutate inputs.
No Django imports. Only Python stdlib + pydantic + codex_core.

Imports:
    from codex_services.booking.slot_master import (
        BookingEngineRequest, ServiceRequest,
        MasterAvailability, EngineResult, BookingChainSolution,
    )
"""

from datetime import date, datetime
from typing import Any

from codex_core.core.base_dto import BaseDTO
from pydantic import Field

from codex_services.booking._shared.dto import (
    BookingRequest,
    BookingSolution,
    ResourceAvailability,
)

from .modes import BookingMode

# ---------------------------------------------------------------------------
# Входные DTO (что подаётся в движок)
# ---------------------------------------------------------------------------


class ServiceRequest(BaseDTO):
    """
    Request for a single service within a booking chain.

    The engine treats this as an atomic requirement. It operates with abstract
    resource IDs (possible_resource_ids) rather than specific business entities.

    Fields:
        service_id (str):
            Unique identifier of the service. String for universality
            (can be "5", "uuid-xxx", "task-1" — doesn't matter).

        duration_minutes (int):
            Duration of the service in minutes. Must be > 0.

        min_gap_after_minutes (int):
            Minimum gap (minutes) after this service before the next one
            in the chain. Default is 0 (no gap).
            Example: if there is a cooling down period of 30 mins → min_gap_after_minutes=30.

        possible_resource_ids (list[str]):
            List of resource IDs capable of performing this service.
            The engine chooses an available resource from this list.
            For RESOURCE_LOCKED mode, this should contain exactly one element.

        parallel_group (str | None):
            Tag for parallel execution group.
            Services with the same parallel_group can be performed simultaneously
            by different resources (if overlap_allowed=True is set in the request).
            None = service is performed independently (standard sequential behavior).

    Example:
        ```python
        ServiceRequest(
            service_id="5",
            duration_minutes=60,
            possible_resource_ids=["1", "3", "7"],
        )
        ```
    """

    service_id: str
    duration_minutes: int = Field(gt=0, description="Длительность в минутах")
    min_gap_after_minutes: int = Field(default=0, ge=0, description="Пауза после услуги перед следующей")
    possible_resource_ids: list[str] = Field(min_length=1, description="Хотя бы один ресурс должен быть указан")
    parallel_group: str | None = Field(
        default=None,
        description="Метка группы параллельного выполнения (одинаковый тег = одновременно)",
    )

    @property
    def total_block_minutes(self) -> int:
        """Return total time that blocks the resource: duration + gap after."""
        return self.duration_minutes + self.min_gap_after_minutes

    def __repr__(self) -> str:
        return f"<ServiceRequest id={self.service_id} dur={self.duration_minutes}>"


class BookingEngineRequest(BookingRequest):
    """
    Input request describing the entire desired booking chain.

    Orchestrates multiple ServiceRequests into a single search task.
    Inherits booking_date from BookingRequest.

    Fields:
        service_requests (list[ServiceRequest]):
            List of services to book. Order is critical for SINGLE_DAY mode —
            the engine will schedule them in the specified sequence.
            Minimum 1 service required.

        booking_date (date):
            Target date. Inherited from BookingRequest.
            Used for SINGLE_DAY and RESOURCE_LOCKED.
            In MULTI_DAY mode, this represents the date of the first service.

        mode (BookingMode):
            Engine operating strategy. Default is SINGLE_DAY.

        overlap_allowed (bool):
            Allow parallel execution of services by different resources.
            False (default) — each subsequent service starts only after the
            previous one (plus its gap) ends.
            True — resources can work independently; services may start
            simultaneously if resources are available.

        group_size (int):
            DEPRECATED. Use duplication of ServiceRequest with parallel_group.

        max_chain_duration_minutes (int | None):
            Maximum total duration of the entire booking (from start of first
            to end of last service). None = no limit.

        days_gap (list[int] | None):
            Day offsets for each service. Used strictly in MULTI_DAY mode.

    Example:
        ```python
        BookingEngineRequest(
            service_requests=[svc_1, svc_2],
            booking_date=date(2024, 5, 10),
            mode=BookingMode.SINGLE_DAY,
            overlap_allowed=True
        )
        ```
    """

    service_requests: list[ServiceRequest] = Field(min_length=1, description="Минимум одна услуга")
    mode: BookingMode = BookingMode.SINGLE_DAY
    overlap_allowed: bool = Field(
        default=False,
        description="Разрешить параллельное выполнение услуг разными ресурсами",
    )
    group_size: int = Field(
        default=1,
        ge=1,
        description="DEPRECATED. Используйте дублирование ServiceRequest с parallel_group.",
    )
    max_chain_duration_minutes: int | None = Field(
        default=None,
        ge=1,
        description="Макс. длительность всей цепочки в минутах (None = без лимита)",
    )
    days_gap: list[int] | None = Field(
        default=None,
        description="Смещение в днях для каждой услуги (только MULTI_DAY)",
    )

    @property
    def total_duration_minutes(self) -> int:
        """Calculate total duration of all services without gap pauses."""
        return sum(s.duration_minutes for s in self.service_requests)

    @property
    def total_block_minutes(self) -> int:
        """
        Calculate total blocking time including pauses between services.
        Used for quick checks: does the chain fit into a given window.
        """
        return sum(s.total_block_minutes for s in self.service_requests)

    def __repr__(self) -> str:
        return f"<BookingEngineRequest date={self.booking_date} services={len(self.service_requests)}>"


# ---------------------------------------------------------------------------
# Данные доступности (подготавливаются адаптером)
# ---------------------------------------------------------------------------


class MasterAvailability(ResourceAvailability):
    """
    Available time windows of a resource for the slot-master booking type.

    Inherits resource_id and free_windows from ResourceAvailability.
    Adds slot-master-specific fields: buffer_between_minutes and work_start.

    Fields:
        resource_id (str): Resource identifier (inherited).
        free_windows (list[tuple[datetime, datetime]]): List of (start, end) tuples (inherited).
        buffer_between_minutes (int): Minimum buffer required between bookings.
        work_start (datetime | None): Shift start anchor for slot alignment.

    Example:
        ```python
        MasterAvailability(
            resource_id="resource_1",
            free_windows=[(datetime(2024,5,10,9,0), datetime(2024,5,10,12,0))],
            buffer_between_minutes=10,
        )
        ```
    """

    buffer_between_minutes: int = Field(default=0, ge=0)
    work_start: datetime | None = Field(
        default=None,
        description="Якорь для выравнивания сетки слотов (например, начало смены)",
    )

    def __repr__(self) -> str:
        return f"<MasterAvailability resource={self.resource_id} windows={len(self.free_windows)}>"


# ---------------------------------------------------------------------------
# Выходные DTO (результат работы движка)
# ---------------------------------------------------------------------------


class SingleServiceSolution(BookingSolution):
    """
    Found slot for a single service in a booking chain.

    Inherits resource_id, start_time, end_time from BookingSolution.
    Adds service_id and gap_end_time.

    Fields:
        service_id (str): Reference to the original ServiceRequest.service_id.
        resource_id (str): Identifier of the resource assigned to this service (inherited).
        start_time (datetime): Scheduled start time of the service (inherited).
        end_time (datetime): Scheduled completion time (excluding gap) (inherited).
        gap_end_time (datetime): End of the blocking period (end_time + gap).

    Example:
        ```python
        slot = SingleServiceSolution(
            service_id="5",
            resource_id="1",
            start_time=datetime(2024, 5, 10, 10, 0),
            end_time=datetime(2024, 5, 10, 11, 0),
            gap_end_time=datetime(2024, 5, 10, 11, 15),
        )
        ```
    """

    service_id: str
    gap_end_time: datetime  # end_time + min_gap_after_minutes

    def __repr__(self) -> str:
        # GDPR Safe: Only IDs and Times. No notes, names, or PII.
        return (
            f"<SingleServiceSolution svc={self.service_id} "
            f"res={self.resource_id} "
            f"start={self.start_time.strftime('%H:%M')}>"
        )


class BookingChainSolution(BaseDTO):
    """
    One complete solution for the entire request (set of slots for all services).

    Found by the engine. Guarantees no conflicts between services and
    respects all resource availability constraints.

    Fields:
        items (list[SingleServiceSolution]):
            List of slots in the order of service execution.

        score (float):
            Quality score of the solution (higher is better).
            Can be influenced by preferred resources, idle time, or resource reuse.

    Example:
        ```python
        solution = BookingChainSolution(items=[slot1, slot2], score=10.0)
        print(f"Booking span: {solution.span_minutes} minutes")
        ```
    """

    items: list[SingleServiceSolution] = Field(min_length=1)
    score: float = Field(default=0.0, description="Оценка качества решения")

    @property
    def starts_at(self) -> datetime:
        """Return the start time of the first service in the chain."""
        return min(s.start_time for s in self.items)

    @property
    def ends_at(self) -> datetime:
        """Return the end time of the last service (excluding gap)."""
        return max(s.end_time for s in self.items)

    @property
    def span_minutes(self) -> int:
        """Return total time from the start of the first to the end of the last service."""
        return int((self.ends_at - self.starts_at).total_seconds() / 60)

    def to_display(self) -> dict[str, Any]:
        """
        Convert the solution into a dictionary for UI/serialization.

        Returns:
            Dict: {service_id: {resource_id, start, end}, ...}
        """
        return {
            item.service_id: {
                "resource_id": item.resource_id,
                "start": item.start_time.strftime("%H:%M"),
                "end": item.end_time.strftime("%H:%M"),
            }
            for item in self.items
        }

    def __repr__(self) -> str:
        # GDPR Safe: Only structural info.
        return f"<BookingChainSolution score={self.score:.2f} items={self.items}>"


class EngineResult(BaseDTO):
    """
    Engine work result containing all discovered solutions.

    Fields:
        mode (BookingMode): The search strategy used.
        solutions (list[BookingChainSolution]): Found valid schedule options.

    Example:
        ```python
        result = ChainFinder().find(request, availability)
        if result.has_solutions:
            print(f"Best start: {result.best.starts_at}")
        ```
    """

    mode: BookingMode
    solutions: list[BookingChainSolution] = Field(default_factory=list)

    @property
    def has_solutions(self) -> bool:
        """Return True if at least one solution was found."""
        return len(self.solutions) > 0

    @property
    def best(self) -> BookingChainSolution | None:
        """
        Return the primary solution.
        - Without scorer: earliest by start time.
        - After scoring: the option with the highest score.
        """
        return self.solutions[0] if self.solutions else None

    @property
    def best_scored(self) -> BookingChainSolution | None:
        """
        Return the option with the maximum score among all solutions.
        Differs from 'best' if the solution list hasn't been sorted yet.
        """
        if not self.solutions:
            return None
        return max(self.solutions, key=lambda s: s.score)

    def get_unique_start_times(self) -> list[str]:
        """
        Return unique start times of the first service for UI grid display.

        Returns:
            List[str]: ["09:00", "09:30", ...]
        """
        times = {s.starts_at.strftime("%H:%M") for s in self.solutions}
        return sorted(times)

    def __repr__(self) -> str:
        return f"<EngineResult mode={self.mode} solutions_count={len(self.solutions)}>"


# ---------------------------------------------------------------------------
# Waitlist DTO (результат find_nearest / waitlist-уведомлений)
# ---------------------------------------------------------------------------


class WaitlistEntry(BaseDTO):
    """
    Notification data for a nearest available slot for waitlisted clients.

    Used when a desired slot was unavailable, but an alternative was found
    (e.g., via find_nearest() or a background worker).

    Fields:
        available_date (date): Date of the found alternative slot.
        available_time (str): Start time of the first service ("HH:MM").
        solution (BookingChainSolution): Complete schedule details.
        days_from_request (int): Delta from original request date for ranking.

    Example:
        # Worker detects a cancellation:
        result = finder.find_nearest(request, search_from=original_date)
        if result.has_solutions:
            entry = WaitlistEntry.from_engine_result(result, original_date)
            notify_client(entry)
    """

    available_date: date
    available_time: str  # "HH:MM"
    solution: BookingChainSolution
    days_from_request: int = 0

    @classmethod
    def from_engine_result(
        cls,
        result: "EngineResult",
        original_date: date,
    ) -> "WaitlistEntry | None":
        """
        Factory method to create a WaitlistEntry from an EngineResult.

        Args:
            result: The engine's output.
            original_date: Original requested date for delta calculation.

        Returns:
            WaitlistEntry or None if no solutions exist.
        """
        if not result.has_solutions:
            return None

        solution = result.best
        if solution is None:  # pragma: no cover
            return None  # pragma: no cover

        available_date = solution.starts_at.date()
        available_time = solution.starts_at.strftime("%H:%M")
        days_delta = (available_date - original_date).days

        return cls(
            available_date=available_date,
            available_time=available_time,
            solution=solution,
            days_from_request=max(0, days_delta),
        )

    def __repr__(self) -> str:
        return f"<WaitlistEntry date={self.available_date} time={self.available_time}>"
