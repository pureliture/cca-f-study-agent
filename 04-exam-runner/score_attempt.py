#!/usr/bin/env python3
"""Spec §10.3 invocation surface.

Thin wrapper that delegates to ``cca_f_study.score_attempt`` (installed
via ``pip install -e .``). The canonical CLI path

    python 04-exam-runner/score_attempt.py <attempt.json> [--json]

remains stable; the implementation lives in the package.
"""

from __future__ import annotations

import sys

from cca_f_study.score_attempt import main


if __name__ == "__main__":
    sys.exit(main())
