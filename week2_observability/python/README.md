# Boukensha — week 2 (Python)

The agent harness for [`week2_observability`](../README.md). Forked from
[`week1_baseline/python/12_context`](../../week1_baseline/python/12_context)
on 2026-07-27; see the parent README for what the fork changed and why the
Ruby mirror is retired.

Plans: [`docs/plans/week2/`](../../docs/plans/week2/).

## What week 1 left here

A hand-rolled agent loop with no SDK dependency: config, tool registry,
prompt builder, five provider backends, an HTTP client with retry/backoff,
the tool-calling loop, JSONL session logging, a run DSL, a REPL, a standard
tool library (filesystem / shell / MUD), a Textual TUI, and real
context-window tracking with auto-compaction.

Two things shipped deliberately narrowed, and week 2 addresses both:

- **Cost/provider tracking is disconnected.** `backends/base.py` still fully
  defines `estimate_cost`, `usage_unit`, and `usage_level` — nothing calls
  them. Reconnecting is the observability pillar's first milestone.
- **There are no lifecycle hooks.** The loop has no seams to attach to, so
  every new capability would otherwise be an edit inside `Agent.run()`.
  Adding them is the foundation milestone everything else depends on.

## What week 2 adds

In this order (see [`docs/plans/week2/README.md`](../../docs/plans/week2/README.md)
for the reasoning):

1. **Lifecycle hooks** — `before_turn`, `before_model`, `before_tools`,
   `after_tool`, `after_turn`. All three pillars attach here rather than
   editing the loop directly.
2. **Observability** — per-turn spend, cache-aware token accounting,
   dead-turn/stall detection, a session summary reporter.
3. **Token optimization** — prompt caching, `after_tool` output trimming,
   compaction rework, turn budgets.
4. **Memory** — per-character facts and learnings, read-before-explore.

## Vocabulary

A **turn** is one user input plus the complete agent run needed to answer it —
one `Agent.run()`. An **iteration** is one pass through the inner loop,
principally one model request and its response. `Logger`'s existing `turn` and
`iteration` events already carry exactly these semantics.

## Layout

```
boukensha/
  agent.py           -- the loop; where hooks will attach
  context.py         -- messages, tools, token tracking, compaction
  logger.py          -- JSONL session log
  registry.py        -- tool registration and dispatch
  client.py          -- HTTP with retry/backoff (no third-party lib)
  backends/          -- anthropic, openai, gemini, ollama, ollama_cloud
  tools/             -- file_system, shell, mud
  repl.py, run_dsl.py, tui.py
examples/example.py  -- MUD demo (real API calls, live MUD)
```

## Running

```bash
../bin/example        # or: uv run python examples/example.py
```

Config resolves from the repo-root `.boukensha/`. `examples/example.py` uses
**3** `.parent` hops to reach the repo root — one fewer than week 1's steps
needed, since this tree sits a level shallower. That constant is the single
most-regressed thing in this project's history; check it first on any new
entry point.
