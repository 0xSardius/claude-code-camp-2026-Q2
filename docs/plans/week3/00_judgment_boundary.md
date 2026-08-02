# Week 3 — the judgment / routine boundary

The spine of the week. **Every subsystem plan must answer this document**: for
each decision it makes, is that a model call or a mechanical one, and what
justifies the choice?

Written first because without it the subsystem plans drift back into heuristics,
which is precisely the failure `capability.md`'s red-flag list describes.

## The principle

> Judgment happens once, at acquisition. Replay is mechanical.

A wall-follower that walks into a lava pit is incapable because no judgment ever
happened — the label was there and nothing read it. A breadth-first search over
a map the agent built *by reasoning about what it saw* is capable, because the
judgment happened at acquisition time and is amortised over every later replay.

Same algorithm. Opposite verdict. The determinism is not the problem; the
**absence of any reasoning anywhere in the chain** is.

This is what makes week 2's `Memory.route()` legitimate: it is a BFS, but every
edge in it was recorded because the agent went somewhere and observed where it
landed. Nothing is inferred, and reverses are not assumed (CircleMUD has
one-way exits). The cheapness is earned.

## The two failure modes

**Reasoning on rails** — a model call for something that has one correct answer
and needs no context. Walking a route you already know. Resting when you are
tired. This is what the notes' "Capable loop (on paper)" list is complaining
about: reasoning at every step, high token cost, high latency, *no distinction
between judgment and routine work*.

**Faked judgment** — a heuristic standing in where reasoning was required. This
is the red-flag list. It is the more dangerous of the two, because it looks like
efficiency and fails silently in exactly the cases the heuristic did not
anticipate.

Week 2 shipped both. `Memory.route()` is the good pattern. `mud_parse.py` is the
bad one, and last week's code-review fixes made it worse — a phantom-room bug
was fixed by adding *more* stop words.

## The test: does the number stand in for a conclusion?

The red-flag list includes "simple number threshold checking," which needs
care, because not every constant is a red flag.

**Faked judgment** — the number substitutes for a conclusion the system should
have reached by reasoning:

- `_MAX_TITLE_LEN = 60` stands in for *"this line looks like a room title."*
  That is a perception judgment, encoded as a length check.
- *"we have seen 20 rooms, so we have explored enough"* stands in for a real
  assessment of coverage.

**Legitimate policy parameter** — the judgment is stated explicitly and the
number only tunes it:

- *"disengage below 40% HP"* — the judgment ("retreating at low health is
  correct") is explicit and auditable. 40 is a tuning knob on a decision that
  was actually made.
- `max_turn_tokens` — an explicit spend ceiling, not a proxy for anything.

The distinguishing question: **if this number were wrong, would a reviewer call
it a bad decision, or a bug?** A bad decision means it is a parameter. A bug
means it is standing in for judgment, and belongs on the model or on real
structure instead.

## Classifying this loop's decisions

First pass. Subsystem plans refine their own rows and must justify any move
from the right-hand column to the left.

| Decision | Where | Why |
|---|---|---|
| Walk a route already in memory | **Mechanical** | Judgment happened when the edges were recorded |
| Rest when movement is exhausted | **Mechanical** | One correct answer; the game states the condition |
| Eat / drink when the game says hungry or thirsty | **Mechanical** | The game states it explicitly; no interpretation |
| Retreat below the health threshold | **Mechanical** | Explicit policy; the threshold is a tuned parameter |
| Record what a room contains | **Mechanical** | Observation, not inference |
| Where to explore next, given unknown exits | **Model** | Weighs danger, distance, and goal — genuine judgment |
| Whether a mob is worth fighting | **Model** | `consider` output plus learnings plus current state |
| Which skill to practise at the guild | **Model** | Depends on playstyle and what the character lacks |
| What to buy, and when a trip to town is worth it | **Model** | Trades gold, risk, travel cost, and expected benefit |
| Is this room's description telling me something dangerous | **Model** | Reading meaning out of prose — the lava-pit case |
| Decomposing a goal into the next concrete objective | **Model** | The core "decide" gap week 2 left |
| Are we stuck / is this turn accomplishing nothing | **Mixed** | Mechanical detection, model decides the response |

The right-hand column is where the money goes, and it should be a minority of
actions. That ratio is the acceptance metric — see below.

## Perception is the hard case

Parsing sits awkwardly across the line. Reading `[ Exits: n e s w ]` is
genuinely mechanical: the game emits a fixed structure and reading it is not a
judgment. Deciding *which line is the room title* is not, which is why the
current length-and-stop-word heuristic keeps producing phantom rooms.

The resolution is not "send every reply to the model" — that is reasoning on
rails at 155 move-replies per session. It is to **stop asking the parser to make
judgments**: extract only what the game emits structurally, and where a real
interpretation is needed, either ask the model once and remember the answer, or
change what we ask for so the structure carries it. `02_perception.md` works
this through.

## The measurable claim

**Judgment ratio: the fraction of actions that required a model call versus ran
mechanically off memory.**

This is the direct answer to the notes' central question, and it is computable
today from the session logs — the reporter already counts tool calls and model
requests per turn.

It is a ratio to *understand*, not to maximise. Driving it to zero means the
lava-pit walker. Driving it to one means the on-paper loop the notes reject. The
claim we want to be able to make at the end of the week is narrower and more
honest:

> The loop handled routine movement, recovery, and known-route travel without
> consulting the model, and spent its model calls on decisions a human would
> also have had to think about.

If that is true, "capable" is demonstrated with a number instead of asserted —
and the deterministic-pathing question is answered in the only way that
survives contact with a lava pit.
