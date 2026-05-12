"""Pure aggregation primitives for the dashboard-data export (spec §8).

This module is IO-free except for `load_domain_map`, which parses
`00-meta/domain-map.md`. Everything else operates on in-memory dicts
so the export logic is unit-testable without fixtures and produces
byte-identical output for byte-identical inputs.
"""

from __future__ import annotations

import json
import re
import warnings
from pathlib import Path
from typing import Any, Iterable

from cca_f_study import _scoring


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


DOMAIN_ORDER: tuple[str, ...] = ("D1", "D2", "D3", "D4", "D5")
WEAK_CONCEPTS_CAP: int = 10
RECOMMENDED_LABS_CAP: int = 5


_DOMAIN_ROW = re.compile(
    r"^\|\s*(D[1-5])\s*\|\s*([^|]+?)\s*\|\s*(\d+)%\s*\|"
)


# ---------------------------------------------------------------------------
# domain-map.md loader
# ---------------------------------------------------------------------------


def load_domain_map(path: Path) -> dict[str, dict[str, Any]]:
    """Return ``{Dn: {title, weight}}`` parsed from `domain-map.md`.

    Falls back to an empty dict if the file is missing; the export still
    produces a contract-shaped output but with ``title`` and ``weight``
    set to placeholders (`""` and `0.0`).
    """
    if not path.exists():
        return {}
    out: dict[str, dict[str, Any]] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        m = _DOMAIN_ROW.match(raw)
        if not m:
            continue
        code, title, pct = m.group(1), m.group(2).strip(), int(m.group(3))
        out[code] = {"title": title, "weight": pct / 100.0}
    return out


# ---------------------------------------------------------------------------
# Attempt loading
# ---------------------------------------------------------------------------


def iter_attempts(attempts_dir: Path) -> list[dict]:
    """Return all attempt dicts under ``attempts_dir`` sorted by ``finished_at``.

    Files that fail to parse are skipped with a ``warnings.warn`` so the
    developer can still see the silent skip; the dashboard degrades
    gracefully when a single attempt file is broken.
    """
    if not attempts_dir.exists():
        return []
    attempts: list[dict] = []
    for path in sorted(attempts_dir.iterdir()):
        # Skip non-files (directories) and non-JSON entries. Also defend
        # against broken symlinks where ``resolve(strict=True)`` would fail.
        try:
            if not path.is_file() or path.suffix != ".json":
                continue
        except OSError as exc:
            warnings.warn(f"skipping {path}: {exc}", stacklevel=2)
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError, OSError) as exc:
            warnings.warn(f"skipping {path}: {exc}", stacklevel=2)
            continue
        if isinstance(data, dict) and isinstance(data.get("answers"), list):
            attempts.append(data)
    # Compound key (finished_at, attempt_id) so ties are broken
    # deterministically by attempt_id rather than filesystem order.
    attempts.sort(
        key=lambda a: (
            str(a.get("finished_at") or ""),
            str(a.get("attempt_id") or ""),
        )
    )
    return attempts


# ---------------------------------------------------------------------------
# Lab status
# ---------------------------------------------------------------------------


def load_lab_status(path: Path) -> list[dict]:
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        # Local import avoids a circular import at module-load time
        # (export_dashboard_data imports this module).
        from cca_f_study.export_dashboard_data import ExportError

        raise ExportError(f"{path}: JSON parse error: {exc.msg}") from exc
    if not isinstance(data, dict):
        return []
    labs = data.get("labs")
    if not isinstance(labs, list):
        return []
    return [lab for lab in labs if isinstance(lab, dict)]


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------


def _flatten_answers(attempts: Iterable[dict]) -> list[dict]:
    flat: list[dict] = []
    for a in attempts:
        for ans in a.get("answers") or []:
            if isinstance(ans, dict):
                flat.append(ans)
    return flat


def _empty_domain_row(code: str, domain_map: dict[str, dict]) -> dict:
    info = domain_map.get(code, {})
    return {
        "domain": code,
        "title": info.get("title", ""),
        "weight": float(info.get("weight", 0.0)),
        "correct": 0,
        "total": 0,
        "accuracy": None,
    }


def build_domain_breakdown(
    answers: list[dict], domain_map: dict[str, dict]
) -> list[dict]:
    """Spec §8.2 C3: always lists D1-D5 in numeric order."""
    buckets = _scoring.compute_breakdowns(answers)["domain"]
    rows: list[dict] = []
    for code in DOMAIN_ORDER:
        row = _empty_domain_row(code, domain_map)
        if code in buckets:
            b = buckets[code]
            row["correct"] = b["correct"]
            row["total"] = b["total"]
            row["accuracy"] = b["accuracy"]
        rows.append(row)
    return rows


def build_scenario_breakdown(answers: list[dict]) -> list[dict]:
    buckets = _scoring.compute_breakdowns(answers)["scenario"]
    rows = [
        {
            "scenario": name,
            "correct": b["correct"],
            "total": b["total"],
            "accuracy": b["accuracy"],
        }
        for name, b in sorted(buckets.items())
    ]
    return rows


def build_weak_concepts(answers: list[dict], cap: int = WEAK_CONCEPTS_CAP) -> list[dict]:
    """Spec §8.2 C4: sorted by miss_rate desc, ties by missed desc; capped at ``cap``."""
    buckets = _scoring.compute_breakdowns(answers)["concept"]
    rows: list[dict] = []
    for tag, b in buckets.items():
        seen = b["total"]
        if seen == 0:
            continue
        missed = seen - b["correct"]
        if missed == 0:
            # Only concepts the learner has missed at least once are "weak".
            continue
        miss_rate = round(missed / seen, 3)
        rows.append(
            {
                "concept_tag": tag,
                "missed": missed,
                "seen": seen,
                "miss_rate": miss_rate,
            }
        )
    # sort by (miss_rate desc, missed desc, concept_tag asc) for deterministic ties
    rows.sort(key=lambda r: (-r["miss_rate"], -r["missed"], r["concept_tag"]))
    return rows[:cap]


def build_lab_progress(
    labs: list[dict],
    weak_concepts: list[dict],
    cap: int = RECOMMENDED_LABS_CAP,
) -> dict:
    """Spec §8.2 C5: prefer labs tagged with the top weak ``concept_tags``
    whose status is `not_started` or `in_progress`, capped at ``cap``.
    """
    counts = {"completed": 0, "in_progress": 0, "not_started": 0}
    for lab in labs:
        status = lab.get("status")
        if status in counts:
            counts[status] += 1

    eligible_statuses = {"not_started", "in_progress"}
    eligible_labs = [lab for lab in labs if lab.get("status") in eligible_statuses]
    # Canonical ordering by lab_id so recommendations are stable across
    # benign reorderings of the input lab-status.json (Fix 2).
    eligible_labs.sort(key=lambda lab: str(lab.get("lab_id") or ""))

    recommended: list[dict] = []
    seen_lab_ids: set[str] = set()
    for w in weak_concepts:  # already sorted by miss_rate desc
        tag = w["concept_tag"]
        # Stable iteration: walk eligible labs in their declared order.
        for lab in eligible_labs:
            if tag in (lab.get("concept_tags") or []):
                lab_id = lab.get("lab_id")
                if not isinstance(lab_id, str) or lab_id in seen_lab_ids:
                    continue
                recommended.append({"lab_id": lab_id, "reason": f"weak concept: {tag}"})
                seen_lab_ids.add(lab_id)
                if len(recommended) >= cap:
                    break
        if len(recommended) >= cap:
            break

    return {
        "total_labs": len(labs),
        "completed": counts["completed"],
        "in_progress": counts["in_progress"],
        "not_started": counts["not_started"],
        "recommended_next": recommended,
    }


def build_trend(attempts: list[dict]) -> list[dict]:
    """Spec §8.2 C6: every attempt, chronological ascending."""
    rows = []
    for a in attempts:
        scaled = _scoring.score(a)["scaled_score"]
        rows.append(
            {
                "attempt_id": a.get("attempt_id"),
                "finished_at": a.get("finished_at"),
                "scaled_score": scaled,
            }
        )
    rows.sort(
        key=lambda r: (
            str(r.get("finished_at") or ""),
            str(r.get("attempt_id") or ""),
        )
    )
    return rows


def latest_attempt_block(attempts: list[dict]) -> dict | None:
    """Return the Phase 6 score summary header for the most recent attempt, or None."""
    if not attempts:
        return None
    # Compound key (finished_at, attempt_id) — when two attempts share the
    # same finished_at, the lexicographically greater attempt_id wins
    # (deterministic and filesystem-order independent).
    latest = max(
        attempts,
        key=lambda a: (
            str(a.get("finished_at") or ""),
            str(a.get("attempt_id") or ""),
        ),
    )
    summary = _scoring.score(latest)
    # Keep only the per-attempt header fields (spec §8.1 latest_attempt shape).
    return {
        "attempt_id": summary["attempt_id"],
        "finished_at": summary["finished_at"],
        "raw_correct": summary["raw_correct"],
        "total": summary["total"],
        "accuracy": summary["accuracy"],
        "scaled_score": summary["scaled_score"],
        "pass": summary["pass"],
        "pass_gap": summary["pass_gap"],
        "pass_progress": summary["pass_progress"],
    }


# ---------------------------------------------------------------------------
# Top-level assembly
# ---------------------------------------------------------------------------


def build_dashboard_data(
    *,
    attempts: list[dict],
    labs: list[dict],
    domain_map: dict[str, dict],
    now_iso: str,
) -> dict:
    answers = _flatten_answers(attempts)
    weak = build_weak_concepts(answers)
    return {
        "generated_at": now_iso,
        "pass_mark": _scoring.PASS_MARK,
        "latest_attempt": latest_attempt_block(attempts),
        "domain_breakdown": build_domain_breakdown(answers, domain_map),
        "scenario_breakdown": build_scenario_breakdown(answers),
        "weak_concepts": weak,
        "lab_progress": build_lab_progress(labs, weak),
        "trend": build_trend(attempts),
    }
