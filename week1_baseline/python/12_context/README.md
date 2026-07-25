# Context Management (Python)

Python port of [`week1_baseline/ruby/12_context`](../../ruby/12_context) —
see [`docs/plans/python_port/12_context`](../../../docs/plans/python_port/12_context)
for the full plan and decisions.

When you call an LLM directly you are responsible for the context window.
There is no auto-compacting. This step adds proper token tracking, visual
warnings, and automatic compaction so the agent never silently blows past
the limit.

## What's new

### `Tasks::Base`/`Tasks::Player` removed

Ruby deletes the task-class layer entirely this step; `Config` absorbs its
responsibilities directly (`system_prompt`, `model`, `provider_type`,
`agent_max_*`). Mirrored: `boukensha/tasks/` no longer exists, and
`run()`/`repl()` resolve settings straight from `Config` instead of
through a task class + `task_settings` dict.

### Accurate context tracking

`Context` now maintains two distinct token counts:

| Attribute | What it measures |
|-----------|-----------------|
| `context_window` | The model's maximum input token capacity, resolved via `models.context_window(model)` |
| `current_tokens` | Tokens actually used in the most recent API call (`usage.input_tokens`, or the provider-specific equivalent) |

`Agent._record_usage` restores a multi-provider usage-field fallback
(Gemini's `usageMetadata`, Ollama's `prompt_eval_count`/`eval_count`) that
Ruby's initial `12_context` source dropped along with the cost-estimation
code it used to live inside of — a real bug (fixed in Ruby too, by
explicit decision): without it, `current_tokens` silently stayed 0 for
every non-Anthropic backend, so `needs_compaction()` never tripped no
matter how full the real window got.

`models.py`'s `TABLE` had the same class of bug independently: it both
disagreed with the backends' own `MODELS` tables (`claude-opus-4-8`/
`claude-sonnet-4-6` listed at 200k here vs. the real 1M in
`backends/anthropic.py`) and omitted every non-Anthropic model entirely,
so any OpenAI/Gemini/Ollama model silently fell back to
`DEFAULT_CONTEXT_WINDOW` (32,000) — compaction would have fired 5x-30x too
early. Fixed by making `models.py`'s table a complete, accurate mirror of
every backend's own `MODELS`.

### Context colour coding (TUI)

The progress and status lines colour the context indicator based on how
full the window is:

| Usage | Colour | Meaning |
|-------|--------|---------|
| < 70% | Grey (`bright_black`) | Normal |
| 70–84% | Yellow | Approaching limit |
| ≥ 85% | Red | Compaction imminent |

A `⚠` symbol also appears in the status bar at 85%+. The idle progress
line and status bar no longer show a session-lifetime running token total
(`session_input_tokens`/`session_output_tokens` are gone) — both now read
live `context.current_tokens`/`context.context_window`/`context.usage_pct`
directly, matching Ruby's switch away from its own `@session_input_tokens`/
`@session_output_tokens`.

### Auto-compaction

At the start of each agent turn, if `current_tokens / context_window ≥
0.85` (configurable via `agent.compaction_threshold` in
`settings.yaml`), the Agent automatically compacts the context before
making any API call:

```
[context compacted — 12 messages dropped to free space]
```

Compaction drops the oldest 40% of messages (keeping at least 2) and
resets `current_tokens` to 0. The first API call after compaction reports
the true new size. The TUI subscribes to the `Logger`'s `"compaction"`
event and appends the notice to the conversation view.

### `Context.compact_messages()`

```python
dropped = context.compact_messages()
# => 12  (number of messages dropped)
```

### `/compact` command

Manual compaction from the REPL or TUI:

```
boukensha> /compact
(compacted context — 12 messages dropped)
```

### `max_turn_tokens` — a second, independent ceiling

`Agent` now accepts `max_turn_tokens` (default from `settings.yaml`'s
`agent.max_turn_tokens`, 60,000) alongside `max_iterations` — two
independent trigger thresholds; the turn wraps up at whichever trips
first, via one final tools-disabled model call rather than aborting mid-turn.

### `list_directory`/`search_files` disabled

Matches Ruby exactly: both tools are commented out in
`tools/file_system.py` (leftover from when this app was a coding harness;
the player agent has no use for them yet), not deleted — easy to
re-enable if a future task needs them.

### `Logger#compaction` event

```json
{"phase": "compaction", "before": 172000, "dropped": 12, "context_window": 1000000}
```

`Logger` also loses per-response cost/provider tracking entirely this
step (`response()` drops `task=`/`backend=`, `_estimate_cost`/
`_task_name`/`_provider_name` are gone) — a real, deliberate regression
mirrored faithfully from Ruby, not a half-finished refactor. `Backends`
still fully define `estimate_cost`/`usage_unit`/`usage_level`, just
disconnected from this call site.

### `OpenAI` backend rewritten for the Responses API

gpt-5.x rejects `reasoning_effort` + tools on `/v1/chat/completions`
("Please use /v1/responses"), so `backends/openai.py` now targets the
Responses API instead of chat completions — messages become `input`
items, the system prompt becomes a top-level `instructions` string, tool
defs are flat (no `function:` wrapper), and tool results round-trip via
`function_call_output` items matched by `call_id`.

### Reasoning/"thinking" content-block normalization

Anthropic (thinking/redacted_thinking + signature), Gemini
(thought/thoughtSignature), and Ollama/OllamaCloud (thinking field) all
normalize into a common `{"type": "reasoning", "text": ..., "signature":
...}` content block (see `backends/base.py`'s module docstring for the
full contract). `Agent._log_reasoning` emits one `reasoning` log event per
block.

### `boukensha.run()` / `boukensha.repl()` — `context_window=` keyword

```python
boukensha.repl(context_window=128_000)  # for a smaller model
```

## Running it

**Automated** (no terminal needed, verifies the plain REPL path):

```bash
cd week1_baseline/python/12_context
uv sync
ANTHROPIC_API_KEY=your_key uv run python -c "
import boukensha
boukensha.repl(tui=False, working_dir=False, mud=False)
"
```

**Interactive** (the actual TUI — needs a real terminal):

```bash
cd week1_baseline/python/12_context
ANTHROPIC_API_KEY=your_key uv run python -c "import boukensha; boukensha.repl()"
```

`examples/example.py` (and `bin/12_context_python`) is the MUD demo,
carried forward from `10_standard_tool_library`/`11_tui` — it doesn't
exercise context-window pressure directly, matching Ruby's own
`examples/example.rb`.

Verified this session: a live round trip per language (real Anthropic API
call + real MUD connection, via the project's dedicated `boukensha` test
character rather than `dummy`, to avoid risking real character progress) —
both succeeded with matching response shape (non-empty string) and a
matching resolved `context_window` (1,000,000 for `claude-sonnet-5`).
Deterministic sub-parts (context tracking math, compaction, usage-field
parsing, the `models.py` table, `required_params()`) verified by direct
code reading against the Ruby source, same rigor as the rest of this
project's non-deterministic-step acceptance bar (established at
`04_api_client`). The actual Textual TUI (colour coding, compaction
notice rendering) was **not** re-verified headlessly this step (11_tui's
pilot-test coverage already exercises the same rendering machinery; the
new pieces here are data values fed into `Static.update()`, not new
widget/event wiring) — worth a headless pilot pass if the TUI's visual
output is ever in question.
