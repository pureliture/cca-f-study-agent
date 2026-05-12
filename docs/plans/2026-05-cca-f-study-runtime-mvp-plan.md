# CCA-F Study Runtime — MVP Implementation Plan (TDD)

- **Plan ID**: 2026-05-cca-f-study-runtime-mvp-plan
- **Spec**: [`docs/specs/2026-05-cca-f-study-runtime-mvp.md`](../specs/2026-05-cca-f-study-runtime-mvp.md)
- **Status**: Draft (for execution)
- **Owner**: lsh1756
- **Date**: 2026-05-11
- **Methodology**: Test-Driven Development (red → green → refactor) per phase, with verification gate before declaring any phase complete.

---

## 0. Cross-cutting rules (apply to every phase)

These rules are non-negotiable and bind every phase below. A phase is **incomplete** if any of these is violated:

- R1. **No runtime PDF parsing.** No script under `src/cca_f_study/`, `04-exam-runner/`, or `06-dashboard/` may open `01-sources/en/guide_en.pdf` for read of *binary content* beyond computing a sha256 during one-shot registration. Runtime scoring/validation/aggregation must succeed with the PDF physically absent.
- R2. **No network I/O.** No `requests`, `httpx`, `urllib.request`, `socket`, `subprocess` to a network tool, etc., in runtime scripts. Tests must work offline.
- R3. **No secrets / no API keys.** Scripts must not require any environment variable.
- R4. **Dashboard stays static.** Plain HTML + vanilla JS + CSS. No build step, no React/Vue/Vite, no bundler, no CDN at runtime. A single vendored `<script src="./vendor/…">` is acceptable.
- R5. **PDF is read-only.** Never write to `01-sources/en/guide_en.pdf`. The Markdown companion at `01-sources/en/companion/guide_en.md` is also read-only and is not a runtime input.
- R6. **TDD order, every phase.** Write failing tests → minimal implementation → tests green → refactor. Do not advance past a phase whose tests are not green.
- R7. **Determinism.** All emitted JSON files must be stable across runs (sorted keys/lists, fixed indent). Tests assert byte-identical re-runs where applicable.
- R8. **Unofficial flag.** Any question not authored from the registered source carries `status ∈ {unofficial, draft, retired}` — never `official`.

---

## 1. Structural layout (aligned with spec §3)

Metadata for the MVP lives under **`00-meta/`** — this matches both spec §3 and the committed tree (see commit `0a6a3b4` "Bootstrap CCA-F study runtime MVP (phases 1-4)"). The runtime resolves source/scenario metadata from `00-meta/` only.

A separate `02-notebooklm-upload/` directory is **not part of the MVP**. It is reserved for a later phase that *exports* a curated NotebookLM upload package from `00-meta/` + `01-sources/` (see `requirement/05-kr-pdf-구조-차이-반영.md` and `requirement/06-kr-pdf-없이-선구현-계획.md`). The MVP runtime does not read from it and the directory does not need to exist.

**Resulting top-level layout for MVP (en-only source set "EN-CORE"):**

```text
cca-f-study-agent/
├── CLAUDE.md
├── README.md
├── pyproject.toml
├── docs/
│   ├── specs/2026-05-cca-f-study-runtime-mvp.md
│   ├── plans/2026-05-cca-f-study-runtime-mvp-plan.md          # this file
│   └── reviews/                                                # written by /review
│
├── 00-meta/                                                    # canonical MVP metadata
│   ├── source-register.md
│   ├── domain-map.md
│   ├── scenario-map.md
│   └── notebooklm-source-index.md
│
├── 01-sources/
│   └── en/
│       ├── guide_en.pdf                                        # canonical, read-only
│       └── companion/guide_en.md                               # token-efficient reference (not runtime input)
│
├── 02-question-bank/
│   ├── seed/sample-questions.jsonl
│   ├── normalized/
│   └── generated/                                              # status != "official" enforced
│
├── 04-exam-runner/                                             # canonical authoring copies of schemas
│   ├── question_schema.json
│   └── attempt_schema.json                                     # (runtime scripts arrive in later phases)
│
├── 05-learning-data/
│   ├── attempts/
│   ├── study-progress.json
│   ├── lab-status.json
│   └── wrong-answer-log.md
│
├── 06-dashboard/                                               # populated in later phases
│   ├── dashboard-spec.md
│   ├── data/dashboard-data.json
│   └── static/
│       ├── index.html
│       ├── app.js
│       └── style.css
│
├── examples/
│   └── attempts/sample-answers.json
│
├── src/cca_f_study/                                            # installed Python package
│   ├── __init__.py
│   ├── validate_questions.py
│   ├── submit_attempt.py                                       # later phase
│   ├── score_attempt.py                                        # later phase
│   ├── export_dashboard_data.py                                # later phase
│   └── _schemas/                                               # package-data copies of 04-exam-runner/*.json
│       ├── question_schema.json
│       └── attempt_schema.json
│
└── tests/
    ├── fixtures/…
    ├── test_validate_questions.py
    ├── test_review_findings.py
    ├── test_submit_attempt.py                                  # later phase
    ├── test_score_attempt.py                                   # later phase
    └── test_export_dashboard_data.py                           # later phase
```

### Schema discovery rule

Schemas exist in **two** locations that must stay byte-identical:

- `04-exam-runner/*.json` — canonical authoring copies (humans read/edit here; matches spec §3 file list).
- `src/cca_f_study/_schemas/*.json` — package-data copies shipped with the wheel.

The validator loads schemas via `importlib.resources` from `cca_f_study._schemas`, so the CLI works under wheel/target installs and from any working directory. A regression test (`tests/test_review_findings.py::test_packaged_schemas_match_canonical_files`) enforces that the two copies stay identical.

### Forward-compat note (deferred)

A future "export NotebookLM upload package" step will curate `02-notebooklm-upload/` from `00-meta/` + `01-sources/`, supporting batched uploads (`02-notebooklm-upload/kr-batch-01-core/`, etc.) as described in the reference docs. The MVP runtime is intentionally agnostic of that directory; nothing in the runtime needs to change when it is added.

---

## Phase 1 — Repository skeleton and metadata

### 1.1 Objective
Establish the canonical directory tree, register the source PDF (read-only), and author MVP metadata under `00-meta/`. Nothing executable yet beyond a smoke test that asserts the structure.

### 1.2 Files to create / modify
- Create: `README.md` (one-paragraph repo intro + link to spec + plan)
- Create: `pyproject.toml` (src layout exposing `cca_f_study`; dev deps `pytest`, `jsonschema`; `[tool.pytest.ini_options]` for `pythonpath = ["src"]`)
- Create: directories `00-meta/`, `01-sources/en/`, `02-question-bank/{seed,normalized,generated}/`, `04-exam-runner/`, `05-learning-data/attempts/`, `06-dashboard/{data,static}/`, `examples/attempts/`, `src/cca_f_study/`, `tests/fixtures/`
- Move: any root-level `./guide_en.pdf` into `01-sources/en/guide_en.pdf`. If the PDF is not yet present, record a `pending` sha256 in `00-meta/source-register.md` and provide step-by-step instructions to import it later.
- (Optional) Place a token-efficient Markdown companion at `01-sources/en/companion/guide_en.md` (not a runtime input; declared in `source-register.md` as a companion, not a source).
- Create: `00-meta/source-register.md` — Source IDs table with `guide_en` as the single active row; reserved (not active) entries documented separately; explicit read-only contract.
- Create: `00-meta/domain-map.md` — D1–D5 with title, weight, brief definition, source reference.
- Create: `00-meta/scenario-map.md` — scenario id (backticked, kebab-case), title, related domains; seeded with at least the scenarios used by the seed bank.
- Create: `00-meta/notebooklm-source-index.md` — declares `EN-CORE` (status: active) and reserves `KR-LECTURES` (status: planned) for forward compatibility.
- Create: `.gitignore` (`__pycache__/`, `.pytest_cache/`, `*.pyc`, `.DS_Store`, `*.egg-info/`, `.venv/`, `.claude/settings.local.json`).

### 1.3 Tests to write first
Smoke tests over the structure (kept lightweight — full validation comes in Phase 4):

- `test_canonical_pdf_path_exists` — `01-sources/en/guide_en.pdf` exists, OR `00-meta/source-register.md` documents a `pending` import (xfail with explicit message).
- `test_00_meta_files_present` — `source-register.md`, `domain-map.md`, `scenario-map.md`, `notebooklm-source-index.md`.
- `test_notebooklm_index_declares_active_en_core` — index file contains an `EN-CORE` block with `Status: active`.
- `test_notebooklm_index_reserves_kr_lectures_planned` — index file contains a `KR-LECTURES` block with `Status: planned`.
- `test_domain_map_lists_d1_through_d5_with_weights` — domain map has D1–D5 rows and weights summing to 1.00 (±0.01).
- `test_runtime_dirs_exist` — `04-exam-runner/`, `05-learning-data/attempts/`, `06-dashboard/data/`, `06-dashboard/static/`, `02-question-bank/seed/` exist.
- `test_pyproject_declares_cca_f_study_package` — parses `pyproject.toml` and asserts `cca_f_study` package presence + `pythonpath = ["src"]`.

### 1.4 Implementation steps
1. Run failing tests (red).
2. Create directory tree with `mkdir -p`.
3. Author the markdown files per §1.2.
4. Author minimal `pyproject.toml`.
5. Move the PDF (if present); otherwise leave `source-register.md` with the pending placeholder.
6. Re-run tests (green).

### 1.5 Validation command
```bash
pytest -q
```

### 1.6 Expected output
- All Phase-1 smoke tests pass, exit 0.
- `ls 00-meta/` shows the four metadata files.

### 1.7 Rollback / safety
- Never delete `01-sources/en/guide_en.pdf` to "regenerate" it. If the move is wrong, restore from git or original location; do not re-encode.
- The Markdown companion under `01-sources/en/companion/` is *not* the runtime source; do not rely on it for validation.
- All edits are local; rollback = `git checkout -- <path>`.

### 1.8 Completion criteria
- Phase-1 smoke tests green.
- `00-meta/` contains the four required markdown files.
- `01-sources/en/guide_en.pdf` sha256 matches the value recorded in `source-register.md` (when the PDF is physically present), or `source-register.md` carries a clearly marked `pending` placeholder otherwise.

---

## Phase 2 — Python package / bootstrap

### 2.1 Objective
Make `cca_f_study` importable so `python -m cca_f_study.validate_questions` resolves. No runtime logic yet beyond a no-op `__main__` and a CLI entry placeholder that prints usage.

### 2.2 Files to create / modify
- `04-exam-runner/__init__.py` (empty)
- `04-exam-runner/_cli.py` (shared `argparse` helpers; pure functions only)
- `pyproject.toml` — `[project]` + `[tool.setuptools.packages.find]` so the directory `04-exam-runner` maps to a package named `cca_f_study`. Use `[tool.setuptools.package-dir]` with `cca_f_study = "04-exam-runner"`.
- `tests/conftest.py` — pytest fixture for tmp working dir + a `repo_root()` fixture.

### 2.3 Tests to write first (`tests/test_bootstrap.py`)
- `test_import_cca_f_study_package` — `import cca_f_study` succeeds.
- `test_cli_helpers_exposed` — `from cca_f_study._cli import build_parser` exists.
- `test_python_dash_m_invocation_returns_zero_on_help` — subprocess `python -m cca_f_study.validate_questions --help` exits 0 (CLI module skeleton exists even before logic).

### 2.4 Implementation steps
1. Write tests (red).
2. Configure `pyproject.toml` package mapping.
3. Add `__init__.py` and stub `validate_questions.py` with an `argparse` parser that supports `--help` and exits 0; the actual validation logic comes in Phase 3.
4. `pip install -e .` (developer step, not committed).
5. Tests green.

### 2.5 Validation command
```bash
pip install -e .
python -c "import cca_f_study; print(cca_f_study.__name__)"
python -m cca_f_study.validate_questions --help
pytest tests/test_bootstrap.py -q
```

### 2.6 Expected output
- `cca_f_study` printed.
- Help text printed; exit 0.
- All bootstrap tests pass.

### 2.7 Rollback / safety
- Editable install is local-only. `pip uninstall cca_f_study` reverses it.
- Do **not** add a `setup.py`; stick with `pyproject.toml` only.

### 2.8 Completion criteria
- Bootstrap tests green.
- Module discoverable via `python -m cca_f_study.<module>`.

---

## Phase 3 — JSON schemas

### 3.1 Objective
Author `question_schema.json` and `attempt_schema.json` as JSON Schema (Draft 2020-12) embodying spec §5 and §6, and wire `validate_questions.py` to enforce the question schema across a JSONL file.

### 3.2 Files to create / modify
- `04-exam-runner/question_schema.json` — required: id, source, domain, scenario, difficulty, stem, choices(A–D), answer, explanation, concept_tags, status.
- `04-exam-runner/attempt_schema.json` — required: attempt_id, attempt_label, started_at, finished_at, question_bank_path, answers[], totals{total,correct}.
- `04-exam-runner/validate_questions.py` — load schema, stream JSONL, validate each line, collect failures with `id` + reason, print summary, exit non-zero on any failure.

### 3.3 Tests to write first (`tests/test_validate_questions.py`)
Fixtures under `tests/fixtures/questions/`:
- `valid.jsonl` — 5 minimal valid questions across D1–D5.
- `invalid_missing_field.jsonl` — drops `explanation`.
- `invalid_bad_domain.jsonl` — `domain: "D9"`.
- `invalid_answer_not_in_choices.jsonl` — `answer: "E"`.
- `invalid_duplicate_id.jsonl` — two records share `id`.
- `invalid_unknown_source.jsonl` — `source: "ghost"` (not declared in source register).

Tests:
- `test_valid_jsonl_passes` — exit 0, stdout includes `invalid questions: 0`.
- `test_missing_field_fails` — non-zero exit, reports the offending `id` + missing field name.
- `test_bad_domain_fails`, `test_answer_not_in_choices_fails` — same shape.
- `test_duplicate_id_fails` — both ids appear in error report.
- `test_unknown_source_fails` — error references the unknown source id.
- `test_summary_counts_match_inputs` — `valid + invalid == total lines parsed`.

### 3.4 Implementation steps
1. Author schemas.
2. Run failing tests.
3. Implement validator with `jsonschema` library + an in-process check for `source` against `00-meta/source-register.md` and for `scenario` against `00-meta/scenario-map.md`. Default schema discovery uses `importlib.resources` against the package-shipped copy under `src/cca_f_study/_schemas/`.
4. Tests green.

### 3.5 Validation command
```bash
pytest tests/test_validate_questions.py -q
python -m cca_f_study.validate_questions tests/fixtures/questions/valid.jsonl
```

### 3.6 Expected output
- All Phase-3 tests green.
- `valid questions: 5` / `invalid questions: 0` printed; exit 0.

### 3.7 Rollback / safety
- Schemas are pure data; no destructive ops.
- Do **not** import any PDF library (R1). Source-set membership is verified against the markdown index, not the PDF.

### 3.8 Completion criteria
- Phase-3 tests green.
- Validator rejects all 5 invalid fixtures; accepts the valid one.

---

## Phase 4 — Sample question bank

### 4.1 Objective
Produce a hand-authored seed JSONL with ≥ 10 questions, ≥ 1 per domain D1–D5, all `status: "official"` and `source` referencing `EN-CORE` / `guide_en`. Validate it with the Phase-3 validator.

### 4.2 Files to create / modify
- `02-question-bank/seed/sample-questions.jsonl` — ≥ 10 lines.
- `00-meta/source-register.md` — `Source IDs` table enumerates allowed `source` values (e.g., `guide_en`) so the validator's source check has an authoritative list.
- `00-meta/scenario-map.md` — every `scenario` value used in the seed bank must be listed there.

### 4.3 Tests to write first (`tests/test_seed_bank.py`)
- `test_seed_bank_has_at_least_ten_questions`.
- `test_seed_bank_covers_all_domains` — D1–D5 each represented ≥ 1.
- `test_seed_bank_passes_validator` — invoking `validate_questions` on the seed file returns exit 0.
- `test_seed_bank_sources_are_registered` — every `source` value appears in the index's `Source IDs` block.
- `test_seed_bank_scenarios_are_in_scenario_map` — every `scenario` value is listed in `scenario-map.md`.
- `test_seed_bank_status_is_official` — every record has `status == "official"`.

### 4.4 Implementation steps
1. Tests red.
2. Author the 10+ questions from human knowledge of CCA-F topics. Topics should anchor in domains:
   - D1 — agent loops, subagents, hand-off.
   - D2 — tool schemas, MCP servers, tool_use.
   - D3 — Claude Code config, CLAUDE.md, slash commands, hooks.
   - D4 — prompt design, structured output, JSON prefill.
   - D5 — context window, retries, deterministic IDs.
3. Tests green.

### 4.5 Validation command
```bash
pytest tests/test_seed_bank.py -q
python -m cca_f_study.validate_questions 02-question-bank/seed/sample-questions.jsonl
```

### 4.6 Expected output
- Phase-4 tests green.
- Validator: `valid questions: ≥10`, `invalid questions: 0`, exit 0.

### 4.7 Rollback / safety
- These are **author-written** questions. Do **not** auto-generate from the PDF or any model (R1, R2). If a question's content is uncertain, mark it `status: "draft"` instead of `"official"` and exclude from the seed bank.

### 4.8 Completion criteria
- ≥ 10 questions, every domain covered, validator green.

---

## Phase 5 — Attempt submission normalization

### 5.1 Objective
Implement `submit_attempt.py`: read answers + question bank, join on `question_id`, emit a normalized attempt JSON per spec §6.2. Refuse to overwrite without `--force`.

### 5.2 Files to create / modify
- `04-exam-runner/submit_attempt.py`
- `examples/attempts/sample-answers.json` (covers the seed bank, deliberately mixes correct/incorrect to produce a useful score later)

### 5.3 Tests to write first (`tests/test_submit_attempt.py`)
Fixtures:
- `tests/fixtures/attempts/questions_small.jsonl` (3 questions).
- `tests/fixtures/attempts/answers_complete.json` (answers all 3).
- `tests/fixtures/attempts/answers_partial.json` (answers 2 of 3).
- `tests/fixtures/attempts/answers_unknown_id.json` (one answer references a missing question).

Tests:
- `test_attempt_id_is_deterministic` — same `finished_at` + `attempt_label` → same `attempt_id` across runs.
- `test_answers_are_joined_with_domain_scenario_tags` — joined fields match the bank.
- `test_correctness_flag_matches_answer_key` — `is_correct == (choice == correct)`.
- `test_missing_answers_filled_with_null_and_marked_incorrect` — partial answers produce `{choice: null, is_correct: false}` rows for unanswered questions.
- `test_unknown_question_id_aborts` — submission fails with a clear error and no output file.
- `test_overwrite_refused_without_force` — second run on same `--out` exits non-zero unless `--force` is passed.
- `test_complete_attempt_totals` — `totals.total == len(answers)`, `totals.correct == sum(is_correct)`.

Additional regression coverage delivered alongside the plan-named tests (separate file `tests/test_submit_attempt_coverage.py` plus appended tests in `tests/test_submit_attempt.py`):
- partial output schema validation, explicit null choice, empty answers, duplicate `question_id` in answers, non-A/B/C/D choice, error-message contains the offending id, sample-attempt schema snapshot.
- post-review hardening: malformed bank row raises `SubmitError`, atomic write (no `.tmp` leftover), empty/whitespace `attempt_label` aborts, `question_bank_path` stored as a CWD-relative POSIX string.

### 5.4 Implementation steps
1. Tests red.
2. Implement loader for JSONL + answers JSON.
3. Implement join + null-fill for missing answers.
4. Implement deterministic `attempt_id` (`att-{finished_at}-{slug(label)}`).
5. Implement overwrite guard.
6. Tests green; refactor for clarity (no IO inside compute functions).

### 5.5 Validation command
```bash
pytest tests/test_submit_attempt.py -q
python 04-exam-runner/submit_attempt.py \
  --questions 02-question-bank/seed/sample-questions.jsonl \
  --answers   examples/attempts/sample-answers.json \
  --out       05-learning-data/attempts/sample-attempt.json
```

### 5.6 Expected output
- Phase-5 tests green.
- `05-learning-data/attempts/sample-attempt.json` exists and matches spec §6.2.

### 5.7 Rollback / safety
- Output files in `05-learning-data/attempts/` are reproducible from inputs; safe to delete and regenerate.
- Never read the source PDF.

### 5.8 Completion criteria
- Phase-5 tests green.
- Sample attempt JSON validates against `attempt_schema.json`.

---

## Phase 6 — Score calculation

### 6.1 Objective
Implement `score_attempt.py` per spec §7. Print a human summary; emit machine JSON with `--json`.

### 6.2 Files to create / modify
- `04-exam-runner/score_attempt.py`
- `04-exam-runner/_scoring.py` — pure functions `compute_raw`, `compute_scaled`, `compute_breakdowns`. No IO.

### 6.3 Tests to write first (`tests/test_score_attempt.py`)
Edge-case fixtures derived in Python or stored under `tests/fixtures/attempts/`:
- `attempt_all_correct.json` (10/10).
- `attempt_all_wrong.json` (0/10).
- `attempt_passing_threshold.json` — choose `correct/total` so `scaled_score == 720` exactly.
- `attempt_below_threshold.json` — `scaled_score == 719`.
- `attempt_zero_questions.json` — empty answers.
- `attempt_multi_domain.json` — mix across D1–D5 for breakdown.

Tests:
- `test_scaled_score_formula` — `round(100 + (c/t)*900)` for each fixture.
- `test_pass_mark_is_720` — declared constant.
- `test_pass_flag_correctness` — boundary at 720.
- `test_pass_gap_signed` — positive when passing, negative when failing.
- `test_zero_questions_returns_100_and_fail` — edge case (spec §7.2 S5).
- `test_domain_breakdown_sums_match_totals`.
- `test_scenario_breakdown_keys_are_present`.
- `test_concept_breakdown_handles_multitag_questions` — a question with 2 tags counts toward both buckets.
- `test_json_flag_emits_machine_summary` — output parses as JSON with the keys expected by Phase 7.
- `test_scoring_is_pure` — calling twice on the same attempt produces identical output.

### 6.4 Implementation steps
1. Tests red.
2. Implement `_scoring.py` pure functions.
3. Wire CLI in `score_attempt.py` (argparse: positional attempt path, optional `--json`).
4. Tests green.

### 6.5 Validation command
```bash
pytest tests/test_score_attempt.py -q
python 04-exam-runner/score_attempt.py 05-learning-data/attempts/sample-attempt.json
python 04-exam-runner/score_attempt.py 05-learning-data/attempts/sample-attempt.json --json
```

### 6.6 Expected output
- Phase-6 tests green.
- Human output includes: `Raw score`, `Scaled score`, `Pass mark`, `Result`, `Gap`, and a `Domain breakdown` block.
- `--json` emits valid JSON with `scaled_score`, `pass`, `pass_gap`, `domain_breakdown`, `scenario_breakdown`, `concept_breakdown`.

### 6.7 Rollback / safety
- Scoring is read-only against attempt files. No writes outside stdout / explicit `--out` (not added in MVP).
- No PDF, no network, no secrets (R1–R3).

### 6.8 Completion criteria
- Phase-6 tests green.
- Sample attempt prints expected summary.

---

## Phase 7 — Dashboard data export

### 7.1 Objective
Implement `export_dashboard_data.py` per spec §8: aggregate all attempts + `lab-status.json`, emit a deterministic `dashboard-data.json`.

### 7.2 Files to create / modify
- `04-exam-runner/export_dashboard_data.py`
- `04-exam-runner/_aggregate.py` — pure aggregation (no IO except in caller).
- `05-learning-data/lab-status.json` — minimal seed file with the lab catalog's first ~5 lab ids in `not_started`.

### 7.3 Tests to write first (`tests/test_export_dashboard_data.py`)
Fixtures: built inline in tests via helper functions (no committed JSON fixture files; `_write_attempts(tmp_path, …)` writes attempt JSONs into `tmp_path` per test).

Tests (actual file names; renames from earlier draft are noted in parentheses):
- `test_output_contains_all_required_top_level_keys` *(was `test_output_has_all_required_top_level_keys`)* — every key from spec §8.1 present.
- `test_latest_attempt_is_most_recent_finished_at` *(was `test_latest_attempt_is_most_recent`)*.
- `test_domain_breakdown_always_lists_d1_through_d5` — even when zero questions in a domain, the entry exists with `accuracy: null`.
- `test_weak_concepts_sorted_by_miss_rate_descending` + `test_weak_concepts_capped_at_ten` + `test_weak_concepts_excludes_zero_miss_rate` *(replaced the single planned `test_weak_concepts_sorted_and_capped_to_10`)*.
- `test_lab_recommendations_prefer_weak_concepts_and_cap_at_five` *(was `test_lab_recommendations_capped_to_5_and_prefer_weak_concepts`)*.
- `test_trend_is_chronological_ascending`.
- `test_export_is_byte_identical_on_repeated_runs` — diff two runs against fresh tmp `--out`.
- `test_export_does_not_read_source_pdf` *(was `test_export_uses_no_pdf_and_no_network`; the network half of the original test now lives in `tests/test_export_coverage.py::test_export_does_not_open_network_sockets`)*.
- `test_empty_attempts_dir_produces_valid_empty_output` — `latest_attempt: null`, breakdowns present but zeroed, `trend: []`.

Additional regression suites delivered alongside the plan-named tests:
- `tests/test_export_review_fixes.py` (9 tests): tie-break by `attempt_id`, atomic-write `*.tmp` cleanup, `ExportError` on malformed lab-status, `--now` ISO validation, stable recommendation order vs. JSON insertion order, non-JSON / sub-directory entries in attempts dir, byte-identity of the canonical CLI command with pinned `--now`.
- `tests/test_export_coverage.py` (10 tests): `latest_attempt` tie determinism, missing `domain-map.md` fallback, lab matching multiple weak concepts (dedup), all-completed → no recommendations, weak concept without matching lab, no network sockets opened, drift-proof `total_labs`, byte-identity on `finished_at` ties, default-UTC ISO-8601 format.

### 7.4 Implementation steps
1. Tests red.
2. Implement aggregation in `_aggregate.py`.
3. Wire CLI with `argparse`: `--attempts`, `--lab-status`, `--out`.
4. Stable JSON: `json.dumps(..., sort_keys=True, indent=2, ensure_ascii=False)` + trailing newline.
5. Tests green.

### 7.5 Validation command
```bash
pytest tests/test_export_dashboard_data.py -q
python 04-exam-runner/export_dashboard_data.py \
  --attempts   05-learning-data/attempts \
  --lab-status 05-learning-data/lab-status.json \
  --out        06-dashboard/data/dashboard-data.json
```

### 7.6 Expected output
- Phase-7 tests green.
- `06-dashboard/data/dashboard-data.json` exists; second run produces a byte-identical file.

### 7.7 Rollback / safety
- The output file is regeneratable; safe to delete.
- Aggregation never reads PDFs (R1) and never hits the network (R2).

### 7.8 Completion criteria
- Phase-7 tests green.
- Output validates against spec §8 contract rules C1–C7.

---

## Phase 8 — Static dashboard

### 8.1 Objective
Author a vanilla-JS dashboard at `06-dashboard/static/` that consumes `../data/dashboard-data.json` and renders the seven widgets in spec §1.

### 8.2 Files to create / modify
- `06-dashboard/static/index.html` — semantic structure with seven sections, each given a stable `id` (`pass-banner`, `pass-progress`, `domain-breakdown`, `scenario-breakdown`, `weak-concepts`, `lab-progress`, `score-trend`).
- `06-dashboard/static/app.js` — `fetch('../data/dashboard-data.json')`, render functions per widget, graceful empty states.
- `06-dashboard/static/style.css` — single stylesheet, mobile-first, no framework.
- (Optional) `06-dashboard/static/vendor/sparkline.js` — only if needed; otherwise inline `<svg>`.

### 8.3 Tests to write first (`tests/test_static_dashboard.py`)
Static parsing (HTML/JS) checks; no headless browser, no JS runtime in test:
- `test_index_html_has_all_seven_widget_anchors` — parse HTML and assert each `id` from §8.2 is present.
- `test_app_js_fetches_relative_dashboard_data` — string search for `'../data/dashboard-data.json'` and `fetch(`.
- `test_no_external_urls_referenced` — scan `index.html` and `app.js` for `http://` / `https://` / CDN hostnames; assert none outside comments.
- `test_no_build_artifacts_required` — no `package.json` under `06-dashboard/`, no `import` from `node_modules`.
- `test_dashboard_handles_null_latest_attempt` — JS source includes a guard string like `latest_attempt == null` or equivalent ternary; this is a coarse static smoke check.

Manual checklist (documented in this plan as part of Phase 10 validation):
- Run `python -m http.server 8000 -d 06-dashboard/static` and browse `http://localhost:8000/`.
- Confirm each of the seven widgets renders against the sample `dashboard-data.json`.
- Confirm the page renders an empty-state when `06-dashboard/data/dashboard-data.json` has zero attempts.

### 8.4 Implementation steps
1. Write static tests red.
2. Author HTML/CSS/JS in vanilla form (R4).
3. Use `<svg>` for bar/sparkline rendering; no chart library.
4. Tests green.

### 8.5 Validation command
```bash
pytest tests/test_static_dashboard.py -q
python -m http.server 8000 -d 06-dashboard/static
```

### 8.6 Expected output
- Static tests green.
- Browser at `http://localhost:8000/` shows the seven widgets.

### 8.7 Rollback / safety
- Pure files; no destructive ops.
- Do **not** introduce npm/yarn/pnpm/Vite/React (R4).
- Do **not** add a service worker or any network fetch beyond the local JSON file.

### 8.8 Completion criteria
- Static tests green.
- Manual smoke confirms all seven widgets render with real and empty `dashboard-data.json`.

---

## Phase 9 — Tests (cross-cutting hardening)

### 9.1 Objective
Add the integration/contract tests that span multiple modules and lock down the cross-cutting rules from §0.

### 9.2 Files to create / modify
- `tests/test_end_to_end.py` — full pipeline: validate → submit → score → export, asserting outputs.
- `tests/test_no_pdf_runtime_dependency.py` — temporarily renames `01-sources/en/guide_en.pdf` to `…/guide_en.pdf.hidden` and runs the four CLI commands; all must succeed.
- `tests/test_no_network_calls.py` — monkeypatches `socket.socket` / `urllib.request.urlopen` to raise; reruns validate + score + export; asserts they still pass.
- `tests/test_dashboard_data_byte_identical.py` — runs `export_dashboard_data.py` twice into two tmp paths and diffs bytes.
- `tests/test_static_dashboard_no_external_urls.py` — overlap with Phase-8 but elevated to a separate file for visibility.

### 9.3 Tests to write first
The Phase-9 tests **are** the tests. Each is written to fail until the cross-cutting guarantees actually hold; the implementation work in earlier phases either already satisfies them or needs targeted hardening (e.g., closing a stray file read).

### 9.4 Implementation steps
1. Write tests red.
2. Fix any leak (e.g., a stray PDF read, a non-deterministic timestamp baked into output).
3. Tests green.

### 9.5 Validation command
```bash
pytest -q
```

### 9.6 Expected output
- Entire suite green, exit 0.
- No skipped tests except those explicitly xfailed when the canonical PDF is not present (Phase-1 fallback).

### 9.7 Rollback / safety
- The PDF-renaming test must restore the original filename in `finally`.
- Network-blocking monkeypatches scoped to fixtures only.

### 9.8 Completion criteria
- Phase-9 tests green.
- Determinism, no-PDF-runtime, and no-network invariants all enforced by tests.

---

## Phase 10 — Final validation

### 10.1 Objective
Execute the canonical command set from the task brief in order, confirm each produces the expected artifact, and produce a one-page run report in `docs/reviews/2026-05-cca-f-study-runtime-mvp-final-validation.md` (only created during this phase, not in earlier phases — kept as a separate review artifact).

### 10.2 Files to create / modify
- `docs/reviews/2026-05-cca-f-study-runtime-mvp-final-validation.md` (the run log).

### 10.3 Tests to write first
No new pytest. Use the canonical commands below as the verification checklist. The "test" is the run report assertion table.

### 10.4 Implementation steps
For each command, run it, capture stdout, compare to the expected output, mark the row PASS or BLOCKED. Stop and emit a BLOCKED report (failed criterion id, exact command/output/error, what was attempted, next concrete fix) if any row fails.

### 10.5 Validation commands (run **exactly** these, in order)

```bash
pytest

python -m cca_f_study.validate_questions \
  02-question-bank/seed/sample-questions.jsonl

python 04-exam-runner/submit_attempt.py \
  --questions 02-question-bank/seed/sample-questions.jsonl \
  --answers examples/attempts/sample-answers.json \
  --out 05-learning-data/attempts/sample-attempt.json

python 04-exam-runner/score_attempt.py \
  05-learning-data/attempts/sample-attempt.json

python 04-exam-runner/export_dashboard_data.py \
  --attempts 05-learning-data/attempts \
  --lab-status 05-learning-data/lab-status.json \
  --out 06-dashboard/data/dashboard-data.json

python -m http.server 8000 -d 06-dashboard/static
```

### 10.6 Expected output per command

| # | Command | Expected |
|---|---------|----------|
| 1 | `pytest` | All tests pass, exit 0. |
| 2 | `validate_questions …seed/sample-questions.jsonl` | `valid questions: ≥10`, `invalid questions: 0`, exit 0. |
| 3 | `submit_attempt.py …` | Creates `05-learning-data/attempts/sample-attempt.json` matching `attempt_schema.json`; no overwrite without `--force`. |
| 4 | `score_attempt.py …sample-attempt.json` | Prints `Raw score`, `Scaled score`, `Pass mark: 720`, `Result: PASS\|FAIL`, `Gap: <signed>`, plus a `Domain breakdown` block. |
| 5 | `export_dashboard_data.py …` | Writes `06-dashboard/data/dashboard-data.json` matching spec §8.1; repeat run is byte-identical. |
| 6 | `python -m http.server 8000 -d 06-dashboard/static` | Server starts; browser at `http://localhost:8000/` shows all seven widgets. |

### 10.7 Rollback / safety
- `python -m http.server` is read-only by default; stop with Ctrl-C.
- Do not commit `__pycache__/` or `.pytest_cache/`.
- Do not edit the canonical PDF.

### 10.8 Completion criteria (maps to spec §12)

| Plan check | Spec criterion |
|------------|----------------|
| Phase-1 done | CC1, CC2, CC3 |
| Phase-3 + Phase-4 done | CC4, CC5 |
| Phase-5 done | CC6 |
| Phase-6 done | CC7 |
| Phase-7 done | CC8, CC14 |
| Phase-9 done | CC11, CC12, CC13 |
| Phase-8 + Phase-10 done | CC9, CC10 |
| Phase-10 final report exists | end-to-end gate |

All eight rows must be PASS for MVP completion. Any BLOCKED row stops the chain per `CLAUDE.md` completion rule.

---

## Appendix A — Required final runtime commands (verbatim)

```bash
pytest

python -m cca_f_study.validate_questions \
  02-question-bank/seed/sample-questions.jsonl

python 04-exam-runner/submit_attempt.py \
  --questions 02-question-bank/seed/sample-questions.jsonl \
  --answers examples/attempts/sample-answers.json \
  --out 05-learning-data/attempts/sample-attempt.json

python 04-exam-runner/score_attempt.py \
  05-learning-data/attempts/sample-attempt.json

python 04-exam-runner/export_dashboard_data.py \
  --attempts 05-learning-data/attempts \
  --lab-status 05-learning-data/lab-status.json \
  --out 06-dashboard/data/dashboard-data.json

python -m http.server 8000 -d 06-dashboard/static
```

## Appendix B — Forbidden in MVP (re-cap)

- ❌ PDF parsing at runtime (any phase, any script).
- ❌ Network calls (HTTP, sockets, subprocess to remote tools).
- ❌ Environment secrets / API keys.
- ❌ React / Vite / bundlers / CDNs in the dashboard.
- ❌ Server / DB / auth.
- ❌ Auto-generated questions presented as `official`.
- ❌ Skipping the TDD red→green order in any phase.

## Appendix C — Forward-compatibility hooks (not implemented in MVP)

These are deliberately **not built** in this plan but the structure must not block them:

- Future `01-sources/kr/raw/*.pdf` + `01-sources/kr/source-manifest.json` (per `05-kr-pdf-구조-차이-반영.md`).
- Future `02-notebooklm-upload/kr-batch-01-core/…` batched upload packages (per `06-kr-pdf-없이-선구현-계획.md`).
- Future `python -m cca_f_study.validate_sources --manifest … --upload-dir …` is **not** part of MVP commands but the package layout reserves the name.
- Future weighted scoring using domain weights from §3 of spec.

No code or files for these may be added in MVP execution.
