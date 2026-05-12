맞아. 내가 `cca-f-guide_kr.pdf` 1개처럼 쓴 건 **단순화한 예시**였고, 실제로 PDF가 수십 개로 쪼개져 있으면 설계가 달라져야 합니다.
이 경우에는 `02-notebooklm-upload/`에 PDF 하나를 두는 구조가 아니라, **PDF 묶음 + manifest + index** 구조로 가야 합니다.

기존 핵심 원칙은 그대로입니다. PDF는 NotebookLM용 읽기 소스, 실습 코드는 repo에서 관리하고, 둘을 인덱스로 연결한다는 구조입니다. 첨부 설계에서도 이론 PDF와 실습 Lab, 복습 노트를 1:1로 연결하는 것을 핵심으로 잡고 있습니다. 

## 수정된 구조

PDF가 수십 개라면 이렇게 해야 합니다.

```text
cca-f-study/
├── 01-sources/
│   ├── kr/
│   │   ├── raw/
│   │   │   ├── 001-introduction.pdf
│   │   │   ├── 002-claude-api.pdf
│   │   │   ├── 003-tool-use.pdf
│   │   │   ├── 004-mcp.pdf
│   │   │   └── ...
│   │   ├── source-manifest.json
│   │   └── source-register.md
│   │
│   └── en/
│       └── guide_en.pdf
│
├── 02-notebooklm-upload/
│   ├── README.md
│   ├── pdfs/
│   │   ├── 001-introduction.pdf
│   │   ├── 002-claude-api.pdf
│   │   ├── 003-tool-use.pdf
│   │   ├── 004-mcp.pdf
│   │   └── ...
│   ├── notebooklm-source-index.md
│   ├── pdf-manifest.md
│   ├── lab-catalog.md
│   ├── domain-map.md
│   ├── scenario-map.md
│   └── glossary_kr-en.md
```

핵심은 `cca-f-guide_kr.pdf` 같은 단일 파일명이 아니라, **`pdfs/` 폴더 전체가 NotebookLM 업로드 대상**이 되는 겁니다.

---

## 각 파일 역할도 바뀜

| 파일/폴더                                  | 역할                                        |
| -------------------------------------- | ----------------------------------------- |
| `01-sources/kr/raw/*.pdf`              | 원본 KR PDF 전체 보관소                          |
| `01-sources/kr/source-manifest.json`   | PDF별 ID, 제목, 순서, 해시, 관련 도메인 기록            |
| `02-notebooklm-upload/pdfs/*.pdf`      | NotebookLM에 실제 업로드할 PDF 사본                |
| `02-notebooklm-upload/pdf-manifest.md` | NotebookLM에게 “이 PDF들이 어떤 순서/관계인지” 알려주는 목차 |
| `notebooklm-source-index.md`           | PDF 묶음과 실습 코드, 문제은행, 노트를 연결               |
| `lab-catalog.md`                       | 실습 코드 목록                                  |
| `domain-map.md`                        | 시험 도메인 기준 매핑                              |
| `scenario-map.md`                      | 시나리오 기준 매핑                                |
| `glossary_kr-en.md`                    | KR/EN 용어 매핑                               |

즉, NotebookLM에 올리는 건 이런 세트입니다.

```text
02-notebooklm-upload/pdfs/*.pdf
02-notebooklm-upload/pdf-manifest.md
02-notebooklm-upload/notebooklm-source-index.md
02-notebooklm-upload/lab-catalog.md
02-notebooklm-upload/domain-map.md
02-notebooklm-upload/scenario-map.md
02-notebooklm-upload/glossary_kr-en.md
```

---

## `pdf-manifest.md`가 추가로 필요함

PDF가 수십 개면 NotebookLM이 “각 PDF가 무슨 순서인지”를 자동으로 잘 이해한다고 기대하면 안 됩니다. 그래서 별도 manifest가 필요합니다.

```markdown
# CCA-F KR PDF Manifest

## Upload Set

This NotebookLM source set contains multiple Korean PDF files for CCA-F study.
Use this manifest as the canonical order and relationship map.

| Order | Source ID | File | Title | Related Domain | Related Lab |
|---:|---|---|---|---|---|
| 001 | KR-C00-INTRO | `pdfs/001-introduction.pdf` | 과정 소개 | D0 Overview | - |
| 002 | KR-C01-API | `pdfs/002-claude-api.pdf` | Claude API 기본 | D4, D5 | `03-labs/C01-claude-api-fundamentals/` |
| 003 | KR-C02-TOOLS | `pdfs/003-tool-use.pdf` | Tool Use와 Structured Output | D2, D4 | `03-labs/C02-tool-use-structured-output/` |
| 004 | KR-C04-MCP | `pdfs/004-mcp.pdf` | MCP Integration | D2 | `03-labs/C04-mcp-integration/` |
```

이 파일이 있어야 NotebookLM에 이렇게 물어볼 수 있습니다.

```text
003-tool-use.pdf와 연결된 실습은 어디야?
D2 Tool Design에 해당하는 PDF들을 순서대로 알려줘.
MCP 관련 PDF와 실습, 모의고사 문제를 연결해서 정리해줘.
```

---

## `notebooklm-source-index.md`도 단일 PDF 기준이 아니라 다중 PDF 기준으로 바꿔야 함

```markdown
# CCA-F NotebookLM Source Index

## C01 — Claude API Fundamentals

### Related PDFs
- `pdfs/002-claude-api.pdf`
- `pdfs/005-messages-api-examples.pdf`

### Related Labs
- `03-labs/C01-claude-api-fundamentals/`

### Related Question Bank
- `02-question-bank/normalized/D4-claude-api.jsonl`

### Key Concepts
- Messages API
- system prompt
- conversation history
- stop_reason
- context window

### Related Domains
- D4 Prompt Engineering & Structured Output
- D5 Context Management & Reliability
```

---

## PDF가 너무 많으면 batch 구조로 나눠야 함

NotebookLM의 현재 업로드 제한이나 용량 제한은 시점에 따라 바뀔 수 있어서 여기서 숫자를 확정하면 위험합니다. 그래서 설계는 처음부터 batch를 지원해야 합니다.

```text
02-notebooklm-upload/
├── batch-01-core/
│   ├── pdfs/
│   ├── pdf-manifest.md
│   └── notebooklm-source-index.md
│
├── batch-02-claude-code/
│   ├── pdfs/
│   ├── pdf-manifest.md
│   └── notebooklm-source-index.md
│
├── batch-03-mcp-tools/
│   ├── pdfs/
│   ├── pdf-manifest.md
│   └── notebooklm-source-index.md
│
└── batch-04-exam-review/
    ├── pdfs/
    ├── pdf-manifest.md
    └── notebooklm-source-index.md
```

추천 batch 기준은 이겁니다.

```text
batch-01-core
= Claude API, model basics, prompt basics, structured output

batch-02-agent-tools
= tool_use, Agent SDK, subagents, orchestration

batch-03-mcp-claude-code
= MCP, Claude Code, skills, CLAUDE.md, CI/CD

batch-04-reliability-exam
= context management, reliability, scenarios, exam review
```

즉, PDF 수십 개를 하나의 NotebookLM notebook에 무조건 다 넣는 게 아니라, **학습 목적별 NotebookLM notebook을 여러 개로 나누는 것도 고려**해야 합니다.

---

## source manifest는 JSON으로 관리하는 게 좋음

Claude Code가 관리하기 좋게 `source-manifest.json`을 둡니다.

```json
{
  "source_set": "cca-f-kr-pdfs",
  "language": "ko",
  "version": "2026-05",
  "documents": [
    {
      "source_id": "KR-C01-API",
      "order": 2,
      "file": "001-sources/kr/raw/002-claude-api.pdf",
      "upload_file": "02-notebooklm-upload/pdfs/002-claude-api.pdf",
      "title": "Claude API 기본",
      "domains": ["D4", "D5"],
      "scenarios": ["S06", "S07"],
      "labs": ["03-labs/C01-claude-api-fundamentals"],
      "sha256": "<hash>"
    },
    {
      "source_id": "KR-C02-TOOLS",
      "order": 3,
      "file": "001-sources/kr/raw/003-tool-use.pdf",
      "upload_file": "02-notebooklm-upload/pdfs/003-tool-use.pdf",
      "title": "Tool Use와 Structured Output",
      "domains": ["D2", "D4"],
      "scenarios": ["S01", "S06"],
      "labs": ["03-labs/C02-tool-use-structured-output"],
      "sha256": "<hash>"
    }
  ]
}
```

이걸 기준으로 Claude Code가 자동 생성할 수 있습니다.

```text
- pdf-manifest.md
- notebooklm-source-index.md
- domain-map.md 일부
- scenario-map.md 일부
- lab-catalog.md 일부
```

---

## Claude Code 프롬프트도 바꿔야 함

이전 프롬프트의 이 부분:

```text
The repository initially contains only one source PDF:
01-sources/en/guide_en.pdf
```

이제 이렇게 바꿔야 합니다.

```text
The repository may contain many source PDFs:
01-sources/kr/raw/*.pdf
01-sources/en/*.pdf

Do not assume there is a single guide PDF.
All PDFs must be registered through:
01-sources/kr/source-manifest.json

NotebookLM upload files must be generated or curated under:
02-notebooklm-upload/

The upload package must include:
- pdfs/*.pdf
- pdf-manifest.md
- notebooklm-source-index.md
- lab-catalog.md
- domain-map.md
- scenario-map.md
- glossary_kr-en.md
```

---

## 수정된 완료 기준

단일 PDF 기준 완료 기준은 버리고, 이렇게 바꿔야 합니다.

```text
완료 기준:
1. 01-sources/kr/raw/*.pdf 파일을 스캔한다.
2. 각 PDF에 source_id, order, title, sha256을 부여한다.
3. 01-sources/kr/source-manifest.json을 생성한다.
4. 02-notebooklm-upload/pdfs/에 업로드 대상 PDF를 복사한다.
5. 02-notebooklm-upload/pdf-manifest.md를 생성한다.
6. 02-notebooklm-upload/notebooklm-source-index.md가 모든 PDF 또는 batch를 참조한다.
7. orphan PDF가 없어야 한다.
8. manifest에는 있는데 실제 파일이 없는 항목이 없어야 한다.
9. domain-map/scenario-map에서 참조하는 source_id가 manifest에 존재해야 한다.
```

검증 명령도 필요합니다.

```bash
python -m cca_f_study.validate_sources \
  --manifest 01-sources/kr/source-manifest.json \
  --upload-dir 02-notebooklm-upload
```

성공 출력은 이런 식이어야 합니다.

```text
Source PDFs: 37
Registered documents: 37
Upload PDFs: 37
Missing files: 0
Orphan PDFs: 0
Invalid source references: 0
Result: OK
```

---

## 최종 구조 추천

PDF가 몇십 개면 최종적으로는 이 구조가 맞습니다.

```text
cca-f-study/
├── 01-sources/
│   ├── kr/
│   │   ├── raw/
│   │   │   ├── 001-*.pdf
│   │   │   ├── 002-*.pdf
│   │   │   └── ...
│   │   ├── source-manifest.json
│   │   └── source-register.md
│   └── en/
│       └── guide_en.pdf
│
├── 02-notebooklm-upload/
│   ├── README.md
│   ├── pdfs/
│   │   ├── 001-*.pdf
│   │   ├── 002-*.pdf
│   │   └── ...
│   ├── pdf-manifest.md
│   ├── notebooklm-source-index.md
│   ├── lab-catalog.md
│   ├── domain-map.md
│   ├── scenario-map.md
│   └── glossary_kr-en.md
│
├── 03-labs/
├── 04-exam-runner/
├── 05-learning-data/
└── 06-dashboard/
```

정리하면, 네 지적이 맞고 **`cca-f-guide_kr.pdf` 하나를 전제로 한 설계는 취약합니다.**
올바른 설계는 **단일 PDF 설계가 아니라 “다중 PDF source set 설계”**입니다.

한 줄로 바꾸면 이겁니다.

```text
cca-f-guide_kr.pdf
```

가 아니라:

```text
KR PDF Source Set
= raw PDFs + source-manifest + pdf-manifest + NotebookLM upload package
```

이렇게 잡아야 나중에 PDF가 5개든 50개든 구조가 안 깨집니다.
