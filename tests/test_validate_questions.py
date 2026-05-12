"""Tests for the question-bank validator (`cca_f_study.validate_questions`)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from cca_f_study import validate_questions as vq


REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURES = Path(__file__).parent / "fixtures" / "questions"
SEED_BANK = REPO_ROOT / "02-question-bank" / "seed" / "sample-questions.jsonl"
SOURCE_REGISTER = REPO_ROOT / "00-meta" / "source-register.md"


# ---------------------------------------------------------------------------
# Source-register parsing
# ---------------------------------------------------------------------------


def test_source_register_lists_guide_en_as_active():
    ids = vq.load_registered_sources(SOURCE_REGISTER)
    assert "guide_en" in ids


def test_source_register_excludes_reserved_only_ids():
    """`kr_lectures` is reserved (not active) and must not be treated as registered."""
    ids = vq.load_registered_sources(SOURCE_REGISTER)
    assert "kr_lectures" not in ids


# ---------------------------------------------------------------------------
# validate_file — valid fixtures
# ---------------------------------------------------------------------------


def test_valid_minimal_fixture_passes():
    report = vq.validate_file(FIXTURES / "valid_minimal.jsonl", registered_sources={"guide_en"})
    assert report.invalid_count == 0
    assert report.valid_count == 2
    assert report.failures == []


def test_seed_bank_passes_validation():
    """The hand-authored seed bank must validate cleanly."""
    report = vq.validate_file(SEED_BANK, registered_sources=vq.load_registered_sources(SOURCE_REGISTER))
    assert report.invalid_count == 0, report.failures
    assert report.valid_count >= 10


def test_seed_bank_covers_all_domains():
    domains = set()
    with SEED_BANK.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                domains.add(json.loads(line)["domain"])
    assert domains == {"D1", "D2", "D3", "D4", "D5"}


# ---------------------------------------------------------------------------
# validate_file — invalid fixtures
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "fixture_name, expected_reason_substr",
    [
        ("invalid_missing_field.jsonl", "explanation"),
        ("invalid_bad_domain.jsonl", "domain"),
        ("invalid_answer_not_in_choices.jsonl", "answer"),
        ("invalid_unknown_source.jsonl", "source"),
    ],
)
def test_invalid_fixtures_are_rejected(fixture_name, expected_reason_substr):
    report = vq.validate_file(
        FIXTURES / fixture_name,
        registered_sources={"guide_en"},
    )
    assert report.invalid_count == 1
    assert report.valid_count == 0
    assert expected_reason_substr.lower() in report.failures[0].reason.lower()


def test_duplicate_id_is_rejected():
    report = vq.validate_file(
        FIXTURES / "invalid_duplicate_id.jsonl",
        registered_sources={"guide_en"},
    )
    # Both rows individually pass schema; the second is rejected for duplicate id.
    assert report.invalid_count == 1
    assert report.valid_count == 1
    assert "duplicate" in report.failures[0].reason.lower()
    assert report.failures[0].question_id == "T-DUP"


# ---------------------------------------------------------------------------
# CLI invocation
# ---------------------------------------------------------------------------


def test_cli_exits_zero_on_valid_seed_bank():
    proc = subprocess.run(
        [sys.executable, "-m", "cca_f_study.validate_questions", str(SEED_BANK)],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "invalid questions: 0" in proc.stdout
    assert "valid questions:" in proc.stdout


def test_cli_exits_nonzero_on_invalid_fixture():
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "cca_f_study.validate_questions",
            str(FIXTURES / "invalid_bad_domain.jsonl"),
        ],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )
    assert proc.returncode != 0
    assert "invalid questions: 1" in proc.stdout
