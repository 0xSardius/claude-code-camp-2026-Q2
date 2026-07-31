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

**Status at time of writing (2026-07-29):** all three assigned capabilities
are built and verified against the live game. The bakery proof passed on its
second, corrected attempt. Remaining: learnings read-back is built but
undemonstrated, and the leveling loop (a separate workstream) has not started.

**Vocabulary, since everything below leans on it.** A *turn* is one instruction
from a human plus all the work the agent does to answer it. An *iteration* is
one round inside that turn — one request to the model and its reply. A single
turn usually takes several iterations, because the agent looks, decides, acts,
sees the result, and decides again. *Tokens* are how the model bills: roughly,
chunks of text going in (input) and coming out (output).

### Setting the ground rules

Three decisions were made up front rather than drifted into.

**Week 2 gets its own codebase.** `week2_capable/` is a copy of week 1's final
step, evolved from there. Week 1 stays frozen as a submitted artifact.

**The Ruby/Python mirror is retired.** All through week 1, every feature was
written twice and the two versions were diffed byte-for-byte. That caught a
real bug on nearly every step. But its value came from porting *from* a Ruby
original, and week 2's features have no original to port from — writing them
twice would be parallel design, not porting. The cost of retiring it is real
and worth stating plainly: we gave up the check that had been finding most of
our bugs.

**Caching is in scope even though it is Anthropic-specific.** The harness
supports five model providers and treats them symmetrically. Prompt caching
breaks that symmetry. We took it anyway, because it was the only lever likely
to be worth an order of magnitude.

### The lifecycle hooks reframed the whole build

The week 2 course material describes five points in the agent's cycle where
custom behavior can attach: before a turn, before each model request, before a
batch of tool calls, after each tool returns, and after a turn. Instead of
editing three features separately into the main loop, all three attach here.

Two things made this feel like the right shape rather than an imposed one. The
course's own description of the after-a-tool hook — "replace raw movement
output with a compact result" — turns out to *be* the token-optimization
trimming lever, arrived at independently. And the course's turn/iteration
vocabulary already matched the codebase exactly, so the existing log events
needed no renaming.

### Scaffolding, and a gotcha that inverted

Copying week 1's final step into `week2_capable/` surfaced this project's
single most-repeated bug immediately — and pointing the *opposite* way.

The example script computes the repo root by walking up a fixed number of
parent directories. Every week 1 step needed 4 hops and repeatedly shipped with
3. The new tree sits one level shallower, so **3 is now correct**, and copying
the known-good week 1 line forward would have overshot past the repo root.

Worth dwelling on: the project's checklist records this gotcha as a *value*
("it should be 4"). Held that way, it would have caused the very bug it was
written to prevent. Held as a *procedure* ("recount the hops"), it works. A
fair amount of our checklist is phrased as values.

### Deciding what to do with 26 stale docstrings

Every module still opens with "Port of week1_baseline/ruby/...". Those are
stale as instructions once the mirror is retired, but accurate as history — and
they carry the reasoning for why each piece is shaped the way it is. Rewriting
all 26 would have destroyed more knowledge than it cleaned up. Kept them, and
added one note at the package level declaring the mirror retired.

### What the old logs said, before we built anything

Week 1 left 25 session logs in the repository. Reading them before writing any
code turned up five problems — one of which changed the plan.

#### The measurement that overturned the plan

We had just written a plan identifying model "thinking" settings as a major
cost lever. The reasoning was sound: the harness never specifies those
settings, so the model runs at its most thorough default.

The data disagreed. Across 404 recorded responses: **4.67 million input tokens
against 62,900 output tokens — a 74:1 ratio.** Thinking is billed as output,
so it accounts for about 6% of spend. Tuning it would have saved cents.
Caching acts on the other 94%.

The lesson is one the plan itself asserted and then nearly failed to follow: *a
lever that is obviously real is not automatically a lever that matters.* The
only way to tell them apart is to measure first.

#### The logging was growing quadratically

Every iteration, the logger wrote out the *entire* conversation so far. Since
conversations grow as a turn proceeds, log size grows as the square of the
conversation length. In the longest session that meant **4.3 MB of a 4.56 MB
file — 94% of it re-writing history already recorded elsewhere.** Across the
repository, session logs were 11 MB of 17 MB total.

This mattered more than housekeeping usually does, because we had just decided
to commit logs for instructor evaluation, and week 2's sessions are far longer
than week 1's.

#### A bug that would only appear the day caching was switched on

The harness tracks how full the model's context window is, and compacts the
conversation when it approaches the limit. It reads that figure from the
response's input-token count.

But once caching is enabled, that field reports only the *uncached remainder* —
the true size is that plus the cached portions. So the tracked number would
collapse to something small, the compaction trigger would stop firing, and a
long run would eventually die of a full context window with no error pointing
at the cause.

This is the same shape as a bug already documented in that same function, just
arriving by a different route. It forced the sequencing: fix the accounting
*before* turning caching on, not after.

#### The price table was wrong for the model we actually use

Confirmed by running it rather than reading it. A million tokens in and out
priced at **$18.00**, using the standard rate. The model we run has been on
introductory pricing through 2026-08-31, which gives **$12.00**. Reconnecting
cost reporting without noticing would have over-reported spend by ~50% all
week.

#### Reasoning logs had never once fired

The harness logs the model's reasoning. The code that captures it and the code
that writes it are both correct and correctly connected. But the model omits
reasoning text unless you ask for a summary, and the logger skips empty
entries — so **zero reasoning events across 2,395 events in 25 sessions.**

Working code, wired correctly, that had never produced output. Invisible
because nothing ever errored.
### Building the hook layer

The acceptance bar was that **nothing changes**: with no custom behavior
registered, the loop must behave exactly as before. That sounds like a wasted
milestone and isn't — it is what makes it safe to hang three subsystems off the
loop afterward.

**Handlers modify a shared object rather than returning a replacement.** With
several handlers on one hook, a returned "nothing" is ambiguous: did the
handler mean *replace this with nothing*, or *I had nothing to say*? Those need
opposite handling, and this project has been bitten by that exact ambiguity at
nearly every step. Mutating a shared object has no such gap.

**The after-a-tool hook runs outside the error handling around the tool call.**
The existing code already warns that a logging failure after a successful tool
call must not be reported to the model as the tool having failed. The same
applies here: a crash in *observation* must never cost a real result. Verified
— a handler that throws leaves the turn alive, the tool result intact, and an
error in the log.

**All three ways a turn can end funnel through one place.** A turn can finish
normally, or hit its action limit, or fail on an API error. Firing the
end-of-turn hook at each of those three exits would have been three chances to
miss one, and the miss would have been nearly invisible — because in week 1's
longest session, *every single turn* left through one of the two non-obvious
exits. A hook wired only to the obvious path would have passed every short test
while reporting nothing in production.

**A 10-test offline suite replaces what the retired mirror took with it.** No
test-runner dependency, no network, no cost. It is narrower than byte-for-byte
parity was — it only covers the hook points — but it covers the specific thing
parity was protecting here: that adding hooks didn't change what the loop does.
Two of the ten exist purely because of the three-exits problem above.

### Building the observability layer

#### The finding that reordered the project

The first thing the new session reporter did, pointed at week 1's logs, was
surface something no planning had predicted:

**56 of 68 turns ended by hitting their spending limit. Only 12 finished.**

The arithmetic explains it exactly. About 11,562 input tokens per response,
times 4.7 responses per turn, is **~59,890 tokens against a 60,000 limit.**
Because the whole conversation is re-sent on every response, the agent was
spending its entire allowance re-reading its own history rather than doing
work.

That reframes caching from a cost optimization into a **capability fix**. The
turn budget is charged for tokens we pay full price for, so cached tokens stop
consuming it — most of those 56 cut-off turns should start finishing.

Nothing in the plan anticipated this. It fell straight out of building the
instrument before the things it measures, which was the entire reason for
sequencing observability first.

#### Truncation was being recorded as success

When the model's reply hit its output ceiling and got cut off mid-sentence, the
harness classified it as a normally completed turn and appended the
half-finished text to the conversation as if it were final.

Measured at 1 in 404 responses, so rare rather than systemic. We deliberately
built **no retry machinery** — at that rate it would be more risk than the
problem. The fix was to stop hiding it: truncation now has its own stop reason,
its own log entry, and is reported as "truncated" rather than "completed". We
also raised the output ceiling from 1024 to 4096 tokens, which costs nothing
since billing is on tokens produced, not on the cap. Expect the rate to climb
now that reasoning tokens count against that same ceiling — but now we will see
it.

### Prompt caching

**Verified against the live API, not just in tests.** Two real calls sharing a
prefix. The second read **1,727 of 1,745 input tokens from cache — 99% — and
cost 89% less.** That was with only 5 tools registered; the real MUD build has
about 30, so the cached portion is substantially larger.

The live check mattered. Every way of getting caching wrong — a misplaced
marker, a prefix that shifts by one byte between requests, a prefix below the
minimum cacheable size — produces the *same* symptom as working-but-not-saving:
no error, just a cache that never fills. Offline tests can assert the shape of
the request; only a real call tells you it hit.

**Two markers, not one, and the reason is worth keeping.** The
conversation-side marker grows as the conversation does — but it is worthless
at exactly the moment the conversation gets compacted or cleared. The
system-side marker is the stable anchor that still works then. It also covers
the tool definitions, and those (not the ~600-token system prompt) are what
carry the cached portion over the minimum size. A marker on the system prompt
alone would have silently never cached.

**Shipped on by default, against the plan's own decision.** It was scoped as
opt-in. Given the 74:1 input ratio and the 82% cut-off finding, leaving it off
became the riskier choice: default-on fails visibly in the reporter, while
default-off fails by the measurement simply never happening. There is a
config kill-switch.

### First live run, and an infrastructure scare

Everything above had been verified offline — 34 tests against a fake client,
plus two isolated API calls. The harness had not touched the real game once
since the fork, and in between we had changed the request payload, added a
thinking parameter, raised the output ceiling, and inserted five hook points
into the main loop. So: a deliberately narrow smoke run. Connect, look, read
the character sheet, stop. No movement, no combat.

It ran as `boukensha`, the disposable test character, **not** `dummy`. Running
a never-before-run build against the character holding the week's progress is
the setup that goes wrong.

#### The scare: all three characters appeared to be deleted

The first attempt failed at login, and probing the server directly returned
CircleMUD's new-character prompt — *"Did I get that right, Boukensha (Y/N)?"* —
for `boukensha`, `dummy`, **and** `balthasar`. On its face: every character
gone, including `dummy` with the week's grinding on it.

The obvious response would have been to answer Y and recreate them. That would
have been the destructive mistake, because the data was never lost.

What actually happened: the container's bind mount had silently detached. The
compose file mounts the host's `lib/` into the container, and `docker inspect`
confirmed the mount *was* configured. But the container's view of
`plrfiles/A-E/` held only the empty seed file, while the host held
`dummy.plr`, `balthasar.plr`, `boukensha.plr` and an index recording dummy at
level 4. Host files carried write timestamps from Jul 18 through Jul 26 — so
the mount had worked during every past play session and stopped afterward. The
container had auto-restarted around Jul 27 under `restart: unless-stopped`,
and on WSL2 a restart where the host path isn't ready yet leaves Docker
serving an empty directory in its place, with no error anywhere.

`docker compose down && up -d` re-established the mount. All three characters
returned, dummy still at level 4.

Two things worth keeping from this. **A failure that presents as "the data is
gone" deserves investigation before remediation** — the remediation here
(recreate the characters) would have caused the exact loss the symptom
suggested had already happened. And the setup has a standing risk: any
auto-restart can silently detach the mount again, and nothing in the harness
would notice. A pre-flight check that the server can see the expected player
index would catch it cheaply.

Also worth flagging separately: our own probe used a *read-only* login
sequence and deliberately never answered the Y/N prompt, because answering
would have created a character. When the agent itself hit the same prompt on
the first run, it refused to answer it and stopped — correctly, and without
being told about that specific case. It had been told not to act on anything
unexpected, and it treated an unrecognised confirmation prompt as exactly
that.

#### What the live run proved

One turn, three iterations, ended `completed`:

| | |
|---|---|
| Billed input tokens | **5** |
| Cache read | 9,545 |
| Cache write | 5,389 |
| Cache hit rate | **63.9%** |
| Reasoning events | **2** |
| Cost | $0.0190, priced on 3/3 responses |
| Truncations | 0 |

Every week 2 change is now confirmed against the real game rather than a fake
client. Caching hits in a live session, not just on two synthetic calls. Cost
reporting produces real numbers on every response. And the reasoning pipeline
that had produced **zero events across 2,395** now emits them.

The 63.9% is a floor, not a ceiling: this was a three-iteration turn with the
filesystem and shell tools disabled, so the cached prefix was both smaller and
reused fewer times than in a real play session. Only 5 input tokens were billed
at full rate.

### Memory, and a proof that failed before it passed

The store, the model-facing tools, and the lifecycle write-discipline all
landed (memory M1–M3). The design decisions are recorded in
`docs/plans/week2/memory.md`; the two that mattered most in practice were
storing **observed edges** rather than flat paths, and never inferring a
reverse edge, since CircleMUD has one-way exits.

#### The first proof attempt proved nothing

The acceptance bar was deliberately strict: run once with empty memory, let it
explore and record; run again and require that it *uses* what it recorded. A
lucky second success counts as a failure.

Run 2 came back reporting the correct menu — and by my own criterion it
**failed**. Two flaws, both in the test rather than the system:

1. **The character never moved.** The MUD persists where a character is
   standing, so after run 1 found the Bakery, run 2 began *inside* the Bakery.
   It read the menu without taking a single step. Navigation — the entire thing
   under test — was never exercised.
2. **The check measured the wrong thing.** It asked "did the agent call a
   memory tool", and reported False. But the `before_turn` hook injects memory
   into the conversation automatically; the log showed run 2 opening with three
   user messages (the task, the `<memory>` block, the `<position>` block). The
   agent had the knowledge and used it — it opened with *"already had this one
   cased from a previous run"* — without ever needing to ask for it. The check
   was blind to the mechanism the system actually uses.

Fixing it meant a test fixture that walks the character back to the start room,
and a better question: **did the agent walk the route it had recorded?**

#### The second attempt

Run 2, from the Temple of Midgaard, with memory warm:

| | run 1 (exploring) | run 2 (knowing) |
|---|---|---|
| Iterations | 14 | **8** |
| Cost | $0.0596 | **$0.0257** |
| Cache hit rate | 91.1% | 95.8% |
| Moves | 4, after searching | **4, no detours** |

Recorded route: `south, south, west, north`. Route walked in run 2:
`south, south, west, north` — identical, with no exploratory moves at all,
then straight to the menu. **PASS.** Memory cut the work by 43% and the cost by
57% on the same task.

Two side observations. The real-session cache hit rates (91% and 96%) came in
far above the smoke test's 63.9%, exactly as predicted — longer turns reuse the
cached prefix more times. And an honest confound worth stating: Midgaard is a
famous CircleMUD zone, so some of run 1's efficiency may come from the model's
pretrained familiarity rather than pure exploration. The run 2 result does not
depend on that, since what it proves is that the agent followed *its own
recorded* route.

#### A limitation the run exposed

Facts deduplicate only on exact text. Run 2 recorded *"Confirmed again: The
Bakery in Midgaard... sells..."* — semantically identical to a fact already
stored, textually different, so it was kept. Three facts where two would do.
Harmless at this size; not harmless across a level-7 grind, where the injected
block is re-read on every iteration of every turn. Relevance filtering was
flagged as a risk in the plan and is now a demonstrated one.

#### Where memory stands

M1–M4 are done and proven. **M5 (learnings read-back) is built but
undemonstrated** — `remember_learning` writes, and learnings ride along in the
automatic injection and in `recall`, so the mechanism is complete. What has not
happened is a run where a recorded lesson visibly changes a later decision.
That needs a grind-shaped task rather than a fetch-shaped one, so it belongs
with the leveling work. Recording it as unproven rather than quietly counting
the plumbing as the feature.

### A pattern worth naming

Four separate defects this week shared one shape, and it is worth recording as
a category rather than four incidents:

**Code that is present, correct, connected — and silently wrong or silently
doing nothing.**

- Cost estimation: fully implemented, never called.
- Reasoning logging: correct on both ends, zero events ever produced.
- Truncation: recorded as successful completion.
- Context accounting: correct today, would break the day caching was enabled.

None of them raised an error. None failed a test. None would show up in a diff
review. They surfaced only by running an instrument over real data, or by
tracing one value end to end. On this project, *"it doesn't crash" and "it
works" have been different claims at nearly every step* — and the gap between
them is where most of our real bugs have lived.

### Operational notes

- A stale 34-character placeholder API key in `.boukensha/.env` produces a 401
  that looks like a billing or permissions problem. The real key lives in the
  repo-root `.env`. Config loads the placeholder, so anything relying on its
  environment loading gets the dummy. Worth deleting so the next person doesn't
  lose time to it.
- Session logs and memory files are committed for instructor evaluation. The
  logging fix above is what makes that sustainable — without it, a serious
  grind run would add tens of megabytes.
- **The MUD container can silently lose its bind mount on an auto-restart**
  (see the live-run section). Symptom: every character appears not to exist.
  Fix: `docker compose down && docker compose up -d` from
  `week0_explore/infrastructure`. Check before a long run rather than after —
  the player files live on the host at `lib/plrfiles/A-E/`, so if the container
  can see those, the mount is healthy.
- `mud_session.Session.close()` sets its socket to `None` while the reader
  thread is still blocked in `recv`, so closing prints an `AttributeError`
  traceback from the dying thread. Cosmetic — the output has already been
  captured by then — but it will clutter every log that closes a session
  cleanly. Not fixed yet; noted so it isn't mistaken for a real failure.
- `bin/report` changes directory before invoking Python, which silently
  reinterpreted relative path arguments against `python/` instead of the
  caller's directory. Fixed by resolving arguments to absolute paths first.

## Technical Conclusions

### Against the four hypotheses

**"Building observability first will make the other two pillars measurable
rather than speculative" — confirmed, and more strongly than predicted.** The
argument for sequencing it first was defensive: without spend and stall data,
"did memory help?" is unanswerable except by impression. What actually happened
was better than that. The first time the reporter ran over week 1's logs it
found that **56 of 68 turns had been ending on the token ceiling rather than
completing** — 82%, invisible for a week, and predicted by nothing in the plan.
That single number reordered the token pillar and reframed caching from a cost
optimization into a capability fix. Building the instrument first didn't just
make the other work measurable; it changed what the other work was for.

**"Prompt caching will dominate" — confirmed. The sub-claim about compaction is
still untested.** Measurement put input against output at **74:1**, so caching
acts on ~94% of spend. It shipped and hit 90.2% across the live runs, with
$0.10 total spend and only 49 tokens billed at full input rate. But the
prediction that `compact_messages()` would fight caching by invalidating the
message prefix remains unproven: **compaction fired zero times** in any week 2
run, because the sessions were short and the context window is 1M. That half of
the hypothesis needs a long grind session to test, and it is the reason
compaction rework was left undone rather than declared unnecessary.

**"Memory keyed per-character, split into facts and learnings, will make the
bakery run provably non-random" — confirmed for facts, unproven for
learnings.** Run 2 walked exactly the route it had recorded, with no
exploratory detours, at 43% fewer iterations and 57% lower cost than run 1. The
facts half is demonstrated. The learnings half is built and never exercised —
no run has yet shown a recorded lesson changing a later decision, because a
fetch-shaped task doesn't create the opportunity. Recorded as unproven rather
than counted as delivered.

**"Observability will surface at least one bug the reviews and playtests
didn't" — confirmed, and it understated the result by four.** It found cost
estimation implemented and never called; reasoning logging correct on both ends
and never once firing across 2,395 events; truncation recorded as successful
completion; and context accounting that would have silently broken compaction
the day caching turned on.

### What the four bugs had in common

They were not four incidents, they were one category: **code that is present,
correct, connected — and silently wrong or silently doing nothing.** None
raised an error. None failed a test. None would surface in a diff review. They
were found only by running an instrument over real data or tracing one value
end to end.

This is the sharpest thing week 2 taught, and it generalizes past this project:
on a system with no instrumentation, "it doesn't crash" is the only signal you
have, and it is a much weaker signal than it feels like. Week 1's runs looked
successful because nothing was measuring them. They *were* succeeding — while
being cut off five times out of six.

### Measure before optimizing, twice validated

The plan asserted this and then nearly failed to follow it. Having found that
the harness never sends thinking settings — so the model runs at its most
thorough default — the obvious conclusion was that tuning them was a major cost
lever. The data said thinking is 6% of spend and tuning it would have saved
cents. **A lever that is obviously real is not automatically a lever that
matters**, and only measurement separates the two. The same discipline is what
turned up the 82% figure.

### Test design fails as readily as code

The bakery proof failed twice before it passed, and both failures were in the
test, not the system. The character never left the Bakery between runs, so
navigation was never exercised; and the check counted memory *tool calls* when
the system delivers memory by automatic injection, so it reported False while
the agent was visibly using memory. An acceptance test can be strict, be
well-intentioned, and still measure the wrong thing — and a strict test that
measures the wrong thing is worse than a loose one, because its failures look
authoritative.

### The cost of retiring the parity check is still outstanding

Week 1's byte-for-byte Ruby/Python diff caught a real bug on nearly every step.
Retiring it was correct — week 2's features have no original to port from — but
the stated replacement was independent code review, **and that did not run
until the very end of the week**. 68 offline tests are real but not independent:
they were written by the same author, against the same understanding, at the
same time as the code. On this project's track record that is not a comfortable
place to submit from. The review commissioned at the end of the week is the
mitigation, not a formality.

### Answers to the week's open questions

- **Structured room graph or freeform text?** Neither, exactly: store observed
  *edges* and treat a route as a query over them. Composition across two
  separately-walked journeys worked on the first attempt, and no migration will
  be needed to add shortest-path later because the graph is already latent in
  the data.
- **What does "per task" mean for token accounting?** Per-turn is the useful
  unit and is what the reporter defaults to; cumulative-per-run is trivially
  available. Per-goal still needs the memory pillar's goal field to key on and
  was not built.
- **Is per-character memory keying sufficient insurance for multi-character?**
  Unknown. The keying is in place and cost nothing, but no run has driven two
  characters, so the insurance is untested.

## Key Takeaway

Week 2 set out to add three capabilities — observability, memory, and token
optimization — and all three landed and were verified against the live game:
turns now complete 100% of the time against week 1's 18%, caching serves 90% of
input tokens, and the bakery run proved the agent follows a route it recorded
rather than one it guessed.

But the thing worth carrying forward is what building the instrument *first*
revealed. Week 1's runs looked successful and were being cut off five times out
of six; cost estimation had never been called; reasoning logging had never
fired once across 2,395 events; truncation was being recorded as success. None
of it crashed, so none of it was visible. **The hardest bugs on this project
have not been the ones that fail loudly — they have been working, wired,
plausible code that quietly does nothing or reports the wrong number, and the
only reliable way to find them has been to measure real behavior rather than
read the code.** That is also why the biggest self-inflicted risk this week was
process rather than code: retiring week 1's parity check without immediately
replacing it with independent review meant running for a week on tests I wrote
against my own assumptions, which is precisely the blind spot that category of
bug lives in.
