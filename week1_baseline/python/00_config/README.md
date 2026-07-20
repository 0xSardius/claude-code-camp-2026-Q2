# 00 · Configuration (Python)

Python port of [`week1_baseline/ruby/00_config`](../../ruby/00_config) — see
[`docs/plans/python_port/00_config`](../../../docs/plans/python_port/00_config)
for the port plan and decisions behind this. This is a **literal mirror** of
the Ruby architecture, not a from-scratch redesign; Ruby and Python run
alongside each other against the same `.boukensha/` config directory.

We want to be able to manage all configuration from an external file eg.
`~/.boukensha/settings.yaml`. We want a dedicated class to handle
configuration, eg. `boukensha.Config`. Please consider that as we add
configuration in each iteration we will be updating the configuration
schema and class. We can hardcode defaults but we should not hardcode
configurable values.

Configuration is organised by **task** — a role in the agentic loop bound to its
own LLM. week1_baseline only drives a single `player` task (the main loop), but
a more advanced loop will assign different LLMs to different tasks. A task is
either a "single-task" or a "multi-task" — the latter being a full agent.

## Design Considerations

We want to use the standard library as much as possible, avoiding extra
dependencies. We need `python-dotenv` to load `.env` files and `pyyaml` to
parse `settings.yaml` (Ruby's stdlib `YAML` has no Python stdlib
equivalent, unlike everything else this step needs).

## Code Changes

| File | Purpose |
|------|---------|
| `boukensha/config.py` | `Config` class |
| `boukensha/tasks/base.py` | abstract `Base` (provider/model + prompt resolution) |
| `boukensha/tasks/player.py` | concrete `Player` (the main loop) |
| `boukensha/__init__.py` | top-level package exports |
| `prompts/system.md` | default system prompt shipped with the package |
| `examples/example.py` | runnable smoke-test |

---

## Config directory resolution

The class looks for a `.boukensha/` directory in this order:

1. **`BOUKENSHA_DIR` env var** — set this to point at any directory you like.
2. **`~/.boukensha`** — the default location for a real install.

Same resolution order as the Ruby version — both implementations read the
same `.boukensha/` directory, so pick one env var / default and it applies
to both.

## Config directory structure

The class expects the following:

```
.boukensha/
  .env                 # stores credentials eg. LLMs APIs (never committed to repo)
  settings.yaml        # all non-secret settings
  prompts/
    <task>/
      system.md        # per-task override for the default system prompt (optional)
```

---

## Tasks

`boukensha.tasks.Base` is an abstract stateless class. All behaviour is
expressed as classmethods that accept a `settings` dict — no instances are
created. Concrete subclasses set a `TASK_NAME` class attribute. For now only
`Player` exists; future steps add per-turn ceilings (`max_iterations`,
`max_turn_tokens`, `max_output_tokens`, `compaction_threshold`) — these are
**not** read yet.

`Config.tasks()` returns the raw dict from `settings.yaml` under `tasks:`. Pass a
name to look up a specific task's settings dict, then pass it to the stateless
class:

```python
from boukensha import Config
from boukensha.tasks import Player

config = Config()
Player.provider(config.tasks("player"))
Player.system_prompt(
    config.tasks("player"),
    user_prompts_dir=config.user_prompts_dir,
    default_prompts_dir=Config.PROMPTS_DIR,
)
```

## System prompt resolution

Per task, `Player.system_prompt` is resolved in this order:

1. **`.boukensha/prompts/<task>/system.md`** — used when the task's
   `prompt_override.system` is `true` and the file exists.
2. **`prompts/system.md`** — the default system prompt shipped with the package.

(We no longer use a top-level `system.override`; override is now per-task via
`prompt_override.system`.)

## Configuration Schema

The following properties so far:
- `tasks`: a map of task name → task config (provider, model, prompt_override).
- `tasks.<name>.prompt_override.system`: when `true`, the task's
  `.boukensha/prompts/<name>/system.md` overrides the default system prompt.
- `mud`: MUD connection information for the main player.

```yaml
tasks:
  player:
    provider: anthropic        # provider name (string)
    model: claude-haiku-4-5
    prompt_override:
      system: true
mud:
  host: localhost
  port: 4000
  username: dummy
  password: helloworld
```

## Setup

```bash
cd week1_baseline/python/00_config
uv sync
```

## Run Example

```bash
./week1_baseline/bin/00_config_python
```

Expected output (values from your `.boukensha/`) — verified byte-for-byte
identical to `./week1_baseline/bin/00_config` (the Ruby version) when both
point at the same `.boukensha/settings.yaml`:

```
=== Boukensha Step 0: Configuration ===

Config dir:     /home/andrew/Sites/Claude-Code-Camp/.boukensha
Tasks:          player

-- player task --
Provider:       anthropic
Model:          claude-haiku-4-5
Prompt override?true
System prompt:  You are a MUD player assistant. Use the tools available to y...

MUD host:       localhost:4000
MUD user:       dummy

API key set?    true

#<Boukensha::Config dir=/home/andrew/Sites/Claude-Code-Camp/.boukensha tasks=player>
```

The `#<Boukensha::Config ...>` repr line is deliberately kept in the Ruby
naming style rather than a Python-idiomatic one (e.g.
`Config(dir=..., tasks=[...])`) — literal-mirror fidelity, and it's what
makes the byte-for-byte output comparison between the two implementations
meaningful.

## Considerations

These are things we observed but we do not want fixed since this will break
with future steps. Carried over unchanged from the Ruby version — the
Python port deliberately mirrors both quirks rather than silently fixing
them:

- We have a default prompt eg. `prompts/system.md`, it's supposed to be
  scoped on task eg. `prompts/<task>/system.md`.
- Our settings file should accept `.yml` or `.yaml`; right now it only takes
  `.yaml` (and the `provider`/`model` error messages still say
  `settings.yml`, matching the Ruby source's own inconsistency here).
