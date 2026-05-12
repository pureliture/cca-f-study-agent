"""Normalize a learner's answers into a CCA-F attempt JSON file.

Reads a question-bank JSONL and an answers JSON, joins them on
``question_id``, computes per-answer correctness, and writes a
deterministic attempt JSON conforming to
``cca_f_study._schemas/attempt_schema.json`` (spec §6.2).

CLI surfaces
------------
    python -m cca_f_study.submit_attempt --questions ... --answers ... --out ...
    python 04-exam-runner/submit_attempt.py --questions ... --answers ... --out ...

Refuses to overwrite ``--out`` unless ``--force`` is passed (spec A5).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
from pathlib import Path
from typing import Any, Sequence


class SubmitError(RuntimeError):
    """Raised when an attempt cannot be normalized."""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


_NON_ALNUM = re.compile(r"[^A-Za-z0-9]+")


def _slug(value: str) -> str:
    """Lowercase, collapse non-alphanumerics into dashes, strip."""
    s = _NON_ALNUM.sub("-", value).strip("-").lower()
    return s or "attempt"


def _store_path(p: Path) -> str:
    """Return a POSIX-style path relative to cwd when possible.

    Falls back to the absolute POSIX form when ``p`` is not under cwd
    (e.g. different drives on Windows, or paths escaping cwd via ``..``).
    Using a relative path keeps the committed attempt JSON portable
    across machines (spec §6.2 example).
    """
    abs_p = p.resolve() if p.exists() else p.absolute()
    try:
        return abs_p.relative_to(Path.cwd().resolve()).as_posix()
    except ValueError:
        return abs_p.as_posix()


def compute_attempt_id(finished_at: str, attempt_label: str) -> str:
    """Deterministic attempt id from ``finished_at`` and ``attempt_label`` (spec A1).

    The colon characters in the ISO timestamp are replaced with dashes so the
    id is filesystem-safe; the format is otherwise stable across runs.
    """
    safe_ts = finished_at.replace(":", "-")
    return f"att-{safe_ts}-{_slug(attempt_label)}"


# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------


def _load_questions(path: Path) -> dict[str, dict]:
    """Return an insertion-ordered ``{id: question}`` map."""
    questions: dict[str, dict] = {}
    if not path.exists():
        raise SubmitError(f"question bank not found: {path}")
    with path.open(encoding="utf-8") as f:
        for lineno, raw in enumerate(f, start=1):
            stripped = raw.strip()
            if not stripped:
                continue
            try:
                record = json.loads(stripped)
            except json.JSONDecodeError as exc:
                raise SubmitError(f"{path}:{lineno} JSON parse error: {exc.msg}") from exc
            if not isinstance(record, dict):
                raise SubmitError(f"{path}:{lineno} row is not a JSON object")
            qid = record.get("id")
            if not isinstance(qid, str) or not qid:
                raise SubmitError(f"{path}:{lineno} missing or invalid 'id'")
            if qid in questions:
                raise SubmitError(f"duplicate question id in bank: {qid}")
            # Validate fields required by the normalization loop so a
            # malformed bank row produces a clean SubmitError rather than
            # a raw KeyError traceback.
            if "answer" not in record:
                raise SubmitError(f"{path}:{lineno} missing required field 'answer'")
            if record["answer"] not in ("A", "B", "C", "D"):
                raise SubmitError(
                    f"{path}:{lineno} invalid 'answer' (must be one of A,B,C,D)"
                )
            if "domain" not in record:
                raise SubmitError(f"{path}:{lineno} missing required field 'domain'")
            if record["domain"] not in ("D1", "D2", "D3", "D4", "D5"):
                raise SubmitError(
                    f"{path}:{lineno} invalid 'domain' (must be one of D1..D5)"
                )
            if "scenario" not in record:
                raise SubmitError(f"{path}:{lineno} missing required field 'scenario'")
            if not isinstance(record["scenario"], str) or not record["scenario"]:
                raise SubmitError(
                    f"{path}:{lineno} invalid 'scenario' (must be a non-empty string)"
                )
            if "concept_tags" not in record:
                raise SubmitError(
                    f"{path}:{lineno} missing required field 'concept_tags'"
                )
            if not isinstance(record["concept_tags"], list) or not all(
                isinstance(t, str) for t in record["concept_tags"]
            ):
                raise SubmitError(
                    f"{path}:{lineno} invalid 'concept_tags' (must be a list of strings)"
                )
            questions[qid] = record
    if not questions:
        raise SubmitError(f"question bank is empty: {path}")
    return questions


def _load_answers(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise SubmitError(f"answers file not found: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SubmitError(f"{path}: JSON parse error: {exc.msg}") from exc
    if not isinstance(data, dict):
        raise SubmitError(f"{path}: expected a JSON object at top level")
    for key in ("attempt_label", "started_at", "finished_at", "answers"):
        if key not in data:
            raise SubmitError(f"{path}: missing required key '{key}'")
    if (
        not isinstance(data["attempt_label"], str)
        or not data["attempt_label"].strip()
    ):
        raise SubmitError(
            f"{path}: 'attempt_label' must be a non-empty string"
        )
    if not isinstance(data["answers"], list):
        raise SubmitError(f"{path}: 'answers' must be an array")
    return data


# ---------------------------------------------------------------------------
# Core normalization
# ---------------------------------------------------------------------------


def submit(
    *,
    questions_path: Path,
    answers_path: Path,
    out_path: Path,
    force: bool = False,
) -> dict:
    """Normalize an answers JSON into an attempt JSON and write it.

    Returns the attempt dict that was written.

    Rules (spec §6.2):
      - A1: ``attempt_id`` deterministic from ``finished_at`` + ``attempt_label``.
      - A2: each answer carries the joined ``domain``, ``scenario``,
            ``concept_tags`` of its question.
      - A3: an unknown ``question_id`` aborts the submission.
      - A4: missing answers are recorded as ``{choice: null, is_correct: false}``.
      - A5: refuse to overwrite ``out_path`` unless ``force=True``.
    """
    if out_path.exists() and not force:
        raise SubmitError(
            f"refusing to overwrite existing file: {out_path} "
            "(pass --force or force=True to override)"
        )

    questions = _load_questions(questions_path)
    raw = _load_answers(answers_path)

    learner_choice: dict[str, str | None] = {}
    for entry in raw["answers"]:
        if not isinstance(entry, dict):
            raise SubmitError(f"{answers_path}: each answer must be a JSON object")
        qid = entry.get("question_id")
        choice = entry.get("choice", None)
        if not isinstance(qid, str):
            raise SubmitError(f"{answers_path}: 'question_id' must be a string")
        if qid not in questions:
            raise SubmitError(f"unknown question_id in answers: {qid}")
        if qid in learner_choice:
            raise SubmitError(f"duplicate question_id in answers: {qid}")
        if choice is not None and choice not in ("A", "B", "C", "D"):
            raise SubmitError(f"invalid choice '{choice}' for {qid} (must be A-D or null)")
        learner_choice[qid] = choice

    normalized: list[dict] = []
    correct_count = 0
    for qid, q in questions.items():  # bank order = stable output order
        choice = learner_choice.get(qid)
        correct = q["answer"]
        is_correct = choice == correct
        if is_correct:
            correct_count += 1
        normalized.append({
            "question_id": qid,
            "domain": q["domain"],
            "scenario": q["scenario"],
            "concept_tags": list(q["concept_tags"]),
            "choice": choice,
            "correct": correct,
            "is_correct": is_correct,
        })

    attempt = {
        "attempt_id": compute_attempt_id(raw["finished_at"], raw["attempt_label"]),
        "attempt_label": raw["attempt_label"],
        "started_at": raw["started_at"],
        "finished_at": raw["finished_at"],
        "question_bank_path": _store_path(questions_path),
        "answers": normalized,
        "totals": {
            "total": len(normalized),
            "correct": correct_count,
        },
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(attempt, ensure_ascii=False, indent=2, sort_keys=True) + "\n"

    # Atomic write: stream to a sibling temp file, fsync, then os.replace
    # which is atomic on POSIX. This avoids a torn out_path if the process
    # is killed mid-write and narrows the TOCTOU window for --force.
    tmp_fd, tmp_name = tempfile.mkstemp(
        prefix=out_path.name + ".",
        suffix=".tmp",
        dir=str(out_path.parent),
    )
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(tmp_fd, "w", encoding="utf-8") as tmp_file:
            tmp_file.write(serialized)
            tmp_file.flush()
            os.fsync(tmp_file.fileno())
        os.replace(tmp_path, out_path)
    except BaseException:
        # Best-effort cleanup; never mask the original exception.
        try:
            if tmp_path.exists():
                tmp_path.unlink()
        except OSError:
            pass
        raise
    return attempt


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m cca_f_study.submit_attempt",
        description="Normalize a learner's answers into a CCA-F attempt JSON file.",
    )
    p.add_argument("--questions", required=True, type=Path, help="Path to question-bank JSONL.")
    p.add_argument("--answers", required=True, type=Path, help="Path to answers JSON.")
    p.add_argument("--out", required=True, type=Path, help="Path to write attempt JSON.")
    p.add_argument("--force", action="store_true", help="Overwrite --out if it exists.")
    return p


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        attempt = submit(
            questions_path=args.questions,
            answers_path=args.answers,
            out_path=args.out,
            force=args.force,
        )
    except SubmitError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(f"attempt_id: {attempt['attempt_id']}")
    print(f"total: {attempt['totals']['total']}  correct: {attempt['totals']['correct']}")
    print(f"written: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
