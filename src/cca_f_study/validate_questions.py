"""Validate a CCA-F question-bank JSONL file against `question_schema.json`.

CLI:
    python -m cca_f_study.validate_questions <path-to-questions.jsonl>

Exit code 0 on full success, non-zero if any line fails validation.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Sequence

import jsonschema


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SCHEMA_PATH = REPO_ROOT / "04-exam-runner" / "question_schema.json"
DEFAULT_SOURCE_REGISTER = REPO_ROOT / "00-meta" / "source-register.md"


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
# Source-register loader
# ---------------------------------------------------------------------------


_SOURCE_IDS_HEADER = re.compile(r"^##\s+Source IDs\s*$", re.IGNORECASE)
_NEXT_SECTION = re.compile(r"^##\s+")
# Match table rows like: | `guide_en` | active | en | `path` |
_SOURCE_ROW = re.compile(
    r"^\|\s*`([A-Za-z0-9_-]+)`\s*\|\s*([A-Za-z_]+)\s*\|",
)


def load_registered_sources(register_path: Path) -> set[str]:
    """Return the set of source IDs marked `active` in `source-register.md`.

    The register's "## Source IDs" section contains a table whose first
    column is the source id (in backticks) and whose second column is the
    status. Only `active` rows are treated as registered.

    Reserved-only IDs (e.g. mentioned in a blockquote outside the table) are
    deliberately excluded — the MVP only validates against currently active
    sources.
    """

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


# ---------------------------------------------------------------------------
# Schema validation
# ---------------------------------------------------------------------------


def _load_schema(schema_path: Path) -> dict:
    return json.loads(schema_path.read_text(encoding="utf-8"))


def _iter_records(jsonl_path: Path) -> Iterable[tuple[int, dict | None, str | None]]:
    """Yield (line_number, parsed_record_or_None, parse_error_or_None)."""

    with jsonl_path.open(encoding="utf-8") as f:
        for lineno, raw in enumerate(f, start=1):
            stripped = raw.strip()
            if not stripped:
                continue
            try:
                yield lineno, json.loads(stripped), None
            except json.JSONDecodeError as exc:
                yield lineno, None, f"JSON parse error: {exc.msg}"


def _format_jsonschema_error(err: jsonschema.ValidationError) -> str:
    path = ".".join(str(p) for p in err.absolute_path) or "<root>"
    # Surface the offending field name when validation is for `required`.
    if err.validator == "required":
        missing = err.message
        return f"schema violation at {path}: {missing}"
    return f"schema violation at {path}: {err.message}"


def validate_file(
    jsonl_path: Path,
    registered_sources: Sequence[str] | set[str] | None = None,
    schema_path: Path = DEFAULT_SCHEMA_PATH,
) -> ValidationReport:
    """Validate a question-bank JSONL file.

    Args:
        jsonl_path: path to the JSONL file.
        registered_sources: collection of source ids accepted for the `source`
            field. If None, loads from the default source register.
        schema_path: path to the JSON Schema for a single question record.
    """

    if registered_sources is None:
        registered_sources = load_registered_sources(DEFAULT_SOURCE_REGISTER)
    registered = set(registered_sources)

    schema = _load_schema(schema_path)
    validator = jsonschema.Draft202012Validator(schema)

    report = ValidationReport()
    seen_ids: dict[str, int] = {}

    for lineno, record, parse_err in _iter_records(jsonl_path):
        if parse_err is not None:
            report.invalid_count += 1
            report.failures.append(Failure(line=lineno, question_id="<unparseable>", reason=parse_err))
            continue

        assert record is not None
        qid = str(record.get("id", "<missing-id>"))

        # Schema check
        schema_errors = sorted(validator.iter_errors(record), key=lambda e: e.path)
        if schema_errors:
            report.invalid_count += 1
            report.failures.append(
                Failure(line=lineno, question_id=qid, reason=_format_jsonschema_error(schema_errors[0]))
            )
            continue

        # Cross-field: answer must be a key of choices (schema enforces enum A-D
        # but not the conjunction). We re-check explicitly for a clearer error.
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
        if record["source"] not in registered:
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
        default=DEFAULT_SCHEMA_PATH,
        help="Path to question_schema.json (default: 04-exam-runner/question_schema.json).",
    )
    p.add_argument(
        "--source-register",
        type=Path,
        default=DEFAULT_SOURCE_REGISTER,
        help="Path to source-register.md (default: 00-meta/source-register.md).",
    )
    return p


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if not args.jsonl_path.exists():
        print(f"error: file not found: {args.jsonl_path}", file=sys.stderr)
        return 2

    registered = load_registered_sources(args.source_register)
    report = validate_file(args.jsonl_path, registered_sources=registered, schema_path=args.schema)

    print(f"valid questions: {report.valid_count}")
    print(f"invalid questions: {report.invalid_count}")
    for failure in report.failures:
        print(f"  - line {failure.line} [{failure.question_id}]: {failure.reason}")

    return 0 if report.invalid_count == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
