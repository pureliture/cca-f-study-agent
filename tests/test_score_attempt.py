"""Tests for `cca_f_study.score_attempt` and `cca_f_study._scoring`.

Covers spec §7 (scoring formula, pass mark 720, breakdowns) and §10.3
(CLI human stdout + machine `--json` output that feeds Phase 7).
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from cca_f_study import _scoring as scoring
from cca_f_study import score_attempt as sa


REPO_ROOT = Path(__file__).resolve().parents[1]
SAMPLE_ATTEMPT = REPO_ROOT / "05-learning-data" / "attempts" / "sample-attempt.json"


# ---------------------------------------------------------------------------
# Helpers — construct in-memory attempts for unit tests
# ---------------------------------------------------------------------------


def _ans(*, domain: str, scenario: str, tags, is_correct: bool) -> dict:
    return {
        "question_id": "Q",
        "domain": domain,
        "scenario": scenario,
        "concept_tags": list(tags),
        "choice": "A" if is_correct else "B",
        "correct": "A",
        "is_correct": is_correct,
    }


def _attempt(answers: list[dict]) -> dict:
    correct = sum(1 for a in answers if a["is_correct"])
    return {
        "attempt_id": "att-test",
        "attempt_label": "test",
        "started_at": "2026-05-12T09:00:00Z",
        "finished_at": "2026-05-12T10:00:00Z",
        "question_bank_path": "test",
        "answers": answers,
        "totals": {"total": len(answers), "correct": correct},
    }


# ---------------------------------------------------------------------------
# Formula — spec §7.1
# ---------------------------------------------------------------------------


def test_pass_mark_is_720():
    assert scoring.PASS_MARK == 720


def test_scaled_score_perfect_score():
    # 10/10 → round(100 + 1.0*900) = 1000
    assert scoring.compute_scaled(correct=10, total=10) == 1000


def test_scaled_score_zero_correct():
    # 0/10 → round(100 + 0*900) = 100
    assert scoring.compute_scaled(correct=0, total=10) == 100


def test_scaled_score_eight_of_ten():
    # 8/10 → 100 + 0.8*900 = 820
    assert scoring.compute_scaled(correct=8, total=10) == 820


def test_scaled_score_exact_threshold():
    # 31/45 → 100 + (31/45)*900 = 100 + 620 = 720 exactly
    assert scoring.compute_scaled(correct=31, total=45) == 720


def test_scaled_score_just_below_threshold():
    # 30/45 → 100 + (30/45)*900 = 700
    assert scoring.compute_scaled(correct=30, total=45) == 700


def test_zero_questions_edge_case():
    # Spec §7.2 S5: total==0 → scaled=100, pass=False, pass_gap=-620
    assert scoring.compute_scaled(correct=0, total=0) == 100


def test_compute_scaled_is_pure():
    """Same inputs → same outputs across many calls (no hidden state)."""
    seen = {scoring.compute_scaled(correct=8, total=10) for _ in range(100)}
    assert seen == {820}


# ---------------------------------------------------------------------------
# Pass/fail/gap derivation
# ---------------------------------------------------------------------------


def test_pass_flag_exactly_at_threshold_is_pass():
    summary = scoring.score(_attempt([_ans(domain="D1", scenario="s1", tags=["t1"], is_correct=True)] * 31
                                     + [_ans(domain="D1", scenario="s1", tags=["t1"], is_correct=False)] * 14))
    assert summary["scaled_score"] == 720
    assert summary["pass"] is True
    assert summary["pass_gap"] == 0


def test_pass_gap_negative_when_failing():
    summary = scoring.score(_attempt([_ans(domain="D1", scenario="s1", tags=["t1"], is_correct=True)] * 30
                                     + [_ans(domain="D1", scenario="s1", tags=["t1"], is_correct=False)] * 15))
    assert summary["scaled_score"] == 700
    assert summary["pass"] is False
    assert summary["pass_gap"] == -20


def test_pass_gap_positive_when_passing_above_threshold():
    summary = scoring.score(_attempt([_ans(domain="D1", scenario="s1", tags=["t1"], is_correct=True)] * 8
                                     + [_ans(domain="D1", scenario="s1", tags=["t1"], is_correct=False)] * 2))
    assert summary["scaled_score"] == 820
    assert summary["pass_gap"] == 100


def test_zero_questions_returns_100_fail_gap_minus_620():
    summary = scoring.score(_attempt([]))
    assert summary["scaled_score"] == 100
    assert summary["pass"] is False
    assert summary["pass_gap"] == -620


def test_pass_progress_capped_at_one():
    perfect = scoring.score(_attempt([_ans(domain="D1", scenario="s1", tags=["t1"], is_correct=True)] * 10))
    assert perfect["pass_progress"] == 1.0


def test_pass_progress_fractional_when_below_pass_mark():
    """pass_progress = min(1.0, scaled / pass_mark)."""
    summary = scoring.score(_attempt([_ans(domain="D1", scenario="s1", tags=["t1"], is_correct=True)] * 5
                                     + [_ans(domain="D1", scenario="s1", tags=["t1"], is_correct=False)] * 5))
    # 5/10 → 100 + 450 = 550 → 550/720 ≈ 0.764
    assert summary["scaled_score"] == 550
    assert 0.76 < summary["pass_progress"] < 0.77


# ---------------------------------------------------------------------------
# Breakdowns — spec §7.3
# ---------------------------------------------------------------------------


def test_domain_breakdown_groups_by_domain():
    summary = scoring.score(_attempt([
        _ans(domain="D1", scenario="s1", tags=["t"], is_correct=True),
        _ans(domain="D1", scenario="s1", tags=["t"], is_correct=False),
        _ans(domain="D2", scenario="s2", tags=["t"], is_correct=True),
    ]))
    db = summary["domain_breakdown"]
    assert db["D1"] == {"correct": 1, "total": 2, "accuracy": 0.5}
    assert db["D2"] == {"correct": 1, "total": 1, "accuracy": 1.0}


def test_scenario_breakdown_groups_by_scenario():
    summary = scoring.score(_attempt([
        _ans(domain="D1", scenario="agentic-orchestration", tags=["t"], is_correct=True),
        _ans(domain="D1", scenario="agentic-orchestration", tags=["t"], is_correct=False),
        _ans(domain="D2", scenario="tool-schema-design", tags=["t"], is_correct=True),
    ]))
    sb = summary["scenario_breakdown"]
    assert sb["agentic-orchestration"]["correct"] == 1
    assert sb["agentic-orchestration"]["total"] == 2
    assert sb["tool-schema-design"]["correct"] == 1


def test_concept_breakdown_multitag_counts_into_every_bucket():
    """A question with two tags counts toward both tags in the breakdown."""
    summary = scoring.score(_attempt([
        _ans(domain="D1", scenario="s1", tags=["mcp", "tool-design"], is_correct=True),
        _ans(domain="D2", scenario="s2", tags=["mcp"], is_correct=False),
    ]))
    cb = summary["concept_breakdown"]
    assert cb["mcp"] == {"correct": 1, "total": 2, "accuracy": 0.5}
    assert cb["tool-design"] == {"correct": 1, "total": 1, "accuracy": 1.0}


def test_breakdowns_have_no_division_by_zero_for_empty_attempt():
    summary = scoring.score(_attempt([]))
    assert summary["domain_breakdown"] == {}
    assert summary["scenario_breakdown"] == {}
    assert summary["concept_breakdown"] == {}


# ---------------------------------------------------------------------------
# Phase 7 contract — machine summary
# ---------------------------------------------------------------------------


REQUIRED_TOP_LEVEL_KEYS = {
    "attempt_id",
    "finished_at",
    "raw_correct",
    "total",
    "accuracy",
    "scaled_score",
    "pass",
    "pass_gap",
    "pass_progress",
    "domain_breakdown",
    "scenario_breakdown",
    "concept_breakdown",
}


def test_score_emits_phase7_contract_keys():
    summary = scoring.score(_attempt([_ans(domain="D1", scenario="s1", tags=["t"], is_correct=True)]))
    assert REQUIRED_TOP_LEVEL_KEYS <= set(summary.keys())


# ---------------------------------------------------------------------------
# CLI surfaces — spec §10.3
# ---------------------------------------------------------------------------


def _run_cli(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "cca_f_study.score_attempt", *args],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )


def test_cli_human_stdout_on_sample_attempt():
    """Spec §10.3: produces the human summary on the seed sample attempt."""
    assert SAMPLE_ATTEMPT.exists(), "Phase 5 sample attempt must exist"
    proc = _run_cli([str(SAMPLE_ATTEMPT)])
    assert proc.returncode == 0, proc.stdout + proc.stderr
    out = proc.stdout
    assert "Raw score: 8 / 10" in out
    assert "Scaled score: 820 / 1000" in out
    assert "Pass mark: 720" in out
    assert "Result: PASS" in out
    assert "Gap: +100" in out
    assert "Domain breakdown:" in out


def test_cli_json_flag_emits_machine_summary(tmp_path):
    proc = _run_cli([str(SAMPLE_ATTEMPT), "--json"])
    assert proc.returncode == 0, proc.stdout + proc.stderr
    data = json.loads(proc.stdout)
    assert REQUIRED_TOP_LEVEL_KEYS <= set(data.keys())
    assert data["scaled_score"] == 820
    assert data["pass"] is True
    assert data["pass_gap"] == 100


def test_cli_via_04_exam_runner_wrapper():
    proc = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "04-exam-runner" / "score_attempt.py"),
            str(SAMPLE_ATTEMPT),
        ],
        capture_output=True, text=True, cwd=REPO_ROOT,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "Result: PASS" in proc.stdout


def test_cli_fails_cleanly_on_missing_attempt(tmp_path):
    missing = tmp_path / "does-not-exist.json"
    proc = _run_cli([str(missing)])
    assert proc.returncode != 0
    # error to stderr; stdout should not be a python traceback
    assert "Traceback" not in proc.stderr


def test_cli_module_function_invocation():
    """Programmatic import works (no implicit __main__ side effects)."""
    summary = sa.score_attempt_file(SAMPLE_ATTEMPT)
    assert summary["scaled_score"] == 820
    assert summary["pass"] is True
