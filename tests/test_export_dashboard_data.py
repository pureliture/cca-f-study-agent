"""Tests for `cca_f_study.export_dashboard_data` and `cca_f_study._aggregate`.

Covers spec §8 (dashboard-data contract C1-C7) and §10.4 (CLI surface).
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
DOMAIN_TITLES = {
    "D1": "Agentic Architecture & Orchestration",
    "D2": "Tool Design & MCP Integration",
    "D3": "Claude Code Configuration & Workflows",
    "D4": "Prompt Engineering & Structured Output",
    "D5": "Context Management & Reliability",
}
DOMAIN_WEIGHTS = {"D1": 0.27, "D2": 0.18, "D3": 0.20, "D4": 0.20, "D5": 0.15}
FROZEN_NOW = "2026-05-11T10:05:00Z"


# ---------------------------------------------------------------------------
# Helpers — build attempts and lab-status fixtures inline
# ---------------------------------------------------------------------------


def _ans(*, qid: str, domain: str, scenario: str, tags, is_correct: bool) -> dict:
    return {
        "question_id": qid,
        "domain": domain,
        "scenario": scenario,
        "concept_tags": list(tags),
        "choice": "A" if is_correct else "B",
        "correct": "A",
        "is_correct": is_correct,
    }


def _attempt(*, attempt_id: str, finished_at: str, answers: list[dict]) -> dict:
    return {
        "attempt_id": attempt_id,
        "attempt_label": attempt_id,
        "started_at": finished_at,
        "finished_at": finished_at,
        "question_bank_path": "test",
        "answers": answers,
        "totals": {"total": len(answers), "correct": sum(1 for a in answers if a["is_correct"])},
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
    path.write_text(json.dumps({"labs": labs}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _build_three_attempts() -> list[dict]:
    """Three attempts with ascending finished_at, varying scores and tags."""
    a1 = _attempt(
        attempt_id="att-001",
        finished_at="2026-05-10T10:00:00Z",
        answers=[
            _ans(qid="Q1", domain="D1", scenario="agentic-orchestration", tags=["agent-loop"], is_correct=False),
            _ans(qid="Q2", domain="D2", scenario="tool-schema-design", tags=["mcp"], is_correct=False),
            _ans(qid="Q3", domain="D3", scenario="claude-code-config", tags=["claude-md"], is_correct=True),
        ],
    )
    a2 = _attempt(
        attempt_id="att-002",
        finished_at="2026-05-10T11:00:00Z",
        answers=[
            _ans(qid="Q1", domain="D1", scenario="agentic-orchestration", tags=["agent-loop"], is_correct=True),
            _ans(qid="Q2", domain="D2", scenario="tool-schema-design", tags=["mcp", "tool-design"], is_correct=False),
            _ans(qid="Q3", domain="D3", scenario="claude-code-config", tags=["claude-md"], is_correct=True),
        ],
    )
    a3 = _attempt(
        attempt_id="att-003",
        finished_at="2026-05-11T10:00:00Z",
        answers=[
            _ans(qid="Q1", domain="D1", scenario="agentic-orchestration", tags=["agent-loop"], is_correct=True),
            _ans(qid="Q2", domain="D2", scenario="tool-schema-design", tags=["mcp"], is_correct=False),
            _ans(qid="Q3", domain="D3", scenario="claude-code-config", tags=["claude-md"], is_correct=True),
        ],
    )
    return [a1, a2, a3]


def _build_lab_status() -> list[dict]:
    return [
        {"lab_id": "lab-d2-mcp", "domain": "D2", "concept_tags": ["mcp"], "status": "not_started", "last_run": None},
        {"lab_id": "lab-d1-agent", "domain": "D1", "concept_tags": ["agent-loop"], "status": "in_progress", "last_run": None},
        {"lab_id": "lab-d3-md", "domain": "D3", "concept_tags": ["claude-md"], "status": "completed", "last_run": None},
        {"lab_id": "lab-d2-tools", "domain": "D2", "concept_tags": ["tool-design"], "status": "not_started", "last_run": None},
        {"lab_id": "lab-d4-prefill", "domain": "D4", "concept_tags": ["json-prefill"], "status": "not_started", "last_run": None},
    ]


def _run(attempts_dir: Path, lab_status: Path, out: Path) -> dict:
    ed.export(
        attempts_dir=attempts_dir,
        lab_status_path=lab_status,
        out_path=out,
        now_iso=FROZEN_NOW,
        domain_map_path=META_DOMAIN_MAP,
    )
    return json.loads(out.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# domain-map.md loader
# ---------------------------------------------------------------------------


def test_load_domain_map_returns_d1_through_d5():
    dm = agg.load_domain_map(META_DOMAIN_MAP)
    assert set(dm.keys()) == {"D1", "D2", "D3", "D4", "D5"}
    assert dm["D1"]["title"] == DOMAIN_TITLES["D1"]
    assert abs(dm["D1"]["weight"] - 0.27) < 1e-9


def test_load_domain_map_weights_sum_to_one():
    dm = agg.load_domain_map(META_DOMAIN_MAP)
    total = sum(v["weight"] for v in dm.values())
    assert abs(total - 1.0) < 0.01


# ---------------------------------------------------------------------------
# C1 — All required top-level keys present
# ---------------------------------------------------------------------------

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


def test_output_contains_all_required_top_level_keys(tmp_path):
    attempts = _write_attempts(tmp_path / "attempts", _build_three_attempts())
    labs = _write_lab_status(tmp_path / "lab-status.json", _build_lab_status())
    out = tmp_path / "dashboard-data.json"
    data = _run(attempts, labs, out)
    assert set(data.keys()) >= REQUIRED_TOP_LEVEL
    assert data["pass_mark"] == 720
    assert data["generated_at"] == FROZEN_NOW


# ---------------------------------------------------------------------------
# C2 — latest_attempt is most recent finished_at
# ---------------------------------------------------------------------------


def test_latest_attempt_is_most_recent_finished_at(tmp_path):
    attempts = _write_attempts(tmp_path / "attempts", _build_three_attempts())
    labs = _write_lab_status(tmp_path / "lab-status.json", _build_lab_status())
    out = tmp_path / "dashboard-data.json"
    data = _run(attempts, labs, out)
    la = data["latest_attempt"]
    assert la["attempt_id"] == "att-003"
    assert la["finished_at"] == "2026-05-11T10:00:00Z"
    # The Phase 7 latest_attempt block must carry the per-attempt header fields.
    for key in ("raw_correct", "total", "accuracy", "scaled_score", "pass", "pass_gap", "pass_progress"):
        assert key in la, f"missing key: {key}"


# ---------------------------------------------------------------------------
# C3 — domain_breakdown always lists D1-D5 in numeric order
# ---------------------------------------------------------------------------


def test_domain_breakdown_always_lists_d1_through_d5(tmp_path):
    # Use an attempt that only touches D1 to force the empty-domain branch
    one_d1 = _attempt(
        attempt_id="att-only-d1",
        finished_at="2026-05-11T09:00:00Z",
        answers=[_ans(qid="Q1", domain="D1", scenario="agentic-orchestration", tags=["agent-loop"], is_correct=True)],
    )
    attempts = _write_attempts(tmp_path / "attempts", [one_d1])
    labs = _write_lab_status(tmp_path / "lab-status.json", _build_lab_status())
    out = tmp_path / "dashboard-data.json"
    data = _run(attempts, labs, out)

    domain_rows = data["domain_breakdown"]
    assert [r["domain"] for r in domain_rows] == ["D1", "D2", "D3", "D4", "D5"]
    # Untouched domains carry total=0 and accuracy=null
    d2 = next(r for r in domain_rows if r["domain"] == "D2")
    assert d2["total"] == 0
    assert d2["correct"] == 0
    assert d2["accuracy"] is None
    # All rows carry title and weight from domain-map.md
    for r in domain_rows:
        assert r["title"] == DOMAIN_TITLES[r["domain"]]
        assert abs(r["weight"] - DOMAIN_WEIGHTS[r["domain"]]) < 1e-9


# ---------------------------------------------------------------------------
# C4 — weak_concepts sorted by miss_rate desc, capped at 10
# ---------------------------------------------------------------------------


def test_weak_concepts_sorted_by_miss_rate_descending(tmp_path):
    attempts = _write_attempts(tmp_path / "attempts", _build_three_attempts())
    labs = _write_lab_status(tmp_path / "lab-status.json", _build_lab_status())
    out = tmp_path / "dashboard-data.json"
    data = _run(attempts, labs, out)

    weak = data["weak_concepts"]
    rates = [w["miss_rate"] for w in weak]
    assert rates == sorted(rates, reverse=True)

    # mcp was missed 3 of 3 times -> miss_rate 1.0
    mcp = next((w for w in weak if w["concept_tag"] == "mcp"), None)
    assert mcp is not None
    assert mcp["seen"] == 3
    assert mcp["missed"] == 3
    assert mcp["miss_rate"] == 1.0


def test_weak_concepts_excludes_zero_miss_rate(tmp_path):
    """A concept the learner has never missed must not appear as "weak"."""
    att = _attempt(
        attempt_id="att-perfect-on-mcp",
        finished_at="2026-05-11T09:00:00Z",
        answers=[
            _ans(qid="Q1", domain="D2", scenario="tool-schema-design", tags=["mcp"], is_correct=True),
            _ans(qid="Q2", domain="D2", scenario="tool-schema-design", tags=["mcp"], is_correct=True),
            _ans(qid="Q3", domain="D1", scenario="agentic-orchestration", tags=["agent-loop"], is_correct=False),
        ],
    )
    attempts = _write_attempts(tmp_path / "attempts", [att])
    labs = _write_lab_status(tmp_path / "lab-status.json", _build_lab_status())
    out = tmp_path / "dashboard-data.json"
    data = _run(attempts, labs, out)
    weak_tags = {w["concept_tag"] for w in data["weak_concepts"]}
    assert "mcp" not in weak_tags
    assert "agent-loop" in weak_tags


def test_weak_concepts_capped_at_ten(tmp_path):
    # Build an attempt with 15 distinct concept tags, all wrong
    tags = [f"tag-{i:02d}" for i in range(15)]
    answers = [
        _ans(qid=f"Q{i}", domain="D1", scenario="agentic-orchestration", tags=[t], is_correct=False)
        for i, t in enumerate(tags)
    ]
    att = _attempt(attempt_id="att-big", finished_at="2026-05-11T09:00:00Z", answers=answers)
    attempts = _write_attempts(tmp_path / "attempts", [att])
    labs = _write_lab_status(tmp_path / "lab-status.json", _build_lab_status())
    out = tmp_path / "dashboard-data.json"
    data = _run(attempts, labs, out)
    assert len(data["weak_concepts"]) == 10


# ---------------------------------------------------------------------------
# C5 — lab recommendations capped at 5 and prefer weak concepts
# ---------------------------------------------------------------------------


def test_lab_recommendations_prefer_weak_concepts_and_cap_at_five(tmp_path):
    attempts = _write_attempts(tmp_path / "attempts", _build_three_attempts())
    labs = _write_lab_status(tmp_path / "lab-status.json", _build_lab_status())
    out = tmp_path / "dashboard-data.json"
    data = _run(attempts, labs, out)

    recs = data["lab_progress"]["recommended_next"]
    assert len(recs) <= 5
    # The top weak concept (mcp, 100% miss) should produce a recommendation
    rec_lab_ids = [r["lab_id"] for r in recs]
    assert "lab-d2-mcp" in rec_lab_ids
    # Completed labs are NOT recommended even if matching
    assert "lab-d3-md" not in rec_lab_ids
    # Recommendation reason mentions the weak concept
    mcp_rec = next(r for r in recs if r["lab_id"] == "lab-d2-mcp")
    assert "mcp" in mcp_rec["reason"]


def test_lab_progress_counts_by_status(tmp_path):
    attempts = _write_attempts(tmp_path / "attempts", _build_three_attempts())
    labs = _write_lab_status(tmp_path / "lab-status.json", _build_lab_status())
    out = tmp_path / "dashboard-data.json"
    data = _run(attempts, labs, out)
    lp = data["lab_progress"]
    assert lp["total_labs"] == 5
    assert lp["completed"] == 1
    assert lp["in_progress"] == 1
    assert lp["not_started"] == 3


# ---------------------------------------------------------------------------
# C6 — trend includes every attempt, sorted chronologically ascending
# ---------------------------------------------------------------------------


def test_trend_is_chronological_ascending(tmp_path):
    attempts = _write_attempts(tmp_path / "attempts", _build_three_attempts())
    labs = _write_lab_status(tmp_path / "lab-status.json", _build_lab_status())
    out = tmp_path / "dashboard-data.json"
    data = _run(attempts, labs, out)
    trend = data["trend"]
    assert [t["attempt_id"] for t in trend] == ["att-001", "att-002", "att-003"]
    finished = [t["finished_at"] for t in trend]
    assert finished == sorted(finished)
    for t in trend:
        assert "scaled_score" in t


# ---------------------------------------------------------------------------
# C7 — Byte-identical on repeated runs with identical inputs
# ---------------------------------------------------------------------------


def test_export_is_byte_identical_on_repeated_runs(tmp_path):
    attempts = _write_attempts(tmp_path / "attempts", _build_three_attempts())
    labs = _write_lab_status(tmp_path / "lab-status.json", _build_lab_status())
    a = tmp_path / "a.json"
    b = tmp_path / "b.json"
    _run(attempts, labs, a)
    _run(attempts, labs, b)
    assert a.read_bytes() == b.read_bytes()


# ---------------------------------------------------------------------------
# Empty input
# ---------------------------------------------------------------------------


def test_empty_attempts_dir_produces_valid_empty_output(tmp_path):
    (tmp_path / "attempts").mkdir()
    labs = _write_lab_status(tmp_path / "lab-status.json", _build_lab_status())
    out = tmp_path / "dashboard-data.json"
    data = _run(tmp_path / "attempts", labs, out)
    assert set(data.keys()) >= REQUIRED_TOP_LEVEL
    assert data["latest_attempt"] is None
    assert data["trend"] == []
    assert data["weak_concepts"] == []
    # Domain breakdown still lists D1-D5 with zeros
    domains = [r["domain"] for r in data["domain_breakdown"]]
    assert domains == ["D1", "D2", "D3", "D4", "D5"]
    for r in data["domain_breakdown"]:
        assert r["total"] == 0
        assert r["accuracy"] is None


# ---------------------------------------------------------------------------
# Cross-cutting — no PDF, no network reads
# ---------------------------------------------------------------------------


def test_export_does_not_read_source_pdf(tmp_path, monkeypatch):
    """Reading any path under 01-sources/en/*.pdf must NEVER happen at export time."""
    real_open = open

    def guarded_open(file, *a, **kw):
        s = str(file)
        if s.endswith(".pdf") or "/01-sources/en/" in s:
            raise AssertionError(f"export must not open PDF or its source dir: {s}")
        return real_open(file, *a, **kw)

    monkeypatch.setattr("builtins.open", guarded_open)
    attempts = _write_attempts(tmp_path / "attempts", _build_three_attempts())
    labs = _write_lab_status(tmp_path / "lab-status.json", _build_lab_status())
    out = tmp_path / "dashboard-data.json"
    _run(attempts, labs, out)


# ---------------------------------------------------------------------------
# CLI surfaces — spec §10.4
# ---------------------------------------------------------------------------


def _run_cli(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "cca_f_study.export_dashboard_data", *args],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )


def test_cli_via_python_dash_m(tmp_path):
    attempts = _write_attempts(tmp_path / "attempts", _build_three_attempts())
    labs = _write_lab_status(tmp_path / "lab-status.json", _build_lab_status())
    out = tmp_path / "dashboard-data.json"
    proc = _run_cli([
        "--attempts", str(attempts),
        "--lab-status", str(labs),
        "--out", str(out),
        "--now", FROZEN_NOW,
    ])
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert out.exists()
    data = json.loads(out.read_text(encoding="utf-8"))
    assert set(data.keys()) >= REQUIRED_TOP_LEVEL


def test_cli_via_04_exam_runner_wrapper(tmp_path):
    """Spec §10.4 surface: python 04-exam-runner/export_dashboard_data.py …"""
    attempts = _write_attempts(tmp_path / "attempts", _build_three_attempts())
    labs = _write_lab_status(tmp_path / "lab-status.json", _build_lab_status())
    out = tmp_path / "dashboard-data.json"
    proc = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "04-exam-runner" / "export_dashboard_data.py"),
            "--attempts", str(attempts),
            "--lab-status", str(labs),
            "--out", str(out),
            "--now", FROZEN_NOW,
        ],
        capture_output=True, text=True, cwd=REPO_ROOT,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert out.exists()


def test_committed_dashboard_data_validates(tmp_path):
    """If the canonical command has been run, the resulting file should
    have the contract shape. This locks CC8 + CC14 in place."""
    committed = REPO_ROOT / "06-dashboard" / "data" / "dashboard-data.json"
    if not committed.exists():
        pytest.skip("dashboard-data.json not generated yet")
    data = json.loads(committed.read_text(encoding="utf-8"))
    assert set(data.keys()) >= REQUIRED_TOP_LEVEL
    assert data["pass_mark"] == 720
    domains = [r["domain"] for r in data["domain_breakdown"]]
    assert domains == ["D1", "D2", "D3", "D4", "D5"]
    # CC14: the canonical regen pins --now to this value so re-runs are
    # byte-identical. If you re-snapshot, update both this assertion and
    # the pinned value in CLAUDE.md / Phase 7 runbook.
    assert data["generated_at"] == "2026-05-12T00:30:00Z"
