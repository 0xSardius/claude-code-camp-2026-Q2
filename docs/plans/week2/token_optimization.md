# Week 2 — Pillar 3: Token-usage optimization

Goal: cut the cost of an autonomous run without cutting its capability.
Builds on `00_lifecycle_hooks.md`, and depends on the observability pillar for
its before/after numbers.

## Measured baseline (2026-07-27)

Extracted from the 25 committed session logs — 404 responses carrying `usage`:

| | |
|---|---|
| Input tokens | 4,671,441 |
| Output tokens | 62,923 |
| Cache reads / writes | **0** |
| Median output per response | 90 tokens |
| Cost @ intro $2/$10 | ~$9.97 (of which **$9.34 is input**) |

**Input outweighs output 74:1**, and this reorders the whole pillar:

- **Caching is very nearly the only lever.** It acts on the 94% of spend that
  is input tokens. A rough projection at 75% cache-hit puts input near $3 —
  call it 60–65% off total, less in practice because writes cost 1.25× and
  every compaction invalidates the conversation prefix.
- **`effort` / thinking tuning is *not* a lever here**, contrary to first
  instinct. The payload sends no `thinking` or `output_config`, so on
  `claude-sonnet-5` adaptive thinking runs by default at `effort: high` — but
  thinking bills as output tokens, and output is 6% of spend. Tuning it would
  save cents. Deliberately dropped from this pillar. (It resurfaces in
  observability as a *logging* gap, not a cost one — see that plan.)
- `max_output_tokens` defaults to 1024 and the max observed response is exactly
  1024, so some responses are being truncated at the cap. Worth raising
  independent of cost.

Consequence: **M2 is the only load-bearing milestone here.** M3–M5 are cleanup.

### Caching is a capability fix, not just a cost one (found 2026-07-27, phase 2)

The session reporter, run over the same logs, turned up what the cost numbers
alone had hidden:

| | |
|---|---|
| Turns ending `completed` | 12 |
| Turns ending `max_tokens` | **56** |
| Input tokens per turn | ~59,890 |
| `agent.max_turn_tokens` default | 60,000 |

**82% of turns were cut off by the spend ceiling and forced into a wind-down**,
because ~11,562 input tokens per response × 4.7 iterations per turn lands
almost exactly on the budget. The budget was being consumed by re-sending the
conversation rather than by doing work.

Since `max_turn_tokens` is a *spend* ceiling, the turn budget is charged
billable input only (`Agent._record_usage`) — so cache reads stop consuming it.
Caching should therefore convert most of those 56 truncated turns into turns
that finish. That makes M2 an autonomy fix as much as a cost fix, and it is the
strongest single argument for doing it next.

## The levers, largest first

### 1. Prompt caching (Anthropic) — expected to dominate

The MUD loop is close to the ideal shape for caching: a stable system prompt, a
large and completely static tool library, and a conversation that only grows at
the end. Cache reads cost ~0.1× of fresh input; writes cost ~1.25× at the
default 5-minute TTL.

Concrete sizing from the current build:

- System prompt: `.boukensha/prompts/player/system.md` is 2,359 bytes (~600
  tokens) — **below the 1,024-token minimum cacheable prefix for
  `claude-sonnet-5` on its own.**
- Tools: `tools/mud.py` registers ~30 tools with full descriptions and JSON
  schemas, plus the filesystem and shell tools.

Render order is `tools` → `system` → `messages`, so a breakpoint on the last
system block caches tools **and** system together — and the tool block is what
carries that prefix over the minimum. A breakpoint on the system prompt alone
would silently never cache (no error, just `cache_creation_input_tokens: 0`).
This is the single most likely way to implement caching and get nothing.

Implementation: `backends/anthropic.py`'s `to_payload` is the only place that
needs to change — add `cache_control: {"type": "ephemeral"}` blocks. The other
four backends ignore the setting entirely. Max 4 breakpoints per request.

**Planned breakpoints**: one on the last system block (covers tools + system),
one on the last content block of the most recently appended turn (so each
request reuses the whole prior conversation).

**Prerequisites and hazards — read these before writing the payload change:**

- **Observability M2 must land first.** `usage.input_tokens` is the *uncached
  remainder only*; the true prompt size is `input_tokens +
  cache_creation_input_tokens + cache_read_input_tokens`. Turning caching on
  before that fix silently breaks `needs_compaction()`. See the observability
  plan.
- **`compact_messages()` fights caching directly.** It drops the oldest 40% of
  messages, which changes the front of the message prefix and invalidates the
  entire cached conversation on every compaction. Either accept the periodic
  full re-write, or rethink compaction (see lever 2) — but know which you chose.
- **The 20-block lookback window.** A breakpoint walks back at most 20 content
  blocks to find a prior cache entry. The longest week 1 session ran 190 tool
  calls across 26 turns — a single turn with many tool_use/tool_result pairs can
  exceed 20 blocks and silently miss. Expect to need an intermediate breakpoint
  in long turns.
- **Hook-injected messages must be appended, never spliced.** Already a hard
  constraint in the hooks plan; this is why.
- **Silent invalidators.** Nothing dynamic may be interpolated into the system
  prompt — no timestamps, no character state, no "current room". Character
  state goes in `messages`, after the breakpoint. The memory pillar's
  `before_turn` fact load must therefore land in the message list, **not** in
  the system prompt, or it invalidates the cache on every single turn and makes
  the two pillars actively cancel each other out.

*Verify*: `usage.cache_read_input_tokens` non-zero and growing across
consecutive requests in one session. If it is zero across repeated requests,
something in the prefix is changing — diff the rendered payload bytes between
two requests rather than guessing.

### 2. Smarter compaction

`Context.compact_messages()` drops the oldest 40% of messages by pure count.
Two known problems, one already fixed and one open:

- **Fixed**: it had no tool_use/tool_result pairing awareness, so a cut landing
  between a call and its result left an orphaned `tool_result` that the API
  rejects outright — 15 dead turns in a row, found live 2026-07-25.
- **Open**: `target_fraction` is accepted but never used (a pre-existing oddity
  ported faithfully from Ruby rather than "fixed"), and dropping by count says
  nothing about dropping by *value*. The oldest messages in a MUD session
  include the map knowledge the agent most needs.

Options: summarize-instead-of-drop, or drop tool_result *bodies* while keeping
the calls, or let the memory pillar absorb the durable content so dropping is
safe. The third is the most interesting and the most coupled — if memory holds
what matters, compaction stops being lossy in the way that hurts.

Note this is now a **week-2 file with no Ruby counterpart**, so the "don't
unilaterally resolve what the source frames as an open question" rule no longer
binds here the way it did during the port. Changing it is a normal design
decision now.

### 3. MUD output trimming — the course's own `after_tool` use

The week 2 hook material describes `after_tool` as the seam that **replaces raw
movement output with a compact result**. That is exactly this lever, and it is
already the documented intent of the hook system.

Raw telnet output carries room descriptions, exit lists, mob lists, and status
prompt noise on every single `move`. From the week 1 session log, `tool_result`
events total ~104 KB across 190 calls (~550 bytes each) — and each one is
re-sent as part of the conversation on every subsequent iteration of that turn,
so the real cost is that figure multiplied by how long it stays in context.

Trim at `after_tool`: for a `move`, a compact "moved north → Temple Square,
exits N/E/S" is worth far less context than the full room dump, *provided* the
first visit to that room recorded the full description into memory (pillar 2).
The two pillars compose here — trimming is only safe because memory keeps what
was trimmed.

### 4. `max_turn_tokens` enforcement

Already implemented in `Agent` as a second independent ceiling alongside
`max_iterations`, with a proper wind-down path (`_wrap_up`) — and **disabled by
default** (`0`). Enabling it is a config decision, not a code change. Pick a
value informed by the observability pillar's per-turn spend numbers rather than
guessing, and note that limits here are *trigger thresholds*, not hard caps:
reaching one still costs one final wind-down call.

## Milestones

**M1 — Baseline.** Instrument and run a representative session; record spend
per turn, per tool, and per iteration using the observability summary reporter.
No optimization yet. This number is what every later milestone is measured
against, so capture it before touching anything.

**M2 — Prompt caching. DONE 2026-07-28.** Two breakpoints in
`backends/anthropic.py::to_payload`: one on the last system block (covers
tools + system — a stable anchor that still hits after compaction or `/clear`,
and the tool schemas are what carry the prefix over the 1024-token minimum),
one on the last content block of the last message (grows with the
conversation). Kill-switch is `agent.prompt_caching` in settings.yaml,
**defaulting ON** rather than opt-in as originally planned — the measured 74:1
input ratio and the 82% turn-cutoff finding made the case decisive.

Verified live, two real calls sharing a prefix:

| | fresh input | cache write | cache read |
|---|---|---|---|
| call 1 | 2 | 1,727 | 0 |
| call 2 | 2 | 16 | **1,727** |

99% of call 2's input served from cache; 89% cheaper than uncached on that
call. Measured with only 5 tools registered — the real MUD build has ~30, so
the cached prefix (and the absolute saving) is substantially larger.

Known gap, unresolved: `_wrap_up` calls with `tools=[]`, a different prefix, so
the wind-down call can never hit the tools+system entry. That is one call per
turn, and 82% of week1 turns ended in a wind-down. Revisit if the reporter
shows the hit rate capping well below expectations.

**M3 — `after_tool` output trimming.** Depends on memory M3 (facts written)
so trimming is non-destructive. Re-measure.

**M4 — Compaction rework.** Only after M2 and M3, because the right compaction
design depends on what caching and memory have already changed about the
message list.

**M5 — Turn budget.** Enable `max_turn_tokens` with an evidence-based value.

## Acceptance

A measured before/after on the *same* task — not a synthetic benchmark. The
honest version of this number reports cost per unit of game progress (XP, or
goal completed), not cost per turn: a change that halves per-turn cost while
doubling the turns needed is not an optimization, and per-turn accounting alone
would report it as a win.
