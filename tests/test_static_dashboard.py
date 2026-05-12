"""Static-parser tests for the Phase 8 dashboard (spec §9, §10.6).

The dashboard is a vanilla HTML+CSS+JS triple under `06-dashboard/static/`.
These tests do **not** spin up a browser; they assert the structural and
safety contract by parsing the source files directly, so they can run in
any CI environment without a headless browser.

Pinned contract (informs both this test file and the frontend agent's
brief):

- The page contains seven widget sections, each anchored by a stable
  ``id`` attribute. The seven ids are listed in ``WIDGET_IDS`` below.
- ``app.js`` fetches ``../data/dashboard-data.json`` (relative to the
  static dir's parent) — the *only* runtime input.
- No external URLs (HTTP/HTTPS/CDN) are referenced from any of the
  three files; the dashboard must work fully offline.
- No build artifacts: no ``package.json`` under ``06-dashboard/``.
- Empty-state guard: ``app.js`` references ``latest_attempt`` in a way
  that suggests it handles the ``null`` case.
"""

from __future__ import annotations

import re
from html.parser import HTMLParser
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
DASHBOARD_ROOT = REPO_ROOT / "06-dashboard"
STATIC_ROOT = DASHBOARD_ROOT / "static"
INDEX_HTML = STATIC_ROOT / "index.html"
APP_JS = STATIC_ROOT / "app.js"
STYLE_CSS = STATIC_ROOT / "style.css"


# The seven widget ids the static dashboard must expose. Pinning them
# here lets the frontend evolve internally while keeping the test
# contract stable for downstream automation.
WIDGET_IDS: tuple[str, ...] = (
    "pass-banner",        # 1. Pass/fail banner + scaled_score + pass_gap
    "pass-progress",      # 2. Progress bar toward 720
    "domain-breakdown",   # 3. Domain (D1-D5) breakdown
    "scenario-breakdown", # 4. Scenario breakdown
    "weak-concepts",      # 5. Weak concepts top-N
    "lab-progress",       # 6. Lab progress + recommended_next
    "score-trend",        # 7. Score trend (sparkline / line)
)


# ---------------------------------------------------------------------------
# File presence
# ---------------------------------------------------------------------------


def test_static_triple_exists():
    assert INDEX_HTML.exists(), f"missing {INDEX_HTML.relative_to(REPO_ROOT)}"
    assert APP_JS.exists(), f"missing {APP_JS.relative_to(REPO_ROOT)}"
    assert STYLE_CSS.exists(), f"missing {STYLE_CSS.relative_to(REPO_ROOT)}"


def test_no_package_json_under_dashboard():
    """No build artifacts: rules out a Node toolchain (CLAUDE.md R4)."""
    pkg = DASHBOARD_ROOT / "package.json"
    assert not pkg.exists(), f"unexpected build manifest at {pkg.relative_to(REPO_ROOT)}"
    node_modules = DASHBOARD_ROOT / "node_modules"
    assert not node_modules.exists(), "node_modules must not be vendored under 06-dashboard/"


# ---------------------------------------------------------------------------
# HTML structure
# ---------------------------------------------------------------------------


class _IdCollector(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.ids: set[str] = set()

    def handle_starttag(self, tag: str, attrs) -> None:
        for k, v in attrs:
            if k == "id" and v:
                self.ids.add(v)


def _parsed_ids() -> set[str]:
    parser = _IdCollector()
    parser.feed(INDEX_HTML.read_text(encoding="utf-8"))
    return parser.ids


def test_html_declares_all_seven_widget_anchors():
    ids = _parsed_ids()
    missing = [w for w in WIDGET_IDS if w not in ids]
    assert not missing, f"index.html is missing widget anchors: {missing}"


def test_html_loads_app_js_and_style_css():
    html = INDEX_HTML.read_text(encoding="utf-8")
    assert "app.js" in html, "index.html must include <script src=\"app.js\"> (or similar)"
    assert "style.css" in html, "index.html must include <link href=\"style.css\"> (or similar)"


def test_html_charset_is_utf8():
    html = INDEX_HTML.read_text(encoding="utf-8").lower()
    # Accept either <meta charset="utf-8"> or http-equiv form.
    assert "utf-8" in html, "page should declare a UTF-8 charset"


# ---------------------------------------------------------------------------
# app.js contract
# ---------------------------------------------------------------------------


def _app_js_text() -> str:
    return APP_JS.read_text(encoding="utf-8")


def test_app_js_fetches_relative_dashboard_data():
    text = _app_js_text()
    # Allow either single- or double-quoted string forms.
    pattern = re.compile(r"""fetch\(\s*['"]\.\./data/dashboard-data\.json['"]""")
    assert pattern.search(text), (
        "app.js must call fetch('../data/dashboard-data.json'); the only "
        "runtime input is the exported JSON sibling to the static dir."
    )


def test_app_js_handles_empty_latest_attempt():
    """Empty-state guard: when no attempts exist, ``latest_attempt`` is null.

    The check is intentionally coarse: any expression that compares
    ``latest_attempt`` to null/undefined or guards a falsy lookup is
    accepted.
    """
    text = _app_js_text()
    candidates = (
        "latest_attempt == null",
        "latest_attempt === null",
        "latest_attempt == undefined",
        "latest_attempt === undefined",
        "!latest_attempt",
        "latest_attempt ?",
        "latest_attempt &&",
        "latest_attempt || ",
        "?.latest_attempt",
    )
    assert any(c in text for c in candidates), (
        "app.js must guard against latest_attempt being null/undefined. "
        f"Tried: {candidates}"
    )


# ---------------------------------------------------------------------------
# No external URLs / no CDN
# ---------------------------------------------------------------------------


_EXTERNAL_URL_RE = re.compile(r"\bhttps?://[^\s\"'`)<>]+", re.IGNORECASE)


def _filter_real_externals(matches: list[str]) -> list[str]:
    """Strip schema/namespace URLs that do not represent a runtime fetch."""
    allowed_prefixes = (
        "http://www.w3.org/",        # SVG / XML / XHTML namespaces
        "https://www.w3.org/",
    )
    return [m for m in matches if not m.startswith(allowed_prefixes)]


def test_html_has_no_external_urls():
    matches = _EXTERNAL_URL_RE.findall(INDEX_HTML.read_text(encoding="utf-8"))
    real = _filter_real_externals(matches)
    assert not real, f"index.html references external URLs: {real}"


def test_app_js_has_no_external_urls():
    matches = _EXTERNAL_URL_RE.findall(_app_js_text())
    real = _filter_real_externals(matches)
    assert not real, f"app.js references external URLs: {real}"


def test_style_css_has_no_external_urls():
    matches = _EXTERNAL_URL_RE.findall(STYLE_CSS.read_text(encoding="utf-8"))
    real = _filter_real_externals(matches)
    assert not real, f"style.css references external URLs: {real}"


def test_html_has_no_cdn_or_module_imports():
    """No <script type='module'> with an absolute URL; no CDN host strings."""
    html = INDEX_HTML.read_text(encoding="utf-8")
    forbidden_hosts = ("cdn.", "unpkg.com", "jsdelivr.net", "esm.sh", "skypack.dev")
    found = [h for h in forbidden_hosts if h in html.lower()]
    assert not found, f"index.html references CDN host(s): {found}"


# ---------------------------------------------------------------------------
# Optional vendor folder hygiene
# ---------------------------------------------------------------------------


def test_canonical_server_command_resolves_data_fetch(tmp_path):
    """Spec §10.6 smoke: `python -m http.server -d 06-dashboard` serves both
    `/static/index.html` and `/data/dashboard-data.json` from the same origin.

    This locks down the fix for a self-inconsistency in the original spec
    (the page fetches `../data/dashboard-data.json` so the doc root must
    be `06-dashboard/`, not `06-dashboard/static/`).
    """
    import socket
    import subprocess
    import sys
    import time
    import urllib.request

    # Pick an ephemeral port to avoid clashes with a real dev server.
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]

    proc = subprocess.Popen(
        [sys.executable, "-m", "http.server", str(port), "-d", str(DASHBOARD_ROOT)],
        cwd=REPO_ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        # Wait briefly for the server to bind.
        deadline = time.time() + 5.0
        while time.time() < deadline:
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{port}/static/", timeout=0.5):
                    break
            except Exception:
                time.sleep(0.05)
        else:
            raise RuntimeError("http.server did not start in time")

        for path in ("/static/index.html", "/static/app.js", "/static/style.css", "/data/dashboard-data.json"):
            with urllib.request.urlopen(f"http://127.0.0.1:{port}{path}", timeout=2.0) as resp:
                assert resp.status == 200, f"{path} returned {resp.status}"
                body = resp.read()
                assert body, f"{path} returned an empty body"
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=2.0)
        except subprocess.TimeoutExpired:
            proc.kill()


def test_vendor_folder_if_present_contains_only_local_files():
    vendor = STATIC_ROOT / "vendor"
    if not vendor.exists():
        pytest.skip("no vendor/ folder used")
    for path in vendor.rglob("*"):
        if path.is_file():
            text = path.read_text(encoding="utf-8", errors="ignore")
            assert "://cdn." not in text.lower(), (
                f"{path.relative_to(REPO_ROOT)} appears to load from a CDN at runtime"
            )
