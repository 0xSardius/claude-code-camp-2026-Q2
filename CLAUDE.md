# Claude Code Camp — Project Notes

Official repo for the [ExamPro](https://www.exampro.co) Claude Code Camp.
The throughline across every week: **teach an AI agent to play a tbaMUD
(CircleMUD-derived) text MUD**, exploring a different agent architecture
each time, and writing down what's learned. This file orients a fresh
session fast; the real detail lives in `docs/journal/` (weekly retros) and
`docs/plans/` (in-progress plans) — read those when working on the thing
they cover, don't assume this file has the full story.

## Repo map

```
week0_explore/     -- "explore" phase: compare agent architectures head-to-head
  HOW_TO_PLAY.md      -- MUD basics, map, starting commands
  CHALLENGES.md        -- primary challenge: beat the Minotaur in the Newbie Zone
  infrastructure/       -- docker-compose for the tbaMUD server (localhost:4000)
  mud_manager/            -- Ruby gem: reference telnet-session implementation
  circlemud-world-parser/  -- Python/uv tool, parses the MUD's world files
  explore_architecture/
    01_plain_agent/          -- bare CLAUDE.md, no tooling
    02_agent_skills/          -- Claude Code Skill (play-mud) + persistent memory
    03_subagent_sdk/           -- Claude Agent SDK, concurrent character agents
    04_n8n/                     -- not started yet (empty)
week1_baseline/     -- "baseline" phase: hand-rolled agent loop, NO SDK
  ruby/00_config, ruby/01_struct_skeleton, ...   -- source of truth, one dir per step
  python/00_config, python/01_struct_skeleton, ...  -- literal port, runs alongside Ruby
  bin/00_config, bin/00_config_python, ...         -- launchers, one Ruby + one Python per step
week2_capable/       -- not started yet (empty)
docs/
  journal/            -- weekly retros: Goal/Uncertainty/Hypothesis/Observations/Conclusions
  plans/python_port/    -- one plan file per week1_baseline step being ported
  explore_architectures.md  -- freeform week0 observations
.boukensha/            -- shared runtime config for week1_baseline (gitignored except .keep)
```

## The MUD

- `docker compose up` in `week0_explore/infrastructure` to run it; `localhost:4000`.
- Two characters exist: `dummy`/`helloworld` (Thief, the main one, currently
  level 3, deep into grinding toward level 7 + the Minotaur) and
  `balthasar`/`magicman` (Magic-user, used for the `03_subagent_sdk`
  concurrency exploration). Both live in `week0_explore/explore_architecture/02_agent_skills/.claude/skills/play-mud/data/`
  and `03_subagent_sdk/data/` as persistent player.md/world.md memory —
  **read those before doing anything with either character**, they contain
  the map, known mob difficulties, and hard-won lessons (which "newbie"
  flavor text is safe to fight, where the guard/dragon/alchemist are, etc.).
- The MUD connection drops unpredictably (10s–few min). Both the
  `play-mud` skill (`scripts/mud.py`) and the Ruby `mud_manager` gem handle
  this with auto-reconnect; don't be surprised by it, don't treat one drop
  as a real failure.

## week1_baseline: the Ruby ↔ Python port

This is the part most likely to need continuing. Ground rules, all decided
and in force — see `docs/plans/python_port/00_config` for the original
reasoning:

- **Ruby is the source of truth.** Python is a literal architectural mirror
  (same classes, same method names, same `__repr__`/`to_s` output down to
  the byte), not an idiomatic rewrite. **Ruby and Python run alongside each
  other** — porting a step never touches the Ruby original.
- **Each numbered step is independently ported from its own Ruby sibling**,
  not from the previous Python step. The Ruby side itself duplicates code
  per step rather than sharing a lib — confirmed by diffing steps against
  each other (e.g. `01_struct_skeleton`'s `config.rb` is missing a constant
  `00_config`'s has, because that step doesn't need it). Don't assume a
  new Python step's file is identical to the previous step's just because
  it looks similar — re-read the actual Ruby source every time.
- **The acceptance test for a ported step is a byte-for-byte diff** between
  `bin/<step>` (Ruby) and `bin/<step>_python` (Python) against the same
  `.boukensha/settings.yaml`. Not "it runs" — the printed output must match
  exactly. This has caught real bugs every time it's been run (see Gotchas).
- **Tooling**: Ruby uses Bundler with `bundle config set --local path
  'vendor/bundle'` (avoids needing `sudo`); Python uses `uv` + `pyproject.toml`
  (matches `circlemud-world-parser`'s existing precedent). Python package
  name is `boukensha`, matching the Ruby module name.
- **Process for a new step**: write a plan to `docs/plans/python_port/<step>`
  first (reference the actual Ruby files, note any divergence from prior
  steps, ask before assuming), get it confirmed, then implement following
  its own milestones. Follow up with a code review (the `code-review`
  skill) before considering a step done — it has found real, non-obvious
  bugs (see Gotchas) that the parity test alone didn't catch.

### Gotchas hit so far (don't re-discover these)

- **`BOUKENSHA_DIR` path math**: `examples/example.rb`/`.py` need exactly
  **4** `../`/`.parent` hops from the `examples/` dir to reach the repo
  root (`ruby/<step>/examples/` → `ruby/<step>/` → `ruby/` →
  `week1_baseline/` → repo root). Every step so far shipped with this off
  by one at first (3 instead of 4) — check it explicitly on new steps.
- **Ruby `||` vs Python `or`**: Ruby's `||` only falls back on `nil`/`false`;
  Python's `or` falls back on *any* falsy value (`0`, `""`, `[]`, `{}`).
  A direct `x || default` → `x or default` translation is wrong whenever
  `x` could legitimately be a falsy-but-valid value (an explicit
  `mud.port: 0`, an empty `BOUKENSHA_DIR=""`). Use `x if x is not None
  else default` instead — found and fixed in `01_struct_skeleton`'s
  `config.py`, worth grepping for elsewhere.
- **Ruby's inclusive range vs Python slicing**: `x[0..N]` in Ruby is `N+1`
  characters; Python's `x[:N]` is `N`. Off-by-one every time this pattern
  gets ported unless deliberately caught.
- **`nil.to_s` vs `str(None)`**: Ruby's `"#{nil}"` interpolates as an empty
  string; Python's `str(None)`/f-string interpolation prints the literal
  text `"None"`. Any ported `__repr__`/`to_s` touching a possibly-`None`
  field needs an explicit `"" if x is None else str(x)` guard.
- **Ruby symbol-keyed hash inspect**: `{direction: ...}.keys` prints as
  `[:direction]`; Python's naturally string-keyed dict prints as
  `['direction']`. Hand-format to match if byte-parity matters for that
  line (done in `Tool.__repr__`). A shared helper for this + the slice/nil
  patterns above was flagged as worth extracting once it recurs a third
  time — hasn't been done yet, consider it if a step 2 hits the same wall.
- **Required-vs-optional keyword args don't port for free.** Ruby
  `def initialize(task:, system: nil)` makes `task` required with no
  default; a naive Python `def __init__(self, task=None, system=None)`
  silently makes both optional. Mirror Ruby's required/optional split
  exactly (`def __init__(self, *, task, system=None)`), don't default
  everything just because it's convenient.
- **Editor stale-buffer conflicts**: if a file is open in the user's IDE
  while I edit it via a tool call, the editor can silently overwrite my
  change with its stale buffer on next save. If asked to re-verify a
  change that mysteriously reverted, check the actual file content on disk
  before assuming anything — don't just trust that a prior edit "stuck."
- **`uv sync` needs a real `README.md` and non-empty package dir before it
  will build** — scaffold those (even as placeholders) before the first
  `uv sync`, not after.

## week0_explore: architecture comparison findings

Full detail in `docs/journal/0_preweek.md` and `docs/explore_architectures.md`.
Headlines: Sonnet 5 handled the MUD loop far better than Haiku (Haiku
wandered off-task exploring the codebase instead of playing); a Claude Code
Skill + persistent markdown memory (`02_agent_skills`) was enough for
autonomous, compounding progress; giving the character a personality
(role-playing "Dummy the thief") measurably improved tactical play, not
just flavor; the Claude Agent SDK (`03_subagent_sdk`) proved out running
multiple character agents concurrently, which the Skill approach can't do
(one conversation = one character).

## Conventions

- `.gitignore` is intentionally per-concern rather than one giant list:
  root patterns cover things that recur everywhere (`Gemfile.lock`,
  `**/vendor/bundle/`, `.bundle/`, `.boukensha/*` except `.keep`); each
  Python project gets its own small `.gitignore` (`__pycache__/`, `*.pyc`),
  matching `circlemud-world-parser`'s existing convention rather than
  bloating the root file. `.venv/` self-ignores via `uv`'s own generated
  `.venv/.gitignore` — don't add it manually.
- `uv.lock` **is** committed (matches `circlemud-world-parser`); `Gemfile.lock`
  is **not** (Ruby gem/library convention) — these are deliberately
  different policies for the two ecosystems, not an inconsistency.
- Ask before assuming on anything with real tradeoffs (fidelity vs idiom,
  naming, commit-vs-ignore policy, etc.) — this project's decisions have
  consistently been made by asking rather than defaulting silently, and
  that's worked well. When in doubt, check `docs/plans/` for whether the
  question's already been answered before re-asking.
