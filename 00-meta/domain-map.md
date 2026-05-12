# Domain Map

The CCA-F runtime uses five domains. Weights are recorded for future weighted scoring; the MVP scorer is **unweighted** (see `CLAUDE.md` and `docs/specs/2026-05-cca-f-study-runtime-mvp.md` §7).

| Domain | Title                                            | Weight | Source IDs |
|--------|--------------------------------------------------|-------:|------------|
| D1     | Agentic Architecture & Orchestration             | 27%    | `guide_en` |
| D2     | Tool Design & MCP Integration                    | 18%    | `guide_en` |
| D3     | Claude Code Configuration & Workflows            | 20%    | `guide_en` |
| D4     | Prompt Engineering & Structured Output           | 20%    | `guide_en` |
| D5     | Context Management & Reliability                 | 15%    | `guide_en` |

Weights sum to **100%**.

## D1 — Agentic Architecture & Orchestration

Single-agent loops, multi-agent hand-off, subagents, plan-and-execute patterns, when to split vs. consolidate agents, lifecycle of an agent turn.

## D2 — Tool Design & MCP Integration

Defining tool schemas, naming, idempotency, error surfaces, the Model Context Protocol (MCP) server/client model, choosing between custom tools and MCP integrations.

## D3 — Claude Code Configuration & Workflows

`CLAUDE.md`, slash commands, hooks, skills, permissions, IDE/CLI configuration, repository-scoped vs. user-scoped settings.

## D4 — Prompt Engineering & Structured Output

System prompts, few-shot patterns, JSON prefill / `stop_sequences`, structured-output schemas, balancing instruction strength vs. flexibility.

## D5 — Context Management & Reliability

Context window budgeting, retries, idempotent operations, deterministic IDs, failure modes (timeouts, partial tool failures), evaluation hooks.
