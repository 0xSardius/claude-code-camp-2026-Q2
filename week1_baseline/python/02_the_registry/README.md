# The Tool Registry (Python)

Python port of [`week1_baseline/ruby/02_the_registry`](../../ruby/02_the_registry)
— see [`docs/plans/python_port/02_the_registry`](../../../docs/plans/python_port/02_the_registry)
for the port plan and decisions. Literal mirror of the Ruby architecture,
running alongside it against the same `.boukensha/` config directory.

The Tool Registry is how BOUKENSHA manages what capabilities the agent can use.

It has two jobs:
  1. storing tools
  2. dispatching tools when asked

## New Files

| File | Description |
|---|---|
| `boukensha/registry.py` | The Registry class — registers tools and dispatches calls |
| `boukensha/errors.py` | BOUKENSHA-specific error classes |

## How It Works

The agent NEVER calls a tool directly.
It emits a structured request (name and args) and the Registry looks up the tool and runs it.

```
Agent:  "Hey registry call move with direction='north'"
Registry: "looking up "move" in the tool table"
Registry: "Found it now calling the block with the provided args"
Registry: "Here's the result"
Agent: "Thanks buddy"
Registry: "Thats why you pay me the big tokes"
```

## boukensha.Registry

| Method | Description |
|---|---|
| `tool(name, *, description, parameters=None, block)` | Registers a new tool on the context |
| `dispatch(name, args=None)` | Looks up a tool by name and calls it with the provided args |

Ruby's `tool(name, description:, parameters: {}, &block)` takes its callable
implicitly via `&block` (a trailing block literal); Python has no equivalent
syntax, so `block` is an explicit keyword-only argument here — callers pass a
lambda/function directly.

## boukensha.UnknownToolError

Raised when `dispatch` is called with a name that has no registered tool.
A harness needs explicit error boundaries — an unrecognised tool name should never silently fail.

**Example:**
```
UnknownToolError: No tool registered as 'flee'
```

## Setup

```bash
cd week1_baseline/python/02_the_registry
uv sync
```

## Run Example

```sh
./week1_baseline/bin/02_the_registry_python
```

Actual output — verified byte-for-byte identical to
`./week1_baseline/bin/02_the_registry` (the Ruby version) when both point
at the same `.boukensha/settings.yaml`:

```
=== BOUKENSHA Step 2: Tool Registry ===

Config:  #<Boukensha::Config dir=/path/to/.boukensha tasks=player>
Context: #<Context task=player turns=0 tools=2>
Tools:
  #<Tool name=move description=Move the player in a direction (north, so params=[:direction]>
  #<Tool name=shout description=Shout a message so everyone in the zone c params=[:message]>

Dispatching 'shout' with message='dragon spotted'...
Result: DRAGON SPOTTED

Dispatching 'move' with direction='north'...
Result: You move north into a torch-lit corridor.

UnknownToolError caught: No tool registered as 'flee'
```

## Considerations

Ruby's `dispatch` converts string keys to symbol keys
(`args.transform_keys(&:to_sym)`) before calling the block, because the API
returns arguments as string-keyed JSON but Ruby blocks with keyword
parameters expect symbol keys — a real gotcha in production harnesses. The
Python port has no equivalent step: `**kwargs` unpacking is already
string-keyed, so `tool.block(**(args or {}))` just works. This isn't a gap —
there's nothing to translate — so no no-op step was added just to mirror
the Ruby line's shape. See the port plan's "New finding" section for the
full reasoning.

We now register tools with the Registry, but `Context.register_tool` is
still directly callable too — same open question as the Ruby version: does a
future implementation stop needing direct registration, and should it be
removed? Left open on purpose, not resolved here.
