# Week 2 — scope, decisions, and sequencing

Week 2's assignment is three capabilities: **an observability layer, basic
memory, and token-usage optimization**. The stated proof goal is the one in
`docs/journal/2_week2.md` — a character autonomously finds the Bakery and lists
its menu, by reasoning about direction rather than wandering, and knowing the
way back. The scale-up target is a leveling / grinding / training / optimizing
loop that reaches level 7 and beats the Minotaur, then generalizes to other
zones and other characters.

Requirements scoping lives in `docs/plans/week2_foundations.md` (written
2026-07-26). This directory is the execution side: one milestoned plan per
pillar, plus the lifecycle-hook foundation they all attach to.

## Structural decisions (confirmed 2026-07-27)

- **Code home**: `week2_observability/` as *one evolving project*, seeded from
  `week1_baseline/python/12_context`. Week 1 stays frozen as a submitted
  artifact. Week 2 is feature work, not a teaching ladder, so the numbered
  per-step directories don't fit.
- **Language**: **Python only**. The Ruby↔Python mirror is retired for week 2.
  It earned its keep across 13 steps — but its value was surfacing Ruby/Python
  semantic gaps while porting from a Ruby source of truth, and week 2's
  features have no Ruby original to port. Writing greenfield features twice
  would be parallel design, not porting. Ruby stays at `12_context`.
  - **Consequence to hold onto**: this retires the byte-for-byte parity
    acceptance test, which caught a real bug on almost every step. Code review
    (the `code-review` skill via `Workflow` at `"medium"` effort) is now the
    *only* independent check, so it is not optional per milestone.
- **Prompt caching is in scope** even though it is Anthropic-specific and
  breaks the five-backend symmetry. It is implemented as an opt-in the
  Anthropic backend honors and the other four ignore.

## Decisions settled 2026-07-27 (after Phase 0)

Four open questions, closed — plus the measurement that reordered the token
pillar. Details live in the per-pillar plans; this is the index.

- **Commit logs and memory files** for instructor evaluation, via the same
  `.gitignore` carve-out pattern `.boukensha/sessions/*.jsonl` already uses.
  **Consequence**: observability M6 (the quadratic prompt logging) moves *ahead*
  of M5, because it's what makes this policy sustainable — logs are currently
  11 MB of a 17 MB repo and grow quadratically with conversation length.
- **`before_model` tracks rather than polls.** Position is a harness-maintained
  belief updated at `after_tool`; a real `look` is issued only when that belief
  is stale. See `00_lifecycle_hooks.md` M3.
- **Store format: record edges, present trails.** Not a flat direction list and
  not an up-front room graph. See `memory.md`.
- **Player file: hybrid** — generated numbers, agent-authored narrative. See
  `memory.md`.
- **Not using `circlemud-world-parser` to preload the map.** It would make the
  memory pillar untestable (you can't show an agent learned a map you handed
  it) and wouldn't generalize to unseen zones. Keep it as a debugging oracle
  for checking whether the learned map is *correct*.

### The measurement that reordered the token pillar

Extracted from the 25 committed session logs (404 responses carrying `usage`):

| | |
|---|---|
| Input tokens | 4,671,441 |
| Output tokens | 62,923 |
| Cache reads / writes | **0** |
| Cost @ intro $2/$10 | ~$9.97 |

**Input outweighs output 74:1.** So prompt caching isn't merely the biggest
lever, it's very nearly the only one — $9.34 of that $9.97 is input tokens.
Conversely, `effort` and thinking tuning act on output, which is 6% of spend;
tuning it would save cents. Token M2 is promoted to the pillar's only
load-bearing milestone; M3–M5 are demoted to cleanup. See
`token_optimization.md`.

## The lifecycle-hook spine

Course material for week 2 defines a hook surface on the agent loop, with these
seams and their intended MUD behavior:

| Hook | Fires | Documented MUD behavior |
|---|---|---|
| `before_turn` | Once, at the start of a turn | Initialize player state — `check(score)` |
| `before_model` | Before each model request | Establish position via `look`; first-visit room surveys |
| `before_tools` | Before a model-selected tool batch runs | Poll |
| `after_tool` | After each tool returns | Process results; **replace raw movement output with a compact result** |
| `after_turn` | Once, at the end of a turn | Documented as an available seam; no MUD-specific behavior specified |

Vocabulary (course definitions, which already match this codebase): a **turn**
is one user input plus the complete agent run needed to answer it — i.e. one
`Agent.run()`. An **iteration** is one pass through the inner loop, principally
one model request and its response. The existing `Logger.turn()` /
`Logger.iteration()` events already carry exactly these semantics, so no
renaming is needed.

**All three pillars are implemented as hook handlers, not as edits scattered
through `Agent.run()`.** That is the main architectural decision of week 2:

- Observability attaches at every seam (spend and stall accounting).
- Memory reads at `before_turn`, surveys at `before_model`, writes at
  `after_tool` / `after_turn`.
- Token optimization lives largely in `after_tool` — the course's own
  "replace raw movement output with a compact result" *is* the trimming lever.

`00_lifecycle_hooks.md` therefore lands first; everything else depends on it.

## Sequencing

1. **`00_lifecycle_hooks.md`** — the seam itself. Nothing else can attach
   without it.
2. **`observability.md`** — second, deliberately. Until per-turn spend and
   dead-turn detection exist, "did memory help?" and "did caching help?" are
   both unanswerable except by impression. Observability is the measuring
   instrument for the other two pillars, so it goes in before them.
3. **`token_optimization.md`** and **`memory.md`** — either order after that.
   Lean toward token optimization first if spend is the blocker for running
   long memory experiments; lean toward memory first if the bakery proof case
   is the nearer deadline.

## Process (unchanged from week 1)

Per milestone: implement → verify live against the real MUD where the milestone
touches gameplay → code review via `Workflow` at `"medium"` effort → record the
observation in `docs/journal/2_week2.md`. Ask before assuming on anything with
a real tradeoff; log the decision here or in the pillar's plan rather than
deciding silently.
