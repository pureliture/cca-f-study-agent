"""Phase 7 review-driven regression tests.

Each test pins one of the Fix #N items from the Phase 7 review:

  Fix 1 -> test_latest_attempt_ties_broken_by_attempt_id
  Fix 2 -> test_lab_recommendations_stable_across_file_reordering
  Fix 3 -> test_dashboard_data_atomic_write_leaves_no_tmp_sibling
           test_dashboard_data_atomic_write_no_partial_on_error
  Fix 5 -> test_load_lab_status_raises_export_error_on_malformed_json
  Fix 6 -> test_now_validation_rejects_non_iso
           test_now_validation_accepts_pinned_canonical_value
  Fix 7/8 -> test_iter_attempts_skips_subdirectory_and_non_json_files
  Fix 4 -> test_canonical_command_with_pinned_now_is_byte_identical_on_rerun
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from cca_f_study import _aggregate as agg
from cca_f_study import export_dashboard_data as ed


REPO_ROOT = Path(__file__).resolve().parents[1]
META_DOMAIN_MAP = REPO_ROOT / "00-meta" / "domain-map.md"
PINNED_NOW = "2026-05-12T00:30:00Z"


# ---------------------------------------------------------------------------
# Local fixture helpers (intentionally duplicated from
# test_export_dashboard_data.py so this file stays self-contained).
# ---------------------------------------------------------------------------


def _ans(*, qid, domain, scenario, tags, is_correct):
    return {
        "question_id": qid,
        "domain": domain,
        "scenario": scenario,
        "concept_tags": list(tags),
        "choice": "A" if is_correct else "B",
        "correct": "A",
        "is_correct": is_correct,
    }


def _attempt(*, attempt_id, finished_at, answers):
    return {
        "attempt_id": attempt_id,
        "attempt_label": attempt_id,
        "started_at": finished_at,
        "finished_at": finished_at,
        "question_bank_path": "test",
        "answers": answers,
        "totals": {
            "total": len(answers),
            "correct": sum(1 for a in answers if a["is_correct"]),
        },
    }


def _write_attempts(dir_path: Path, attempts: list[dict]) -> Path:
    dir_path.mkdir(parents=True, exist_ok=True)
    for a in attempts:
        (dir_path / f"{a['attempt_id']}.json").write_text(
            json.dumps(a, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    return dir_path


def _write_lab_status(path: Path, labs: list[dict]) -> Path:
    path.write_text(
        json.dumps({"labs": labs}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path


def _minimal_labs() -> list[dict]:
    return [
        {
            "lab_id": "lab-a",
            "domain": "D1",
            "concept_tags": ["agent-loop"],
            "status": "not_started",
            "last_run": None,
        },
        {
            "lab_id": "lab-b",
            "domain": "D2",
            "concept_tags": ["mcp"],
            "status": "in_progress",
            "last_run": None,
        },
    ]


# ---------------------------------------------------------------------------
# Fix 1 — deterministic tie-break on (finished_at, attempt_id)
# ---------------------------------------------------------------------------


def test_latest_attempt_ties_broken_by_attempt_id(tmp_path):
    """Two attempts sharing finished_at must resolve to the
    lexicographically greater attempt_id, regardless of filesystem order.
    """
    tied = "2026-05-11T10:00:00Z"
    a_lo = _attempt(
        attempt_id="att-aaa",
        finished_at=tied,
        answers=[
            _ans(
                qid="Q1",
                domain="D1",
                scenario="agentic-orchestration",
                tags=["agent-loop"],
                is_correct=False,
            )
        ],
    )
    a_hi = _attempt(
        attempt_id="att-zzz",
        finished_at=tied,
        answers=[
            _ans(
                qid="Q1",
                domain="D1",
                scenario="agentic-orchestration",
                tags=["agent-loop"],
                is_correct=True,
            )
        ],
    )

    attempts_dir = _write_attempts(tmp_path / "attempts", [a_lo, a_hi])
    labs = _write_lab_status(tmp_path / "lab-status.json", _minimal_labs())
    out = tmp_path / "dashboard-data.json"
    ed.export(
        attempts_dir=attempts_dir,
        lab_status_path=labs,
        out_path=out,
        now_iso=PINNED_NOW,
        domain_map_path=META_DOMAIN_MAP,
    )
    data = json.loads(out.read_text(encoding="utf-8"))
    # Fix rule: ties on finished_at are broken by the lexicographically
    # GREATER attempt_id (because max() is used and attempt_id is the
    # secondary sort key in ascending order).
    assert data["latest_attempt"]["attempt_id"] == "att-zzz"

    # Also verify the in-memory primitive directly so we are not
    # accidentally relying on JSON serialization order.
    direct = agg.latest_attempt_block([a_lo, a_hi])
    direct_rev = agg.latest_attempt_block([a_hi, a_lo])
    assert direct["attempt_id"] == "att-zzz"
    assert direct_rev["attempt_id"] == "att-zzz"


# ---------------------------------------------------------------------------
# Fix 3 — atomic write, no leftover *.tmp
# ---------------------------------------------------------------------------


def test_dashboard_data_atomic_write_leaves_no_tmp_sibling(tmp_path):
    attempts_dir = _write_attempts(
        tmp_path / "attempts",
        [
            _attempt(
                attempt_id="att-001",
                finished_at="2026-05-11T10:00:00Z",
                answers=[
                    _ans(
                        qid="Q1",
                        domain="D1",
                        scenario="agentic-orchestration",
                        tags=["agent-loop"],
                        is_correct=True,
                    )
                ],
            )
        ],
    )
    labs = _write_lab_status(tmp_path / "lab-status.json", _minimal_labs())
    out_dir = tmp_path / "out"
    out = out_dir / "dashboard-data.json"
    ed.export(
        attempts_dir=attempts_dir,
        lab_status_path=labs,
        out_path=out,
        now_iso=PINNED_NOW,
        domain_map_path=META_DOMAIN_MAP,
    )
    leftovers = list(out_dir.glob("*.tmp")) + list(out_dir.glob("*.tmp.*"))
    assert leftovers == [], f"unexpected temp files: {leftovers}"
    assert out.exists()


def test_dashboard_data_atomic_write_no_partial_on_error(tmp_path):
    """Induce a write failure (the would-be parent is a regular file) and
    assert the original output is untouched and no .tmp sibling remains.
    """
    attempts_dir = _write_attempts(
        tmp_path / "attempts",
        [
            _attempt(
                attempt_id="att-001",
                finished_at="2026-05-11T10:00:00Z",
                answers=[
                    _ans(
                        qid="Q1",
                        domain="D1",
                        scenario="agentic-orchestration",
                        tags=["agent-loop"],
                        is_correct=True,
                    )
                ],
            )
        ],
    )
    labs = _write_lab_status(tmp_path / "lab-status.json", _minimal_labs())

    # ``out_parent`` is a regular file; mkdir(parents=True, exist_ok=True)
    # will raise FileExistsError when asked to create children below it.
    out_parent = tmp_path / "not-a-dir"
    out_parent.write_text("blocker", encoding="utf-8")
    blocked_out = out_parent / "child" / "dashboard-data.json"

    with pytest.raises(Exception):
        ed.export(
            attempts_dir=attempts_dir,
            lab_status_path=labs,
            out_path=blocked_out,
            now_iso=PINNED_NOW,
            domain_map_path=META_DOMAIN_MAP,
        )

    # The blocker file is untouched and no *.tmp sibling lingers in tmp_path.
    assert out_parent.read_text(encoding="utf-8") == "blocker"
    leftovers = list(tmp_path.rglob("*.tmp")) + list(tmp_path.rglob("*.tmp.*"))
    assert leftovers == [], f"unexpected temp files: {leftovers}"


# ---------------------------------------------------------------------------
# Fix 5 — malformed lab-status.json raises ExportError, not JSONDecodeError
# ---------------------------------------------------------------------------


def test_load_lab_status_raises_export_error_on_malformed_json(tmp_path):
    attempts_dir = _write_attempts(
        tmp_path / "attempts",
        [
            _attempt(
                attempt_id="att-001",
                finished_at="2026-05-11T10:00:00Z",
                answers=[
                    _ans(
                        qid="Q1",
                        domain="D1",
                        scenario="agentic-orchestration",
                        tags=["agent-loop"],
                        is_correct=True,
                    )
                ],
            )
        ],
    )
    bad_labs = tmp_path / "lab-status.json"
    bad_labs.write_text("{ not json }", encoding="utf-8")
    out = tmp_path / "dashboard-data.json"
    with pytest.raises(ed.ExportError) as excinfo:
        ed.export(
            attempts_dir=attempts_dir,
            lab_status_path=bad_labs,
            out_path=out,
            now_iso=PINNED_NOW,
            domain_map_path=META_DOMAIN_MAP,
        )
    msg = str(excinfo.value)
    assert "JSON parse error" in msg
    assert str(bad_labs) in msg


# ---------------------------------------------------------------------------
# Fix 6 — --now validation
# ---------------------------------------------------------------------------


def test_now_validation_rejects_non_iso(tmp_path):
    attempts_dir = _write_attempts(
        tmp_path / "attempts",
        [
            _attempt(
                attempt_id="att-001",
                finished_at="2026-05-11T10:00:00Z",
                answers=[
                    _ans(
                        qid="Q1",
                        domain="D1",
                        scenario="agentic-orchestration",
                        tags=["agent-loop"],
                        is_correct=True,
                    )
                ],
            )
        ],
    )
    labs = _write_lab_status(tmp_path / "lab-status.json", _minimal_labs())
    out = tmp_path / "dashboard-data.json"
    with pytest.raises(ed.ExportError) as excinfo:
        ed.export(
            attempts_dir=attempts_dir,
            lab_status_path=labs,
            out_path=out,
            now_iso="garbage",
            domain_map_path=META_DOMAIN_MAP,
        )
    assert "ISO" in str(excinfo.value)


def test_now_validation_accepts_pinned_canonical_value(tmp_path):
    attempts_dir = _write_attempts(
        tmp_path / "attempts",
        [
            _attempt(
                attempt_id="att-001",
                finished_at="2026-05-11T10:00:00Z",
                answers=[
                    _ans(
                        qid="Q1",
                        domain="D1",
                        scenario="agentic-orchestration",
                        tags=["agent-loop"],
                        is_correct=True,
                    )
                ],
            )
        ],
    )
    labs = _write_lab_status(tmp_path / "lab-status.json", _minimal_labs())
    out = tmp_path / "dashboard-data.json"
    ed.export(
        attempts_dir=attempts_dir,
        lab_status_path=labs,
        out_path=out,
        now_iso=PINNED_NOW,
        domain_map_path=META_DOMAIN_MAP,
    )
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["generated_at"] == PINNED_NOW


# ---------------------------------------------------------------------------
# Fix 7 / Fix 8 — iter_attempts ignores subdirectories and non-JSON files
# ---------------------------------------------------------------------------


def test_iter_attempts_skips_subdirectory_and_non_json_files(tmp_path):
    attempts_dir = tmp_path / "attempts"
    real = _attempt(
        attempt_id="att-real",
        finished_at="2026-05-11T10:00:00Z",
        answers=[
            _ans(
                qid="Q1",
                domain="D1",
                scenario="agentic-orchestration",
                tags=["agent-loop"],
                is_correct=True,
            )
        ],
    )
    _write_attempts(attempts_dir, [real])
    # Confound 1: a sub-directory that happens to contain JSON files.
    (attempts_dir / "subdir").mkdir()
    (attempts_dir / "subdir" / "inner.json").write_text("{}", encoding="utf-8")
    # Confound 2: a non-JSON file alongside the real attempt.
    (attempts_dir / "notes.txt").write_text("hello", encoding="utf-8")

    labs = _write_lab_status(tmp_path / "lab-status.json", _minimal_labs())
    out = tmp_path / "dashboard-data.json"
    ed.export(
        attempts_dir=attempts_dir,
        lab_status_path=labs,
        out_path=out,
        now_iso=PINNED_NOW,
        domain_map_path=META_DOMAIN_MAP,
    )
    data = json.loads(out.read_text(encoding="utf-8"))
    assert [t["attempt_id"] for t in data["trend"]] == ["att-real"]


# ---------------------------------------------------------------------------
# Fix 2 — stable lab recommendations across file reordering
# ---------------------------------------------------------------------------


def test_lab_recommendations_stable_across_file_reordering(tmp_path):
    # Two attempts that make `mcp` and `agent-loop` weak concepts (each missed).
    attempts = [
        _attempt(
            attempt_id="att-001",
            finished_at="2026-05-10T10:00:00Z",
            answers=[
                _ans(
                    qid="Q1",
                    domain="D1",
                    scenario="agentic-orchestration",
                    tags=["agent-loop"],
                    is_correct=False,
                ),
                _ans(
                    qid="Q2",
                    domain="D2",
                    scenario="tool-schema-design",
                    tags=["mcp"],
                    is_correct=False,
                ),
            ],
        ),
    ]
    # Two labs both eligible AND both matching different weak concepts.
    labs_a = [
        {
            "lab_id": "lab-alpha-agent",
            "domain": "D1",
            "concept_tags": ["agent-loop"],
            "status": "not_started",
            "last_run": None,
        },
        {
            "lab_id": "lab-beta-mcp",
            "domain": "D2",
            "concept_tags": ["mcp"],
            "status": "not_started",
            "last_run": None,
        },
    ]
    labs_b = list(reversed(labs_a))  # same semantics, reversed declaration

    def _run_with(labs):
        a_dir = _write_attempts(tmp_path / "a-attempts", attempts)
        l_path = _write_lab_status(tmp_path / "lab.json", labs)
        out = tmp_path / "out.json"
        ed.export(
            attempts_dir=a_dir,
            lab_status_path=l_path,
            out_path=out,
            now_iso=PINNED_NOW,
            domain_map_path=META_DOMAIN_MAP,
        )
        return json.loads(out.read_text(encoding="utf-8"))[
            "lab_progress"
        ]["recommended_next"]

    recs_a = _run_with(labs_a)
    recs_b = _run_with(labs_b)
    assert recs_a == recs_b
    # Sanity: both recommendations actually present.
    rec_ids = {r["lab_id"] for r in recs_a}
    assert rec_ids == {"lab-alpha-agent", "lab-beta-mcp"}


# ---------------------------------------------------------------------------
# Fix 4 — canonical command is byte-identical on rerun (CC14)
# ---------------------------------------------------------------------------


def test_canonical_command_with_pinned_now_is_byte_identical_on_rerun(tmp_path):
    """Run the canonical CLI command twice with the same --now and assert
    byte-identical output. This locks CC14 on the canonical surface that
    is documented in the Phase 7 runbook."""
    out_a = tmp_path / "a.json"
    out_b = tmp_path / "b.json"

    cmd_template = [
        sys.executable,
        str(REPO_ROOT / "04-exam-runner" / "export_dashboard_data.py"),
        "--attempts",
        str(REPO_ROOT / "05-learning-data" / "attempts"),
        "--lab-status",
        str(REPO_ROOT / "05-learning-data" / "lab-status.json"),
        "--now",
        PINNED_NOW,
    ]
    proc_a = subprocess.run(
        cmd_template + ["--out", str(out_a)],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )
    proc_b = subprocess.run(
        cmd_template + ["--out", str(out_b)],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )
    assert proc_a.returncode == 0, proc_a.stdout + proc_a.stderr
    assert proc_b.returncode == 0, proc_b.stdout + proc_b.stderr
    assert out_a.read_bytes() == out_b.read_bytes()
