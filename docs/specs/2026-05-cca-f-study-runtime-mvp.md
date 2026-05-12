# CCA-F Study Runtime — MVP Specification

- **Spec ID**: 2026-05-cca-f-study-runtime-mvp
- **Status**: Draft
- **Owner**: lsh1756
- **Date**: 2026-05-11
- **Applies to**: `cca-f-study-agent` repository
- **Audience**: Claude Code / implementation agents executing follow-up plans

---

## 0. Architectural premise (inherited)

Learning material management is split across three layers, consistent with the prior design:

| Layer            | Where it lives                                 | Tool                       |
|------------------|------------------------------------------------|----------------------------|
| Theory (PDF)     | `01-sources/en/`                                | NotebookLM (read-only)     |
| Labs / code      | repository (later phases)                       | Jupyter / VS Code          |
| Index / mapping  | `00-meta/` (markdown)                           | repository (text linkage)  |

This MVP only adds the **runtime layer** (question bank, attempts, scoring, dashboard data, static dashboard). It does not replace the theory↔lab↔index structure; it sits beside it.

---

## 1. Goals

The MVP must enable the learner to answer the following questions from local artifacts only:

1. **Am I currently passing?** — pass / fail vs. 720.
2. **How far am I from 720?** — absolute gap in scaled-score points.
3. **Which domain is weakest?** — D1–D5 breakdown with correct/total and accuracy.
4. **Which scenario is weakest?** — scenario-level accuracy breakdown.
5. **Which concepts do I repeatedly miss?** — top weak `concept_tags` across attempts.
6. **Which labs should I do next?** — lab recommendations derived from weak domains/concepts and `lab-status.json`.
7. **Is my score trend improving?** — per-attempt scaled-score series over time.

Concrete deliverable goals:

- G1. Register the English source PDF as a read-only artifact.
- G2. Define and validate a question bank JSONL schema.
- G3. Accept a learner's mock-exam answers and produce a normalized attempt JSON.
- G4. Compute raw score, scaled score, pass/fail, and breakdowns from attempt JSON.
- G5. Aggregate attempts + lab status into a single `dashboard-data.json`.
- G6. Serve a fully static HTML/CSS/JS dashboard that consumes only `dashboard-data.json`.
- G7. Cover the four runtime scripts with `pytest` tests.

---

## 2. Non-goals (MVP)

The following are explicitly **out of scope** for this MVP. They must not be implemented in this iteration, even if convenient:

- N1. **PDF parsing at runtime.** No PDF text extraction, OCR, or embedding-based ingestion drives scoring or dashboard generation.
- N2. **External API calls.** No calls to Anthropic, OpenAI, NotebookLM, GitHub, etc. from runtime scripts.
- N3. **API keys / secrets.** Runtime must work without any environment secret.
- N4. **Automatic question generation** from the PDF or any model.
- N5. **GitHub mock-exam auto-import** workflows.
- N6. **NotebookLM integration automation.**
- N7. **React / Vite / SPA dashboard.** Dashboard is static HTML + vanilla JS + CSS only.
- N8. **Server / DB / auth.** No backend, no login, no persistent service. File-system is the storage.
- N9. **Auto-generation of lab code.** Lab status is recorded manually in `lab-status.json` for now.
- N10. **Mutation of the source PDF.** The PDF is treated as immutable evidence.
- N11. **Claiming any generated/community question is official.** Every non-source question is flagged `unofficial`.

Out-of-scope items are deferred to the "확장판" phase referenced in `04-구현-계획-및-프롬프트.md` §10.

---

## 3. Repository structure (MVP target tree)

```text
cca-f-study-agent/
├── CLAUDE.md
├── README.md
├── pyproject.toml
├── docs/
│   ├── specs/
│   │   └── 2026-05-cca-f-study-runtime-mvp.md         # this document
│   ├── plans/                                          # written in the next prompt
│   └── reviews/                                        # written by /review prompt
│
├── 01-sources/
│   └── en/
│       └── guide_en.pdf                                # read-only source artifact
│
├── 00-meta/
│   ├── source-register.md                              # PDF registration (sha256, lang, type)
│   ├── domain-map.md                                   # D1–D5 definitions + weights
│   ├── scenario-map.md                                 # scenario taxonomy
│   └── notebooklm-source-index.md                      # theory↔lab linkage (uploaded with PDF)
│
├── 02-question-bank/
│   ├── seed/
│   │   └── sample-questions.jsonl                      # ≥10 hand-authored seed questions
│   ├── normalized/                                     # validated/canonical bank
│   └── generated/                                      # unofficial generated bank (empty in MVP)
│
├── 04-exam-runner/
│   ├── __init__.py
│   ├── question_schema.json                            # JSON Schema for question records
│   ├── attempt_schema.json                             # JSON Schema for attempt records
│   ├── validate_questions.py                           # importable as cca_f_study.validate_questions
│   ├── submit_attempt.py
│   ├── score_attempt.py
│   └── export_dashboard_data.py
│
├── 05-learning-data/
│   ├── attempts/                                       # one JSON per submitted attempt
│   ├── study-progress.json                             # optional learner-curated state
│   ├── lab-status.json                                 # lab id → {status, last_run}
│   └── wrong-answer-log.md                             # human-readable error notebook
│
├── 06-dashboard/
│   ├── dashboard-spec.md                               # written in a later prompt
│   ├── data/
│   │   └── dashboard-data.json                         # the single source for the dashboard
│   └── static/
│       ├── index.html
│       ├── app.js
│       └── style.css
│
├── examples/
│   └── attempts/
│       └── sample-answers.json                         # demo input for submit_attempt.py
│
└── tests/
    ├── test_validate_questions.py
    ├── test_submit_attempt.py
    ├── test_score_attempt.py
    └── test_export_dashboard_data.py
```

Implementation note: the Python package importable as `cca_f_study` lives under `04-exam-runner/` and is exposed via `pyproject.toml`'s package configuration. Hyphenated directory names are not Python packages themselves; they hold the package and supporting JSON.

---

## 4. Source PDF policy

- P1. The canonical path for the English source PDF is `01-sources/en/guide_en.pdf`.
- P2. The PDF is **read-only**. No runtime script may open it for write. No script may rewrite, re-encode, or move it.
- P3. **No runtime script parses the PDF.** Scoring, validation, and dashboard generation must succeed with the PDF absent from the working directory, as long as `source-register.md` exists.
- P4. The PDF is registered exactly once in `00-meta/source-register.md` with at minimum:
  - `path`: `01-sources/en/guide_en.pdf`
  - `language`: `en`
  - `source_type`: `PDF`
  - `sha256`: hex digest of the file
  - `imported_at`: ISO-8601 UTC timestamp
  - `note`: `read-only source artifact`
- P5. The `source` field on every question must reference a registered source identifier (see §5). A question may *not* claim a source that is not registered.
- P6. Generated or community questions are stored under `02-question-bank/generated/` and carry `status: "unofficial"`. They must never overwrite the seed bank.

---

## 5. Question bank model

### 5.1 Storage

- Format: **JSONL** (one JSON object per line, UTF-8, no trailing comma).
- Seed bank lives at `02-question-bank/seed/sample-questions.jsonl` and must contain at least one question per domain (D1–D5).
- Normalized bank lives at `02-question-bank/normalized/` (one or more JSONL files), produced by validation.

### 5.2 Question record schema

```jsonc
{
  "id": "Q-D1-001",                    // string, unique across all banks, kebab/upper-case
  "source": "guide_en_pdf",            // string, must match a registered source id
  "domain": "D1",                      // enum: D1 | D2 | D3 | D4 | D5
  "scenario": "agentic-orchestration", // string, kebab-case, must appear in scenario-map.md
  "difficulty": "medium",              // enum: easy | medium | hard
  "stem": "…",                         // string, the question text
  "choices": {
    "A": "…",
    "B": "…",
    "C": "…",
    "D": "…"
  },
  "answer": "B",                       // enum: A | B | C | D
  "explanation": "…",                  // string, rationale for the correct answer
  "concept_tags": ["mcp", "tool-design"], // array<string>, kebab-case
  "status": "official"                 // enum: official | unofficial | draft | retired
}
```

Validation rules (enforced by `validate_questions.py`):

- V1. All required fields are present and non-empty.
- V2. `id` is unique across the entire scanned set.
- V3. `domain` ∈ {D1, D2, D3, D4, D5}.
- V4. `choices` contains exactly the keys `A`, `B`, `C`, `D`.
- V5. `answer` ∈ keys of `choices`.
- V6. `concept_tags` is a non-empty array of kebab-case strings.
- V7. `status` ∈ {official, unofficial, draft, retired}.
- V8. `source` matches a source id declared in `00-meta/source-register.md`.
- V9. Questions in `02-question-bank/generated/` must have `status != "official"`.

### 5.3 Domain weights (informational, MVP does not yet weight scoring)

| Domain | Title                                          | Weight |
|--------|------------------------------------------------|--------|
| D1     | Agentic Architecture & Orchestration           | 27%    |
| D2     | Tool Design & MCP Integration                  | 18%    |
| D3     | Claude Code Configuration & Workflows          | 20%    |
| D4     | Prompt Engineering & Structured Output         | 20%    |
| D5     | Context Management & Reliability               | 15%    |

Weights are recorded for later weighted-scoring extensions; **MVP scoring is unweighted** (see §7).

---

## 6. Attempt submission model

### 6.1 Inputs

- **Question bank** (JSONL) used during the attempt.
- **Answers file** (`examples/attempts/sample-answers.json`):

```jsonc
{
  "attempt_label": "self-mock-001",
  "started_at": "2026-05-11T09:00:00Z",
  "finished_at": "2026-05-11T10:00:00Z",
  "answers": [
    { "question_id": "Q-D1-001", "choice": "B" },
    { "question_id": "Q-D2-003", "choice": "A" }
  ]
}
```

### 6.2 Normalized attempt record schema

`submit_attempt.py` joins answers with the question bank and writes one JSON file to `05-learning-data/attempts/`:

```jsonc
{
  "attempt_id": "att-2026-05-11T10-00-00Z-self-mock-001",
  "attempt_label": "self-mock-001",
  "started_at": "2026-05-11T09:00:00Z",
  "finished_at": "2026-05-11T10:00:00Z",
  "question_bank_path": "02-question-bank/seed/sample-questions.jsonl",
  "answers": [
    {
      "question_id": "Q-D1-001",
      "domain": "D1",
      "scenario": "agentic-orchestration",
      "concept_tags": ["mcp", "tool-design"],
      "choice": "B",
      "correct": "B",
      "is_correct": true
    }
  ],
  "totals": {
    "total": 10,
    "correct": 8
  }
}
```

Rules:

- A1. `attempt_id` is deterministic from `finished_at` and `attempt_label`.
- A2. Every answer carries the joined `domain`, `scenario`, and `concept_tags` of its question. Scoring never re-reads the question bank.
- A3. Answers referencing unknown `question_id` fail submission.
- A4. Missing answers for questions in the bank are recorded as `choice: null, is_correct: false`.
- A5. Attempt files are append-only. `submit_attempt.py` must refuse to overwrite an existing file unless `--force` is passed.

---

## 7. Scoring policy

### 7.1 Formulae (MVP defaults)

```
raw_correct  = sum(is_correct)
total        = len(answers)
accuracy     = raw_correct / total
scaled_score = round(100 + accuracy * 900)
pass_mark    = 720
pass         = scaled_score >= pass_mark
pass_gap     = scaled_score - pass_mark        // signed
pass_progress = min(1.0, scaled_score / pass_mark)
```

### 7.2 Properties

- S1. Scoring is **deterministic**: same attempt JSON → same output.
- S2. Scoring is **unweighted** in MVP. Domain weights live in `00-meta/domain-map.md` but are not applied here.
- S3. `score_attempt.py` accepts an attempt path and prints a human-readable summary to stdout; an optional `--json` flag emits a machine-readable summary identical to the per-attempt block embedded in `dashboard-data.json` (§8).
- S4. Scoring must not require network, secrets, or the source PDF.
- S5. Edge case `total == 0` returns `scaled_score = 100`, `pass = false`, `pass_gap = -620`.

### 7.3 Breakdowns

`score_attempt.py` also computes:

- `domain_breakdown[D]`: `{ correct, total, accuracy }` for each domain present in the attempt.
- `scenario_breakdown[scenario]`: same shape, keyed by scenario.
- `concept_breakdown[tag]`: same shape, keyed by `concept_tag`, with one tag potentially counting toward multiple questions.

---

## 8. Dashboard data contract

`export_dashboard_data.py` aggregates **all** files under `05-learning-data/attempts/` plus `05-learning-data/lab-status.json` into a single `06-dashboard/data/dashboard-data.json`. This file is the **only** input the static dashboard consumes.

### 8.1 Schema

```jsonc
{
  "generated_at": "2026-05-11T10:05:00Z",
  "pass_mark": 720,

  "latest_attempt": {
    "attempt_id": "att-2026-05-11T10-00-00Z-self-mock-001",
    "finished_at": "2026-05-11T10:00:00Z",
    "raw_correct": 8,
    "total": 10,
    "accuracy": 0.8,
    "scaled_score": 820,
    "pass": true,
    "pass_gap": 100,
    "pass_progress": 1.0
  },

  "domain_breakdown": [
    {
      "domain": "D1",
      "title": "Agentic Architecture & Orchestration",
      "weight": 0.27,
      "correct": 2, "total": 3, "accuracy": 0.667
    }
    // … D2–D5
  ],

  "scenario_breakdown": [
    { "scenario": "agentic-orchestration", "correct": 1, "total": 2, "accuracy": 0.5 }
  ],

  "weak_concepts": [
    { "concept_tag": "mcp", "missed": 3, "seen": 4, "miss_rate": 0.75 }
    // sorted by miss_rate desc, ties by missed desc; top N = 10
  ],

  "lab_progress": {
    "total_labs": 12,
    "completed": 4,
    "in_progress": 2,
    "not_started": 6,
    "recommended_next": [
      { "lab_id": "lab-d2-mcp-basics", "reason": "weak concept: mcp" }
    ]
  },

  "trend": [
    { "attempt_id": "…", "finished_at": "…", "scaled_score": 740 },
    { "attempt_id": "…", "finished_at": "…", "scaled_score": 820 }
    // chronological asc by finished_at
  ]
}
```

### 8.2 Contract rules

- C1. The file MUST include every top-level key above. Empty arrays/objects are allowed when no data exists, but the key must be present.
- C2. `latest_attempt` is the attempt with the most recent `finished_at`.
- C3. `domain_breakdown` always lists D1–D5 in numeric order, even when zero questions were asked in that domain (`correct = total = 0`, `accuracy = null`).
- C4. `weak_concepts` is capped at 10 entries.
- C5. `lab_progress.recommended_next` is capped at 5 entries and derives from a deterministic rule: prefer labs tagged with the learner's top weak `concept_tags` whose `lab-status` is `not_started` or `in_progress`.
- C6. `trend` includes every attempt found, sorted chronologically ascending.
- C7. The export is pure: given identical inputs it produces byte-identical output (stable key ordering, sorted lists).

### 8.3 `lab-status.json` shape

```jsonc
{
  "labs": [
    {
      "lab_id": "lab-d2-mcp-basics",
      "domain": "D2",
      "concept_tags": ["mcp", "tool-design"],
      "status": "not_started",          // not_started | in_progress | completed
      "last_run": null                  // ISO-8601 or null
    }
  ]
}
```

---

## 9. Static dashboard scope

- D1. Pure static assets in `06-dashboard/static/`: one `index.html`, one `app.js`, one `style.css`.
- D2. Fetches `../data/dashboard-data.json` via `fetch()` only; no inline data, no build step.
- D3. Renders exactly the seven learner questions in §1, in this order:
  1. Pass/fail banner with `scaled_score` and `pass_gap`.
  2. Progress bar toward 720.
  3. Domain breakdown bar chart (D1–D5).
  4. Scenario breakdown table or bar chart.
  5. Weak concepts top-N list.
  6. Lab progress widget with `recommended_next`.
  7. Score trend line/sparkline.
- D4. Vanilla JS only. No React, no Vue, no bundler, no npm install required to view.
- D5. CSS is hand-written or vendored as a single stylesheet. No Tailwind build step.
- D6. Charting library, if any, must be a single `<script src="…">` from a vendored local file under `06-dashboard/static/vendor/` (no CDN at runtime). A no-library implementation using `<svg>` is acceptable and preferred.
- D7. Dashboard must degrade gracefully when fields are empty (e.g., zero attempts shows a "no data yet" state rather than a JS error).

---

## 10. Runtime commands (the final implementation must support all of these)

These are the canonical CLI surfaces. The implementation step must wire them to working scripts.

### 10.1 Validate the question bank

```bash
python -m cca_f_study.validate_questions 02-question-bank/seed/sample-questions.jsonl
```

Expected stdout (exit code 0 on success):

```text
valid questions: N
invalid questions: 0
```

On any validation failure, exit code is non-zero and each failure is printed with `id` and reason.

### 10.2 Submit / normalize an attempt

```bash
python 04-exam-runner/submit_attempt.py \
  --questions 02-question-bank/seed/sample-questions.jsonl \
  --answers   examples/attempts/sample-answers.json \
  --out       05-learning-data/attempts/sample-attempt.json
```

Writes the normalized attempt JSON (§6.2). Refuses to overwrite without `--force`.

### 10.3 Score an attempt

```bash
python 04-exam-runner/score_attempt.py 05-learning-data/attempts/sample-attempt.json
```

Human-readable stdout:

```text
Raw score: 8 / 10
Scaled score: 820 / 1000
Pass mark: 720
Result: PASS
Gap: +100

Domain breakdown:
  D1: 2/3
  D2: 1/2
  D3: 2/2
  D4: 2/2
  D5: 1/1
```

With `--json`, emits the machine-readable summary used by the dashboard exporter.

### 10.4 Export dashboard data

```bash
python 04-exam-runner/export_dashboard_data.py \
  --attempts   05-learning-data/attempts \
  --lab-status 05-learning-data/lab-status.json \
  --out        06-dashboard/data/dashboard-data.json
```

Writes the `dashboard-data.json` defined in §8.

### 10.5 Run tests

```bash
pytest
```

### 10.6 Open the dashboard

```bash
python -m http.server 8000 -d 06-dashboard/static
```

Then open `http://localhost:8000/` in a browser.

---

## 11. Validation strategy

### 11.1 Test layers

| Layer       | Mechanism                                    | What it proves                                                  |
|-------------|----------------------------------------------|------------------------------------------------------------------|
| Schema      | `tests/test_validate_questions.py`           | Invalid fixtures are rejected; valid seed bank passes.          |
| Submission  | `tests/test_submit_attempt.py`               | Join correctness, missing-answer handling, overwrite guard.     |
| Scoring     | `tests/test_score_attempt.py`                | Scaled-score formula, edge cases (0/N, N/N), breakdown sums.    |
| Aggregation | `tests/test_export_dashboard_data.py`        | Contract §8: every required key present, sort/cap rules hold.   |

### 11.2 Fixtures

- `tests/fixtures/questions/valid.jsonl` and `…/invalid_*.jsonl` for schema tests.
- `tests/fixtures/attempts/answers_*.json` + matching expected attempt JSON.
- `tests/fixtures/lab-status/*.json` for export tests.

### 11.3 Static dashboard validation

- Manual smoke test: run §10.4 then §10.6 and confirm the seven widgets render with the fixture data.
- Automated check: `tests/test_export_dashboard_data.py` validates `dashboard-data.json` shape — the dashboard itself does not need a JS test harness in MVP.

### 11.4 Determinism checks

- The exporter is invoked twice with the same inputs in CI/local; outputs are byte-compared.

---

## 12. Completion criteria

The MVP is "done" only when **every** item below holds.

- CC1. `01-sources/en/guide_en.pdf` exists and is unchanged from its original sha256.
- CC2. `00-meta/source-register.md` registers the PDF with the fields listed in §4 P4.
- CC3. `00-meta/domain-map.md` and `00-meta/scenario-map.md` exist and are referenced by at least one seed question each.
- CC4. `02-question-bank/seed/sample-questions.jsonl` contains ≥ 10 questions, with ≥ 1 per domain D1–D5.
- CC5. `python -m cca_f_study.validate_questions 02-question-bank/seed/sample-questions.jsonl` prints `invalid questions: 0` and exits 0.
- CC6. `examples/attempts/sample-answers.json` exists; running `submit_attempt.py` (§10.2) produces a file under `05-learning-data/attempts/` matching the schema in §6.2.
- CC7. `score_attempt.py` (§10.3) prints raw score, scaled score, pass/fail, gap, and a per-domain breakdown.
- CC8. `export_dashboard_data.py` (§10.4) writes `06-dashboard/data/dashboard-data.json` whose shape matches §8.1 and obeys §8.2 contract rules.
- CC9. `pytest` exits 0 with ≥ 1 test per layer in §11.1.
- CC10. `python -m http.server 8000 -d 06-dashboard/static` serves a page that renders all seven widgets in §1 using the generated `dashboard-data.json`.
- CC11. None of the runtime scripts in §10 read or parse `01-sources/en/guide_en.pdf`. Removing the PDF must not break commands §10.1–§10.5.
- CC12. None of the runtime scripts perform network I/O or require environment secrets.
- CC13. Every question whose origin is not the source PDF carries `status` ≠ `"official"`.
- CC14. `dashboard-data.json` regenerates byte-identically on repeated runs with the same inputs (§8.2 C7).

A task or prompt that cannot satisfy a criterion must stop and emit a BLOCKED report containing: the failed criterion id, the exact command/output/error, what was attempted, and the next concrete fix.

---

## 13. Explicit out-of-scope items for MVP

(Recap of §2 with the precise items deferred to the post-MVP "확장판".)

| Out-of-scope item                                       | Deferred to                  |
|---------------------------------------------------------|------------------------------|
| PDF text extraction / OCR                               | post-MVP extension           |
| Automatic question generation from the PDF              | post-MVP extension           |
| NotebookLM API/automation                               | post-MVP extension           |
| GitHub mock-exam auto-import                            | post-MVP extension           |
| Duplicate-question detection workflow                   | post-MVP extension           |
| Question review workflow tooling                        | post-MVP extension           |
| React / Vite dashboard                                  | post-MVP dashboard v2        |
| Auto-generated lab scaffolds                            | post-MVP labs phase          |
| Claude Code skill packs beyond superpowers              | post-MVP skills phase        |
| Server / DB / auth                                      | not planned                  |
| Weighted scoring using domain weights                   | post-MVP scoring v2          |
| Multi-language source bank (ko, etc.)                   | post-MVP i18n                |

---

## 14. Traceability to inputs

- Inherits MVP boundary and safety rules from `CLAUDE.md` (root) — PDF read-only, no external APIs, no secrets, static dashboard.
- Reuses the theory↔lab↔index architecture from `01-1차-설계.md`.
- Aligns command surface and completion gates with `04-구현-계획-및-프롬프트.md` §11.
- Domain weights and question-record fields come from `CLAUDE.md` and are restated here for self-containment.

## 15. Next prompts (downstream contract)

This spec is the contract for the next prompts in the chain:

1. `/plan` → `docs/plans/2026-05-cca-f-study-runtime-mvp-plan.md` (TDD-oriented phases).
2. `/implement` → code under `04-exam-runner/`, `06-dashboard/static/`, `tests/`.
3. `/dashboard-design` → `06-dashboard/dashboard-spec.md`, wireframe, component map.
4. `/review` → `docs/reviews/2026-05-cca-f-study-runtime-mvp-review.md`.
5. `/fix` → blockers and important findings only; scope frozen by this spec.

No implementation code is written in this step.
