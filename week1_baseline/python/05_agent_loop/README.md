# The Agent Loop (Python)

Python port of [`week1_baseline/ruby/05_agent_loop`](../../ruby/05_agent_loop)
— see [`docs/plans/python_port/05_agent_loop`](../../../docs/plans/python_port/05_agent_loop)
for the port plan and decisions. Literal mirror of the Ruby architecture,
running alongside it against the same `.boukensha/` config directory.

The Agent Loop is the heart of BOUKENSHA. Everything built before this —
the structs, the registry, the prompt builder, the client — was setup. The
loop is where the agent actually does work.

## New Files

| File | Description |
|---|---|
| `boukensha/agent.py` | The agent loop — sends requests, dispatches tools, and knows when to stop |

## How It Works

```
send messages to API
        ↓
stop_reason == "tool_use"?
    yes → extract tool calls
        → dispatch each tool via Registry
        → inject results as tool_result messages
        → go back to top
    no  → return final text response
```

## boukensha.Agent

| Method | Description |
|---|---|
| `run()` | Starts the loop and returns the final text response when the agent is done |

## Every Backend Speaks the Same Normalized Shape

Five providers means five different response formats — Anthropic nests
tool calls inside `content`, Ollama puts them in `message["tool_calls"]`,
OpenAI nests them under `choices[0]["message"]["tool_calls"]`, and Gemini
calls them `functionCall` parts. Rather than teach the Agent loop about
each of these, every backend implements `parse_response`, converting its
raw response into one common shape:

```python
{
    "stop_reason": "tool_use" | "end_turn",
    "content": [
        {"type": "text", "text": "..."},
        {"type": "tool_use", "id": "...", "name": "...", "input": {...}},
    ],
}
```

`Agent` only ever sees this shape — it calls `builder.parse_response(response)`,
which delegates to the backend, and never inspects a raw provider response.

The conversion also runs in reverse. When the conversation history is
replayed on the next request, Ollama, OllamaCloud, OpenAI, and Gemini each
rebuild a provider-specific assistant message from the normalized `content`
blocks via a private `_assistant_message` (or `_assistant_parts`) method —
the inverse of `parse_response`. Anthropic's `content` array doubles as
both the normalized shape and the wire format, so it needs no extra
conversion.

**Tool call IDs aren't universal.** Anthropic and OpenAI assign every tool
call a unique `id`, echoed back in the `tool_result`. Ollama, OllamaCloud,
and Gemini don't assign call ids at all — those backends reuse the tool's
`name` as its `id` and match the `tool_result` back to the call by name.

**One live translation trap worth knowing about**: `to_payload`'s `tools`
parameter must be checked with `tools is None`, never `tools or ...`. An
explicit `tools=[]` (used by `Agent`'s wrap-up call to disable tool
declarations) is falsy in Python but must still be honored as an override,
not treated as "missing."

## Task Configuration

This step uses the task-based configuration introduced in the earlier
baseline steps:

```yaml
tasks:
  player:
    provider: anthropic
    model: claude-sonnet-5
    prompt_override:
      system: true
    max_iterations: 25
    max_output_tokens: 1024
```

When `prompt_override.system` is true, Boukensha reads
`.boukensha/prompts/player/system.md`. Otherwise it falls back to this
step's shipped `prompts/system.md`. `max_iterations` controls model
round-trips per turn before wind-down, and `max_output_tokens` is passed
to each model reply.

## Considerations

**The assistant message must be stored before the tool result.** The
Anthropic API requires the assistant's tool_use block to appear in the
message history before its corresponding tool_result. BOUKENSHA handles
this in `_handle_tool_calls` — get the order wrong and the API rejects the
request.

**The model can call multiple tools in one turn.** The loop handles this
by iterating over all tool_use blocks in a single response before making
the next API call.

**`MAX_ITERATIONS` is a turn ceiling.** A poorly prompted agent can loop
forever if the model keeps calling tools. BOUKENSHA stops starting new
work after 25 iterations by default and makes one short wrap-up call with
tools disabled. This keeps the turn bounded while still returning a
useful final response.

**The agent has no way to stop itself.** The model signals it is done via
`stop_reason: "end_turn"`. BOUKENSHA watches for that signal and exits the
loop. The agent never decides unilaterally to stop.

## This step's acceptance test is not a byte-diff

`Agent.run()` makes multiple real, non-deterministic API calls — the
model's exact tool-call sequence and final wording differ between runs and
languages. Verified instead with one real live run per language (both
converged correctly, dispatched the right tools, and returned a coherent
final summary), plus direct code review of the deterministic parts
(`parse_response`/`_assistant_message` shape translation, the
`tools:`-override plumbing, `_call_opts`'s nil-vs-truthy handling).

## Setup

```bash
cd week1_baseline/python/05_agent_loop
uv sync
```

## Run Example

```sh
./week1_baseline/bin/05_agent_loop_python
```

Needs a real provider API key in the environment (e.g. `ANTHROPIC_API_KEY`)
— this step makes real, billed, multi-turn API calls. Verified live against
`./week1_baseline/bin/05_agent_loop` (the Ruby version): both converge in a
small number of iterations, correctly dispatch tools, and return a coherent
final response.
