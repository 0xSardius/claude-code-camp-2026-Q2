# Week 2 — Lifecycle hooks (foundation)

Build the hook surface described in the week 2 course material. Everything else
this week attaches to it. Land this before observability, memory, or token
optimization.

## Where the seams are in the current code

All line references are to `week1_baseline/python/12_context/boukensha/agent.py`
as seeded into `week2_capable/python/boukensha/agent.py`.

| Hook | Insertion point |
|---|---|
| `before_turn` | `run()`, after `reset_turn_tokens()` / `_compact_if_needed()`, before the `while True:` |
| `before_model` | Inside the loop, immediately before `response = self._client.call(...)` |
| `before_tools` | In `_handle_tool_calls`, after `tool_calls` is extracted, before the dispatch loop |
| `after_tool` | In `_handle_tool_calls`, in the `try/except/else` around `registry.dispatch`, wrapping `result` |
| `after_turn` | Every return path out of a turn: the `end_turn` return in `run()`, and **both** returns in `_wrap_up` (success and the `ApiError` fallback) |

**`after_turn` has three return paths, not one.** `_wrap_up` returns from two
places and `run()` from a third. A hook that only fires on the happy path will
silently under-report every turn that hit `max_iterations` or `max_tokens` —
which, from the week 1 session logs, is 26 of 26 turns in the longest grind
session. Wire all three, or restructure `run()` so there is exactly one exit.

## Design

### Hook signature and payload

Hooks receive a single mutable payload object rather than positional args, so
new fields can be added without breaking existing handlers. Each hook gets:

- `context`, `registry`, `logger` — so a handler can inject a tool call
  (`before_model`'s `look`), append a message, or emit a log event.
- Hook-specific fields: `after_tool` gets `name`, `args`, `result`, `ok`,
  `error`; `before_tools` gets the pending `tool_calls` list.

### Handlers may modify, and that is the point

`after_tool`'s documented job is to **replace raw movement output with a
compact result** — so the hook's return value (or its mutation of
`payload.result`) must be what actually lands in
`context.add_message("tool_result", ...)`. This is the single most important
contract in the hook system; a fire-and-forget observer-only design would not
support the course's own stated use.

Decide and document explicitly: does a handler mutate `payload.result` in
place, or return a replacement? **Recommendation: mutate the payload.** With
multiple handlers registered on one hook, a return-value convention forces a
"did this handler mean to replace it with `None`, or just not return?"
ambiguity — exactly the falsy-vs-`None` trap this project has hit repeatedly
(see the `||` vs `or` gotcha in the root `CLAUDE.md`).

### Failure policy

A handler that raises must not kill the turn. Catch per-handler, log the
failure as a first-class event, and continue — with one carve-out: a handler
that raises during `after_tool` **must not** cause the real tool result to be
discarded. That is the same shape as the existing `try/except/else` around
`registry.dispatch`, whose comment already warns that a logging failure after a
successful dispatch must not be misreported to the model as a tool failure.

### Registration and lifetime

`Repl.run_turn` constructs a **fresh `Agent` per turn** (`repl.py:141`). Any
hook state that must persist across turns — memory handles, cumulative spend,
consecutive-dead-turn counters — therefore cannot live on the `Agent`. Hooks
are registered once on a longer-lived object (the `Repl`, or a `Hooks`
registry passed into both) and handed to each `Agent` at construction, the same
way `logger` already is.

Watch the keyword-argument shape: Ruby's required/optional split doesn't port
for free (documented gotcha), and Python's once-at-def-time default evaluation
already bit this project on `logger=Logger()` in `06_the_logger`. A `hooks=None`
parameter with lazy construction inside `__init__` is the pattern that already
works here.

## Milestones

**M1 — Hook registry and the five seams, no handlers.**
A `Hooks` class with `on(name, handler)` and `fire(name, payload)`, wired into
`Agent` at all five seams including all three `after_turn` exits. Threaded
through `Repl` and `Boukensha.run`/`.repl` as a new keyword argument, defaulting
to an empty registry so every existing caller behaves identically.
*Verify*: run an existing example end-to-end with no handlers registered and
confirm byte-identical behavior to the pre-hook build. Then register a trivial
counting handler on each of the five and assert the fire counts match the
`turn` / `iteration` / `tool_call` counts in the session JSONL.

**M2 — `after_tool` result replacement.**
Prove the mutation contract: register a handler that rewrites one tool's result
and confirm the rewritten text — not the original — is what lands in
`context.messages` and in the `tool_result` log event.
*Verify*: assert on `context.messages` directly, not on the model's behavior.

**M3 — MUD state handlers (`before_turn`, `before_model`).**
`before_turn` runs `check("score")` to initialize player state.

`before_model` **tracks rather than polls** (settled 2026-07-27). Its job is to
ensure the model knows where it is — which is usually free. Maintain a
current-room belief in the harness, updated at `after_tool` from `move` and
`look` results, and have `before_model` inject that belief as context with no
MUD round trip. Issue a real `look` only when the belief is stale or absent:

- **First iteration of a turn** — anything could have happened between turns.
- **After a `flee`** — flees go in a *random* direction, so position is
  genuinely unknown. This is the case that most needs it.
- **After a reconnect** — the session drops constantly.
- **After death or respawn.**
- **When parsing failed** — output that didn't resolve to a known room.

Rejected: "look when a movement occurred." A `move` already returns the new
room description in its own output, so a following `look` is redundant.
Also rejected: unconditional per-iteration `look` — 119 extra round trips in
the longest week 1 session, to a connection that drops every 10s–few min.

The triggers above give ~30 looks per session instead of 119, each justified.
The first-visit survey keys off the memory store, so survey frequency **decays
toward zero as the map fills in** — `before_model` gets cheaper the longer the
agent plays, which is the right direction for a multi-hour grind.

**M4 — `before_tools` poll.**
Poll before a model-selected tool batch runs. Scope what "poll" means here
against `mud_session.py`'s reader — this is adjacent to the `"> "` sentinel
collision fixed 2026-07-26, so any new read-before-dispatch path needs the same
quiet-window discipline rather than a fresh naive read.

## Risks

- **Injected tool calls change the message list.** Every hook that runs a tool
  and appends its result grows the context the model sees. That interacts
  directly with both other pillars: it accelerates compaction (memory pillar)
  and it must be *appended*, never spliced into the middle, or it invalidates
  the cached prefix (token pillar). Append-only is a hard constraint on hook
  handlers, not a style preference.
- **Hooks that call tools can fail on a dropped connection.** The MUD drops
  unpredictably. A `before_model` `look` that raises on a dead socket must not
  abort the turn — the failure policy above covers it, but it needs a live test
  against an actually-dropped connection, not just a unit test.
