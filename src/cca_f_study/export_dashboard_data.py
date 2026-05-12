"""Export the deterministic ``dashboard-data.json`` consumed by the static
dashboard (spec §8, §10.4).

CLI surfaces
------------
    python -m cca_f_study.export_dashboard_data \
        --attempts   <dir> \
        --lab-status <path> \
        --out        <path> \
       [--now        <ISO-8601 UTC>] \
       [--domain-map <path>]

    python 04-exam-runner/export_dashboard_data.py …

``--now`` controls the value emitted as ``generated_at``. Pass it
explicitly to obtain a byte-identical output (spec §8.2 C7); when
omitted, the current UTC time is used.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

from cca_f_study import _aggregate


class ExportError(RuntimeError):
    """Raised when export inputs are missing or malformed."""


DEFAULT_DOMAIN_MAP = Path(__file__).resolve().parents[2] / "00-meta" / "domain-map.md"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def export(
    *,
    attempts_dir: Path,
    lab_status_path: Path,
    out_path: Path,
    now_iso: str | None = None,
    domain_map_path: Path | None = None,
) -> dict:
    """Aggregate attempts + lab status into ``dashboard-data.json`` and write it.

    Returns the written dashboard dict.
    """
    # Fix 6: validate caller-supplied --now is parseable ISO-8601 so we
    # don't bake garbage into generated_at.
    if now_iso is not None:
        try:
            datetime.fromisoformat(now_iso.replace("Z", "+00:00"))
        except (TypeError, ValueError) as exc:
            raise ExportError(
                f"--now is not a valid ISO-8601 UTC timestamp: {now_iso!r} ({exc})"
            ) from exc

    attempts = _aggregate.iter_attempts(Path(attempts_dir))
    labs = _aggregate.load_lab_status(Path(lab_status_path))
    domain_map_p = Path(domain_map_path) if domain_map_path else DEFAULT_DOMAIN_MAP
    domain_map = _aggregate.load_domain_map(domain_map_p)

    resolved_now = now_iso or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    data = _aggregate.build_dashboard_data(
        attempts=attempts,
        labs=labs,
        domain_map=domain_map,
        now_iso=resolved_now,
    )

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n"

    # Atomic write: stream to a sibling temp file, fsync, then os.replace
    # which is atomic on POSIX. Mirrors submit_attempt.submit so a SIGINT
    # or disk-full mid-write cannot leave a torn dashboard-data.json.
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
    return data


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m cca_f_study.export_dashboard_data",
        description="Aggregate attempts + lab status into dashboard-data.json (spec §8).",
    )
    p.add_argument("--attempts", required=True, type=Path, help="Directory of attempt JSON files.")
    p.add_argument("--lab-status", required=True, type=Path, help="Path to lab-status.json.")
    p.add_argument("--out", required=True, type=Path, help="Output dashboard-data.json path.")
    p.add_argument(
        "--now",
        type=str,
        default=None,
        help="ISO-8601 UTC timestamp to use as 'generated_at' (omit for current time).",
    )
    p.add_argument(
        "--domain-map",
        type=Path,
        default=None,
        help="Path to 00-meta/domain-map.md (default: repo-root domain map).",
    )
    return p


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        data = export(
            attempts_dir=args.attempts,
            lab_status_path=args.lab_status,
            out_path=args.out,
            now_iso=args.now,
            domain_map_path=args.domain_map,
        )
    except ExportError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    n_attempts = len(data.get("trend", []))
    print(f"generated_at: {data['generated_at']}")
    print(f"attempts aggregated: {n_attempts}")
    print(f"written: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
