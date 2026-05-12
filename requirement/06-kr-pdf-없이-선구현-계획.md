그렇게 시작해도 됩니다.
단, 처음부터 `02-notebooklm-upload/`를 **“단일 PDF 전용 폴더”**가 아니라 **“NotebookLM 업로드 패키지의 현재 버전”**으로 정의해야 합니다.

즉 처음에는 이렇게 시작합니다.

```text
02-notebooklm-upload/
├── guide_en.pdf
├── notebooklm-source-index.md
├── lab-catalog.md
├── domain-map.md
├── scenario-map.md
└── glossary_en-kr.md
```

나중에 KR PDF가 추가되면 **기존 구조를 폐기하는 게 아니라 source set을 확장**합니다.

---

## 1. 초기 설계에서 미리 정해둘 것

처음부터 `notebooklm-source-index.md`에 이렇게 써두면 됩니다.

```markdown
# NotebookLM Source Index

## Source Sets

### EN-CORE
- Status: active
- Files:
  - `guide_en.pdf`
- Role:
  - Primary English reference for CCA-F structure, domains, scenarios, and terminology.

### KR-LECTURES
- Status: planned
- Files:
  - TBD
- Role:
  - Korean lecture PDFs to be added later.
```

즉, 현재는 `EN-CORE`만 활성화되어 있고, `KR-LECTURES`는 나중에 추가될 source set으로 남겨두는 겁니다.

---

## 2. KR PDF가 “몇 개 안 되는 경우”

예를 들어 KR PDF가 1~5개 정도라면 단순 확장으로 충분합니다.

```text
02-notebooklm-upload/
├── guide_en.pdf
├── kr/
│   ├── 001-intro_kr.pdf
│   ├── 002-tool-use_kr.pdf
│   └── 003-mcp_kr.pdf
├── notebooklm-source-index.md
├── pdf-manifest.md
├── lab-catalog.md
├── domain-map.md
├── scenario-map.md
└── glossary_en-kr.md
```

이때 새로 추가되는 핵심 파일은 `pdf-manifest.md`입니다.

```markdown
# PDF Manifest

| Source ID | Language | File | Title | Related Domain | Related Lab |
|---|---|---|---|---|---|
| EN-CORE-001 | en | `guide_en.pdf` | CCA-F English Guide | All | All |
| KR-001 | ko | `kr/001-intro_kr.pdf` | 과정 소개 | Overview | - |
| KR-002 | ko | `kr/002-tool-use_kr.pdf` | Tool Use | D2, D4 | `03-labs/C02-tool-use-structured-output/` |
| KR-003 | ko | `kr/003-mcp_kr.pdf` | MCP | D2 | `03-labs/C04-mcp-integration/` |
```

---

## 3. KR PDF가 “수십 개”인 경우

수십 개면 `02-notebooklm-upload/` 하나에 다 때려 넣기보다 batch로 나누는 게 좋습니다.

```text
02-notebooklm-upload/
├── en-core/
│   ├── guide_en.pdf
│   ├── pdf-manifest.md
│   └── notebooklm-source-index.md
│
├── kr-batch-01-core/
│   ├── pdfs/
│   │   ├── 001-intro_kr.pdf
│   │   ├── 002-api_kr.pdf
│   │   └── 003-structured-output_kr.pdf
│   ├── pdf-manifest.md
│   └── notebooklm-source-index.md
│
├── kr-batch-02-tools-mcp/
│   ├── pdfs/
│   │   ├── 004-tool-use_kr.pdf
│   │   ├── 005-mcp_kr.pdf
│   │   └── 006-agent-sdk_kr.pdf
│   ├── pdf-manifest.md
│   └── notebooklm-source-index.md
│
├── lab-catalog.md
├── domain-map.md
├── scenario-map.md
└── glossary_en-kr.md
```

이 경우 NotebookLM도 하나로 몰기보다 다음처럼 나누는 게 좋습니다.

```text
NotebookLM Notebook 1: CCA-F EN Core
NotebookLM Notebook 2: CCA-F KR Core
NotebookLM Notebook 3: CCA-F Tools / MCP / Agent SDK
NotebookLM Notebook 4: CCA-F Exam Review
```

이렇게 해야 NotebookLM의 컨텍스트가 너무 넓어져서 답변 품질이 떨어지는 걸 줄일 수 있습니다.

---

## 4. 원본 보관소는 별도로 두는 게 좋음

`02-notebooklm-upload/`는 NotebookLM에 올릴 “패키지”이고, 원본 source of truth는 별도로 둬야 합니다.

추천 구조:

```text
01-sources/
├── en/
│   └── guide_en.pdf
└── kr/
    ├── raw/
    │   ├── 001-intro_kr.pdf
    │   ├── 002-api_kr.pdf
    │   └── ...
    └── source-manifest.json

02-notebooklm-upload/
├── en-core/
├── kr-batch-01-core/
├── kr-batch-02-tools-mcp/
├── lab-catalog.md
├── domain-map.md
├── scenario-map.md
└── glossary_en-kr.md
```

즉:

```text
01-sources/
= 원본 보관

02-notebooklm-upload/
= NotebookLM에 올릴 curated copy
```

---

## 5. 나중에 KR PDF 추가 시 작업 절차

KR PDF가 들어오면 이렇게 처리하면 됩니다.

```text
1. 01-sources/kr/raw/ 에 PDF 추가
2. source-manifest.json에 파일 등록
3. sha256, title, language, source_id 부여
4. 어떤 batch에 넣을지 결정
5. 02-notebooklm-upload/kr-batch-XX/pdfs/ 로 복사
6. pdf-manifest.md 갱신
7. notebooklm-source-index.md 갱신
8. domain-map.md / scenario-map.md 갱신
9. glossary_en-kr.md에 새 용어 추가
10. NotebookLM에 해당 batch 업로드
```

Claude Code에게는 이렇게 시키면 됩니다.

```text
01-sources/kr/raw/에 새 KR PDF들이 추가되었다.

작업:
1. 모든 PDF를 스캔해서 source-manifest.json을 갱신해라.
2. 각 PDF에 source_id, order, title, language, sha256을 부여해라.
3. PDF 제목/파일명 기준으로 적절한 NotebookLM batch를 제안해라.
4. 02-notebooklm-upload/ 아래에 필요한 batch 폴더를 생성해라.
5. pdf-manifest.md를 생성/갱신해라.
6. notebooklm-source-index.md에서 EN guide와 KR PDF의 관계를 연결해라.
7. domain-map.md와 scenario-map.md의 source reference를 갱신해라.
8. glossary_en-kr.md에 새로 발견한 용어 후보를 추가하되, status는 `needs_review`로 표시해라.

완료 기준:
- source-manifest.json에 모든 KR PDF가 등록되어야 한다.
- 등록된 파일 중 실제 파일이 없는 항목이 없어야 한다.
- raw에는 있는데 manifest에 없는 orphan PDF가 없어야 한다.
- upload batch에 포함된 PDF는 manifest의 source_id를 가져야 한다.
- domain-map/scenario-map에서 참조하는 source_id는 모두 manifest에 존재해야 한다.
```

---

## 6. 그래서 지금 구조를 어떻게 잡아야 하냐

지금 당장은 네가 말한 구조로 시작해도 됩니다.

```text
02-notebooklm-upload/
├── guide_en.pdf
├── notebooklm-source-index.md
├── lab-catalog.md
├── domain-map.md
├── scenario-map.md
└── glossary_en-kr.md
```

다만 파일 안의 표현을 이렇게 해야 합니다.

```text
guide_en.pdf 하나만 있는 구조
```

가 아니라:

```text
현재 활성화된 source set은 EN-CORE 하나뿐이다.
나중에 KR-LECTURES source set을 추가할 수 있다.
```

그리고 나중에 KR PDF가 들어오면 최종적으로 이렇게 진화시킵니다.

```text
02-notebooklm-upload/
├── en-core/
│   ├── guide_en.pdf
│   ├── pdf-manifest.md
│   └── notebooklm-source-index.md
│
├── kr-batch-01-core/
│   ├── pdfs/
│   ├── pdf-manifest.md
│   └── notebooklm-source-index.md
│
├── kr-batch-02-tools-mcp/
│   ├── pdfs/
│   ├── pdf-manifest.md
│   └── notebooklm-source-index.md
│
├── lab-catalog.md
├── domain-map.md
├── scenario-map.md
└── glossary_en-kr.md
```

---

## 최종 정리

처음에는 단순하게:

```text
02-notebooklm-upload/
├── guide_en.pdf
├── notebooklm-source-index.md
├── lab-catalog.md
├── domain-map.md
├── scenario-map.md
└── glossary_en-kr.md
```

나중에 KR PDF가 추가되면:

```text
단일 EN 업로드 패키지
→ EN-CORE source set
→ KR-LECTURES source set 추가
→ PDF가 많으면 kr-batch-01, kr-batch-02로 분리
→ manifest/index/map/glossary 갱신
```

즉, 지금 설계의 핵심 수정은 이것 하나입니다.

```text
02-notebooklm-upload는 “guide_en.pdf 전용 폴더”가 아니라
“NotebookLM에 올릴 source set 패키지”다.
```

이렇게 정의해두면 KR PDF가 나중에 1개가 들어오든 50개가 들어오든 구조를 버리지 않고 확장할 수 있습니다.
