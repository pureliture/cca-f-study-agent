"""Score a normalized CCA-F attempt JSON file (spec §7, §10.3).

CLI surfaces
------------
    python -m cca_f_study.score_attempt <attempt.json> [--json]
    python 04-exam-runner/score_attempt.py <attempt.json> [--json]

Default output is the human-readable summary (Raw / Scaled / Pass mark /
Result / Gap + a Domain breakdown block). With ``--json`` the same
information is emitted as the Phase 7 machine contract (see
``cca_f_study._scoring.score``).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Sequence

from cca_f_study import _scoring


class ScoreError(RuntimeError):
    """Raised when an attempt cannot be scored (e.g. file missing or malformed)."""


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------


def _load_attempt(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise ScoreError(f"attempt file not found: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ScoreError(f"{path}: JSON parse error: {exc.msg}") from exc
    if not isinstance(data, dict):
        raise ScoreError(f"{path}: expected a JSON object at top level")
    if not isinstance(data.get("answers"), list):
        raise ScoreError(f"{path}: 'answers' must be an array")
    return data


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def score_attempt_file(path: Path) -> dict[str, Any]:
    """Read ``path`` and return the Phase 7-shaped summary."""
    attempt = _load_attempt(Path(path))
    return _scoring.score(attempt)


# ---------------------------------------------------------------------------
# Formatting
# ---------------------------------------------------------------------------


def format_human(summary: dict[str, Any]) -> str:
    """Format the human-readable summary (spec §10.3)."""
    raw_correct = summary["raw_correct"]
    total = summary["total"]
    scaled = summary["scaled_score"]
    pass_mark = _scoring.PASS_MARK
    is_pass = summary["pass"]
    gap = summary["pass_gap"]

    lines = [
        f"Raw score: {raw_correct} / {total}",
        f"Scaled score: {scaled} / 1000",
        f"Pass mark: {pass_mark}",
        f"Result: {'PASS' if is_pass else 'FAIL'}",
        f"Gap: {gap:+d}",
        "",
        "Domain breakdown:",
    ]

    domain = summary.get("domain_breakdown") or {}
    if domain:
        for code in sorted(domain.keys()):
            bucket = domain[code]
            lines.append(f"  {code}: {bucket['correct']}/{bucket['total']}")
    else:
        lines.append("  (no answers)")

    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m cca_f_study.score_attempt",
        description="Score a normalized CCA-F attempt JSON file.",
    )
    p.add_argument("attempt_path", type=Path, help="Path to the attempt JSON file.")
    p.add_argument(
        "--json",
        action="store_true",
        dest="as_json",
        help="Emit the machine-readable Phase 7 summary on stdout.",
    )
    return p


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        summary = score_attempt_file(args.attempt_path)
    except ScoreError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if args.as_json:
        sys.stdout.write(
            json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        )
    else:
        sys.stdout.write(format_human(summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
