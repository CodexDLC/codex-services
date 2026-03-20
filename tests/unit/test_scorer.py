"""Unit tests for BookingScorer."""

from datetime import datetime, timedelta

import pytest

from codex_services.booking.slot_master.dto import (
    BookingChainSolution,
    EngineResult,
    SingleServiceSolution,
)
from codex_services.booking.slot_master.modes import BookingMode
from codex_services.booking.slot_master.scorer import BookingScorer, ScoringWeights


def dt(h: int, m: int = 0) -> datetime:
    return datetime(2024, 5, 10, h, m)


def make_item(
    service_id: str = "s1",
    resource_id: str = "m1",
    start_h: int = 9,
    dur: int = 60,
) -> SingleServiceSolution:
    start = dt(start_h)
    end = start + timedelta(minutes=dur)
    return SingleServiceSolution(
        service_id=service_id,
        resource_id=resource_id,
        start_time=start,
        end_time=end,
        gap_end_time=end,
    )


def make_chain(*items: SingleServiceSolution, score: float = 0.0) -> BookingChainSolution:
    return BookingChainSolution(items=list(items), score=score)


def make_result(*chains: BookingChainSolution) -> EngineResult:
    return EngineResult(mode=BookingMode.SINGLE_DAY, solutions=list(chains))


def weights_only_preferred(bonus: float = 10.0) -> ScoringWeights:
    return ScoringWeights(
        preferred_resource_bonus=bonus,
        same_resource_bonus=0.0,
        min_idle_bonus_per_hour=0.0,
        early_slot_penalty_per_hour=0.0,
    )


def weights_only_same(bonus: float = 5.0) -> ScoringWeights:
    return ScoringWeights(
        preferred_resource_bonus=0.0,
        same_resource_bonus=bonus,
        min_idle_bonus_per_hour=0.0,
        early_slot_penalty_per_hour=0.0,
    )


def weights_only_penalty(penalty: float = 1.0) -> ScoringWeights:
    return ScoringWeights(
        preferred_resource_bonus=0.0,
        same_resource_bonus=0.0,
        min_idle_bonus_per_hour=0.0,
        early_slot_penalty_per_hour=penalty,
    )


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestBookingScorerEdgeCases:
    def test_empty_result_returned_unchanged(self) -> None:
        scorer = BookingScorer()
        result = make_result()
        scored = scorer.score(result)
        assert not scored.has_solutions

    def test_single_solution_gets_score(self) -> None:
        scorer = BookingScorer(
            weights=weights_only_preferred(10.0),
            preferred_resource_ids=["m1"],
        )
        result = make_result(make_chain(make_item(resource_id="m1")))
        scored = scorer.score(result)
        assert scored.solutions[0].score == pytest.approx(10.0)

    def test_returns_new_result_not_same_object(self) -> None:
        scorer = BookingScorer()
        result = make_result(make_chain(make_item()))
        scored = scorer.score(result)
        assert scored is not result


# ---------------------------------------------------------------------------
# Preferred resource bonus
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestPreferredResourceBonus:
    def test_preferred_resource_gets_higher_score(self) -> None:
        scorer = BookingScorer(weights=weights_only_preferred(10.0), preferred_resource_ids=["m1"])
        chain_preferred = make_chain(make_item(resource_id="m1"))
        chain_other = make_chain(make_item(resource_id="m2"))
        scored = scorer.score(make_result(chain_preferred, chain_other))
        assert scored.solutions[0].score == pytest.approx(10.0)
        assert scored.solutions[1].score == pytest.approx(0.0)

    def test_no_preferred_ids_no_bonus(self) -> None:
        scorer = BookingScorer(weights=weights_only_preferred(10.0), preferred_resource_ids=[])
        scored = scorer.score(make_result(make_chain(make_item(resource_id="m1"))))
        assert scored.solutions[0].score == pytest.approx(0.0)

    def test_bonus_applied_per_matching_service(self) -> None:
        # 2 services, both with preferred resource → 2x bonus
        scorer = BookingScorer(weights=weights_only_preferred(10.0), preferred_resource_ids=["m1"])
        chain = make_chain(make_item("s1", "m1", 9), make_item("s2", "m1", 11))
        scored = scorer.score(make_result(chain))
        assert scored.solutions[0].score == pytest.approx(20.0)

    def test_bonus_applied_only_to_preferred_services(self) -> None:
        # 2 services: m1 (preferred) and m2 (not) → 1x bonus
        scorer = BookingScorer(weights=weights_only_preferred(10.0), preferred_resource_ids=["m1"])
        chain = make_chain(make_item("s1", "m1", 9), make_item("s2", "m2", 11))
        scored = scorer.score(make_result(chain))
        assert scored.solutions[0].score == pytest.approx(10.0)


# ---------------------------------------------------------------------------
# Same resource bonus
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestSameResourceBonus:
    def test_same_resource_for_two_services_gets_bonus(self) -> None:
        scorer = BookingScorer(weights=weights_only_same(5.0))
        chain_same = make_chain(make_item("s1", "m1", 9), make_item("s2", "m1", 11))
        chain_diff = make_chain(make_item("s1", "m1", 9), make_item("s2", "m2", 11))
        scored = scorer.score(make_result(chain_same, chain_diff))
        best = scored.solutions[0]
        worst = scored.solutions[1]
        assert best.score == pytest.approx(5.0)
        assert worst.score == pytest.approx(0.0)

    def test_single_service_no_same_resource_bonus(self) -> None:
        scorer = BookingScorer(weights=weights_only_same(5.0))
        chain = make_chain(make_item("s1", "m1", 9))
        scored = scorer.score(make_result(chain))
        assert scored.solutions[0].score == pytest.approx(0.0)

    def test_three_services_same_resource_cumulative(self) -> None:
        # m1 does 3 services → count=3 → bonus = 5.0 * (3-1) = 10.0
        scorer = BookingScorer(weights=weights_only_same(5.0))
        chain = make_chain(
            make_item("s1", "m1", 9),
            make_item("s2", "m1", 11),
            make_item("s3", "m1", 13),
        )
        scored = scorer.score(make_result(chain))
        assert scored.solutions[0].score == pytest.approx(10.0)


# ---------------------------------------------------------------------------
# Early slot penalty
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestEarlySlotPenalty:
    def test_later_start_gets_lower_score(self) -> None:
        scorer = BookingScorer(weights=weights_only_penalty(1.0))
        chain_9 = make_chain(make_item(start_h=9))
        chain_12 = make_chain(make_item(start_h=12))
        scored = scorer.score(make_result(chain_9, chain_12))
        # Both have negative scores; 9:00 is less penalized → first in sorted order
        assert scored.solutions[0].starts_at.hour == 9
        assert scored.solutions[0].score > scored.solutions[1].score

    def test_penalty_value_matches_hours(self) -> None:
        scorer = BookingScorer(weights=weights_only_penalty(1.0))
        chain = make_chain(make_item(start_h=10))
        scored = scorer.score(make_result(chain))
        assert scored.solutions[0].score == pytest.approx(-10.0)

    def test_zero_penalty_no_effect(self) -> None:
        scorer = BookingScorer(weights=weights_only_penalty(0.0))
        chain = make_chain(make_item(start_h=9))
        scored = scorer.score(make_result(chain))
        assert scored.solutions[0].score == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# Sorting
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestScorerSorting:
    def test_sorted_by_score_descending(self) -> None:
        scorer = BookingScorer(
            weights=weights_only_preferred(10.0),
            preferred_resource_ids=["m1"],
        )
        chain_a = make_chain(make_item(resource_id="m2", start_h=9))  # score 0
        chain_b = make_chain(make_item(resource_id="m1", start_h=10))  # score 10
        chain_c = make_chain(make_item(resource_id="m1", start_h=11))  # score 10
        scored = scorer.score(make_result(chain_a, chain_b, chain_c))
        assert scored.solutions[0].score == pytest.approx(10.0)
        assert scored.solutions[1].score == pytest.approx(10.0)
        assert scored.solutions[2].score == pytest.approx(0.0)

    def test_equal_score_sorted_by_starts_at_asc(self) -> None:
        # Two chains with the same score — earlier start should come first
        scorer = BookingScorer(
            weights=weights_only_preferred(10.0),
            preferred_resource_ids=["m1"],
        )
        chain_11 = make_chain(make_item(resource_id="m1", start_h=11))
        chain_10 = make_chain(make_item(resource_id="m1", start_h=10))
        scored = scorer.score(make_result(chain_11, chain_10))
        assert scored.solutions[0].starts_at.hour == 10
        assert scored.solutions[1].starts_at.hour == 11

    def test_score_rounded_to_4_decimals(self) -> None:
        scorer = BookingScorer(
            weights=ScoringWeights(
                preferred_resource_bonus=0.0,
                same_resource_bonus=0.0,
                min_idle_bonus_per_hour=1.0 / 3,  # irrational
                early_slot_penalty_per_hour=0.0,
            )
        )
        # Two services with idle time between them
        chain = make_chain(make_item("s1", "m1", 9), make_item("s2", "m2", 11))
        scored = scorer.score(make_result(chain))
        score = scored.solutions[0].score
        # Score should be rounded to at most 4 decimal places
        assert score == round(score, 4)
