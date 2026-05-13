"""Phase 9 regression — full pipeline end-to-end test (spec §10.1–§10.4).

Drives all four CLI surfaces in sequence via subprocess and validates each
stage's output without mutating any production file.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]

SEED_BANK = REPO_ROOT / "02-question-bank" / "seed" / "sample-questions.jsonl"
SAMPLE_ANSWERS = REPO_ROOT / "examples" / "attempts" / "sample-answers.json"
LAB_STATUS = REPO_ROOT / "05-learning-data" / "lab-status.json"

# Canonical --now pinned so the export stage is deterministic.
FROZEN_NOW = "2026-05-12T00:30:00Z"


def _run(*args: str | Path) -> subprocess.CompletedProcess:
    """Run a command with the project repo as cwd; always capture output."""
    return subprocess.run(
        [sys.executable, *[str(a) for a in args]],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )


def test_full_pipeline_validate_submit_score_export(tmp_path: Path) -> None:
    """Drive all four CLI surfaces in order and assert each stage's output."""

    attempt_out = tmp_path / "attempt.json"
    attempts_dir = tmp_path / "attempts"
    attempts_dir.mkdir(parents=True, exist_ok=True)
    dashboard_out = tmp_path / "dashboard-data.json"

    # -----------------------------------------------------------------------
    # Stage 1 — validate questions (spec §10.1)
    # -----------------------------------------------------------------------
    proc1 = _run(
        "-m", "cca_f_study.validate_questions",
        SEED_BANK,
    )
    assert proc1.returncode == 0, (
        f"validate_questions failed.\nstdout: {proc1.stdout}\nstderr: {proc1.stderr}"
    )
    assert "invalid questions: 0" in proc1.stdout, (
        f"Expected 'invalid questions: 0' in stdout.\nstdout: {proc1.stdout}"
    )

    # -----------------------------------------------------------------------
    # Stage 2 — submit attempt (spec §10.2)
    # -----------------------------------------------------------------------
    proc2 = _run(
        "04-exam-runner/submit_attempt.py",
        "--questions", SEED_BANK,
        "--answers", SAMPLE_ANSWERS,
        "--out", attempt_out,
    )
    assert proc2.returncode == 0, (
        f"submit_attempt failed.\nstdout: {proc2.stdout}\nstderr: {proc2.stderr}"
    )
    assert attempt_out.exists(), "submit_attempt did not create the attempt JSON file"

    attempt_data = json.loads(attempt_out.read_text(encoding="utf-8"))
    assert attempt_data["totals"] == {"total": 10, "correct": 8}, (
        f"Unexpected totals: {attempt_data['totals']}"
    )
    attempt_id = attempt_data["attempt_id"]
    assert attempt_id, "attempt_id must be a non-empty string"

    # Copy the attempt into the per-test attempts dir so the export stage can
    # pick it up without touching the production 05-learning-data/attempts/.
    (attempts_dir / f"{attempt_id}.json").write_bytes(attempt_out.read_bytes())

    # -----------------------------------------------------------------------
    # Stage 3 — score attempt, human-readable (spec §10.3)
    # -----------------------------------------------------------------------
    proc3 = _run(
        "04-exam-runner/score_attempt.py",
        attempt_out,
    )
    assert proc3.returncode == 0, (
        f"score_attempt (human) failed.\nstdout: {proc3.stdout}\nstderr: {proc3.stderr}"
    )
    stdout3 = proc3.stdout
    assert "Raw score: 8 / 10" in stdout3, f"Missing 'Raw score' in:\n{stdout3}"
    assert "Scaled score: 820 / 1000" in stdout3, f"Missing 'Scaled score' in:\n{stdout3}"
    assert "Result: PASS" in stdout3, f"Missing 'Result: PASS' in:\n{stdout3}"
    assert "Gap: +100" in stdout3, f"Missing 'Gap: +100' in:\n{stdout3}"

    # -----------------------------------------------------------------------
    # Stage 3b — score attempt, --json machine output (spec §10.3)
    # -----------------------------------------------------------------------
    proc3b = _run(
        "04-exam-runner/score_attempt.py",
        attempt_out,
        "--json",
    )
    assert proc3b.returncode == 0, (
        f"score_attempt (--json) failed.\nstdout: {proc3b.stdout}\nstderr: {proc3b.stderr}"
    )
    score_json = json.loads(proc3b.stdout)
    assert score_json["scaled_score"] == 820, (
        f"Expected scaled_score=820, got {score_json.get('scaled_score')}"
    )
    assert score_json["pass"] is True, (
        f"Expected pass=True, got {score_json.get('pass')}"
    )

    # -----------------------------------------------------------------------
    # Stage 4 — export dashboard data (spec §10.4)
    # -----------------------------------------------------------------------
    proc4 = _run(
        "04-exam-runner/export_dashboard_data.py",
        "--attempts", attempts_dir,
        "--lab-status", LAB_STATUS,
        "--out", dashboard_out,
        "--now", FROZEN_NOW,
    )
    assert proc4.returncode == 0, (
        f"export_dashboard_data failed.\nstdout: {proc4.stdout}\nstderr: {proc4.stderr}"
    )
    assert dashboard_out.exists(), "export_dashboard_data did not create the output file"

    dashboard_data = json.loads(dashboard_out.read_text(encoding="utf-8"))

    # All 8 required top-level keys must be present.
    required_keys = {
        "generated_at",
        "pass_mark",
        "latest_attempt",
        "domain_breakdown",
        "scenario_breakdown",
        "weak_concepts",
        "lab_progress",
        "trend",
    }
    missing = required_keys - set(dashboard_data.keys())
    assert not missing, f"Missing top-level keys in dashboard: {missing}"

    # latest_attempt must reflect the Stage-2 submission.
    latest = dashboard_data["latest_attempt"]
    assert latest is not None, "latest_attempt should not be None"
    assert latest["scaled_score"] == 820, (
        f"Expected latest_attempt.scaled_score=820, got {latest.get('scaled_score')}"
    )
    assert latest["attempt_id"] == attempt_id, (
        f"latest_attempt.attempt_id mismatch: "
        f"expected {attempt_id!r}, got {latest.get('attempt_id')!r}"
    )
