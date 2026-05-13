"""R1 lockdown: every runtime CLI succeeds with the canonical PDF absent.

Temporarily renames ``01-sources/en/guide_en.pdf`` to a sibling
``.r1-hidden`` name, runs all four spec §10 CLI commands, and verifies
each exits 0.  Restores the PDF in finally so the working tree is
unchanged at the end (also when an assertion fails mid-test).
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
PDF = REPO_ROOT / "01-sources" / "en" / "guide_en.pdf"
HIDDEN = PDF.with_suffix(".pdf.r1-hidden")
SEED_BANK = REPO_ROOT / "02-question-bank" / "seed" / "sample-questions.jsonl"
SAMPLE_ANSWERS = REPO_ROOT / "examples" / "attempts" / "sample-answers.json"
LAB_STATUS = REPO_ROOT / "05-learning-data" / "lab-status.json"
FROZEN_NOW = "2026-05-12T00:30:00Z"


def _run(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, *args],
        capture_output=True, text=True, cwd=REPO_ROOT,
    )


def test_all_cli_commands_work_with_pdf_absent(tmp_path):
    if not PDF.exists():
        pytest.skip("canonical PDF not present in this checkout")
    # Move the PDF out of place for the duration of the test.
    PDF.rename(HIDDEN)
    try:
        assert not PDF.exists(), "PDF must be absent during the body"

        # §10.1 validate
        proc = _run(["-m", "cca_f_study.validate_questions", str(SEED_BANK)])
        assert proc.returncode == 0, proc.stdout + proc.stderr

        # §10.2 submit
        attempt_out = tmp_path / "att.json"
        proc = _run([
            str(REPO_ROOT / "04-exam-runner" / "submit_attempt.py"),
            "--questions", str(SEED_BANK),
            "--answers",   str(SAMPLE_ANSWERS),
            "--out",       str(attempt_out),
        ])
        assert proc.returncode == 0, proc.stdout + proc.stderr

        # §10.3 score
        proc = _run([
            str(REPO_ROOT / "04-exam-runner" / "score_attempt.py"),
            str(attempt_out),
        ])
        assert proc.returncode == 0, proc.stdout + proc.stderr

        # §10.4 export
        attempts_dir = tmp_path / "attempts"
        attempts_dir.mkdir()
        # Copy the attempt into a fresh attempts dir so we are not
        # mutating 05-learning-data/attempts.
        (attempts_dir / "att.json").write_bytes(attempt_out.read_bytes())
        dash_out = tmp_path / "dashboard-data.json"
        proc = _run([
            str(REPO_ROOT / "04-exam-runner" / "export_dashboard_data.py"),
            "--attempts",   str(attempts_dir),
            "--lab-status", str(LAB_STATUS),
            "--out",        str(dash_out),
            "--now",        FROZEN_NOW,
        ])
        assert proc.returncode == 0, proc.stdout + proc.stderr
        # And the exported file is non-trivial
        data = json.loads(dash_out.read_text(encoding="utf-8"))
        assert data["pass_mark"] == 720
    finally:
        if HIDDEN.exists():
            HIDDEN.rename(PDF)
        assert PDF.exists(), "PDF restore failed — manual recovery required"
