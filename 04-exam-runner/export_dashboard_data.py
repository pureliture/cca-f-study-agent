#!/usr/bin/env python3
"""Spec §10.4 invocation surface.

Thin wrapper that delegates to ``cca_f_study.export_dashboard_data``.

    python 04-exam-runner/export_dashboard_data.py \
        --attempts   05-learning-data/attempts \
        --lab-status 05-learning-data/lab-status.json \
        --out        06-dashboard/data/dashboard-data.json
"""

from __future__ import annotations

import sys

from cca_f_study.export_dashboard_data import main


if __name__ == "__main__":
    sys.exit(main())
