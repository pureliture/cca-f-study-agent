# CCA-F 학습 런타임

> 📘 English version: [README_en.md](README_en.md)

Claude Certified Architect — Foundations (CCA-F) 시험을 준비하기 위한 의존성이 가벼운 로컬 Python 학습 도구입니다. 로컬 문제은행을 검증하고, 모의고사 응시를 기록하며, 합격 기준 점수 720점에 대비한 환산 점수를 계산하고, 7-위젯 정적 대시보드를 제공합니다 — 어떤 단계에서도 **PDF 파싱·네트워크 호출·API 키가 필요하지 않습니다**.

## 현재 상태

| 항목 | 값 |
|---|---|
| MVP 단계 완료 | 10 / 10 |
| 사양 목표 (G1–G7) | 7 / 7 |
| 완료 기준 (CC1–CC14) | 14 / 14 PASS |
| pytest | 130 passing · 1 intentional skip |
| 시드 응시 | 8 / 10 정답 → 환산 820 → **PASS** (gap +100) |
| 최신 커밋 | `418c1f1` Phase 10: final validation report — MVP PASS |

---

## 런타임 파이프라인

<img src="docs/assets/pipeline.svg" alt="5단계 런타임 파이프라인: 문제 검증, 응시 제출, 점수 산정, 대시보드 데이터 export, 정적 대시보드 렌더. 각 단계마다 구동 CLI 명령과 생성 산출물이 표기됨.">

---

## 주요 기능

- **문제 등록·검증** — JSONL 형식으로 문제를 작성하거나 import한 뒤, `validate_questions`가 다른 작업 이전에 모든 필드를 JSON 스키마에 대해 검증합니다.
- **모의고사 응시 제출** — `submit_attempt`가 학습자의 선택지를 문제은행과 join하고, 표기를 정규화하며 문항별 메타데이터를 기록합니다.
- **CCA-F 합격선 기준 채점** — `score_attempt`가 100–1000 척도(`100 + 정답/총수 × 900`)의 환산 점수를 계산하고 720 합격선과 비교합니다.
- **결정적 대시보드 데이터 export** — `export_dashboard_data`가 모든 응시와 lab-status 파일을 단일 `dashboard-data.json`으로 집계합니다. 동일 입력이면 동일 byte 결과가 보장됩니다.
- **브라우저로 진행 상황 확인** — `python -m http.server`로 띄우는 vanilla HTML/CSS/JS 대시보드가 합격/불합격, 도메인 약점, 약점 개념 태그, lab 진행률, 점수 추이를 보여줍니다 — 빌드 단계 없음, CDN 없음.
- **완전 로컬 동작** — 모든 산출물이 JSON 또는 JSONL 평문 파일입니다. 런타임에 PDF를 읽지 않고, 외부 통신도 없습니다.

---

## 빠른 시작

첫 설정 후 (`pip install -e ".[dev]"`) 아래 6개 명령을 순서대로 실행하세요:

```bash
# 1. 시드 문제은행 검증 (스키마 체크)
python -m cca_f_study.validate_questions 02-question-bank/seed/sample-questions.jsonl

# 2. 모의고사 응시 제출 (답안을 문제은행과 join)
python 04-exam-runner/submit_attempt.py \
  --questions 02-question-bank/seed/sample-questions.jsonl \
  --answers   examples/attempts/sample-answers.json \
  --out       05-learning-data/attempts/sample-attempt.json

# 3. 응시 채점 (합격선 720 대비 환산 점수)
python 04-exam-runner/score_attempt.py 05-learning-data/attempts/sample-attempt.json

# 4. 대시보드 데이터 export (응시 + lab status 집계)
python 04-exam-runner/export_dashboard_data.py \
  --attempts   05-learning-data/attempts \
  --lab-status 05-learning-data/lab-status.json \
  --out        06-dashboard/data/dashboard-data.json \
  --now        2026-05-12T00:30:00Z

# 5. 정적 대시보드 서빙
python -m http.server 8000 -d 06-dashboard
# 그런 다음 브라우저에서 http://localhost:8000/static/ 열기

# 6. 전체 테스트 스위트 실행
pytest
```

---

## 데이터 흐름

<img src="docs/assets/data-flow.svg" alt="sample-questions.jsonl에서 시작해 validate → submit → score → export 4단계 변환을 거쳐 dashboard-data.json에 도달하는 산출물 체인. 정적 HTML 대시보드가 이를 7개 위젯으로 렌더링하고, lab-status.json은 export 단계의 보조 입력으로 들어옴.">

| 산출물 | 생성자 | 소비자 |
|---|---|---|
| `02-question-bank/seed/sample-questions.jsonl` | 수작업 작성 | `validate_questions`, `submit_attempt` |
| `examples/attempts/sample-answers.json` | 학습자 입력 | `submit_attempt` |
| `05-learning-data/attempts/sample-attempt.json` | `submit_attempt` | `score_attempt`, `export_dashboard_data` |
| `05-learning-data/lab-status.json` | 수작업 작성 | `export_dashboard_data` |
| `06-dashboard/data/dashboard-data.json` | `export_dashboard_data` | 정적 대시보드 |

---

## 대시보드 미리보기

<img src="docs/assets/dashboard-wireframe.svg" alt="7-위젯 학습 대시보드의 와이어프레임: 합격/불합격 배너, 720 진행 바, D1–D5 도메인 breakdown 바, 시나리오 breakdown, 약점 개념 태그 클라우드, 추천 다음 lab을 포함한 lab 진행률, 점수 추이 스파크라인.">

대시보드는 한 화면에서 7가지 질문에 답합니다:

1. **합격했는가?** — 환산 점수와 720까지의 격차를 보여주는 합격/불합격 배너
2. **합격선까지 얼마나 가까운가?** — 100–1000 척도의 시각적 진행 바
3. **어느 도메인이 약한가?** — CCA-F 5개 도메인(D1–D5)별 정답률 바
4. **어떤 시나리오에서 어려움을 겪는가?** — 시나리오 유형별 정답률 breakdown
5. **다음에 어떤 개념을 공부해야 하는가?** — 틀린 문제에서 추출한 약점 개념 태그
6. **lab 순서에서 어디까지 왔는가?** — lab 완료 상태 + `recommended_next`
7. **점수가 향상되고 있는가?** — 응시별 점수 추이 스파크라인

---

## 프로젝트 진척

<img src="docs/assets/status-matrix.svg" alt="완성도 매트릭스: 10단계 / 7개 사양 목표 / 14개 완료 기준 모두 완료로 표시. 푸터에 MVP PASS, 130 tests passing, 시드 응시 8/10 → 820 PASS, 날짜 2026-05-13.">

| 분류 | 전체 | 완료 |
|---|---|---|
| 계획 단계 (Plan phases) | 10 | **10** |
| 사양 목표 (G1–G7) | 7 | **7** |
| 완료 기준 (CC1–CC14) | 14 | **14** |

전체 증거 기록은 [최종 검증 리포트](docs/reviews/2026-05-cca-f-study-runtime-mvp-final-validation.md)를 참고하세요.

---

## 디렉터리 구조

```text
.
├── CLAUDE.md                          # 프로젝트 규칙 (안전·채점·문제 규칙)
├── README.md                          # 한국어 (이 문서)
├── README_en.md                       # 영어 버전
├── pyproject.toml
├── 00-meta/                           # source register, 도메인·시나리오 맵
├── 01-sources/en/                     # 카노니컬 source PDF (read-only, 런타임에서 미파싱)
├── 02-question-bank/
│   └── seed/
│       └── sample-questions.jsonl    # 시드 10문항
├── 04-exam-runner/
│   ├── question_schema.json
│   ├── attempt_schema.json
│   ├── submit_attempt.py             # CLI shim
│   ├── score_attempt.py              # CLI shim
│   └── export_dashboard_data.py      # CLI shim
├── 05-learning-data/
│   ├── attempts/                     # 응시 JSON 파일
│   └── lab-status.json
├── 06-dashboard/
│   ├── data/
│   │   └── dashboard-data.json       # export 결과
│   └── static/
│       └── index.html                # 7-위젯 정적 대시보드
├── examples/
│   └── attempts/
│       └── sample-answers.json
├── docs/
│   ├── assets/                       # SVG 다이어그램 (이 README가 임베드)
│   ├── plans/
│   ├── reviews/
│   ├── specs/
│   └── use-cases/
├── src/
│   └── cca_f_study/
│       ├── __init__.py
│       ├── validate_questions.py
│       ├── submit_attempt.py
│       ├── score_attempt.py
│       ├── export_dashboard_data.py
│       ├── _aggregate.py
│       ├── _scoring.py
│       └── _schemas/
└── tests/                             # 130 passing · 1 intentional skip
```

---

## 안전 경계

- **런타임에서 PDF 미파싱.** Source PDF는 read-only 증거 자료이며, 어떤 런타임 모듈도 이를 열지 않습니다.
- **네트워크 호출 없음.** 어떤 단계에서도 HTTP 요청을 하지 않습니다. `tests/test_no_network_calls.py`로 회귀 보장.
- **시크릿·API 키 불필요.** 런타임은 Python 3.x 인터프리터와 위 디렉터리의 로컬 파일만 필요합니다.
- **생성된 문제는 절대 "official"이 아님.** 등록된 source에서 유래하지 않은 모든 문제는 `status != "official"`을 가집니다.
- **대시보드는 정적 유지.** 프론트엔드는 `python -m http.server`로 서빙되는 vanilla HTML/CSS/JS이며, 빌드 단계도 CDN도 없습니다.
- **Byte-identical 재생성.** 동일한 입력으로 `export_dashboard_data`를 두 번 실행하면 같은 바이트 결과가 나옵니다. `tests/test_dashboard_data_byte_identical.py`로 검증됨.

---

## 문서 색인

- [MVP 사양](docs/specs/2026-05-cca-f-study-runtime-mvp.md)
- [구현 계획](docs/plans/2026-05-cca-f-study-runtime-mvp-plan.md)
- [최종 검증 리포트](docs/reviews/2026-05-cca-f-study-runtime-mvp-final-validation.md)
- [프로젝트 규칙](CLAUDE.md)
- [비주얼 오버뷰](docs/overview.html) — 4개 다이어그램을 풀사이즈로 정리한 단일 페이지

---

## MVP 범위 밖 (post-MVP)

- 적응형 문제 자동 생성 (Claude API를 호출해 새 문제 작성).
- 다중 사용자 / 원격 배포 — 이 런타임은 단일 머신 전용입니다.
- 자동 PDF 파싱으로 source guide에서 문제 추출.
- CI/CD 파이프라인 — 모든 검증은 로컬 pytest로 수행됩니다.
- 영속 데이터베이스 — 모든 데이터는 평문 JSON/JSONL 파일에 저장됩니다.
- 대화형 문제 편집기 — 문제는 JSONL 파일을 손으로 작성합니다.
