# The Logger (Python)

Python port of [`week1_baseline/ruby/06_the_logger`](../../ruby/06_the_logger)
— see [`docs/plans/python_port/06_the_logger`](../../../docs/plans/python_port/06_the_logger)
for the port plan and decisions. Literal mirror of the Ruby architecture,
running alongside it against the same `.boukensha/` config directory.

`boukensha.Logger` records each agent run as structured JSON Lines.
It is a file logger, not user-facing display output.

## Session Logs

Each `Logger` instance creates a session id and writes one log file for
that session:

```text
.boukensha/sessions/<session-id>.jsonl
```

Every line is a complete JSON object with `session_id`, `at`, and `phase`
fields, plus phase-specific data. This keeps logs grep/tail friendly and
machine readable.

```json
{"phase":"session_start","session_id":"20260723T190755Z-a735bb75","at":"2026-07-23T15:07:55-04:00"}
{"phase":"iteration","n":1,"max":25,"session_id":"20260723T190755Z-a735bb75","at":"2026-07-23T15:07:55-04:00"}
```

Model response lines include the active task, provider, model, normalized
token counts, and estimated USD cost when the backend has token pricing
data:

```json
{"phase":"response","task":"player","provider":"anthropic","model":"claude-sonnet-5","input_tokens":620,"output_tokens":49,"cost_usd":0.002595}
```

## Logger API

A plain object with one method per phase — the real signatures, not the
Ruby README's abbreviated table (missing `max:`/`stop_reason:`/`budget:`
in places, and omitting `limit_reached`/`turn_end` entirely — this port
mirrors the actual class):

| Method | Phase | Logs |
|---|---|---|
| `iteration(*, n, max)` | `iteration` | loop counter and ceiling |
| `limit_reached(*, kind, n, max)` | `limit_reached` | which limit fired |
| `turn_end(*, reason, iterations, tokens=None)` | `turn_end` | why the turn ended |
| `prompt(*, messages, tools)` | `prompt` | messages, tools |
| `tool_call(*, name, args)` | `tool_call` | tool name and arguments |
| `tool_result(*, name, result, ok=True, error=None)` | `tool_result` | tool result, success/failure |
| `response(*, text, usage=None, stop_reason=None, task=None, backend=None)` | `response` | response text, token usage, task/provider/model, estimated cost |
| `raw(*, data)` | `raw` | raw provider response when debug is enabled |

## Task Configuration

Step 6 uses the task-based settings shape:

```yaml
tasks:
  player:
    provider: anthropic
    model: claude-sonnet-5
    prompt_override:
      system: true
```

When `prompt_override.system` is true, the player task reads
`.boukensha/prompts/player/system.md`. Otherwise it falls back to this
step's shipped `prompts/system.md`.

Default usage:

```python
from boukensha import Agent, Logger

logger = Logger()
agent = Agent(context=ctx, registry=registry, builder=builder, client=client, logger=logger)
```

You can also provide a session id or override the destination directory:

```python
Logger(session_id="manual-session")
Logger(dir="/tmp/boukensha-sessions")
```

For compatibility, `log=` still accepts an explicit file path, but normal
iteration usage should write under `.boukensha/sessions`.

## Debug Events

Call `boukensha.enable_debug()` before running the agent to include raw
provider responses:

```python
import boukensha
boukensha.enable_debug()
```

Ruby's `Boukensha.debug!`/`Boukensha.debug?`/`Boukensha.quiet!`/
`Boukensha.loud!`/`Boukensha.quiet?`/`Boukensha.config` become
`enable_debug()`/`is_debug()`/`enable_quiet()`/`disable_quiet()`/
`is_quiet()`/`config()` — Ruby's bang/question-mark method names have no
valid Python identifier form, dropped the same way every other Ruby bang
method has been in this port (`validate_model!` → `validate_model`, etc.).
`quiet`/`loud` are declared for parity but not currently called by
anything in this step, matching the Ruby source.

## A note on two Python-specific gotchas this step hit

**Ruby evaluates a keyword default *expression* fresh on every call;
Python evaluates a default *value* once, at function-definition time.**
`Agent`'s Ruby constructor defaults to `logger: Logger.new` — every call
without an explicit logger gets its own fresh instance. A naive Python
`def __init__(self, ..., logger=Logger(), ...)` would construct exactly
one `Logger` at import time and silently share it across every `Agent`
that doesn't pass its own. Fixed with `logger=None`, then
`self._logger = logger if logger is not None else Logger()` inside
`__init__`. Verified directly: two `Agent`s built without `logger=` get
distinct instances with distinct session ids.

**`backend.class.name.split("::").last.gsub(...)` (the provider-name
label in log lines) has a real quirk**: it turns `OpenAI` into
`open_ai`, not `openai` — a genuine artifact of the CamelCase→snake_case
regex catching the `nA` boundary in "Ope**nA**I". Ported with the
identical regex, not "corrected", since nothing frames it as a bug.

## Setup

```bash
cd week1_baseline/python/06_the_logger
uv sync
```

## Run Example

```sh
./week1_baseline/bin/06_the_logger_python
```

Needs a real provider API key in the environment (e.g. `ANTHROPIC_API_KEY`)
— this step makes real, billed, multi-turn API calls. Verified live
against `./week1_baseline/bin/06_the_logger` (the Ruby version): both
produce a valid JSONL session log with the documented phase sequence and
response metadata.
