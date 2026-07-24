# The Boukensha.run DSL (Python)

Python port of [`week1_baseline/ruby/07_the_run_dsl`](../../ruby/07_the_run_dsl)
— see [`docs/plans/python_port/07_the_run_dsl`](../../../docs/plans/python_port/07_the_run_dsl)
for the port plan and decisions. Literal mirror of the Ruby architecture,
running alongside it against the same `.boukensha/` config directory.

**This README documents the actual `run()` behavior, not the Ruby step's
own README** — that one is significantly out of date for this step (wrong
step number, two documented parameters that don't exist, wrong hardcoded
defaults, two backends listed instead of five, and a stdout-logging claim
nothing in the code does). See the port plan for the full list.

## What this step adds

A single top-level entry point: `boukensha.run`.

Every previous step required you to manually create and wire together a
`Context`, `Registry`, `Backend`, `PromptBuilder`, `Client`, `Logger`, and
`Agent`. This step hides all of that behind one function call.

## The new primitive

### `boukensha.RunDSL`

A tiny host object passed to your `setup` callback, exposing only `tool`.
This keeps the DSL surface intentionally small and prevents callers from
reaching internal state.

Ruby's version works via `instance_eval`, rebinding the block's `self` to
the DSL object so `tool(...)` reads as a bare call. Python has no
`instance_eval`/blocks equivalent, so the callback receives the `RunDSL`
object explicitly instead:

```python
def setup(dsl):
    dsl.tool("read_file", description="Read a file",
              parameters={"path": {"type": "string"}}, block=read_file)
```

### `boukensha.run`

Accepts keyword arguments that describe *what* to do. All plumbing is
handled internally.

| Option | Default | Description |
|---|---|---|
| `task` | *(required)* | The user message handed to the agent |
| `system` | task's configured/shipped system prompt | System prompt override |
| `model` | task's configured model (`settings.yaml`) | Model name override |
| `backend` | task's configured provider (`settings.yaml`) | `"anthropic"`, `"openai"`, `"gemini"`, `"ollama"`, or `"ollama_cloud"` |
| `api_key` | the matching `*_API_KEY` env var | API key for the chosen backend (not needed for `ollama`) |
| `ollama_host` | `"http://localhost:11434"` | Ollama base URL |
| `log` | `None` | Optional path override; by default logs go to `.boukensha/sessions/<session-id>.jsonl` |
| `max_output_tokens` | task's configured value (default `1024`) | Max tokens per API response |
| `setup` | `None` | A callback receiving a `RunDSL` to register tools on |

`model`/`backend`/`system`/`max_output_tokens` all default from
`settings.yaml` via the `player` task, not hardcoded literals — matching
every prior step's config-driven behavior, unlike what the Ruby step's own
README currently documents.

## Before and after

**Step 5 — manual plumbing:**

```python
ctx = Context(task=Player, system="You are a MUD player assistant.")
registry = Registry(ctx)
backend = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"], model="claude-haiku-4-5")
builder = PromptBuilder(ctx, backend)
client = Client(builder)
logger = Logger()
agent = Agent(context=ctx, registry=registry, builder=builder, client=client, logger=logger)

registry.tool("read_file", description="Read a file",
    parameters={"path": {"type": "string"}}, block=lambda path: Path(path).read_text())

ctx.add_message("user", "Read lib/boukensha.rb")
agent.run()
```

**Step 7 — just describe what you want:**

```python
import boukensha

def setup(dsl):
    dsl.tool("read_file", description="Read a file",
        parameters={"path": {"type": "string"}}, block=lambda path: Path(path).read_text())

result = boukensha.run(task="Read lib/boukensha.rb", setup=setup)
```

## `Logger` gains `turn`/`subscribe`

Both new this step, both currently unused by anything in the actual
example (declared for completeness, same as `LoopError`/`quiet!`/`loud!`
in earlier steps): `logger.turn(n=...)` logs a `"turn"` phase line;
`logger.subscribe(callback)` registers a callback invoked with each log
event as it's written — **before** `session_id`/`at` are merged in for the
JSONL line, matching Ruby exactly.

## Setup

```bash
cd week1_baseline/python/07_the_run_dsl
uv sync
```

## Run Example

```sh
./week1_baseline/bin/07_the_run_dsl_python
```

Needs a real provider API key in the environment (e.g. `ANTHROPIC_API_KEY`)
— this step makes real, billed, multi-turn API calls. Verified live
against `./week1_baseline/bin/07_the_run_dsl` (the Ruby version): both
converge correctly, dispatch tools, and produce a valid JSONL session log
with the documented phase sequence and `session_start` snapshot metadata.
