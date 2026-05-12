# CCA-F Study Runtime

This repository implements a local study runtime for Claude Certified Architect — Foundations.

## MVP boundary

The initial repository contains only one source PDF:

- `./guide_en.pdf`

The PDF is a read-only source artifact.  
Runtime scoring and dashboard generation must not depend on parsing the PDF.

 - `./requirement/`에 cca-f 학습을 돕기위한 claude code 중심의 에이전트 개발 설계 관련 문서가 있음.

## Runtime source of truth

Runtime uses:

- question bank JSONL
- submitted attempt JSON
- lab status JSON
- dashboard-data JSON

## Scoring

Default scoring:

- `scaled_score = round(100 + (correct / total) * 900)`
- `pass_mark = 720`

Dashboard must show:

- raw score
- scaled score
- pass/fail
- gap to pass mark
- domain breakdown
- scenario breakdown
- weak concept tags
- lab progress
- trend

## Domain weights

- D1 Agentic Architecture & Orchestration: 27%
- D2 Tool Design & MCP Integration: 18%
- D3 Claude Code Configuration & Workflows: 20%
- D4 Prompt Engineering & Structured Output: 20%
- D5 Context Management & Reliability: 15%

## Question rules

Each question must have:

- id
- source
- domain
- scenario
- difficulty
- stem
- choices A-D
- answer
- explanation
- concept_tags
- status

Generated or community questions are unofficial.

## Safety

- Do not call external APIs in MVP.
- Do not require API keys.
- Do not mutate source PDF.
- Do not claim any generated question is official.
- Keep dashboard static until MVP is complete.

## Common Prompt Header
아래 블록은 모든 단계 프롬프트 맨 위에 붙이세요.
```
You are working inside the CCA-F study runtime repository.

Mandatory skill usage:
- Use the superpowers plugin workflow.
- Before acting, explicitly identify which superpowers skills apply.
- Use `brainstorming` for design/spec clarification.
- Use `writing-plans` for implementation planning.
- Use `using-git-worktrees` if the repository is already under git and a worktree/branch is appropriate.
- Use `test-driven-development` for implementation tasks.
- Use `executing-plans` or `subagent-driven-development` for plan execution.
- Use `requesting-code-review` for review steps.
- Use `verification-before-completion` before declaring any step complete.
- Use `frontend-design` for dashboard UX/UI design and dashboard implementation.

Completion rule:
Do not mark this task complete until every Completion Criteria item is satisfied.
If any criterion cannot be satisfied, stop only after writing a BLOCKED report that includes:
1. failed criterion
2. exact command/output/error
3. what you attempted
4. next concrete fix

MVP boundary:
- The repository initially contains only one source PDF: `01-sources/en/guide_en.pdf`.
- The PDF is read-only source evidence.
- Do not parse the PDF at runtime in MVP.
- Do not call external APIs.
- Do not require paid API keys.
- Keep the first dashboard static: HTML + CSS + vanilla JS.
- Runtime source of truth is local JSON/JSONL files.
- Generated/community questions are unofficial.
```