"""R2 lockdown: runtime entrypoints open no network sockets.

Monkeypatches ``socket.socket`` and ``urllib.request.urlopen``, then
calls each module's ``main()`` and asserts the calls succeed without
triggering the patched-out network primitives.
"""

from __future__ import annotations

import socket
import urllib.request
from pathlib import Path

import pytest

from cca_f_study import validate_questions as vq
from cca_f_study import submit_attempt as sa
from cca_f_study import score_attempt as score
from cca_f_study import export_dashboard_data as ed


REPO_ROOT = Path(__file__).resolve().parents[1]
SEED_BANK = REPO_ROOT / "02-question-bank" / "seed" / "sample-questions.jsonl"
SAMPLE_ANSWERS = REPO_ROOT / "examples" / "attempts" / "sample-answers.json"
LAB_STATUS = REPO_ROOT / "05-learning-data" / "lab-status.json"
SAMPLE_ATTEMPT = REPO_ROOT / "05-learning-data" / "attempts" / "sample-attempt.json"
FROZEN_NOW = "2026-05-12T00:30:00Z"


@pytest.fixture()
def network_blocked(monkeypatch):
    def _boom(*a, **kw):
        raise AssertionError("runtime must not open a network socket")
    monkeypatch.setattr(socket, "socket", _boom)
    monkeypatch.setattr(urllib.request, "urlopen", _boom)
    yield


def test_validate_questions_does_not_use_network(network_blocked, tmp_path, monkeypatch):
    # Run from repo root so the validator can find 00-meta/*.md via cwd resolution.
    monkeypatch.chdir(REPO_ROOT)
    rc = vq.main([str(SEED_BANK)])
    assert rc == 0


def test_submit_attempt_does_not_use_network(network_blocked, tmp_path, monkeypatch):
    monkeypatch.chdir(REPO_ROOT)
    out = tmp_path / "att.json"
    rc = sa.main([
        "--questions", str(SEED_BANK),
        "--answers",   str(SAMPLE_ANSWERS),
        "--out",       str(out),
    ])
    assert rc == 0
    assert out.exists()


def test_score_attempt_does_not_use_network(network_blocked, monkeypatch):
    monkeypatch.chdir(REPO_ROOT)
    rc = score.main([str(SAMPLE_ATTEMPT)])
    assert rc == 0


def test_export_dashboard_data_does_not_use_network(network_blocked, tmp_path, monkeypatch):
    monkeypatch.chdir(REPO_ROOT)
    out = tmp_path / "dashboard-data.json"
    rc = ed.main([
        "--attempts",   str(REPO_ROOT / "05-learning-data" / "attempts"),
        "--lab-status", str(LAB_STATUS),
        "--out",        str(out),
        "--now",        FROZEN_NOW,
    ])
    assert rc == 0
    assert out.exists()
