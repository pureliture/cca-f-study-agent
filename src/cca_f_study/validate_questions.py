"""Validate a CCA-F question-bank JSONL file against `question_schema.json`.

CLI:
    python -m cca_f_study.validate_questions <path-to-questions.jsonl>

Exit code 0 on full success, non-zero if any line fails validation.

Schemas ship with the package (see `cca_f_study._schemas`) and load via
`importlib.resources`, so the CLI works from any working directory and
under wheel/target installs.  The canonical authoring copies under
`04-exam-runner/` stay byte-identical to the packaged ones (enforced by
`tests/test_review_findings.py`).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from importlib.resources import files
from pathlib import Path
from typing import Iterable, Iterator, Sequence

import jsonschema


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Failure:
    line: int
    question_id: str
    reason: str


@dataclass
class ValidationReport:
    valid_count: int = 0
    invalid_count: int = 0
    failures: list[Failure] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Default-path discovery
# ---------------------------------------------------------------------------


def _default_question_schema() -> dict:
    """Load `question_schema.json` from the installed package data."""
    return json.loads(
        (files("cca_f_study._schemas") / "question_schema.json").read_text(encoding="utf-8")
    )


def _resolve_meta_file(filename: str, explicit: Path | None) -> Path | None:
    """Find a metadata file (source-register.md, scenario-map.md, ...).

    Search order:
      1. explicit path argument, if given.
      2. `<CWD>/00-meta/<filename>` (project run from the repo root).
      3. `<repo-root-from-__file__>/00-meta/<filename>` (development checkout
         where the validator is installed in editable mode from the repo).
    Returns the first path that exists, or None.
    """
    if explicit is not None:
        return explicit if explicit.exists() else None

    candidates = [
        Path.cwd() / "00-meta" / filename,
        # Resolve relative to this file in case the package is editable-installed
        # from the canonical checkout: src/cca_f_study/validate_questions.py
        # → parents[2] is the repo root.
        Path(__file__).resolve().parents[2] / "00-meta" / filename,
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


# ---------------------------------------------------------------------------
# Metadata loaders
# ---------------------------------------------------------------------------


_SOURCE_IDS_HEADER = re.compile(r"^##\s+Source IDs\s*$", re.IGNORECASE)
_SCENARIO_HEADER = re.compile(r"^#\s+Scenario Map\s*$", re.IGNORECASE)
_NEXT_SECTION = re.compile(r"^##\s+")
_SOURCE_ROW = re.compile(r"^\|\s*`([A-Za-z0-9_-]+)`\s*\|\s*([A-Za-z_]+)\s*\|")
_SCENARIO_ROW = re.compile(r"^\|\s*`([a-z0-9][a-z0-9-]*)`\s*\|")


def load_registered_sources(register_path: Path) -> set[str]:
    """Return source IDs marked `active` in `source-register.md`."""
    if not register_path.exists():
        return set()
    in_section = False
    active: set[str] = set()
    for raw in register_path.read_text(encoding="utf-8").splitlines():
        if _SOURCE_IDS_HEADER.match(raw):
            in_section = True
            continue
        if in_section and _NEXT_SECTION.match(raw):
            break
        if not in_section:
            continue
        m = _SOURCE_ROW.match(raw)
        if not m:
            continue
        source_id, status = m.group(1), m.group(2).lower()
        if status == "active":
            active.add(source_id)
    return active


def load_allowed_scenarios(scenario_map_path: Path) -> set[str]:
    """Return scenario IDs declared in `scenario-map.md`.

    Parses the first markdown table in the file; the first column wraps the
    scenario ID in backticks and matches `^[a-z0-9][a-z0-9-]*$`.
    """
    if not scenario_map_path.exists():
        return set()
    scenarios: set[str] = set()
    for raw in scenario_map_path.read_text(encoding="utf-8").splitlines():
        # Skip table separators like `|----|----|`.
        if raw.lstrip().startswith("|-"):
            continue
        m = _SCENARIO_ROW.match(raw)
        if m:
            scenarios.add(m.group(1))
    return scenarios


# ---------------------------------------------------------------------------
# Record streaming
# ---------------------------------------------------------------------------


def _iter_records(jsonl_path: Path) -> Iterator[tuple[int, object | None, str | None]]:
    """Yield (line_number, parsed_value_or_None, parse_error_or_None)."""
    with jsonl_path.open(encoding="utf-8") as f:
        for lineno, raw in enumerate(f, start=1):
            stripped = raw.strip()
            if not stripped:
                continue
            try:
                yield lineno, json.loads(stripped), None
            except json.JSONDecodeError as exc:
                yield lineno, None, f"JSON parse error: {exc.msg}"


# ---------------------------------------------------------------------------
# Error formatting
# ---------------------------------------------------------------------------


def _format_jsonschema_error(err: jsonschema.ValidationError) -> str:
    path = ".".join(str(p) for p in err.absolute_path) or "<root>"
    if err.validator == "required":
        return f"schema violation at {path}: {err.message}"
    return f"schema violation at {path}: {err.message}"


# ---------------------------------------------------------------------------
# Path-aware policy
# ---------------------------------------------------------------------------


def _is_under_generated(jsonl_path: Path) -> bool:
    """True iff the file lives under a `02-question-bank/generated` directory."""
    try:
        parts = jsonl_path.resolve().parts
    except OSError:
        parts = jsonl_path.parts
    for i in range(len(parts) - 1):
        if parts[i] == "02-question-bank" and parts[i + 1] == "generated":
            return True
    return False


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def validate_file(
    jsonl_path: Path,
    *,
    registered_sources: Sequence[str] | set[str] | None = None,
    allowed_scenarios: Sequence[str] | set[str] | None = None,
    schema_path: Path | None = None,
) -> ValidationReport:
    """Validate a question-bank JSONL file.

    Args:
        jsonl_path: path to the JSONL file.
        registered_sources: accepted values for `source`. If None, loads from
            the discovered `00-meta/source-register.md` (or an empty set).
        allowed_scenarios: accepted values for `scenario`. If None, loads from
            the discovered `00-meta/scenario-map.md` (or an empty set).
        schema_path: explicit path to a question schema JSON. If None, loads
            the package-shipped schema via `importlib.resources`.
    """

    if registered_sources is None:
        register = _resolve_meta_file("source-register.md", None)
        registered_sources = load_registered_sources(register) if register else set()
    registered: set[str] = set(registered_sources)

    if allowed_scenarios is None:
        scenario_map = _resolve_meta_file("scenario-map.md", None)
        allowed_scenarios = load_allowed_scenarios(scenario_map) if scenario_map else set()
    scenarios: set[str] = set(allowed_scenarios)

    if schema_path is not None:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
    else:
        schema = _default_question_schema()
    validator = jsonschema.Draft202012Validator(schema)

    is_generated_path = _is_under_generated(jsonl_path)

    report = ValidationReport()
    seen_ids: dict[str, int] = {}

    for lineno, record, parse_err in _iter_records(jsonl_path):
        if parse_err is not None:
            report.invalid_count += 1
            report.failures.append(Failure(line=lineno, question_id="<unparseable>", reason=parse_err))
            continue

        # Finding #5: a JSONL row must be a JSON object.
        if not isinstance(record, dict):
            report.invalid_count += 1
            kind = type(record).__name__
            report.failures.append(
                Failure(
                    line=lineno,
                    question_id="<non-object-row>",
                    reason=f"row is not an object (got JSON {kind})",
                )
            )
            continue

        qid = str(record.get("id", "<missing-id>"))

        # Schema check
        schema_errors = sorted(validator.iter_errors(record), key=lambda e: list(e.path))
        if schema_errors:
            report.invalid_count += 1
            report.failures.append(
                Failure(line=lineno, question_id=qid, reason=_format_jsonschema_error(schema_errors[0]))
            )
            continue

        # answer must reference a present choice key (defence-in-depth alongside the schema enum)
        if record["answer"] not in record["choices"]:
            report.invalid_count += 1
            report.failures.append(
                Failure(
                    line=lineno,
                    question_id=qid,
                    reason=f"answer '{record['answer']}' is not present in choices",
                )
            )
            continue

        # Source registration
        if registered and record["source"] not in registered:
            report.invalid_count += 1
            report.failures.append(
                Failure(
                    line=lineno,
                    question_id=qid,
                    reason=(
                        f"source '{record['source']}' is not registered in "
                        f"00-meta/source-register.md (active sources: {sorted(registered)})"
                    ),
                )
            )
            continue

        # Finding #3: scenario must exist in scenario-map.md
        if scenarios and record["scenario"] not in scenarios:
            report.invalid_count += 1
            report.failures.append(
                Failure(
                    line=lineno,
                    question_id=qid,
                    reason=(
                        f"scenario '{record['scenario']}' is not declared in "
                        f"00-meta/scenario-map.md"
                    ),
                )
            )
            continue

        # Finding #2: generated bank cannot ship status=official
        if is_generated_path and record["status"] == "official":
            report.invalid_count += 1
            report.failures.append(
                Failure(
                    line=lineno,
                    question_id=qid,
                    reason=(
                        "questions under 02-question-bank/generated/ must not "
                        "carry status='official' (spec V9)"
                    ),
                )
            )
            continue

        # Duplicate id check
        if qid in seen_ids:
            report.invalid_count += 1
            report.failures.append(
                Failure(
                    line=lineno,
                    question_id=qid,
                    reason=f"duplicate id (first seen on line {seen_ids[qid]})",
                )
            )
            continue

        seen_ids[qid] = lineno
        report.valid_count += 1

    return report


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m cca_f_study.validate_questions",
        description="Validate a CCA-F question-bank JSONL file.",
    )
    p.add_argument(
        "jsonl_path",
        type=Path,
        help="Path to the question-bank JSONL file.",
    )
    p.add_argument(
        "--schema",
        type=Path,
        default=None,
        help="Path to a question schema JSON (default: packaged schema).",
    )
    p.add_argument(
        "--source-register",
        type=Path,
        default=None,
        help="Path to source-register.md (default: discover under CWD or repo root).",
    )
    p.add_argument(
        "--scenario-map",
        type=Path,
        default=None,
        help="Path to scenario-map.md (default: discover under CWD or repo root).",
    )
    return p


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if not args.jsonl_path.exists():
        print(f"error: file not found: {args.jsonl_path}", file=sys.stderr)
        return 2

    register = _resolve_meta_file("source-register.md", args.source_register)
    if register is None:
        print(
            "warning: 00-meta/source-register.md not found; "
            "source-id check will be skipped",
            file=sys.stderr,
        )
        registered: set[str] = set()
    else:
        registered = load_registered_sources(register)

    scenario_map = _resolve_meta_file("scenario-map.md", args.scenario_map)
    if scenario_map is None:
        print(
            "warning: 00-meta/scenario-map.md not found; "
            "scenario check will be skipped",
            file=sys.stderr,
        )
        scenarios: set[str] = set()
    else:
        scenarios = load_allowed_scenarios(scenario_map)

    report = validate_file(
        args.jsonl_path,
        registered_sources=registered,
        allowed_scenarios=scenarios,
        schema_path=args.schema,
    )

    print(f"valid questions: {report.valid_count}")
    print(f"invalid questions: {report.invalid_count}")
    for failure in report.failures:
        print(f"  - line {failure.line} [{failure.question_id}]: {failure.reason}")

    return 0 if report.invalid_count == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
