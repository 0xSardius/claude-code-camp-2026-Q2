# Week 2 — Pillar 1: Observability

Goal: make an unattended run legible while it is happening — what it is
spending, and whether it is actually accomplishing anything. Builds on
`00_lifecycle_hooks.md`; every milestone here is a hook handler plus a `Logger`
change.

Motivating data point (from `docs/plans/observability.md`): Andrew hit excessive
token spend in week 1 accomplishing a simple goal. Second motivating data
point, from this project: the `compact_messages()` bug burned 15 turns and real
API calls doing nothing, and nothing in the existing log would have surfaced
that without a human manually diffing checkpoints.

## Current state

`12_context`'s `Logger` deliberately dropped per-response cost/provider
tracking — a documented, intentional narrowing relative to `06_the_logger`
through `11_tui`. The backends were **not** gutted: `backends/base.py` still
fully defines `estimate_cost(input_tokens=, output_tokens=)`,
`input_token_cost_per_million`, `output_token_cost_per_million`, `usage_unit`,
and `usage_level`. Nothing calls them. Re-connecting is mostly re-wiring, not
rebuilding — but see M2, which is a real bug, not a re-wire.

## Milestones

### M1 — Re-connect per-response cost

Restore cost/provider fields on `Logger.response()` and thread the backend
through so `estimate_cost` can be called. The `06`–`11` implementations are the
reference for shape; do not re-derive from scratch.

Two accuracy problems to settle while doing it, both of which make a naive
re-connect produce confidently wrong numbers:

1. **The `MODELS` price table is stale for the model actually in use.**
   `.boukensha/settings.yaml` runs `claude-sonnet-5`, and
   `backends/anthropic.py` lists it at `{"input": 3.0, "output": 15.0}`. Sonnet 5
   is on introductory pricing of **$2.00 / $10.00 per MTok through 2026-08-31**
   — i.e. every cost number this pillar produces before that date is ~50% high
   unless the table is corrected or the intro window is modeled. Decide
   explicitly: hardcode intro pricing with a dated comment, or model the window.
   Don't silently ship the stale number.
2. **Cached tokens are not priced like fresh input.** Cache reads cost ~0.1× and
   cache writes ~1.25× (5-minute TTL) or ~2× (1-hour). Once the token pillar
   turns caching on, an `estimate_cost(input, output)` that ignores
   `cache_creation_input_tokens` / `cache_read_input_tokens` overstates spend
   badly — and it will overstate it *most* exactly when caching is working best,
   which would make the token-optimization pillar look like it failed.
   `estimate_cost`'s signature needs cache-aware parameters before caching lands.

### M2 — Cache-aware usage accounting (a real bug, not a re-wire)

`Agent._record_usage` calls `context.update_tokens(tokens["input"])`, and
`Context.needs_compaction()` compares `current_tokens / context_window` against
the 0.85 threshold. But **`usage.input_tokens` is the uncached remainder only** —
the true prompt size is `input_tokens + cache_creation_input_tokens +
cache_read_input_tokens`.

So the moment prompt caching is enabled, `current_tokens` collapses to a small
number, `usage_fraction` collapses with it, and `needs_compaction()` stops
firing no matter how full the real context window gets. This is the *same shape*
as the bug already documented in `agent.py`'s own comment — the multi-provider
usage-field fallback that Ruby's `12_context` dropped, without which
`current_tokens` silently stays 0 for non-Anthropic backends and compaction
never trips. Same failure, new cause.

Fix `_usage_tokens` to sum all three fields for the context-size figure, and
keep them separated for the cost figure (M1 needs them apart). Land this
**before** the token pillar enables caching, not after.

*Verify*: a live call with caching on, asserting `context.current_tokens`
matches the summed total rather than the uncached remainder.

### M3 — Dead-turn / stall detection

Make "this turn accomplished nothing, N times in a row" a first-class surfaced
signal rather than something inferred after the fact by a human.

Attaches at `after_turn`. Needs a definition of "accomplished nothing" that
would actually have caught the `compact_messages()` incident — where every turn
made a real API call, spent real tokens, and produced no progress. Candidate
signals, to be chosen deliberately rather than combined by reflex:

- Turn ended in an `ApiError` fallback (`_wrap_up`'s except path).
- Zero successful tool dispatches in the turn (`after_tool` with `ok=True`
  never fired).
- Game state unchanged across the turn — the memory pillar's fact store makes
  this checkable (same room, same HP, same XP).

State lives outside `Agent` (fresh per turn — see hooks plan). Emit a
`stall` log event with the consecutive count, and decide whether the harness
*acts* on it (halt the run) or only reports it. **Recommendation: report at
first, act only once the false-positive rate is known** — a harness that halts
on a bad heuristic is worse than one that doesn't halt at all.

### M4 — Wait/retry policy as an observable

Week 1's grind sessions needed a human to decide when to poll for movement
regen, how long to wait, and when to give up and reroute (the failed Armory
search). Encode that decision and log its outcomes: what was waited on, how
long, whether it resolved, and what the harness did next.

Attaches at `after_tool` (a tool result indicating "too exhausted to move" is
the trigger) and `before_tools`.

### M3a — Reasoning logging is silently dead (found 2026-07-27)

`Agent._log_reasoning` emits a `reasoning` event per reasoning block, and
`backends/anthropic.py` normalizes `thinking`/`redacted_thinking` into them.
But the payload never sends a `thinking` parameter, and on `claude-sonnet-5`
`thinking.display` defaults to `"omitted"` — so blocks arrive with empty text,
`_log_reasoning` skips every empty non-redacted block, and **no `reasoning`
event has ever been written.**

This is an observability gap, not a cost one (thinking bills as output tokens,
which are 6% of spend — see the token plan's baseline). Setting
`thinking: {"type": "adaptive", "display": "summarized"}` makes the agent's
reasoning visible in the very logs being committed for evaluation, which is
worth having for roughly nothing.

*Note the caching interaction*: toggling `thinking` on or off invalidates the
messages cache but **not** the tools+system cache, so this is safe to set once
at startup and leave alone. Don't toggle it per-request.

### M5 — Session summary reporter

A reader over the JSONL that answers, for a finished or in-flight run: total
spend, spend per turn, cache hit rate, iterations per turn, tool call counts by
name, stall events, and wall-clock. Standalone — do not couple it to the TUI.

This is what makes the other pillars measurable: the before/after number for
"did caching help?" comes from here.

### M6 — Fix the prompt-log bloat

> **Reordered 2026-07-27: this now runs BEFORE M5.** The decision to commit
> session logs for instructor evaluation makes it a prerequisite rather than a
> cleanup task — logs are already **11 MB of a 17 MB repo** (~65%), and week 2's
> grind sessions are far longer than week 1's. Fixing this first means the long
> runs are never recorded in the expensive format. M5 also reads the format M6
> changes, so doing M5 first would mean writing it twice.

Measured from the longest week 1 session
(`.boukensha/sessions/20260725T144647Z-bff5b1e0.jsonl`, 4.56 MB):

| phase | events | bytes |
|---|---:|---:|
| `prompt` | 119 | **4,300,210** |
| `tool_result` | 190 | 104,271 |
| `response` | 145 | 93,127 |
| everything else | 448 | ~63,000 |

`Logger.prompt()` serializes the **entire message list** on every iteration, so
log size grows quadratically with conversation length: 94% of that file is
re-serialized conversation history. It is not a token cost, but it is a real
observability cost — it makes the logs slow to read, expensive to ship
anywhere, and it will get worse as week 2's hooks inject more messages.

Fix by logging a message-list *delta* or digest per iteration plus the full list
once at turn start, keeping the full-fidelity dump behind the existing debug
flag (`Logger.raw()`'s `is_debug()` pattern is the precedent).

**Note the interaction with M5**: any consumer that reconstructs prompt state
from the log must be updated in the same milestone, or the summary reporter
silently reads a format that no longer exists.

## Open questions

- **What "per task" means for spend accounting** once a task spans many turns
  and possibly hours of real-world waiting. Per-turn is already available;
  per-goal needs the memory pillar's "current goal" fact to key on; cumulative
  per-run is trivial. Probably all three, but the *primary* number a human
  watches should be chosen, not defaulted.
- Whether stall detection should halt an unattended run (see M3).
