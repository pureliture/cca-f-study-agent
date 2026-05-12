# CCA-F Study Runtime

Local study runtime for **Claude Certified Architect — Foundations (CCA-F)**.

The runtime is a small, dependency-light Python toolkit plus a static dashboard.  
It is designed to operate **without parsing the source PDF, without any external API call, and without secrets**.

- Spec: [`docs/specs/2026-05-cca-f-study-runtime-mvp.md`](docs/specs/2026-05-cca-f-study-runtime-mvp.md)
- Plan: [`docs/plans/2026-05-cca-f-study-runtime-mvp-plan.md`](docs/plans/2026-05-cca-f-study-runtime-mvp-plan.md)
- Project rules: [`CLAUDE.md`](CLAUDE.md)

## MVP scope (this iteration)

This iteration implements **phases 1–4 of the plan**:

1. Repository skeleton + project rules
2. Python package bootstrap (`cca_f_study`)
3. Question + attempt JSON Schemas
4. Seed question bank, sample answers, and the question-bank validator

Scoring, dashboard export, and the static dashboard are **not** part of this iteration.

## Quick start

```bash
# 1. Install the package in editable mode (dev only)
pip install -e ".[dev]"

# 2. Validate the seed question bank
python -m cca_f_study.validate_questions 02-question-bank/seed/sample-questions.jsonl

# 3. Run the test suite
pytest
```

## Layout

```text
.
├── CLAUDE.md
├── README.md
├── pyproject.toml
├── 00-meta/                       # source register, domain/scenario maps, NotebookLM index
├── 01-sources/en/                 # canonical source PDF (read-only)
├── 02-question-bank/seed/         # hand-authored seed questions (JSONL)
├── 04-exam-runner/                # JSON Schemas (runtime scripts arrive in later phases)
├── 05-learning-data/              # attempts + lab status (filled by later phases)
├── 06-dashboard/                  # static dashboard (built in a later phase)
├── examples/attempts/             # sample answers input
├── docs/                          # specs, plans, reviews
├── src/cca_f_study/               # Python package (validator + future runtime modules)
└── tests/                         # pytest suite
```

## Safety

- The source PDF is **read-only**. The runtime never parses it.
- No network calls. No API keys.
- Any question whose origin is not the registered source carries `status != "official"`.
