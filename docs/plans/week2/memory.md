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

### Settled 2026-07-27: record edges, present trails

Freeform text for everything *except* movement, which gets one narrow piece of
structure. Two facts drove this:

- **Room identity is the hard problem.** tbaMUD room names are not unique ("A
  Dark Alley" recurs), so a graph needs a fingerprint (name + sorted exit list
  + description hash). A wrong fingerprint corrupts the map silently and in the
  worst way — two rooms merge, or one splits.
- **Exits aren't reliably symmetric.** CircleMUD supports one-way exits, so
  "reverse the path by inverting each direction" is wrong in the general case.
  An edge is only known bidirectional once observed in both directions.

So: **store `(from_room, direction, to_room)` edge triples; a "trail" is a
query over accumulated edges, not a stored object.** A flat direction list
would not scale — 50 places is up to 2,450 journeys, shared path prefixes get
duplicated, nothing composes, and an inefficient first recording gets replayed
forever. Storing edges fixes all four: composition works as soon as two
journeys share a room, shortest path is a BFS, and shared prefixes *are* the
same edges. No migration is needed later, because the graph is already latent
in the data.

The identity risk is contained by a useful asymmetry: **trail replay is robust
to bad room keys; composition is not.** Replaying a recorded sequence works
even if two rooms collide on a fingerprint. So ship edge recording + trail
replay first, and enable composition/shortest-path only once the fingerprints
are shown to hold.

Known remaining limits, accepted: edges never expire (a route through a
now-dangerous room stays "valid"), and real scaling pressure arrives with
multi-zone exploration, which is week 3 territory.

**Not using `circlemud-world-parser` to preload the map** — it would make this
pillar untestable, since you can't demonstrate an agent learned a map you
handed it, and it wouldn't generalize to unseen zones. Keep it as a debugging
oracle for verifying the learned map is correct.

### Layout

Split by *who writes it*, which keeps the two write paths from tangling:

```
.boukensha/memory/<character>/
  state.json     -- level, hp, position belief    (harness-written)
  trails.json    -- recorded edges                 (harness-written)
  facts.md       -- world/character observations   (agent-written)
  learnings.md   -- efficiency observations        (agent-written)
  journal.md     -- human-readable narrative       (agent + generated)
```

JSON for harness-owned files (nothing reads them in a prompt); Markdown for
agent-owned ones (they get injected into context, and Markdown is what the
model writes well).

**Committed to git**, per the 2026-07-27 decision, via the same `.gitignore`
carve-out pattern `.boukensha/sessions/*.jsonl` already uses. These are small
by nature and are arguably the most interesting evaluation artifact in the
repo — they show what the agent taught itself.

### The player file is a CLAUDE.md for the character, and caching splits it

Today's hand-maintained `player.md` does four jobs at once: current character
state, accumulated world knowledge, a progress narrative, and standing
playstyle instructions. That *is* a CLAUDE.md for the character.

Week 2 splits it, and the reason is **prompt caching, not tidiness**. A
CLAUDE.md that rewrites itself every turn cannot live in the system prompt: any
byte change to the cached prefix invalidates the whole cache, and caching is
~94% of the token spend. So the split follows write cadence:

| Job | Written by | Changes | Where it lives |
|---|---|---|---|
| Playstyle, personality, standing rules | human | rarely | **system prompt** — cached |
| Character state (level, HP, position) | harness, from `score` | every turn | injected as a message, after the breakpoint |
| World knowledge, learnings | agent | on discovery | injected as a message, after the breakpoint |
| Progress narrative | agent | end of session | **never sent to the model** |

Row one already exists: `.boukensha/prompts/player/system.md`, written
2026-07-26. The stable half of the character's CLAUDE.md is already built and
already in the right place; week 2 adds the volatile half and keeps it *out* of
the system prompt.

**`journal.md` is hybrid**: the stats section is *rendered from recorded state*
so it structurally cannot fabricate progress, and the narrative section is
agent-authored prose clearly marked as its own account. Generation can't
produce "I nearly died to the guard, so I avoid that room," and that's the part
that makes today's `player.md` valuable. The generated half shares
implementation with observability M5's session reporter — same inputs,
different rendering. The narrative half costs output tokens, which the
measurement showed are 6% of spend, so it is effectively free.

**Deferred deliberately**: the agent does *not* get to rewrite its own
`system.md` playstyle in week 2. It invalidates the cache, it's a large
behavioral lever with no rollback, and a bad self-edit would quietly degrade
every later session. Learnings accumulate in `learnings.md`; promoting one into
standing playstyle stays a human decision. Revisit once the learnings loop has
a track record — it is the natural next autonomy step.

## Milestones

**M1 — Store.**
The per-character layout above, under `.boukensha/memory/<character>/`.
Gitignore: **committed**, via a carve-out mirroring `sessions/*.jsonl`
(settled 2026-07-27).

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

**M4 — Bakery proof run. DONE 2026-07-29 (PASS on the second attempt).**
Two runs against the live MUD with the same starting character state. Run one:
the agent explores and finds the bakery, recording as it goes. Run two: with the
store warm, the agent goes there.
*Acceptance*: run two's log shows a memory read preceding the movement
decisions, and the route taken matches the recorded route. A successful run two
with no memory read in the log is a **failure** of this milestone, not a pass —
it means it guessed again.
Then: list the menu, and get back.

**M5 — Learnings read-back. MECHANISM BUILT, UNDEMONSTRATED.**
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
