"""Regression coverage tests for `cca_f_study.submit_attempt`.

These tests make the existing guards in `submit()` explicit and protected.
Spec references: docs/specs/2026-05-cca-f-study-runtime-mvp.md §6.2 (A1-A5)
and §8.1 (attempt schema).

This file only CREATES new test cases against new fixtures; it does not
modify the implementation or the original test file.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from cca_f_study import submit_attempt as sa


REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURES = Path(__file__).parent / "fixtures" / "attempts"
QUESTIONS_SMALL = FIXTURES / "questions_small.jsonl"
ANSWERS_PARTIAL = FIXTURES / "answers_partial.json"
ANSWERS_UNKNOWN = FIXTURES / "answers_unknown_id.json"
ANSWERS_NULL_CHOICE = FIXTURES / "answers_null_choice.json"
ANSWERS_EMPTY = FIXTURES / "answers_empty.json"
ANSWERS_DUPLICATE = FIXTURES / "answers_duplicate_id.json"
ANSWERS_BAD_CHOICE = FIXTURES / "answers_bad_choice.json"

SAMPLE_ATTEMPT = REPO_ROOT / "05-learning-data" / "attempts" / "sample-attempt.json"


def _attempt_schema():
    import json
    from importlib.resources import files
    return json.loads(
        (files("cca_f_study._schemas") / "attempt_schema.json").read_text(encoding="utf-8")
    )


def _read(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Section A — Schema compliance for the partial-answer (null-choice) path
# ---------------------------------------------------------------------------


def test_partial_attempt_output_validates_against_attempt_schema(tmp_path):
    import jsonschema

    out = tmp_path / "attempt.json"
    sa.submit(
        questions_path=QUESTIONS_SMALL,
        answers_path=ANSWERS_PARTIAL,
        out_path=out,
    )
    data = _read(out)
    # The partial fixture omits Q2, so A4 should fill that as choice=null.
    nulls = [a for a in data["answers"] if a["choice"] is None]
    assert nulls, (
        "Partial fixture is expected to produce at least one null choice "
        "so that the schema's anyOf [enum, null] branch is exercised."
    )
    jsonschema.Draft202012Validator(_attempt_schema()).validate(data)


# ---------------------------------------------------------------------------
# Section B — Explicit null choice in the learner's answers file
# ---------------------------------------------------------------------------


def test_explicit_null_choice_treated_as_unanswered(tmp_path):
    out = tmp_path / "attempt.json"
    sa.submit(
        questions_path=QUESTIONS_SMALL,
        answers_path=ANSWERS_NULL_CHOICE,
        out_path=out,
    )
    data = _read(out)
    by_id = {a["question_id"]: a for a in data["answers"]}
    assert by_id["Q1"]["choice"] is None
    assert by_id["Q1"]["is_correct"] is False
    assert by_id["Q2"]["choice"] == "B"
    assert by_id["Q2"]["is_correct"] is True
    assert by_id["Q3"]["choice"] == "C"
    assert by_id["Q3"]["is_correct"] is True
    assert data["totals"] == {"total": 3, "correct": 2}


def test_explicit_null_choice_output_passes_schema_validation(tmp_path):
    import jsonschema

    out = tmp_path / "attempt.json"
    sa.submit(
        questions_path=QUESTIONS_SMALL,
        answers_path=ANSWERS_NULL_CHOICE,
        out_path=out,
    )
    jsonschema.Draft202012Validator(_attempt_schema()).validate(_read(out))


# ---------------------------------------------------------------------------
# Section C — Empty answers list
# ---------------------------------------------------------------------------


def test_empty_answers_fills_all_with_null(tmp_path):
    import jsonschema

    out = tmp_path / "attempt.json"
    sa.submit(
        questions_path=QUESTIONS_SMALL,
        answers_path=ANSWERS_EMPTY,
        out_path=out,
    )
    data = _read(out)
    assert data["totals"] == {"total": 3, "correct": 0}
    for ans in data["answers"]:
        assert ans["choice"] is None
        assert ans["is_correct"] is False
    jsonschema.Draft202012Validator(_attempt_schema()).validate(data)


# ---------------------------------------------------------------------------
# Section D — Duplicate `question_id` inside the answers file
# ---------------------------------------------------------------------------


def test_duplicate_question_id_in_answers_aborts(tmp_path):
    out = tmp_path / "attempt.json"
    with pytest.raises(sa.SubmitError) as exc:
        sa.submit(
            questions_path=QUESTIONS_SMALL,
            answers_path=ANSWERS_DUPLICATE,
            out_path=out,
        )
    msg = str(exc.value).lower()
    assert "duplicate" in msg
    assert "q1" in msg
    assert not out.exists(), "No attempt file should be written on abort"


# ---------------------------------------------------------------------------
# Section E — Invalid choice value (non-A/B/C/D)
# ---------------------------------------------------------------------------


def test_invalid_choice_value_aborts(tmp_path):
    out = tmp_path / "attempt.json"
    with pytest.raises(sa.SubmitError) as exc:
        sa.submit(
            questions_path=QUESTIONS_SMALL,
            answers_path=ANSWERS_BAD_CHOICE,
            out_path=out,
        )
    assert "'E'" in str(exc.value)
    assert not out.exists(), "No attempt file should be written on abort"


# ---------------------------------------------------------------------------
# Section F — Tighten the dead `or "missing"` branch
# ---------------------------------------------------------------------------


def test_unknown_question_id_error_message_names_the_id(tmp_path):
    out = tmp_path / "attempt.json"
    with pytest.raises(sa.SubmitError) as exc:
        sa.submit(
            questions_path=QUESTIONS_SMALL,
            answers_path=ANSWERS_UNKNOWN,
            out_path=out,
        )
    assert "QX-NONE" in str(exc.value)
    assert not out.exists()


# ---------------------------------------------------------------------------
# Section G — Committed sample-attempt.json schema conformance (Spec CC6)
# ---------------------------------------------------------------------------


def test_committed_sample_attempt_validates_against_schema():
    import jsonschema

    if not SAMPLE_ATTEMPT.exists():
        pytest.skip("sample-attempt.json not produced yet")
    data = json.loads(SAMPLE_ATTEMPT.read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator(_attempt_schema()).validate(data)
