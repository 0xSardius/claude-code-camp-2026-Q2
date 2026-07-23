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
  ruby/00_config, ruby/01_struct_skeleton, ruby/02_the_registry, ...   -- source of truth, one dir per step
  python/00_config, python/01_struct_skeleton, (02_the_registry next)  -- literal port, runs alongside Ruby
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
  other** — porting a step never touches the Ruby original, **except**:
  genuine bugs found in the Ruby source while planning/porting get fixed in
  Ruby too (explicitly authorized 2026-07-21, `02_the_registry`) — a
  literal mirror of a bug isn't the goal, a literal mirror of correct
  behavior is. Fix clear bugs; don't unilaterally resolve things the Ruby
  source itself frames as an open question (e.g. a README's own
  "Considerations" section asking "should this have been removed") —
  those stay open until a human decides.
- **Each numbered step is independently ported from its own Ruby sibling**,
  not from the previous Python step. The Ruby side itself duplicates code
  per step rather than sharing a lib — confirmed by diffing steps against
  each other (e.g. `01_struct_skeleton`'s `config.rb` is missing a constant
  `00_config`'s has, because that step doesn't need it). Don't assume a
  new Python step's file is identical to the previous step's just because
  it looks similar — re-read the actual Ruby source every time.
  **Narrow exception (added 2026-07-22, `02_the_registry`):** if that fresh
  re-read confirms a file's Ruby source is byte-identical to a prior step's,
  it's fine to copy the *prior step's already-ported Python file* forward
  instead of re-deriving from Ruby — re-deriving risks silently losing a
  Python-side fix (falsy-`or`, `None`-to-string, slice-width, etc.) that
  file already has. The rule's real intent is "verify, don't assume" — the
  diff *is* the verification step, not something to skip.
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
  skill, run via `Workflow` at **`"medium"` effort** — downgraded from
  `"high"` 2026-07-23 after 5 steps at `~400-500k` tokens each; medium has
  caught the same class of bug for meaningfully less cost) before
  considering a step done — it has found real, non-obvious bugs (see
  Gotchas) that the parity test alone didn't catch. This whole process is
  now also captured as a project skill: `.claude/skills/python-port/`.

### Gotchas hit so far (don't re-discover these)

- **`BOUKENSHA_DIR` path math**: `examples/example.rb`/`.py` need exactly
  **4** `../`/`.parent` hops from the `examples/` dir to reach the repo
  root (`ruby/<step>/examples/` → `ruby/<step>/` → `ruby/` →
  `week1_baseline/` → repo root). Every Ruby step so far has shipped with
  this off by one at first (3 instead of 4) — `00_config`, `01_struct_skeleton`,
  and `02_the_registry` all needed the same one-line fix. **Check this
  first, before reading anything else, on every new step.**
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
- **Dict/hash keys need normalizing at the point of storage, not just at
  one call site.** `Context#register_tool` stored `tool.name` as-is; when
  `02_the_registry` added a `Registry` that always normalizes to a string
  before registering, the *old*, still-public `register_tool` method
  became a bypass — a `Tool` built with a symbol name and registered
  directly would silently land under a different key type, making it
  permanently undispatchable even though `tool_count` said it existed.
  Fixed by normalizing inside `register_tool` itself (`tool.name.to_s`),
  not by trusting every caller to normalize first. Same principle applies
  in Python (`str(tool.name)`) even though it's lower-risk there (no
  symbol/string duality) — backported to `01_struct_skeleton` for
  consistency. General lesson: if two code paths can both reach a shared
  mutable structure, normalize at the structure's own boundary, not at
  each caller.
- **Ruby's symbol/string keyword-argument gap has no Python equivalent —
  don't manufacture one.** `02_the_registry`'s whole teaching point is that
  Ruby blocks need symbol-keyed args (`|direction:|`) while incoming data
  is string-keyed JSON, so `dispatch` does `args.transform_keys(&:to_sym)`.
  Python's `**kwargs` unpacking is already string-keyed — there's nothing
  to translate, so the ported `dispatch` is legitimately shorter. Don't add
  a no-op step just to have "something" mirroring that line; document
  *why* it's shorter instead. (General version of this: not every Ruby
  line needs a Python counterpart — some Ruby-specific problems just don't
  exist on the other side.)
- **A fix can reintroduce the exact gotcha it was inspired by.** The
  `register_tool` string-normalization fix (above) used bare `str(tool.name)`
  in Python — which hits the `nil.to_s`-vs-`str(None)` gotcha (already
  documented above it in this same list) on a `None`-named `Tool`. Ruby's
  `tool.name.to_s` didn't need an equivalent guard (`nil.to_s` is already
  `""`), so the asymmetry was easy to miss porting Ruby → Python. Caught by
  a code-review pass, not the parity test (both steps' example output never
  exercises a `None`-named tool) — fixed with the same `"" if x is None
  else str(x)` guard as everywhere else. Lesson: when fixing one gotcha,
  check whether the fix's own code touches ground already covered by a
  *different* documented gotcha.
- **Normalizing a key can turn "coexists under two keys" into "silently
  overwrites."** Before the `register_tool` fix, a symbol-named and a
  string-named `Tool` with the same underlying name landed under two
  distinct hash/dict keys (one of them permanently undispatchable, but
  still present in `tool_count`/`tools`). After the fix they collide onto
  one key and the second registration silently wins — no duplicate-name
  guard exists. Confirmed and **left as-is on purpose** (2026-07-22): plain
  hash/dict last-write-wins is normal semantics, and `register_tool`'s
  public-API duplication is already an open question the Ruby README's own
  "Considerations" section raises ("should this have been removed") — adding
  duplicate-detection now would be resolving that open question
  unilaterally, which this project's conventions say not to do.
- **The `BOUKENSHA_DIR` off-by-one bug class hits other directory-relative
  constants too, not just that one.** `03_prompt_builder` added
  `Config::PROMPTS_DIR`, and it shipped with the exact same 3-`../`-
  instead-of-4 (well, 3-instead-of-2 for this particular constant's
  shallower path) bug on arrival. Check the hop math on *any* new
  `File.expand_path(...,  __dir__)`-style constant a step introduces, not
  just `BOUKENSHA_DIR` by name.
- **Regressions of already-fixed bugs are the norm for this project, not
  an edge case.** Every step since `02_the_registry` has reintroduced at
  least one previously-fixed bug (`register_tool`'s `.to_s` normalization
  regressed in `03_prompt_builder` AND `04_api_client`; `03`'s
  `to_messages(system, messages)` arity fix and its `claude-sonnet-5`
  MODELS entry both fully reverted in `04_api_client`). Always diff every
  file against its predecessor even when you're confident it's unchanged —
  don't skip the diff because a file "should" carry forward cleanly.
- **Ruby's `JSON.pretty_generate` and Python's `json.dumps(indent=2)`
  disagree on two things** (found in `03_prompt_builder`, matters for any
  step that pretty-prints a payload/response for display): (1) empty
  containers — Ruby emits one newline for `{}` but two for `[]` (a real,
  confirmed asymmetry in Ruby's json gem), Python collapses both to one
  line regardless of indent; (2) non-ASCII — Ruby's `JSON.generate` passes
  UTF-8 through by default, Python's `json.dumps` defaults to
  `ensure_ascii=True` (escaping to `\uXXXX`). A hand-rolled
  `ruby_pretty_json` helper (see `03_prompt_builder`/`04_api_client`'s
  `examples/example.py`) matches Ruby exactly; don't trust
  `json.dumps(..., indent=2)` for anything byte-parity-tested.
- **Ruby can overload one name across a class method and an instance
  method; Python cannot.** `backends/base.rb`'s `self.model_info(model)`
  (class method, 1-arg MODELS lookup) and `#model_info` (instance method,
  0-arg getter) coexist fine in Ruby (separate method tables). A literal
  Python port defining both as `model_info` in one class body just has the
  second definition silently clobber the first. Fixed by renaming the
  class-side lookup (`find_model_info`) rather than the instance-side one,
  since the instance property is the one appearing in the class's
  documented public API. General lesson: when a Ruby name-collision has no
  Python equivalent, check which of the two colliding meanings is actually
  the documented/public one before deciding which name to keep.
- **`urllib.request.urlopen` splits "get the response" from "read the
  body" into two steps; Ruby's `Net::HTTP#request` does both atomically in
  one call, inside one `begin/rescue`.** `04_api_client`'s first port of
  `Client#call` fetched the body (`response.read()`) *after* the
  try/except that catches transient errors, so a connection reset mid-body
  -download would crash unretried and unwrapped instead of being retried
  like Ruby's version — caught by code review, not the live-call
  verification. Fix: pull status AND body inside the same try/except.
  Related: an unclosed `urllib` response leaks its underlying socket the
  way an unclosed Ruby `Net::HTTP` connection doesn't (Ruby's one-off
  `.request()` call closes its connection when it returns) — close the
  response in a `finally` on every path (success, terminal error, and
  before each retry), not just some of them.
- **A step whose behavior is inherently non-deterministic (real network
  calls, timestamps, randomness) can't use the byte-for-byte diff
  acceptance test.** `04_api_client` makes real, billed API calls — a full
  launcher-output diff is structurally impossible, not just inconvenient.
  Resolved (2026-07-22) by agreeing on a different bar with the user: one
  real round-trip per language proving success + matching JSON *shape* (not
  values), one deliberately-invalid-key round-trip per language (free,
  deterministic, verifies the `ApiError` path), and everything actually
  deterministic (payload construction, retry/backoff logic) still verified
  by direct code reading, same rigor as a normal review. Don't silently
  relax the acceptance bar without an explicit decision like this one.
- **Never read or print a secret's value into the transcript, even when
  told it's fine to *use* it.** The user has a real `ANTHROPIC_API_KEY` in
  the repo-root `.env` (gitignored) and said using it was fine — but the
  right move was still to source it inline into the specific shell command
  that needed it (`set -a; source .env; set +a; <command>`) rather than
  `cat`/`grep` the file or write the value into any tracked or
  logged/echoed location. "You can use X" is not "you can display X."

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
