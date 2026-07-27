# Week 2 Technical Documentation

## Technical Goal
Find the Bakery and List the Menu (Agent should reason its direction and not
randomly navigate, and it should know how to get back every time).

Underneath that stated goal, week2's build is the three capabilities the
bootcamp assigned — **an observability layer, basic memory, and token-usage
optimization** — carried far enough that the harness can autonomously drive a
character toward an arbitrary goal, not just the bakery. The bakery run is the
proof case; the scale-up target is a leveling/grinding/training loop that gets
`dummy` to level 7 and beats the Minotaur, then generalizes to other areas and
other characters.

## Technical Uncertainty
- We don't know whether re-connecting the cost/usage tracking that `12_context`
  disconnected is enough for autonomy-grade observability, or whether the
  useful signal is something the current JSONL log can't express at all
  (per-goal spend, "this turn accomplished nothing", wait/retry outcomes).
- We don't know what "per task" should mean for token accounting once a session
  spans many turns and possibly many real-world hours of movement/respawn
  waiting — per-turn, per-goal, or cumulative across an unattended run.
- We don't know whether a memory layer needs a real structured room graph or
  whether freeform text-per-fact is enough to make navigation provably
  non-random on a second run.
- We don't know how much of week1's token spend was avoidable. Prompt caching,
  smarter compaction, and MUD-output trimming are all plausible levers, but we
  haven't measured which one dominates — and Andrew's week1 experience
  (excessive spend on a simple goal) says the answer matters.
- We're uncertain whether dropping the Ruby↔Python parity discipline for week2
  costs us the bug-catching that the byte-for-byte diff provided all through
  week1, or whether code review alone carries that weight on greenfield code
  with no reference implementation to diff against.
- We don't know whether memory keyed per-character is sufficient insurance for
  the eventual multi-character requirement, or whether deferring concurrent
  steering will turn out to have baked in a single-character assumption we
  can't cheaply undo.

## Technical Hypothesis
- I hypothesize that building observability **first** will make the other two
  pillars measurable rather than speculative: without per-turn cost and
  dead-turn detection in place, "did memory help?" and "did caching help?" are
  both unanswerable except by impression.
- I hypothesize that prompt caching will dominate the token-optimization
  result, because the MUD loop's prefix (system prompt + a large tool library +
  a growing conversation) is exactly the shape caching is designed for — and
  that the existing `compact_messages()` will fight it, since dropping the
  oldest 40% of messages invalidates the cached message prefix every time it
  fires.
- I hypothesize that a memory layer keyed per-character, split into *facts*
  (places, goals) and *learnings* (efficiency observations the agent writes
  about its own play), will be enough to make the bakery run provably
  non-random on a second attempt — and that the discipline ("check memory
  first, only explore if it's not there") is a real piece of logic, not just
  storage.
- I hypothesize that the observability layer will surface at least one bug the
  code review and playtests didn't, on the same pattern as week1: the bugs that
  mattered most (`compact_messages()`'s orphaned `tool_result`, the
  `read_until_prompt` `"> "` sentinel collision) only became reachable under
  sustained real load, which is precisely what an observability layer is for.

## Technical Observations
<!-- Fill in as work lands. Each entry: what was built/found, what it cost,
     what it changed. Same style as week1 — specific, with the surprising part
     called out rather than smoothed over. -->

- Set week2's structural ground rules before writing any code (2026-07-27),
  rather than defaulting silently: week2 lives in `week2_capable/` as one
  evolving Python project seeded from `week1_baseline/python/12_context`
  (week1 stays frozen as a submitted artifact); the Ruby↔Python parity mirror
  is **retired** for week2 (the port methodology proved out over 13 steps and
  every live playtest ran Python, so the mirror's remaining value didn't
  justify writing every greenfield feature twice); and Anthropic-specific
  prompt caching is explicitly in scope for the token-optimization pillar even
  though it breaks the five-backend symmetry, because it's where the
  order-of-magnitude win is.
- The week 2 course material's **lifecycle hooks** (`before_turn`,
  `before_model`, `before_tools`, `after_tool`, `after_turn`) reframed the
  whole build: rather than editing three separate features into `Agent.run()`,
  all three pillars become hook handlers attached to one seam. The course's own
  description of `after_tool` — "replace raw movement output with a compact
  result" — turns out to *be* the token-optimization pillar's output-trimming
  lever, which is a strong signal the seam is in the right place. Its
  turn/iteration vocabulary also already matches this codebase exactly (a turn
  is one `Agent.run()`, an iteration is one pass of the inner loop and its
  model request), so `Logger`'s existing `turn`/`iteration` events needed no
  renaming.
- Reading the week 1 session logs to size the observability work surfaced two
  concrete problems before any code was written. First, `Logger.prompt()`
  re-serializes the entire message list every iteration, so log size grows
  quadratically with conversation length — in the longest grind session that's
  4.3 MB of a 4.56 MB file (94%) spent re-writing conversation history. Second,
  and more load-bearing: `usage.input_tokens` is the *uncached remainder only*,
  so the moment prompt caching is enabled, `Context.current_tokens` collapses
  and `needs_compaction()` stops firing no matter how full the real context
  window gets. That's the same failure shape as the already-documented
  multi-provider usage-fallback bug, arriving by a new route — and it means the
  observability fix has to land *before* the token-optimization pillar turns
  caching on, not after. Also found the price table stale for the model
  actually in use (`claude-sonnet-5` is on introductory pricing through
  2026-08-31, so a naive cost re-connect would report ~50% high).

## Technical Conclusions
<!-- Written at the end of the week. -->

## Key Takeaway
<!-- Written at the end of the week. -->
