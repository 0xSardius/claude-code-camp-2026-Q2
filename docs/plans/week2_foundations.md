# Week 2 Foundations — Requirements (memory, observability, generality)

Status: **requirements scoping, not an execution plan yet.** No milestones,
no file-by-file design — that comes per-pillar once this scope is
confirmed, following the same orient → plan → execute rhythm
`docs/plans/python_port/` used for week1. This doc exists to nail down
*what* needs to be true before deciding *how* to build it.

Supersedes the placeholder `docs/plans/observability.md` (token-spend
observability is one of three pillars here, not the whole scope) —
keeping that file as a pointer, not deleting it, since it may become the
narrower execution-plan home for the observability pillar specifically
once this doc is confirmed.

## The goal

The harness should be able to autonomously control a character: send it
into the world, have it play toward a real goal, and — for `dummy`
specifically — grind to level 7 and kill the Minotaur in the Newbie Zone
(`week0_explore/CHALLENGES.md`). The system needs to generalize to any
character, or multiple characters steered by the harness in the same
session, not just `dummy`.

Assessed 2026-07-26: roughly **15% of the way there, all things
considered** — the tool/context harness itself is ~85-90% done, but
autonomy infrastructure (this doc) is ~10%, real game progress toward
level 7 is ~10-15% of the total exp climb (the curve compounds — level
3→4 took 555 exp, level 4→5 needs 4,982), and the Minotaur fight itself is
completely unscoped (never scouted, difficulty unconfirmed).

## Guiding constraint: two traps, from the week2 course material

- **Journey-first trap**: optimizing around one player journey risks
  building a special-case system instead of a general engine.
- **Architecture-first trap**: optimizing around a general engine before
  proving a player journey risks building abstractions for the wrong
  goal.

Resolution for this project: prove the *smallest* journey that's already
forced to be general, rather than either a Dummy-specific script or a
speculative framework. See "Minimal proof case" below.

## Minimal proof case: find the bakery, record the menu

A generalized character autonomously finds the Bakery and records what's
for sale — **without guessing randomly**, which is the actual test: it
must be provable on a second run (already knows where the bakery is, or
knows it doesn't and explores deliberately) rather than just getting
lucky once. This forces the core memory primitives to exist for real
without yet needing combat, leveling, or multi-character complexity.

Requirements:
- Memory keyed **per-character**, not a shared file — the "any character"
  requirement breaks a single global store immediately (two characters
  would clobber or blend state).
- A minimal real schema: at least "places visited + what's there" (a
  room/shop fact) and "current goal." Not yet the richer stuff
  (playstyle, efficiency learnings) the scale-up goal needs.
- A decision policy for *when* memory gets consulted vs. when the agent
  should just go look — "check memory first, only explore if it's not
  there" is itself a small piece of logic, not just storage.

## Scale-up goal: grind within a playstyle, level at the guild, record the journey, find efficiencies, kill the Minotaur

Adds real weight beyond "more of the same minimal proof":

- **Playstyle**: generalizes the personality file written 2026-07-26 for
  Dummy (`.boukensha/prompts/player/system.md` — backstab-first,
  loot-everything, thief voice). That file is Thief-specific by
  construction. A general system needs playstyle as a *parameter* (likely
  keyed the same way as memory — per-character or per-class), not a
  hardcoded prompt file per project.
- **Leveling at the guild**: practice-session management (train skills
  when available, e.g. backstab is still "poor" tier as of 2026-07-26 per
  `player.md`) needs to be a real, recognized part of the loop, not
  something only a human operator remembers to do.
- **Recording the journey**: a human-readable log distinct from the
  machine-consulted memory — close to what `player.md`'s progress log
  already does by hand, except agent-authored instead of me authoring it
  after the fact.
- **Finding efficiencies**: memory-as-*learnings*, not just memory-as-
  facts — the agent notices "mob X gave more exp per turn than mob Y" and
  writes that down for its own future reference, then actually consults it
  before choosing what to fight next. A real feature (write + read own
  learnings), not a side effect of state storage.
- **The Minotaur fight**: needs scouting and a real strategy before it's
  attempted at all — level 7 is an unconfirmed gate (flavor text on a
  warning sign, never tested), not a known-sufficient threshold.

## Generality: any character, or multiple characters in one session

This is an architecture fork, not just a schema question. Today,
`Tools::Mud.register`/`tools/mud.py`'s `register()` opens exactly one
`Session` (one socket, one character) per call. Running several
characters concurrently under one harness needs a real decision:
independent `Context`/`Registry`/`Agent`/`Session` sets per character
(structurally already possible — `week0_explore/explore_architecture/03_subagent_sdk`
proved the *concept* with the Claude Agent SDK, not this hand-rolled
harness) plus something to actually steer them (a scheduler? round-robin
turns? genuinely concurrent threads/processes?).

**Open question, not yet decided**: design the memory/playstyle schema to
not preclude multi-character now (cheap — just key everything by
character name from the start), but defer building actual concurrent
steering until the single-character path is proven? Or use the bakery/menu
proof case itself to exercise two characters early and shake out the
architecture sooner? Leaning toward the former (cheap insurance now,
defer the expensive part) but not decided.

**Cheap validation available for free**: `balthasar` (the mage from
`03_subagent_sdk`) is a second character with a genuinely different
playstyle already sitting in this project. Before generalizing any
schema, sanity-check "would this still make sense for balthasar casting
spells instead of Dummy backstabbing" — a sniff test, not a build.

## Pillar 1: Memory

- Per-character keyed storage (not a shared file like today's
  `player.md`/`world.md`, which are hand-maintained by a human for one
  architecture and don't generalize).
- Two distinct kinds of content, not one blob:
  - **Facts**: place/goal/inventory state — what the bakery/menu proof
    case needs.
  - **Learnings**: efficiency observations the agent writes about its own
    play — what the scale-up goal's "find efficiencies" needs.
- A read-before-explore, write-after-anything-goal-relevant discipline —
  mirrors what the `play-mud` Skill already does by convention
  (`data/player.md`/`data/world.md`), just as a real harness feature
  instead of external markdown files I curate by hand.

## Pillar 2: Observability (token spend + turn/stall tracking)

`12_context`'s `Logger` deliberately removed per-response cost/provider
tracking (a documented, intentional regression relative to `06_the_logger`
through `11_tui`) — backends still compute `estimate_cost`/`usage_unit`/
`usage_level`, nothing calls them anymore. Re-connecting this is necessary
but not sufficient for autonomy-grade observability. Not a hypothetical
concern: `docs/plans/observability.md` records that Andrew hit excessive
token spend in week1 accomplishing a simple goal — the exact failure mode
this pillar exists to make visible before it happens again. Minimum bar:

- **Token spend per task/turn**, re-connected from the backends' existing
  (already-implemented, just disconnected) cost-estimation methods. Needs
  a decision on what "per task" means once sessions are long-running and
  autonomous — per-turn, per-goal, cumulative across a whole unattended
  run like 2026-07-25/26's grind sessions?
- **Dead-turn / stall detection.** The `compact_messages()` bug found
  2026-07-25 burned 15 turns and real API calls doing nothing, and
  nothing in the existing Logger/JSONL output would have surfaced that
  without a human manually diffing checkpoints and reading raw session
  logs. Autonomous operation needs "this turn accomplished nothing, N
  times in a row" to be a first-class, surfaced signal, not something
  inferred after the fact.
- **Wait/retry policy as an observable, not just an operator judgment
  call.** Tonight's sessions needed a human to decide when to poll for
  movement regen, how long to wait, when to give up and reroute (the
  shopping trip's failed Armory search). That decision-making needs to be
  encoded and its outcomes logged, not left to whoever's watching.

## Not yet decided / explicitly open

- Single-character-first vs. exercise-two-characters-early (see
  Generality section above).
- Whether memory needs a real room-graph structure (richer, more general)
  or freeform text-per-fact is good enough for the bakery/menu proof and
  can be revisited once the scale-up goal is actually attempted.
- What "per task" means for token-spend accounting once tasks span many
  turns and possibly many real-world hours (movement/respawn waits).
- Whether the two known, already-fixed protocol bugs (`compact_messages()`
  orphaned-tool_result, `read_until_prompt`'s "> " sentinel collision)
  have siblings not yet found — both were only caught by sustained live
  load, not review or short playtests, which is itself a data point for
  how much observability needs to lean on real usage rather than static
  checks.

## Next step

Confirm this scope, then write a real, milestoned execution plan per
pillar (starting with whichever pillar is chosen first) — same rigor as
`docs/plans/python_port/`'s per-step plans: reference actual current
code, note genuine open questions, no silent defaults.
