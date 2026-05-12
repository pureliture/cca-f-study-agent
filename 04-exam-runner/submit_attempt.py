#!/usr/bin/env python3
"""Spec §10.2 invocation surface.

This script is a thin wrapper that delegates to
``cca_f_study.submit_attempt`` (installed via ``pip install -e .``).
Keep the implementation in the package; this file only re-exports the
entry point so the canonical CLI path

    python 04-exam-runner/submit_attempt.py --questions ... --answers ... --out ...

continues to work without duplicating logic.
"""

from __future__ import annotations

import sys

from cca_f_study.submit_attempt import main


if __name__ == "__main__":
    sys.exit(main())
