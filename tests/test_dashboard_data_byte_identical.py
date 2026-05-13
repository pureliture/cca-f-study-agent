"""Phase 9 regression — dashboard-data byte-identical determinism tests.

Verifies that the canonical export command produces exactly the same bytes
on repeated runs (spec §8.2 C7) and that the committed
``06-dashboard/data/dashboard-data.json`` matches a fresh export.
"""

from __future__ import annotations

import filecmp
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]

# Canonical inputs — read-only; never written by these tests.
ATTEMPTS_DIR = REPO_ROOT / "05-learning-data" / "attempts"
LAB_STATUS = REPO_ROOT / "05-learning-data" / "lab-status.json"
COMMITTED_DASHBOARD = REPO_ROOT / "06-dashboard" / "data" / "dashboard-data.json"

# Pinned timestamp so both exports are byte-identical (spec §8.2 C7 / CC14).
FROZEN_NOW = "2026-05-12T00:30:00Z"


def _export_to(out_path: Path) -> subprocess.CompletedProcess:
    """Run the canonical export command and write the result to ``out_path``."""
    return subprocess.run(
        [
            sys.executable,
            "04-exam-runner/export_dashboard_data.py",
            "--attempts", str(ATTEMPTS_DIR),
            "--lab-status", str(LAB_STATUS),
            "--out", str(out_path),
            "--now", FROZEN_NOW,
        ],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )


def test_canonical_export_is_byte_identical_on_rerun(tmp_path: Path) -> None:
    """Running the export twice with the same --now produces identical bytes."""
    out_a = tmp_path / "dashboard-a.json"
    out_b = tmp_path / "dashboard-b.json"

    proc_a = _export_to(out_a)
    assert proc_a.returncode == 0, (
        f"First export failed.\nstdout: {proc_a.stdout}\nstderr: {proc_a.stderr}"
    )

    proc_b = _export_to(out_b)
    assert proc_b.returncode == 0, (
        f"Second export failed.\nstdout: {proc_b.stdout}\nstderr: {proc_b.stderr}"
    )

    # Sanity: the output must be non-trivially large.
    size = out_a.stat().st_size
    assert size > 500, f"dashboard-data.json is suspiciously small ({size} bytes)"

    assert filecmp.cmp(out_a, out_b, shallow=False), (
        "Two export runs with identical inputs and --now produced different bytes"
    )


def test_committed_dashboard_matches_fresh_export(tmp_path: Path) -> None:
    """The committed dashboard-data.json matches a fresh export with the pinned --now."""
    if not COMMITTED_DASHBOARD.exists():
        pytest.skip("committed 06-dashboard/data/dashboard-data.json not found")

    fresh = tmp_path / "dashboard-fresh.json"
    proc = _export_to(fresh)
    assert proc.returncode == 0, (
        f"Export failed.\nstdout: {proc.stdout}\nstderr: {proc.stderr}"
    )

    assert filecmp.cmp(fresh, COMMITTED_DASHBOARD, shallow=False), (
        "Fresh export does not match the committed dashboard-data.json. "
        "Re-run the canonical export command and commit the result, or "
        "update --now if the inputs have changed."
    )
