# NotebookLM Source Index

Index of source sets that can be uploaded to NotebookLM for human study. Forward-compatible with multi-PDF batches (see `06-kr-pdf-없이-선구현-계획.md` and `05-kr-pdf-구조-차이-반영.md`).

## Source sets

### EN-CORE
- **Status**: `active`
- **Source IDs**: `guide_en`
- **Files**:
  - `01-sources/en/guide_en.pdf` *(read-only; see `00-meta/source-register.md` for current presence status)*
- **Role**: Primary English reference for CCA-F structure, domains, scenarios, and terminology.
- **Domains covered**: D1, D2, D3, D4, D5
- **Scenarios covered**: all scenarios listed in `00-meta/scenario-map.md`

### KR-LECTURES
- **Status**: `planned`
- **Source IDs**: *(to be assigned, prefix `kr_`)*
- **Files**: *(TBD — to be staged under `01-sources/kr/raw/` and curated under a future `02-notebooklm-upload/` batch)*
- **Role**: Korean lecture PDFs to be added later; activation will not break the active `EN-CORE` set.

## Notes for future expansion

- When KR PDFs arrive, add them to `01-sources/kr/raw/`, register each in a `source-manifest.json`, and either (a) extend this index with a flat `kr/` set, or (b) introduce batch subdirectories under `02-notebooklm-upload/` (`kr-batch-01-core/`, etc.).
- The runtime does **not** depend on this index for scoring. The index is human + author-tooling metadata only.
