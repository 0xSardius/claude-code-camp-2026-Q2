# 02 — De-brittle the perception layer

**Written after the fact.** The other plans in this directory were written
before their work; this one was not. Perception was rebuilt on 2026-08-02 in
commit `16f06d6`, on the first day, before the plan doc existed. This records
what was done and why, so the sequencing in [`README.md`](README.md) has
something to point at.

## The problem

Week 2's `mud_parse.py` decided which line was the room name by accumulating
guesses: the first non-blank line, unless it was over 60 characters, unless it
ended in sentence punctuation, unless it contained two quote marks, unless it
started with one of a list of phrases.

Every bug found in week 2 added another guess. That is four of the five
patterns the red-flag list in [`capability.md`](capability.md) names — a regex
over content, a stop-word list, a number threshold standing in for a judgment,
and hardcoded string labels used as categories.

Worse, the week 2 code review "fixed" a phantom-room bug by adding more stop
words. The pile was growing, not shrinking.

## The fix

Not a better guess. The server had been marking room titles with its own colour
code the whole time, and the parser was stripping that off before looking at
the text.

Two structural signals, both from the server:

1. The `[ Exits: ]` block. Without it, this is not a room reply.
2. The first title-coloured line **above** that block.

The same colour also marks mobs and players, but the server always lists those
below the exits, so position separates them.

## How it was verified

Measured against the whole captured corpus before changing anything. All 243
real room-bearing replies carry the marker, and the markup rule agreed with the
old guessing rule on every one — including both cases where narration precedes
the room name.

It also handles a case week 2 could not. "A tall figure watches you closely" is
short and unpunctuated, so the old rule would have taken it as a room name and
written a phantom node into the map permanently. The markup rule cannot do
that, whatever the text says.

## The deliberate cost

Where the markup is absent, the parser **declines** rather than falling back to
guessing. Colour could be disabled server-side, and that is a mode we have
never seen. A decline shows up as a parse gap in the logs; a silent guess is
how phantom rooms got written in the first place.

`_MAX_TITLE_LEN`, `SPEECH`, `TOOL_TEXT` and `_plausible_title` were all
deleted. The file got 15 lines shorter.

## What it caught in our own tests

One test had to change, and the reason is the point. `test_review_fixes.py`
held room samples that had been hand-typed **without** the colour codes, so
they were not room replies at all — they were text matching an idea of the
format rather than the server's actual output. Swapping the rule made that file
fail, which is the corpus catching the same class of mistake inside the test
suite itself.

## How this held up

It was not touched again for the rest of the week. Room parsing caused no
further bugs across every live run.

One later fault was adjacent but separate: room *identity* keyed on the exits
list rather than the description, which collapsed three different Main Street
segments into one map node. That was a `Memory.room_key` problem, not a parsing
one — the parser had read all three rooms correctly. See the 2026-08-05 entry
in [`../../journal/3_week3.md`](../../journal/3_week3.md).
