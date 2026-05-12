"""Tests for `cca_f_study.submit_attempt`.

Covers spec §6.2 normalization rules and the two CLI surfaces required
by the plan: `python -m cca_f_study.submit_attempt` and
`python 04-exam-runner/submit_attempt.py`.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from cca_f_study import submit_attempt as sa


REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURES = Path(__file__).parent / "fixtures" / "attempts"
QUESTIONS_SMALL = FIXTURES / "questions_small.jsonl"
ANSWERS_COMPLETE = FIXTURES / "answers_complete.json"
ANSWERS_PARTIAL = FIXTURES / "answers_partial.json"
ANSWERS_UNKNOWN = FIXTURES / "answers_unknown_id.json"


# ---------------------------------------------------------------------------
# attempt_id
# ---------------------------------------------------------------------------


def test_attempt_id_is_deterministic():
    a = sa.compute_attempt_id("2026-05-11T10:00:00Z", "self-mock-001")
    b = sa.compute_attempt_id("2026-05-11T10:00:00Z", "self-mock-001")
    assert a == b


def test_attempt_id_matches_spec_example():
    assert (
        sa.compute_attempt_id("2026-05-11T10:00:00Z", "self-mock-001")
        == "att-2026-05-11T10-00-00Z-self-mock-001"
    )


def test_attempt_id_changes_with_label():
    a = sa.compute_attempt_id("2026-05-11T10:00:00Z", "label-a")
    b = sa.compute_attempt_id("2026-05-11T10:00:00Z", "label-b")
    assert a != b


# ---------------------------------------------------------------------------
# Joining + correctness
# ---------------------------------------------------------------------------


def _read(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8"))


def test_answers_are_joined_with_domain_scenario_tags(tmp_path):
    out = tmp_path / "attempt.json"
    sa.submit(questions_path=QUESTIONS_SMALL, answers_path=ANSWERS_COMPLETE, out_path=out)
    data = _read(out)
    for ans in data["answers"]:
        assert "domain" in ans and ans["domain"] in {"D1", "D2", "D3", "D4", "D5"}
        assert "scenario" in ans and isinstance(ans["scenario"], str)
        assert "concept_tags" in ans and isinstance(ans["concept_tags"], list)


def test_correctness_flag_matches_answer_key(tmp_path):
    out = tmp_path / "attempt.json"
    sa.submit(questions_path=QUESTIONS_SMALL, answers_path=ANSWERS_COMPLETE, out_path=out)
    data = _read(out)
    for ans in data["answers"]:
        assert ans["is_correct"] is (ans["choice"] == ans["correct"])


def test_complete_attempt_totals(tmp_path):
    out = tmp_path / "attempt.json"
    sa.submit(questions_path=QUESTIONS_SMALL, answers_path=ANSWERS_COMPLETE, out_path=out)
    data = _read(out)
    # Q1=A correct, Q2 chose D (correct=B) wrong, Q3=C correct → 2/3
    assert data["totals"] == {"total": 3, "correct": 2}


# ---------------------------------------------------------------------------
# Partial answers
# ---------------------------------------------------------------------------


def test_missing_answers_filled_with_null_and_marked_incorrect(tmp_path):
    out = tmp_path / "attempt.json"
    sa.submit(questions_path=QUESTIONS_SMALL, answers_path=ANSWERS_PARTIAL, out_path=out)
    data = _read(out)
    assert data["totals"]["total"] == 3
    nulls = [a for a in data["answers"] if a["choice"] is None]
    assert len(nulls) == 1
    assert nulls[0]["question_id"] == "Q2"
    assert nulls[0]["is_correct"] is False


# ---------------------------------------------------------------------------
# Error paths
# ---------------------------------------------------------------------------


def test_unknown_question_id_aborts(tmp_path):
    out = tmp_path / "attempt.json"
    with pytest.raises(sa.SubmitError) as exc:
        sa.submit(questions_path=QUESTIONS_SMALL, answers_path=ANSWERS_UNKNOWN, out_path=out)
    msg = str(exc.value).lower()
    assert "unknown" in msg or "missing" in msg
    assert not out.exists(), "No attempt file should be written on abort"


def test_overwrite_refused_without_force(tmp_path):
    out = tmp_path / "attempt.json"
    out.write_text("{}", encoding="utf-8")
    with pytest.raises(sa.SubmitError):
        sa.submit(questions_path=QUESTIONS_SMALL, answers_path=ANSWERS_COMPLETE, out_path=out)
    assert out.read_text(encoding="utf-8") == "{}", "Existing content must be preserved"


def test_overwrite_allowed_with_force(tmp_path):
    out = tmp_path / "attempt.json"
    out.write_text("{}", encoding="utf-8")
    sa.submit(
        questions_path=QUESTIONS_SMALL,
        answers_path=ANSWERS_COMPLETE,
        out_path=out,
        force=True,
    )
    assert _read(out)["totals"]["total"] == 3


# ---------------------------------------------------------------------------
# Schema compliance + determinism
# ---------------------------------------------------------------------------


def test_output_validates_against_attempt_schema(tmp_path):
    import jsonschema
    from importlib.resources import files

    out = tmp_path / "attempt.json"
    sa.submit(questions_path=QUESTIONS_SMALL, answers_path=ANSWERS_COMPLETE, out_path=out)
    schema = json.loads(
        (files("cca_f_study._schemas") / "attempt_schema.json").read_text(encoding="utf-8")
    )
    jsonschema.Draft202012Validator(schema).validate(_read(out))


def test_output_is_byte_identical_across_runs(tmp_path):
    a = tmp_path / "a.json"
    b = tmp_path / "b.json"
    sa.submit(questions_path=QUESTIONS_SMALL, answers_path=ANSWERS_COMPLETE, out_path=a)
    sa.submit(questions_path=QUESTIONS_SMALL, answers_path=ANSWERS_COMPLETE, out_path=b)
    assert a.read_bytes() == b.read_bytes()


# ---------------------------------------------------------------------------
# CLI surfaces
# ---------------------------------------------------------------------------


def test_cli_via_python_dash_m(tmp_path):
    out = tmp_path / "attempt.json"
    proc = subprocess.run(
        [
            sys.executable, "-m", "cca_f_study.submit_attempt",
            "--questions", str(QUESTIONS_SMALL),
            "--answers", str(ANSWERS_COMPLETE),
            "--out", str(out),
        ],
        capture_output=True, text=True, cwd=REPO_ROOT,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert out.exists()
    assert "attempt_id:" in proc.stdout


def test_cli_via_04_exam_runner_wrapper(tmp_path):
    """Spec §10.2 invocation: python 04-exam-runner/submit_attempt.py …"""
    out = tmp_path / "attempt.json"
    proc = subprocess.run(
        [
            sys.executable, str(REPO_ROOT / "04-exam-runner" / "submit_attempt.py"),
            "--questions", str(QUESTIONS_SMALL),
            "--answers", str(ANSWERS_COMPLETE),
            "--out", str(out),
        ],
        capture_output=True, text=True, cwd=REPO_ROOT,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert out.exists()


def test_cli_overwrite_guard_exits_nonzero(tmp_path):
    out = tmp_path / "attempt.json"
    out.write_text("{}", encoding="utf-8")
    proc = subprocess.run(
        [
            sys.executable, "-m", "cca_f_study.submit_attempt",
            "--questions", str(QUESTIONS_SMALL),
            "--answers", str(ANSWERS_COMPLETE),
            "--out", str(out),
        ],
        capture_output=True, text=True, cwd=REPO_ROOT,
    )
    assert proc.returncode != 0
    assert out.read_text(encoding="utf-8") == "{}"


# ---------------------------------------------------------------------------
# Regression tests for review fixes (malformed bank, atomic write, label
# validation, portable question_bank_path).
# ---------------------------------------------------------------------------


def test_malformed_bank_row_raises_submit_error(tmp_path):
    """Fix 1: a bank row missing 'answer' must raise SubmitError (not KeyError)."""
    bad_bank = tmp_path / "bad_bank.jsonl"
    # Q1 is valid; Q2 (line 2) is malformed — missing required 'answer'.
    bad_bank.write_text(
        '{"id":"Q1","source":"g","domain":"D1","scenario":"s","difficulty":"easy",'
        '"stem":"s","choices":{"A":"a","B":"b","C":"c","D":"d"},"answer":"A",'
        '"explanation":"e","concept_tags":[],"status":"official"}\n'
        '{"id":"Q2","stem":"only-stem"}\n',
        encoding="utf-8",
    )
    out = tmp_path / "attempt.json"
    with pytest.raises(sa.SubmitError) as exc:
        sa.submit(questions_path=bad_bank, answers_path=ANSWERS_COMPLETE, out_path=out)
    msg = str(exc.value)
    assert ":2" in msg, f"expected line number in error message, got: {msg}"
    assert "answer" in msg, f"expected missing field name in error message, got: {msg}"
    assert not out.exists()


def test_atomic_write_does_not_leave_tmp_on_success(tmp_path):
    """Fix 2: after a successful write, no sibling .tmp file remains."""
    out = tmp_path / "attempt.json"
    sa.submit(questions_path=QUESTIONS_SMALL, answers_path=ANSWERS_COMPLETE, out_path=out)
    assert out.exists()
    leftovers = [p for p in tmp_path.iterdir() if p.name != out.name]
    assert leftovers == [], f"unexpected sibling files after atomic write: {leftovers}"
    # Specifically: no *.tmp anywhere in the parent.
    assert list(tmp_path.glob("*.tmp")) == []


def test_atomic_write_cleans_tmp_on_error(tmp_path):
    """Fix 2: if the rename fails, the .tmp file must not be left behind.

    We make the rename fail by making out_path a directory — os.replace
    cannot replace a non-empty directory with a file on POSIX.
    """
    out = tmp_path / "attempt.json"
    out.mkdir()
    (out / "marker").write_text("blocker", encoding="utf-8")
    with pytest.raises(Exception):
        sa.submit(
            questions_path=QUESTIONS_SMALL,
            answers_path=ANSWERS_COMPLETE,
            out_path=out,
            force=True,
        )
    assert list(tmp_path.glob("*.tmp")) == []


def test_empty_attempt_label_aborts(tmp_path):
    """Fix 3: an empty attempt_label must be rejected before any write."""
    answers = tmp_path / "answers.json"
    answers.write_text(
        json.dumps(
            {
                "attempt_label": "",
                "started_at": "2026-05-11T09:00:00Z",
                "finished_at": "2026-05-11T10:00:00Z",
                "answers": [
                    {"question_id": "Q1", "choice": "A"},
                    {"question_id": "Q2", "choice": "B"},
                    {"question_id": "Q3", "choice": "C"},
                ],
            }
        ),
        encoding="utf-8",
    )
    out = tmp_path / "attempt.json"
    with pytest.raises(sa.SubmitError) as exc:
        sa.submit(questions_path=QUESTIONS_SMALL, answers_path=answers, out_path=out)
    assert "attempt_label" in str(exc.value)
    assert not out.exists()


def test_whitespace_only_attempt_label_aborts(tmp_path):
    """Fix 3: whitespace-only attempt_label must also be rejected."""
    answers = tmp_path / "answers.json"
    answers.write_text(
        json.dumps(
            {
                "attempt_label": "   ",
                "started_at": "2026-05-11T09:00:00Z",
                "finished_at": "2026-05-11T10:00:00Z",
                "answers": [
                    {"question_id": "Q1", "choice": "A"},
                    {"question_id": "Q2", "choice": "B"},
                    {"question_id": "Q3", "choice": "C"},
                ],
            }
        ),
        encoding="utf-8",
    )
    out = tmp_path / "attempt.json"
    with pytest.raises(sa.SubmitError):
        sa.submit(questions_path=QUESTIONS_SMALL, answers_path=answers, out_path=out)
    assert not out.exists()


def test_question_bank_path_is_relative_when_under_cwd(tmp_path, monkeypatch):
    """Fix 4: when --questions is under cwd, the stored path is POSIX-relative."""
    monkeypatch.chdir(REPO_ROOT)
    out = tmp_path / "attempt.json"
    # QUESTIONS_SMALL is an absolute path under REPO_ROOT.
    sa.submit(
        questions_path=QUESTIONS_SMALL,
        answers_path=ANSWERS_COMPLETE,
        out_path=out,
    )
    stored = _read(out)["question_bank_path"]
    assert not stored.startswith("/"), f"expected relative path, got: {stored}"
    assert str(REPO_ROOT) not in stored, f"abs repo prefix leaked: {stored}"
    assert stored == "tests/fixtures/attempts/questions_small.jsonl"


def test_committed_sample_attempt_stores_relative_question_bank_path():
    """Fix 4: the committed sample attempt uses the spec's relative path form."""
    sample = REPO_ROOT / "05-learning-data" / "attempts" / "sample-attempt.json"
    data = json.loads(sample.read_text(encoding="utf-8"))
    assert data["question_bank_path"] == "02-question-bank/seed/sample-questions.jsonl"
