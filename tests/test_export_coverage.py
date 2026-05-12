"""Phase 7 coverage-gap tests for dashboard-data export.

These tests close gaps flagged in a code review: behaviors that are
implemented in `cca_f_study._aggregate` / `cca_f_study.export_dashboard_data`
but were not exercised by `tests/test_export_dashboard_data.py`.
"""

from __future__ import annotations

import json
import socket
import subprocess
import sys
import urllib.request
from datetime import datetime
from pathlib import Path

import pytest

from cca_f_study import _aggregate as agg
from cca_f_study import export_dashboard_data as ed


REPO_ROOT = Path(__file__).resolve().parents[1]
META_DOMAIN_MAP = REPO_ROOT / "00-meta" / "domain-map.md"
FROZEN_NOW = "2026-05-12T00:30:00Z"


def _ans(*, qid, domain, scenario, tags, is_correct):
    return {
        "question_id": qid, "domain": domain, "scenario": scenario,
        "concept_tags": list(tags),
        "choice": "A" if is_correct else "B",
        "correct": "A", "is_correct": is_correct,
    }


def _attempt(*, attempt_id, finished_at, answers):
    return {
        "attempt_id": attempt_id, "attempt_label": attempt_id,
        "started_at": finished_at, "finished_at": finished_at,
        "question_bank_path": "test", "answers": answers,
        "totals": {"total": len(answers), "correct": sum(1 for a in answers if a["is_correct"])},
    }


def _write_attempts(dir_path, attempts):
    dir_path.mkdir(parents=True, exist_ok=True)
    for a in attempts:
        (dir_path / f"{a['attempt_id']}.json").write_text(
            json.dumps(a, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    return dir_path


def _write_lab_status(path, labs):
    path.write_text(json.dumps({"labs": labs}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _run(attempts_dir, lab_status, out, *, domain_map_path=META_DOMAIN_MAP):
    ed.export(
        attempts_dir=attempts_dir, lab_status_path=lab_status, out_path=out,
        now_iso=FROZEN_NOW, domain_map_path=domain_map_path,
    )
    return json.loads(out.read_text(encoding="utf-8"))


REQUIRED_TOP_LEVEL = {
    "generated_at",
    "pass_mark",
    "latest_attempt",
    "domain_breakdown",
    "scenario_breakdown",
    "weak_concepts",
    "lab_progress",
    "trend",
}


# ---------------------------------------------------------------------------
# Section A — latest_attempt tie behavior (Blocker B1 regression)
# ---------------------------------------------------------------------------


def test_latest_attempt_with_identical_finished_at_is_deterministic(tmp_path):
    """Two attempts share finished_at; whichever wins must be stable across re-runs."""
    same_finished = "2026-05-11T10:00:00Z"
    a1 = _attempt(
        attempt_id="att-aaa",
        finished_at=same_finished,
        answers=[_ans(qid="Q1", domain="D1", scenario="agentic-orchestration",
                      tags=["agent-loop"], is_correct=True)],
    )
    a2 = _attempt(
        attempt_id="att-zzz",
        finished_at=same_finished,
        answers=[_ans(qid="Q2", domain="D2", scenario="tool-schema-design",
                      tags=["mcp"], is_correct=False)],
    )

    attempts_dir = _write_attempts(tmp_path / "attempts", [a1, a2])
    labs = _write_lab_status(tmp_path / "lab-status.json", [])

    out1 = tmp_path / "run1.json"
    out2 = tmp_path / "run2.json"
    data1 = _run(attempts_dir, labs, out1)
    data2 = _run(attempts_dir, labs, out2)

    assert data1["latest_attempt"] is not None
    assert data2["latest_attempt"] is not None
    assert data1["latest_attempt"]["attempt_id"] == data2["latest_attempt"]["attempt_id"]


# ---------------------------------------------------------------------------
# Section B — load_domain_map missing-file fallback
# ---------------------------------------------------------------------------


def test_load_domain_map_returns_empty_when_file_missing(tmp_path):
    result = agg.load_domain_map(tmp_path / "no-such.md")
    assert result == {}


def test_export_completes_when_domain_map_missing(tmp_path):
    a1 = _attempt(
        attempt_id="att-001",
        finished_at="2026-05-10T10:00:00Z",
        answers=[_ans(qid="Q1", domain="D1", scenario="agentic-orchestration",
                      tags=["agent-loop"], is_correct=True)],
    )
    attempts_dir = _write_attempts(tmp_path / "attempts", [a1])
    labs = _write_lab_status(tmp_path / "lab-status.json", [])
    out = tmp_path / "dashboard-data.json"

    data = _run(attempts_dir, labs, out, domain_map_path=tmp_path / "no-such.md")

    assert set(data.keys()) >= REQUIRED_TOP_LEVEL
    domain_rows = data["domain_breakdown"]
    assert [r["domain"] for r in domain_rows] == ["D1", "D2", "D3", "D4", "D5"]
    for row in domain_rows:
        assert row["title"] == ""
        assert row["weight"] == 0.0


# ---------------------------------------------------------------------------
# Section C — Lab recommendation algorithm corner cases
# ---------------------------------------------------------------------------


def test_lab_matching_multiple_weak_concepts_appears_only_once(tmp_path):
    """A single lab tagged with multiple top weak concepts should appear once."""
    att = _attempt(
        attempt_id="att-001",
        finished_at="2026-05-11T09:00:00Z",
        answers=[
            _ans(qid="Q1", domain="D2", scenario="tool-schema-design",
                 tags=["mcp", "tool-design"], is_correct=False),
        ],
    )
    attempts_dir = _write_attempts(tmp_path / "attempts", [att])
    labs = _write_lab_status(tmp_path / "lab-status.json", [
        {"lab_id": "lab-d2-combo", "domain": "D2",
         "concept_tags": ["mcp", "tool-design"], "status": "not_started",
         "last_run": None},
    ])
    out = tmp_path / "dashboard-data.json"
    data = _run(attempts_dir, labs, out)

    recs = data["lab_progress"]["recommended_next"]
    matching = [r for r in recs if r["lab_id"] == "lab-d2-combo"]
    assert len(matching) == 1
    assert len(set(r["lab_id"] for r in recs)) == len(recs)


def test_all_labs_completed_yields_empty_recommendations(tmp_path):
    att = _attempt(
        attempt_id="att-001",
        finished_at="2026-05-11T09:00:00Z",
        answers=[
            _ans(qid="Q1", domain="D2", scenario="tool-schema-design",
                 tags=["mcp"], is_correct=False),
            _ans(qid="Q2", domain="D2", scenario="tool-schema-design",
                 tags=["tool-design"], is_correct=False),
            _ans(qid="Q3", domain="D1", scenario="agentic-orchestration",
                 tags=["agent-loop"], is_correct=False),
            _ans(qid="Q4", domain="D3", scenario="claude-code-config",
                 tags=["claude-md"], is_correct=False),
            _ans(qid="Q5", domain="D4", scenario="prompt-engineering",
                 tags=["json-prefill"], is_correct=False),
        ],
    )
    attempts_dir = _write_attempts(tmp_path / "attempts", [att])
    labs = _write_lab_status(tmp_path / "lab-status.json", [
        {"lab_id": "lab-d2-mcp", "domain": "D2", "concept_tags": ["mcp"],
         "status": "completed", "last_run": None},
        {"lab_id": "lab-d2-tools", "domain": "D2",
         "concept_tags": ["tool-design"], "status": "completed", "last_run": None},
        {"lab_id": "lab-d1-agent", "domain": "D1",
         "concept_tags": ["agent-loop"], "status": "completed", "last_run": None},
        {"lab_id": "lab-d3-md", "domain": "D3", "concept_tags": ["claude-md"],
         "status": "completed", "last_run": None},
        {"lab_id": "lab-d4-prefill", "domain": "D4",
         "concept_tags": ["json-prefill"], "status": "completed", "last_run": None},
    ])
    out = tmp_path / "dashboard-data.json"
    data = _run(attempts_dir, labs, out)

    assert data["lab_progress"]["recommended_next"] == []


def test_weak_concept_without_matching_lab_does_not_break_export(tmp_path):
    att = _attempt(
        attempt_id="att-001",
        finished_at="2026-05-11T09:00:00Z",
        answers=[
            _ans(qid="Q1", domain="D1", scenario="agentic-orchestration",
                 tags=["nonexistent-tag"], is_correct=False),
        ],
    )
    attempts_dir = _write_attempts(tmp_path / "attempts", [att])
    labs = _write_lab_status(tmp_path / "lab-status.json", [
        {"lab_id": "lab-d2-mcp", "domain": "D2", "concept_tags": ["mcp"],
         "status": "not_started", "last_run": None},
    ])
    out = tmp_path / "dashboard-data.json"
    data = _run(attempts_dir, labs, out)

    weak_tags = [w["concept_tag"] for w in data["weak_concepts"]]
    assert "nonexistent-tag" in weak_tags
    recs = data["lab_progress"]["recommended_next"]
    assert len(recs) < 5
    assert all(r["lab_id"] != "lab-nonexistent" for r in recs)


# ---------------------------------------------------------------------------
# Section D — Hardening the no-PDF / no-network guard (R3 finding)
# ---------------------------------------------------------------------------


def _boom(*a, **kw):
    raise AssertionError("export must not open network sockets")


def _boom2(*a, **kw):
    raise AssertionError("export must not call urlopen")


def test_export_does_not_open_network_sockets(tmp_path, monkeypatch):
    monkeypatch.setattr(urllib.request, "urlopen", _boom2)
    monkeypatch.setattr(socket, "socket", _boom)

    a1 = _attempt(
        attempt_id="att-001",
        finished_at="2026-05-10T10:00:00Z",
        answers=[_ans(qid="Q1", domain="D1", scenario="agentic-orchestration",
                      tags=["agent-loop"], is_correct=True)],
    )
    attempts_dir = _write_attempts(tmp_path / "attempts", [a1])
    labs = _write_lab_status(tmp_path / "lab-status.json", [])
    out = tmp_path / "dashboard-data.json"

    data = _run(attempts_dir, labs, out)
    assert set(data.keys()) >= REQUIRED_TOP_LEVEL


# ---------------------------------------------------------------------------
# Section E — Drift-proof assertions
# ---------------------------------------------------------------------------


def test_lab_progress_totals_track_inline_fixture_size(tmp_path):
    inline_labs = [
        {"lab_id": "lab-1", "domain": "D1", "concept_tags": ["agent-loop"],
         "status": "not_started", "last_run": None},
        {"lab_id": "lab-2", "domain": "D2", "concept_tags": ["mcp"],
         "status": "in_progress", "last_run": None},
        {"lab_id": "lab-3", "domain": "D3", "concept_tags": ["claude-md"],
         "status": "completed", "last_run": None},
        {"lab_id": "lab-4", "domain": "D4", "concept_tags": ["json-prefill"],
         "status": "not_started", "last_run": None},
    ]
    expected_n = len(inline_labs)

    att = _attempt(
        attempt_id="att-001",
        finished_at="2026-05-10T10:00:00Z",
        answers=[_ans(qid="Q1", domain="D1", scenario="agentic-orchestration",
                      tags=["agent-loop"], is_correct=True)],
    )
    attempts_dir = _write_attempts(tmp_path / "attempts", [att])
    labs = _write_lab_status(tmp_path / "lab-status.json", inline_labs)
    out = tmp_path / "dashboard-data.json"
    data = _run(attempts_dir, labs, out)

    assert data["lab_progress"]["total_labs"] == expected_n


# ---------------------------------------------------------------------------
# Section F — Spec §8.2 C2 + C7 cross-validation
# ---------------------------------------------------------------------------


def test_finished_at_ties_do_not_break_byte_identity(tmp_path):
    same_finished = "2026-05-11T10:00:00Z"
    a1 = _attempt(
        attempt_id="att-aaa",
        finished_at=same_finished,
        answers=[_ans(qid="Q1", domain="D1", scenario="agentic-orchestration",
                      tags=["agent-loop"], is_correct=True)],
    )
    a2 = _attempt(
        attempt_id="att-zzz",
        finished_at=same_finished,
        answers=[_ans(qid="Q2", domain="D2", scenario="tool-schema-design",
                      tags=["mcp"], is_correct=False)],
    )
    attempts_dir = _write_attempts(tmp_path / "attempts", [a1, a2])
    labs = _write_lab_status(tmp_path / "lab-status.json", [])

    out_a = tmp_path / "a.json"
    out_b = tmp_path / "b.json"
    _run(attempts_dir, labs, out_a)
    _run(attempts_dir, labs, out_b)

    assert out_a.read_bytes() == out_b.read_bytes()


# ---------------------------------------------------------------------------
# Section G — --now default-UTC ISO-8601 format
# ---------------------------------------------------------------------------


def test_default_now_is_iso_8601_format(tmp_path, monkeypatch):
    a1 = _attempt(
        attempt_id="att-001",
        finished_at="2026-05-10T10:00:00Z",
        answers=[_ans(qid="Q1", domain="D1", scenario="agentic-orchestration",
                      tags=["agent-loop"], is_correct=True)],
    )
    attempts_dir = _write_attempts(tmp_path / "attempts", [a1])
    labs = _write_lab_status(tmp_path / "lab-status.json", [])
    out = tmp_path / "dashboard-data.json"

    ed.export(
        attempts_dir=attempts_dir,
        lab_status_path=labs,
        out_path=out,
        now_iso=None,
        domain_map_path=META_DOMAIN_MAP,
    )
    data = json.loads(out.read_text(encoding="utf-8"))

    parsed = datetime.fromisoformat(data["generated_at"].replace("Z", "+00:00"))
    assert parsed is not None
