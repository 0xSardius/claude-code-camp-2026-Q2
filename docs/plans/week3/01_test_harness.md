# Week 3 — test harness (built first)

Built before any subsystem work, on the evidence of two people's experience:
`capability.md` records AB losing half a week to testing, and the same wall on
SolEnrich with real money on the line. Week 2 also makes the case from the other
direction — 68 passing tests hid 18 real defects, 7 of them high severity, and
the tests that failed hardest were the ones I had written against my own
assumptions.

The goal is narrow: **every subsystem policy must be developable and testable
with no MUD connection, no model call, and no token spend.** If a policy can
only be exercised by playing the game, it will not get exercised.

## What we already have

The committed session logs contain **493 real captured tool outputs across 22
tools** — ANSI codes, status prompts, wrapped prose and all. Every subsystem in
the week 3 scope has real material:

| Subsystem | Fixtures available |
|---|---|
| Navigation | 155 `move`, 106 `look` |
| Combat | 64 `attack`, 23 `consider`, 1 `examine` |
| Progression | 56 `check` (score) |
| Economy / inventory | 23 `get_item`, 5 `shop`, 5 `drop_item`, 1 `equip_item` |
| Recovery | 11 `set_position`, 1 `consume_item` (carries "You are hungry.") |
| Session lifecycle | 7 `mud_connect`, 1 `mud_disconnect`, 1 `send_raw` |

This matters more than convenience. A parser tested against hand-written
samples encodes the author's idea of the format rather than the server's — which
is exactly how `_plausible_title` came to reject real room titles and accept
gossip lines. Fixtures cut from real transcripts do not have that failure mode.

## Design

### Layer 1 — a fixture library

Extract the captured outputs into a queryable corpus, keyed by tool and tagged
by what makes each interesting (a dark room, a failed move, a fight in progress,
an empty corpse, a shop list). Sourced from the logs, checked in, and readable
as plain text so a human can see what a test is actually asserting against.

Tagging is the work here. 155 `move` samples are not 155 useful cases; the value
is in finding the handful that are structurally different — the ones that broke
week 2's parser.

### Layer 2 — a fake MUD

A `Session`-shaped object that replays fixtures instead of holding a socket, so
`tools/mud.py` and everything above it runs unchanged. It needs to model:

- **State**, so movement composes: the character is somewhere, and `move north`
  yields the room to the north. A small hand-built map of real captured rooms is
  enough; this is not a MUD reimplementation.
- **Failure injection**, because the failure paths are what we cannot test
  live on demand: a dropped connection mid-turn, a refused move, death, movement
  exhaustion, a mob attacking unprompted.

The second is the part that earns its keep. Week 2's real bugs were all on
paths that are hard to reach deliberately against a live server.

### Layer 3 — a fake model

Subsystem policies must be testable without the API. A scripted client that
returns canned tool-call sequences already exists in the week 2 tests
(`FakeClient`) and generalises: given a scenario, assert the policy *chose* the
right action, without paying for the model to choose it.

This is what makes the judgment-boundary work checkable. A policy classified as
mechanical must produce its action with the fake model returning nothing at all
— if it cannot, it was not mechanical.

### Layer 4 — scenario tests

End-to-end, offline, over the three layers above. The scenarios worth writing
first are the ones we know break things, because they already have:

- Walk into a dark room, then move again → must not fabricate a map edge
- Get attacked mid-navigation → must break off cleanly
- Run out of movement → must rest rather than retry
- Connection drops mid-turn → must reconnect and re-establish position
- Die → must recover rather than continue against a corpse
- A gossip line arrives just before a room description → must not become a room

## Milestones

**M1 — Fixture extraction.** Pull the 493 outputs from the logs into a tagged,
checked-in corpus. Verify by re-running week 2's existing parser tests against
fixtures drawn from the corpus rather than inline strings.

**M2 — Fake MUD with state.** Movement composes across a small real map;
`tools/mud.py` runs against it unchanged. Verify by replaying the bakery run
offline and getting the same recorded route.

**M3 — Failure injection.** The six scenarios above, each reproducible on
demand.

**M4 — Policy test kit.** The scaffolding a subsystem plan can assume: given
fixtures and a scenario, assert the chosen action. Every later subsystem lands
with tests written against this rather than inventing its own.

## Acceptance

- A subsystem policy can be written, run, and debugged with the MUD server
  stopped and no API key set.
- The six known-breaking scenarios are reproducible on demand.
- Week 2's parser tests pass against real fixtures rather than inline samples.

## Risks

- **Fixture rot.** A fake MUD that drifts from the real one gives confident
  green tests about a game that does not exist. Mitigation: fixtures are cut
  from real transcripts and never hand-edited, and any live run that surfaces
  an output shape we do not have gets captured back into the corpus.
- **Over-building.** This is a test harness, not a MUD. The moment it needs its
  own combat maths it has gone too far — at that point the thing under test
  should be exercised against the real server instead.
- **The offline/online gap is real and stays real.** Week 2's most expensive
  bugs (the `"> "` sentinel collision, the orphaned `tool_result` after
  compaction) only became reachable under sustained live load. The harness makes
  iteration cheap; it does not replace running the thing.
