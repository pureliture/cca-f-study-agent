# Source Register

This register declares the **read-only source artifacts** that anchor the CCA-F study runtime.  
Runtime scripts under `src/cca_f_study/` and `04-exam-runner/` **must not parse these PDFs**.  
They are evidence for human study (via NotebookLM) and for authoring/curating the question bank — nothing more.

## Source IDs

The `source` field on every question must be one of the IDs below.  
Source IDs are also referenced by `00-meta/domain-map.md`, `00-meta/scenario-map.md`, and `00-meta/notebooklm-source-index.md`.

| Source ID  | Status | Language | Path                              |
|------------|--------|----------|-----------------------------------|
| `guide_en` | active | en       | `01-sources/en/guide_en.pdf`      |

> **Reserved (not active in MVP)**: `kr_lectures` — future Korean PDF source set, to be activated when KR PDFs are added under `01-sources/kr/raw/`. See `06-kr-pdf-없이-선구현-계획.md`.

## EN-CORE — `guide_en`

| Field            | Value                                                  |
|------------------|--------------------------------------------------------|
| `source_id`      | `guide_en`                                             |
| `path`           | `01-sources/en/guide_en.pdf`                           |
| `language`       | `en`                                                   |
| `source_type`    | `PDF`                                                  |
| `sha256`         | `f4d2d909b2c456fbef93a8d67480f0259f7016fd94067682b83901f631385924` |
| `imported_at`    | `2026-05-12T00:23:16Z`                                 |
| `read_only`      | **true**                                                |
| `note`           | read-only source artifact; do not parse at runtime     |

### Companion (token-efficient reference)

A Markdown rendering of the same guide is kept alongside the PDF for **author/tooling token efficiency only**. It is **not** the runtime source and is **not** read by any runtime script.

| Field         | Value                                                         |
|---------------|---------------------------------------------------------------|
| `role`        | companion (human/author reference; not runtime input)         |
| `path`        | `01-sources/en/companion/guide_en.md`                         |
| `sha256`      | `d6acc9a92e54eef67d17cb396080d5822d467c392890c75be3e304a055fd1490` |
| `read_only`   | **true**                                                       |
| `note`        | textual companion to `guide_en.pdf`; not a substitute source  |

The companion file shares the canonical `source_id` (`guide_en`) — it is the same body of evidence in a different encoding. Questions still cite `source: "guide_en"` regardless of which rendering the author consulted.

### Read-only contract

- No tool, script, or test in this repository may **open the PDF for writing** under any circumstance.
- The PDF may be **read once** during registration to compute `sha256`. Runtime scripts must work — and tests must pass — when the PDF is physically absent (the registration row is the runtime source of truth, not the binary).
- The PDF is **not parsed**: no text extraction, no OCR, no embeddings.
- The PDF is **not mutated**: no annotation, no re-encoding, no metadata edits.

## Generated / community sources

Questions originating from any source **not listed** in the Source IDs table above must carry `status` ∈ {`unofficial`, `draft`, `retired`} — never `official`. They live under `02-question-bank/generated/` and never overwrite the seed bank.
