# The REPL Loop (Python)

Python port of [`week1_baseline/ruby/08_the_repl_loop`](../../ruby/08_the_repl_loop)
— see [`docs/plans/python_port/08_the_repl_loop`](../../../docs/plans/python_port/08_the_repl_loop)
for the port plan and decisions. Literal mirror of the Ruby architecture,
running alongside it against the same `.boukensha/` config directory.

**This README documents the actual behavior, not the Ruby step's own
README** — that one has the usual off-by-one step number, and its
"Running it" section references a directory (`07_the_repl_loop`) and file
(`step7.rb`) that don't exist anywhere in this codebase. See the port plan
for the full list of discrepancies.

## What this step adds

| | `07_the_run_dsl` | `08_the_repl_loop` |
|---|---|---|
| Entry point | `boukensha.run(task="…")` | `boukensha.repl()` |
| Turns | one | many |
| History | discarded | accumulates across turns |
| User interaction | none | stdin prompt |

## New primitives

### `boukensha.Repl`

The interactive session loop. Built-in commands:

| Command | Effect |
|---|---|
| `/quiet` | Toggles a flag — currently a no-op (see below) |
| `/loud` | Toggles the same flag back |
| `/clear` | Wipe conversation history (tools stay registered) |
| `/help` | Print the command list |
| `/exit` / `/quit` | Leave the REPL |
| Ctrl-D | EOF — leave the REPL |
| Ctrl-C | Interrupt — leave the REPL gracefully |

**`/quiet`/`/loud` don't currently suppress anything.** Confirmed by
grepping the whole Ruby step: `Boukensha.quiet?` is defined but never read
anywhere. Typing `/quiet` prints a "logging suppressed" message, but no
code path actually checks the flag. Ported faithfully as a no-op —
decided with the user (2026-07-24) not to invent new suppression behavior
Ruby doesn't have, same treatment as other declared-but-unused primitives
in this codebase (`LoopError`, `Logger.subscribe`, `Logger.turn` before
this step wired it up).

### `boukensha.repl`

Same signature as `boukensha.run`, minus `task`. Register tools via a
`setup` callback; then the REPL loop takes over.

```python
import boukensha

def setup(dsl):
    dsl.tool("read_file", description="Read a file from disk",
        parameters={"path": {"type": "string"}}, block=lambda path: Path(path).read_text())

boukensha.repl(model="claude-haiku-4-5", setup=setup)
```

## Changes from step 7

### `Context.clear_messages()`
Wipes `messages` while keeping tools registered. Used by the REPL `/clear`
command. Ruby: `clear_messages!` — the bang has no Python identifier
equivalent, dropped like every other Ruby bang method in this port.

### `Agent.run()` — persists the final reply
Before this step, the agent returned the final text without adding it to
the context. That was fine for one-shot runs (context is thrown away
anyway), but a REPL needs the full transcript so subsequent turns see the
prior exchange. Now `context.add_message("assistant", text)` happens on
all three exit paths: `run()`'s success path, `_wrap_up()`'s success path,
and its `ApiError` fallback path.

### `Client` — a friendlier 401 message
`ApiError("authentication failed (401) — check your API key")` instead of
the generic retry-exhausted message, specifically for 401 responses.

### `Config._resolve_dir()` — a third fallback tier
Now checks, in order: (1) an explicit `BOUKENSHA_DIR` env var, (2) a
`.boukensha/` directory in the current working directory, (3) the
`~/.boukensha` default.

### `Logger.turn()`
Existed since `07_the_run_dsl` as a declared-but-unused method; now
actually called once per REPL turn, logging a `"turn"` phase to the
session JSONL file. (The Ruby step's own README claims this prints a
`╔══ turn N ══╗` banner to the terminal — it doesn't; confirmed
`logger.rb` is byte-identical to `07`'s, which only writes to disk.)

## A note on `Repl` construction

A **new `Agent` is built every turn** inside `Repl._run_turn`, even though
`Context`/`Registry`/`Builder`/`Client`/`Logger` are all shared across the
whole session. This is deliberate, not an inefficiency to "fix": it resets
the per-turn tool-calling iteration budget while conversation history
persists via the shared `Context` — a completely different object with a
completely different lifetime.

## Running it

```bash
cd week1_baseline/python/08_the_repl_loop
uv sync
ANTHROPIC_API_KEY=your_key uv run python examples/example.py
```

```
╔══════════════════════════════════════╗
║  BOUKENSHA MUD Assistant (v0.8.0)    ║
╚══════════════════════════════════════╝
  config:    /path/to/.boukensha
  provider:  anthropic (claude-sonnet-5)  ✓ API key set

  /quiet or /loud   toggle logging
  /clear           reset conversation history
  /exit or /quit    leave the REPL

boukensha> list the files in the current directory
...
boukensha> /exit
Goodbye.
```

Needs a real provider API key in the environment — this step makes real,
billed, multi-turn API calls. Verified live against
`./week1_baseline/bin/08_the_repl_loop` (the Ruby version) using scripted
stdin (a real task, then `/exit`) rather than an interactive session,
since this step's own point — the interactive loop — can't be exercised
by "run it, capture stdout" the way prior steps' verification worked. Both
produce a valid JSONL session log with the correct phase sequence,
including a `"turn"` line.
