# Scenario Map

Scenarios are the practical contexts in which CCA-F concepts are tested. Every question's `scenario` field must match a scenario id listed below.

| Scenario ID                  | Title                                     | Related Domains |
|------------------------------|-------------------------------------------|-----------------|
| `agentic-orchestration`      | Designing an agent loop / hand-off        | D1              |
| `subagent-delegation`        | Delegating work to subagents              | D1              |
| `tool-schema-design`         | Authoring a tool schema                   | D2, D4          |
| `mcp-integration`            | Wiring an MCP server                      | D2              |
| `claude-code-config`         | Configuring `CLAUDE.md`, slash commands   | D3              |
| `claude-code-hooks`          | Authoring/maintaining hooks               | D3              |
| `structured-output`          | JSON prefill / `stop_sequences`           | D4              |
| `prompt-design`              | Crafting a system prompt                  | D4              |
| `context-budgeting`          | Managing the context window               | D5              |
| `retry-and-idempotency`      | Retries, deterministic IDs                | D5              |

Scenario IDs are kebab-case and stable. New scenarios are appended; existing ones are not renamed (rename = new ID).
