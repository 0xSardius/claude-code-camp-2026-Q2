# Week 3 — scope, decisions, and sequencing

Final week. The goal, from `docs/journal/3_week3.md`: **an agent architecture
that can perceive, understand, decide, act, remember, and recover.**

Concretely, the thing we want to be able to do is turn the agent loose and have
it grind experience using thief skills, level and train, periodically come back
to town to buy equipment, play in a way that is recognisably a thief rather than
a generic combatant — and take a task from a human when we want to steer it.

**The Minotaur is a bonus, not the bar.** From `capability.md`: *"you are trying
to build a capable system that COULD do this task, not create a messy terrible
system that uses brittle shortcuts that won't stand under prod."* If we reach
level 7 and win, good. If we build a loop that could and ran out of week, that
is the assignment.

Working notes that seeded all of this: [`capability.md`](capability.md).

## The central question, and the answer we are building on

*"Is brute-forcing pathing using deterministic code capable?"*

The notes answer this themselves, in the line about the algorithmic walker that
ignores a lava-pit label. **The distinction is not deterministic vs. agentic —
it is where the knowledge came from.**

A wall-follower that walks into a lava pit is incapable because no judgment ever
happened. A breadth-first search over a map the agent built *by reasoning about
what it saw* is capable, because judgment happened once at acquisition and is
amortised over every later replay. Same algorithm; opposite verdict.

That is the spine of the week, and it is written up properly in
[`00_judgment_boundary.md`](00_judgment_boundary.md). Every subsystem plan has
to answer to it.

Note what the notes' own "Capable loop (on paper)" list says: reasoning at every
step, high token cost, high latency, **no distinction between judgment and
routine work**. Those are listed as *problems*. So the design target is not
"reason more" — it is *routine work runs mechanically off memory; judgment runs
on the model; and judgment is never faked with heuristics.* The red-flag list is
exactly the failure mode of faking it.

## Structural decisions

- **Code home: `week3_capable/`**, forked from `week2_observability/python` the
  same way week 2 forked from week 1's final step. Week 2 is a submitted
  artifact and stays frozen — including its bugs. The "fix the week 2
  retroactive stuff" work lands in week 3's copy, not by editing what was
  handed in.
- **Python only**, single model (`claude-sonnet-5`), unchanged from week 2.
- **Multi-model routing deferred.** The notes raise it (Vercel gateway, separate
  models for code-gen / review / plan-gen). Interesting, but the harness already
  has five backends and a working single-model loop; adding a gateway is
  infrastructure that does not move capability. Revisit only if a specific
  subsystem is demonstrably bottlenecked on model choice.
- **Subsystem plans get written as we reach them**, not all up front. This is
  the notes' own stance: *"keep varying and wrangle your systems and subsystems.
  Leave the goal for later... it is often an iterative process of discovery that
  takes you places you didn't originally think you would go."* Writing seven
  speculative plan docs on day one would contradict that.

## Sequencing

**1. Test harness** ([`01_test_harness.md`](01_test_harness.md)) — first, not
last. The notes flag this twice: AB lost half a week to it, and the SolEnrich /
x402 experience made the same point with real money on the line. We have **493
real captured tool outputs across 22 tools** in the committed session logs, so
the fixtures already exist. Building this first means every subsystem policy is
developed offline against real game text, with no MUD and no token spend.

**2. De-brittle the perception layer** ([`02_perception.md`](02_perception.md),
written when we start it) — the week 2 retroactive fix. `mud_parse.py` hits four
of the five red flags: 18 regex uses, a stop-word list, number thresholds
(`_MAX_TITLE_LEN = 60`), and hardcoded string labels standing in for categories.
Worse, last week's code-review fixes *added* to that pile — a phantom-room bug
was fixed by adding more stop words. Every subsystem reads parsed state, so this
is a prerequisite rather than a cleanup.

**3. The driver** — goal decomposition, scheduling, stall detection, recovery,
and the human task interface. This is the "decide" and "recover" half of the
goal statement, and neither exists today.

**4. Subsystem policies**, in dependency order: navigation, combat (thief-shaped
— backstab, sneak, hide, flee), recovery (rest / eat / drink), progression
(practice and level at the guild), economy (return to town, buy equipment).

Scope honesty: that is five subsystems plus a driver in a week where testing
historically eats half. If it compresses, **navigation, combat, and recovery are
the ones the grind loop cannot run without.** Progression and economy degrade to
stubs without stopping the loop.

## Acceptance — how we know it is "capable"

Not "did it beat the Minotaur." Three numbers, all computable from the week 2
session reporter:

- **Judgment ratio** — what fraction of actions needed a model call versus ran
  mechanically off memory. This is the direct, measurable answer to the notes'
  central question. A loop that walks known routes, rests, and eats without
  consulting the model, while reserving it for genuine decisions, is capable in
  exactly the sense the notes mean.
- **Cost per unit of progress** — spend per XP, not spend per turn. A change
  that halves per-turn cost while doubling turns needed is not an improvement,
  and per-turn accounting alone would score it as one.
- **Recovery rate** — failures encountered versus failures survived
  unattended: disconnects, death, being stuck, running out of movement.

## Retrospective questions to answer at the end

Carried from `capability.md`, to be answered with evidence rather than
impression:

- Was the technical goal possible?
- If not, how long would it have taken?
- Would it have been worth the time and money?
- What is the longevity of the solution — what breaks first under real use?
- What domain knowledge did we gain about engineering agent loops?

## Process

Unchanged from week 2, with one correction applied: **code review runs per
milestone, not at the end of the week.** Week 2 deferred it and the review then
confirmed 18 defects — 7 high severity — sitting behind 68 passing tests. That
was the single largest self-inflicted risk of that week.

The journal (`docs/journal/3_week3.md`) is being written by hand this week; this
directory carries the plans and decisions.
