# Week 2 — Pillar 2: Basic memory

Goal: the harness remembers, per character, what it has learned — enough that
the bakery run is provably non-random on a second attempt. Builds on
`00_lifecycle_hooks.md`.

The acceptance bar is *provability*, not success. A run that finds the bakery by
luck passes no test. The bar is: on run two, the agent either already knows
where the bakery is and goes there directly, or knows it doesn't and explores
deliberately — and the log shows which.

## What exists to learn from

Week 0's `play-mud` Skill accumulated real, hard-won knowledge in
`week0_explore/explore_architecture/02_agent_skills/.claude/skills/play-mud/data/`
— `player.md` (23 KB) and `world.md` (15 KB): the Newbie Zone map, mob
difficulties, which "newbie" flavor text is safe to fight, where the guard /
dragon / alchemist are. Those files are **hand-maintained by a human for one
architecture and one character**. They are the content model to learn from and
the maintenance model to reject.

Week 1's live playtest made the gap concrete: with no persistent map memory, a
single missing piece of context (a room *name* instead of a route) derailed an
entire turn, and the fix was pasting the map into the task prompt by hand. That
is the thing this pillar removes.

## Design

### Per-character keying, from the start

Storage is keyed by character name from day one — `dummy`, `balthasar`,
`boukensha` all coexist. This is the cheap insurance identified in
`week2_foundations.md`: it doesn't build concurrent multi-character steering
(deferred), but it stops a single global store from baking in a
single-character assumption that would be expensive to undo.

Sanity-check every schema decision against `balthasar` (a Magic-user with a
genuinely different playstyle) before committing to it. Sniff test, not a build:
*would this still make sense for a mage casting spells instead of a thief
backstabbing?*

### Two kinds of content, not one blob

- **Facts** — place/route/goal/inventory state. What the bakery proof needs.
  "The Bakery is two north and one east of the Temple Square." "Current goal:
  find the Bakery."
- **Learnings** — efficiency observations the agent writes about its *own* play.
  "Mob X gave more XP per turn than mob Y." What the scale-up goal needs, and a
  real feature (write *and* read back) rather than a side effect of storage.

Keep them in separate files or separate namespaces. They have different write
cadences, different consumers, and different trust levels — a fact is
observation, a learning is inference.

### Read-before-explore is logic, not storage

"Check memory first, only explore if it's not there" is a real piece of the
loop. It attaches at `before_turn` (load the character's facts and current goal
into context) and gates `before_model`'s first-visit room survey — a room the
store already knows is not a first visit.

### Open: structure vs freeform

`week2_foundations.md` leaves this open, and it should stay open until the
bakery run forces an answer. Freeform text-per-fact is cheaper and reads well
in the prompt; a real room graph is more general and makes "know the way back"
mechanical instead of inferred. **Recommendation: start freeform with a
structured *route* record as the one exception**, since "know the way back"
is an explicit goal requirement and is the one thing freeform text is worst at.
Revisit when the scale-up loop is attempted.

## Milestones

**M1 — Store.**
A per-character store on disk under `.boukensha/` (matching the existing
`sessions/` and `prompts/` layout), with facts and learnings separated.
Gitignore policy needs a decision, same as the `sessions/*.jsonl` carve-out
made in `06_the_logger`: memory files are generated artifacts, but they may be
worth committing for instructor evaluation. **Ask before defaulting.**

**M2 — Memory tools.**
Register read/write tools on the registry so the model can consult and record
deliberately, alongside the `before_turn` automatic load. Note the store is now
reachable from two paths — the automatic hook and the model-facing tool — which
is exactly the shape of the `register_tool` normalization bug documented in the
root `CLAUDE.md`: **normalize keys at the store's own boundary, not at each
caller.** Do not repeat that one.

**M3 — Write discipline.**
Facts written at `after_tool` (a successful `move` records a route edge; a
`look` in an unknown room records the room) and at `after_turn` (goal progress).
Append-only with respect to the message list — see the hooks plan's hard
constraint; a memory write must never splice into conversation history.

**M4 — Bakery proof run.**
Two runs against the live MUD with the same starting character state. Run one:
the agent explores and finds the bakery, recording as it goes. Run two: with the
store warm, the agent goes there.
*Acceptance*: run two's log shows a memory read preceding the movement
decisions, and the route taken matches the recorded route. A successful run two
with no memory read in the log is a **failure** of this milestone, not a pass —
it means it guessed again.
Then: list the menu, and get back.

**M5 — Learnings read-back.**
The agent writes an efficiency observation and later consults it before choosing
what to fight. This is the piece the scale-up goal needs and the piece most
likely to be quietly skipped, because facts alone will make the bakery run pass.
Don't skip it.

## Risks

- **Memory grows the prompt.** Every fact loaded at `before_turn` is context the
  model pays for on every iteration of that turn. This pillar and the token
  pillar pull against each other; measure with the observability pillar's
  summary reporter rather than assuming it's free. Loading the *whole* store
  every turn will not scale to a level-7 grind — expect to need relevance
  filtering, and expect that to be its own small design problem.
- **A wrong fact is worse than no fact.** `player.md`/`world.md` are trustworthy
  because a human curated them. An agent-written store will accumulate errors
  (a room misremembered, a mob's difficulty misjudged after one lucky fight).
  Decide how a fact gets corrected or expired before the store gets large.
