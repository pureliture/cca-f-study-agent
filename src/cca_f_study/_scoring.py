"""Pure scoring functions for CCA-F attempts (spec §7).

All functions in this module are IO-free, deterministic, and side-effect
free so they can be unit-tested without fixtures and reused by both
``score_attempt`` (CLI) and ``export_dashboard_data`` (Phase 7).
"""

from __future__ import annotations

from typing import Any


PASS_MARK: int = 720
SCALED_MIN: int = 100
SCALED_RANGE: int = 900  # so the scaled score lives in [100, 1000]


# ---------------------------------------------------------------------------
# Core formula
# ---------------------------------------------------------------------------


def compute_scaled(*, correct: int, total: int) -> int:
    """Return the scaled score for ``correct/total``.

    Formula (spec §7.1):
        scaled_score = round(100 + (correct / total) * 900)

    Edge case (spec §7.2 S5): when ``total == 0`` the scaled score is
    100 (the formula's intercept) and the caller treats it as a failure.
    """
    if total == 0:
        return SCALED_MIN
    accuracy = correct / total
    return round(SCALED_MIN + accuracy * SCALED_RANGE)


def compute_pass_gap(scaled_score: int) -> int:
    """Signed distance from the pass mark (positive = above, negative = below)."""
    return scaled_score - PASS_MARK


def compute_pass_progress(scaled_score: int) -> float:
    """``min(1.0, scaled_score / pass_mark)``."""
    return min(1.0, scaled_score / PASS_MARK)


# ---------------------------------------------------------------------------
# Breakdowns
# ---------------------------------------------------------------------------


def _empty_bucket() -> dict:
    return {"correct": 0, "total": 0}


def _finalize_bucket(bucket: dict) -> dict:
    total = bucket["total"]
    accuracy = (bucket["correct"] / total) if total else None
    if accuracy is not None:
        accuracy = round(accuracy, 3)
    return {"correct": bucket["correct"], "total": total, "accuracy": accuracy}


def compute_breakdowns(answers: list[dict]) -> dict[str, dict[str, dict]]:
    """Return ``{domain, scenario, concept}`` breakdowns as dict-of-buckets.

    Each bucket has ``{correct, total, accuracy}``. ``concept`` double-counts
    a question into every tag in its ``concept_tags`` list (spec §7.3).
    """
    domain: dict[str, dict] = {}
    scenario: dict[str, dict] = {}
    concept: dict[str, dict] = {}

    for ans in answers:
        is_correct = bool(ans.get("is_correct"))

        d = ans.get("domain")
        if isinstance(d, str):
            bucket = domain.setdefault(d, _empty_bucket())
            bucket["total"] += 1
            if is_correct:
                bucket["correct"] += 1

        s = ans.get("scenario")
        if isinstance(s, str):
            bucket = scenario.setdefault(s, _empty_bucket())
            bucket["total"] += 1
            if is_correct:
                bucket["correct"] += 1

        tags = ans.get("concept_tags") or []
        for t in tags:
            if not isinstance(t, str):
                continue
            bucket = concept.setdefault(t, _empty_bucket())
            bucket["total"] += 1
            if is_correct:
                bucket["correct"] += 1

    return {
        "domain": {k: _finalize_bucket(v) for k, v in sorted(domain.items())},
        "scenario": {k: _finalize_bucket(v) for k, v in sorted(scenario.items())},
        "concept": {k: _finalize_bucket(v) for k, v in sorted(concept.items())},
    }


# ---------------------------------------------------------------------------
# Top-level score()
# ---------------------------------------------------------------------------


def score(attempt: dict[str, Any]) -> dict[str, Any]:
    """Compute a Phase 7-shaped scoring summary for one attempt dict.

    The summary key set is the Phase 7 contract (see spec §8.1
    ``latest_attempt`` plus the breakdowns from §7.3). It is the
    machine-readable summary emitted by ``score_attempt --json``.
    """
    answers = list(attempt.get("answers") or [])
    totals = attempt.get("totals") or {}
    total = int(totals.get("total", len(answers)))
    correct = int(totals.get("correct", sum(1 for a in answers if a.get("is_correct"))))

    scaled = compute_scaled(correct=correct, total=total)
    pass_gap = compute_pass_gap(scaled)
    pass_progress = compute_pass_progress(scaled)
    accuracy = (correct / total) if total else 0.0

    breakdowns = compute_breakdowns(answers)

    return {
        "attempt_id": attempt.get("attempt_id"),
        "finished_at": attempt.get("finished_at"),
        "raw_correct": correct,
        "total": total,
        "accuracy": round(accuracy, 3),
        "scaled_score": scaled,
        "pass": scaled >= PASS_MARK,
        "pass_gap": pass_gap,
        "pass_progress": round(pass_progress, 4),
        "domain_breakdown": breakdowns["domain"],
        "scenario_breakdown": breakdowns["scenario"],
        "concept_breakdown": breakdowns["concept"],
    }
