# A Terminal UI (Python)

Python port of [`week1_baseline/ruby/11_tui`](../../ruby/11_tui) — see
[`docs/plans/python_port/11_tui`](../../../docs/plans/python_port/11_tui)
for the full plan and decisions.

**This is not a literal architectural mirror**, unlike every step 00-10.
Ruby's TUI is built on `charm`, a native-extension binding to Go's Bubble
Tea/Lip Gloss/Bubbles libraries — there's no Python equivalent to bind to.
This port replicates the same *behavior* using
[Textual](https://textual.textualize.io/) (6.5.0+, stable, pure Python),
not bubbletea's Elm-style `init`/`update`/`view` architecture.

## What's here

Same four-zone layout as Ruby's version: a scrollable conversation
viewport, a live progress line (spinner, iteration count, elapsed time,
token counts, tool-call count while a turn runs), an input box, and an
always-on status line (version, model, context tokens, tool count, clock).

| Key | Action |
|---|---|
| `Enter` | Submit input or slash command |
| `Esc` | Interrupt the running agent turn |
| `Ctrl+L` | Clear conversation history |
| `PgUp` / `PgDn` | Scroll conversation viewport |
| `Ctrl+C` / `Ctrl+D` | Quit (Textual's own default bindings) |

```python
boukensha.repl(tui=True)   # default -- launches the Textual TUI
boukensha.repl(tui=False)  # falls back to the plain terminal REPL
```

### The Esc-to-interrupt gap (read before relying on it)

Ruby interrupts a running turn via `Thread#raise(Interrupt)` — forcibly
injecting an exception into the background thread, which can unwind it
out of a blocking HTTP call. **Python has no safe equivalent.** This port
uses **cooperative cancellation** instead: `Agent` checks an
`interrupt_event` (a `threading.Event`) once per iteration, at the top of
its loop. Pressing Esc stops the turn at the *next iteration boundary* —
correct and verified live for the common multi-iteration/tool-calling
case, but it cannot stop a turn mid-single-API-call the way Ruby's
thread-level interrupt theoretically could. A real, acknowledged platform
gap, not silently glossed over — see the plan doc for the full reasoning
and the options considered.

### `Repl` refactored for composability

Matches Ruby's step-11 refactor: `on_output()`, `handle_command()`, and
`run_turn()` are now public so `Tui` (or any other front-end) can drive
`Repl` instead of it hard-coding `print`/`input()`. `logger`, `context`,
`model`, `version` are now public attributes.

`/quiet` and `/loud` are **gone** — Ruby deleted
`Boukensha.quiet!`/`.loud!`/`.quiet?` entirely at the module level this
step (confirmed via diff: a real deletion, not a regression to restore).
They'd been established as a permanent no-op since `08_the_repl_loop`
anyway (nothing ever read the flag).

## A bug found the hard way: don't name a Textual App attribute `_context`

`textual.app.App` already defines an internal `_context` attribute.
`Tui.__init__` originally did `self._context = repl.context` — silently
clobbering Textual's own internal state. The result wasn't an exception,
it was **`app.run_test()` hanging forever with zero diagnostic output** —
mounting never completed, `on_mount()` was never even reached. Found by
bisecting a minimal reproduction down to a single renamed attribute
(`hasattr(textual.app.App(), "_context")` confirms the collision).
Renamed to `self._boukensha_context` — Ruby's `Tui#initialize`'s
`@context` doesn't collide with anything in bubbletea, so this is a
Python/Textual-specific gotcha with no Ruby-side counterpart.

## A second bug found live: `call_from_thread` from the wrong thread

`Repl.on_output`'s callback needs to write into the conversation log
safely from **two different threads**: `handle_command()` (slash commands
like `/help`) runs synchronously on Textual's own app thread, while
`run_turn()` runs on the worker thread `_run_turn_worker` spawns.
Unconditionally wrapping every write in `self.call_from_thread(...)`
crashed on the very first `/help` — Textual raises `RuntimeError` if
`call_from_thread` is called *from* the app's own thread. Fixed by
checking `threading.get_ident() == self._thread_id` (the same check
`call_from_thread` makes internally) and writing directly when already on
the app's thread.

Both of the above were caught by an actual headless run (Textual's
`App.run_test()` pilot API), not by static review — worth noting since
this step has no scripted-stdin substitute for the *real* interactive
render (see "Running it" below).

## Running it

**Automated** (no terminal needed, verifies the plain REPL path):

```bash
cd week1_baseline/python/11_tui
uv sync
ANTHROPIC_API_KEY=your_key uv run python -c "
import boukensha
boukensha.repl(tui=False, working_dir=False, mud=False)
"
```

**Interactive** (the actual TUI — needs a real terminal):

```bash
cd week1_baseline/python/11_tui
ANTHROPIC_API_KEY=your_key uv run python -c "import boukensha; boukensha.repl()"
```

`examples/example.py` (and `bin/11_tui_python`) is carried over unchanged
from `10_standard_tool_library` — it's the MUD demo, and doesn't exercise
the TUI, matching Ruby's own README note that its `examples/example.rb`
is "carried over unchanged" for the same reason.

Verified this session: the plain `--no-tui` REPL path live (real API
call, matches Ruby's output). The actual Textual TUI verified headlessly
via `App.run_test()`'s pilot API — mount, all four slash commands, all
four keybindings, a full live turn with real tool calls and streaming
progress-line updates, and a live Esc-mid-turn interrupt all confirmed
working end-to-end against the real Anthropic API.
