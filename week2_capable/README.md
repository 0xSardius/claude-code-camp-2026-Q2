# week2_capable

Week 2 of Claude Code Camp: teaching the agent harness to play tbaMUD
*autonomously* — an observability layer, basic memory, and token-usage
optimization, all built on a lifecycle-hook agent loop.

Plans and milestones: [`docs/plans/week2/`](../docs/plans/week2/).
Weekly retro: [`docs/journal/2_week2.md`](../docs/journal/2_week2.md).
Requirements scoping that preceded them:
[`docs/plans/week2_foundations.md`](../docs/plans/week2_foundations.md).

## Layout

```
python/       -- the harness (forked from week1_baseline/python/12_context)
  boukensha/    -- the package
  examples/     -- runnable entry points
bin/          -- launchers
```

Unlike `week1_baseline`, this is **one evolving project**, not a ladder of
numbered steps. Week 2 is feature work rather than a teaching sequence, so
there is no per-step directory and no byte-for-byte parity target.

## Relationship to week 1

Forked from `week1_baseline/python/12_context` on 2026-07-27. Two consequences
worth knowing before editing:

- **The Ruby↔Python mirror is retired.** There is no Ruby counterpart to this
  tree. `week1_baseline/` stays frozen as a submitted artifact — don't backport
  changes into it. The mirror earned its keep across 13 steps, but its value
  was surfacing semantic gaps while porting *from* a Ruby source of truth, and
  week 2's features have no Ruby original.
- **That retires the byte-for-byte parity acceptance test**, which caught a
  real bug on nearly every week 1 step. Independent code review (the
  `code-review` skill via `Workflow` at `"medium"` effort) is now the only
  independent check, so it is not optional per milestone.

Module docstrings still open with `Port of week1_baseline/ruby/...`. Those are
kept on purpose as provenance — they record the Ruby/Python gaps and the
reasoning behind the code's shape. History, not an obligation to mirror.

## Running

```bash
week2_capable/bin/example
```

Resolves config from the repo-root `.boukensha/` (settings, prompts, session
logs). `uv` handles the venv; there is no separate install step.

> **Note:** the example makes real, billed API calls and connects to the live
> MUD at `localhost:4000` — start the server first
> (`docker compose up` in `week0_explore/infrastructure`).
