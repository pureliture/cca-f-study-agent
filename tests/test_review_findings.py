"""Regression tests for the 2026-05 code-review findings.

Each test maps to one finding in the review feedback:
- Finding 1: schema discovery survives an install outside the checkout.
- Finding 2: questions under 02-question-bank/generated/ cannot be `official`.
- Finding 3: scenario IDs must appear in scenario-map.md.
- Finding 5: non-object JSONL rows are reported, not crashed.
- Plus: schemas in 04-exam-runner/ stay byte-identical to the packaged copies.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

from cca_f_study import validate_questions as vq


REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURES = Path(__file__).parent / "fixtures" / "questions"
SOURCE_REGISTER = REPO_ROOT / "00-meta" / "source-register.md"
SCENARIO_MAP = REPO_ROOT / "00-meta" / "scenario-map.md"


# ---------------------------------------------------------------------------
# Finding 1 — schemas packaged as resources
# ---------------------------------------------------------------------------


def test_default_schema_loads_via_importlib_resources():
    """validate_file() with no schema_path must load the packaged schema."""
    report = vq.validate_file(
        FIXTURES / "valid_minimal.jsonl",
        registered_sources={"guide_en"},
        allowed_scenarios={"agentic-orchestration", "tool-schema-design"},
    )
    assert report.invalid_count == 0
    assert report.valid_count == 2


def test_cli_works_from_unrelated_cwd(tmp_path):
    """Run the CLI from a tmp dir; schemas must still be discoverable.

    This reproduces the wheel-install scenario noted in finding #1: when
    `__file__/../../04-exam-runner/question_schema.json` does not exist,
    the validator must still find its schema via importlib.resources.
    """
    # Stage the same fixture and the project's metadata into a clean dir
    # so the validator can also resolve sources/scenarios from there.
    fixture_dst = tmp_path / "questions.jsonl"
    fixture_dst.write_text(
        (FIXTURES / "valid_minimal.jsonl").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    (tmp_path / "00-meta").mkdir()
    shutil.copy(SOURCE_REGISTER, tmp_path / "00-meta" / "source-register.md")
    shutil.copy(SCENARIO_MAP, tmp_path / "00-meta" / "scenario-map.md")

    proc = subprocess.run(
        [sys.executable, "-m", "cca_f_study.validate_questions", str(fixture_dst)],
        capture_output=True,
        text=True,
        cwd=tmp_path,  # NOT the repo root — proves CWD-independence
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "invalid questions: 0" in proc.stdout


def test_packaged_schemas_match_canonical_files():
    """The package copy must stay byte-identical to 04-exam-runner/."""
    from importlib.resources import files

    canonical_q = (REPO_ROOT / "04-exam-runner" / "question_schema.json").read_bytes()
    canonical_a = (REPO_ROOT / "04-exam-runner" / "attempt_schema.json").read_bytes()
    pkg_q = (files("cca_f_study._schemas") / "question_schema.json").read_bytes()
    pkg_a = (files("cca_f_study._schemas") / "attempt_schema.json").read_bytes()
    assert pkg_q == canonical_q
    assert pkg_a == canonical_a


# ---------------------------------------------------------------------------
# Finding 2 — generated bank cannot carry status=official
# ---------------------------------------------------------------------------


def test_generated_bank_rejects_official_status(tmp_path):
    """A JSONL under 02-question-bank/generated/ with status=official fails."""
    gen_dir = tmp_path / "02-question-bank" / "generated"
    gen_dir.mkdir(parents=True)
    target = gen_dir / "questions.jsonl"
    target.write_text(
        (FIXTURES / "generated_official.jsonl").read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    report = vq.validate_file(
        target,
        registered_sources={"guide_en"},
        allowed_scenarios={"agentic-orchestration", "tool-schema-design"},
    )

    # G-001 is `official` and under generated/ -> reject
    # G-002 is `unofficial` -> accept
    assert report.invalid_count == 1
    assert report.valid_count == 1
    failure = report.failures[0]
    assert failure.question_id == "G-001"
    assert "generated" in failure.reason.lower()
    assert "official" in failure.reason.lower()


def test_seed_bank_official_is_still_allowed():
    """Seed bank is under 02-question-bank/seed/, not generated/."""
    report = vq.validate_file(
        REPO_ROOT / "02-question-bank" / "seed" / "sample-questions.jsonl",
        registered_sources=vq.load_registered_sources(SOURCE_REGISTER),
        allowed_scenarios=vq.load_allowed_scenarios(SCENARIO_MAP),
    )
    assert report.invalid_count == 0
    assert report.valid_count >= 10


# ---------------------------------------------------------------------------
# Finding 3 — scenario IDs must exist in scenario-map.md
# ---------------------------------------------------------------------------


def test_load_allowed_scenarios_from_map():
    scenarios = vq.load_allowed_scenarios(SCENARIO_MAP)
    assert "agentic-orchestration" in scenarios
    assert "tool-schema-design" in scenarios
    # A plausible typo must NOT appear.
    assert "agent-orchestration" not in scenarios


def test_unknown_scenario_is_rejected():
    report = vq.validate_file(
        FIXTURES / "invalid_unknown_scenario.jsonl",
        registered_sources={"guide_en"},
        allowed_scenarios=vq.load_allowed_scenarios(SCENARIO_MAP),
    )
    assert report.invalid_count == 1
    assert report.valid_count == 0
    assert "scenario" in report.failures[0].reason.lower()
    assert "agent-orchestration" in report.failures[0].reason


# ---------------------------------------------------------------------------
# Finding 5 — non-object JSONL rows are reported cleanly
# ---------------------------------------------------------------------------


def test_non_object_rows_are_reported_not_crashed():
    """`[]`, `"text"`, `42` lines must be invalid rows, not exceptions."""
    report = vq.validate_file(
        FIXTURES / "invalid_non_object_rows.jsonl",
        registered_sources={"guide_en"},
        allowed_scenarios={"agentic-orchestration"},
    )
    # 1 valid (first line) + 3 invalid (array, string, integer)
    assert report.valid_count == 1
    assert report.invalid_count == 3
    for f in report.failures:
        assert "object" in f.reason.lower() or "not an object" in f.reason.lower()
