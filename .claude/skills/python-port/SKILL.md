---
name: python-port
description: Port the next week1_baseline Ruby step (week1_baseline/ruby/<NN_name>) to Python (week1_baseline/python/<NN_name>). Use this whenever the user asks to port, plan, or execute a Python port of a new or existing Boukensha step, says a Ruby step is ready to port, asks "what's next to port", or references docs/plans/python_port/ — even if they just say something like "let's do the python version of 05" or "port the next ruby piece". This skill encodes the exact process this project has used successfully five times (00_config through 04_api_client) and the gotchas that keep recurring — don't improvise a different process without reading this first.
---

# Python Port

Ports one `week1_baseline/ruby/<NN_name>` step to
`week1_baseline/python/<NN_name>`. This project's root `CLAUDE.md` has the
full standing ground rules (Ruby is source of truth, Python is a literal
architectural mirror not an idiomatic rewrite, steps port independently
from their own Ruby sibling) — **read it first**, this skill assumes it.

The process below is deterministic and has been run five times
successfully. Don't skip steps because a step "looks simple" — the two
steps that looked simplest (`01_struct_skeleton`, `02_the_registry`) are
exactly where the recurring bugs were first found.

## 0. Orient

Read, in order:
1. Root `CLAUDE.md` — the ground rules and, critically, the **"Gotchas hit
   so far"** list. This list is the living catalog of every Ruby-vs-Python
   translation trap and every Ruby bug pattern found so far. It is
   maintained *there*, not duplicated in this skill, because it grows with
   every step — always read the current version, don't rely on memory of
   an older one.
2. `docs/plans/python_port/<previous_step>` — the most recently completed
   port plan. It shows the exact plan format expected (see step 3) and
   often documents a divergence from *its* predecessor that's still
   relevant.
3. `week1_baseline/python/<previous_step>/` — the actual prior Python
   source. Step 3 below carries files forward from here, not from Ruby
   from scratch, whenever the Ruby sources are byte-identical.

## 1. Research the new Ruby step

Read every file in `week1_baseline/ruby/<new_step>/`, then diff every file
that also exists in the previous step against its predecessor:

```bash
cd week1_baseline/ruby
for f in lib/boukensha.rb lib/boukensha/*.rb lib/boukensha/tasks/*.rb lib/boukensha/backends/*.rb; do
  [ -f "<previous_step>/$f" ] && [ -f "<new_step>/$f" ] && {
    echo "--- $f ---"
    diff "<previous_step>/$f" "<new_step>/$f" && echo "IDENTICAL"
  }
done
```

For every file the diff shows as changed, understand *why* — is it a
genuinely new feature for this step, or a regression of something already
fixed? **Check the `BOUKENSHA_DIR` off-by-one first, before reading
anything else** — `examples/example.rb` needs exactly 4 `../`/`.parent`
hops from the `examples/` dir to the repo root
(`ruby/<step>/examples/` → `ruby/<step>/` → `ruby/` → `week1_baseline/` →
repo root). Every single step so far has shipped with 3 instead of 4 at
first. If this step adds a *new* directory-relative constant (like
`03_prompt_builder`'s `PROMPTS_DIR`), check its hop math too — the same
off-by-one class of bug has now hit more than one constant.

**Regressions are a real, recurring pattern, not a hypothetical worth
watching for "just in case."** Every step since `02_the_registry` has
reintroduced at least one bug a prior step already fixed (most often
`Context#register_tool`'s missing `.to_s` normalization). This means:
*don't assume a file matches its predecessor just because it looks
similar* — diff it, every time, even for files you're confident are
carried forward unchanged. When you find a regression, re-apply the exact
fix from the plan doc that fixed it originally (search
`docs/plans/python_port/` for the bug's name if you don't remember the
fix), and note in the new plan that it's a *reapplication*, not a
discovery. If the same regression happens two steps in a row, say so
explicitly to the user rather than silently fixing it a third time — it's
a signal about how the Ruby side is being scaffolded, worth surfacing
rather than perpetually working around.

Also check: does the README's own "Considerations" or similar section
frame something as an open, unresolved design question (e.g.
`02_the_registry`'s "should `register_tool` have been removed")? Leave
those alone — don't unilaterally resolve something the source material
itself frames as open. Does the README show an "expected output" example
that doesn't match what the actual code produces? That's a recurring,
apparently intentional pattern (the README examples are aspirational/
illustrative, not literal) — port the real code, note the mismatch in the
plan, don't chase the README's example.

## 2. Decide what needs the user's input vs. what doesn't

Two different categories of thing come out of step 1 — treat them
differently:

**Just fix it, note it in the plan, don't ask:**
- The `BOUKENSHA_DIR`/other-constant off-by-one bug (always the same fix).
- A regression of a bug already fixed in a prior step (always the same
  fix — reapply it).
- Anything the fix for is a single, obviously-correct one-liner with no
  design tradeoff.

**Ask via `AskUserQuestion` before writing the plan:**
- A genuinely new bug whose fix has more than one reasonable shape (e.g.
  `03_prompt_builder`'s `to_messages` arity mismatch — could have been
  fixed by changing the delegator, the backends, or left as a documented
  gap; each has different blast radius).
- Anything that changes the *acceptance test itself* — e.g.
  `04_api_client` making real, non-deterministic, billed network calls
  meant the usual byte-for-byte diff couldn't be the bar anymore, which
  needed the user to decide what "passing" means for that step.
- Anything touching real-world cost, credentials, or external services —
  confirm before making a live call, and never read/print a secret's value
  into the transcript even when told it's fine to *use* it (source it into
  a subshell inline, or write it to a gitignored file, without echoing it).
- Any tension with a standing rule in `CLAUDE.md` itself (e.g. whether
  copying a file forward from the previous Python step, rather than
  re-deriving from this step's own Ruby sibling, is acceptable when the
  Ruby sources are confirmed byte-identical — this came up once already
  and was resolved by amending `CLAUDE.md` with a narrow exception; check
  there first for whether your question has already been answered before
  re-asking).

## 3. Write the plan

Write `docs/plans/python_port/<new_step>` before touching any Python code.
Use the previous step's plan as the literal template — same section
structure every time:

- **Goal** — one paragraph.
- **Decisions carried forward (unchanged)** — a table, copied from the
  previous plan, plus anything new this step adds.
- **New for this step: fixing real Ruby bugs in flight** — every bug from
  step 1/2, both the auto-fixed ones and the ones the user decided on, with
  the reasoning and (for regressions) which prior step originally fixed it.
- **Reference files** — a table of every Ruby file this step touches, each
  row saying whether it's new, changed, or byte-identical to the previous
  step's sibling (cite the diff).
- **Target directory layout** — the full Python tree, annotating which
  files are "carry forward from `<prev>`" vs. "NEW".
- **File-by-file port notes** — for every new/changed file, the actual
  Python code (or close to final), with inline comments explaining every
  Ruby→Python translation decision that isn't obvious (symbol vs. string
  keys, required-vs-optional kwargs, `nil.to_s` vs `str(None)`, etc. — see
  `CLAUDE.md`'s gotchas list for the standing catalog of these).
- **New bin launchers** — the two launcher scripts, verbatim.
- **`.gitignore`** — almost always identical to every prior step's.
- **Milestones / execution order** — a numbered list. This becomes your
  task list for step 4. It always ends with "run the `code-review` skill
  before calling it done."
- **No open questions — ready to implement** (or: what's still open, if
  anything, and why it's blocking).

Get the plan confirmed by the user (or, if every question was already
resolved via `AskUserQuestion` in step 2, a lighter "here's the plan,
executing" is fine — use judgment on how much re-confirmation is needed
based on how much was already decided).

## 4. Execute

Follow the plan's milestones in order. A few things that apply to every
step regardless of what the plan says:

- **Scaffold before `uv sync`**: create `pyproject.toml`, `.python-version`,
  a placeholder `README.md`, and empty `__init__.py` stubs for every
  package dir *before* running `uv sync` — hatchling fails without a real
  README and a non-empty package dir, and fixing that after a failed sync
  is strictly more work than doing it right the first time.
- **"Carry forward" means copy the already-fixed Python file**, not
  re-derive from Ruby — once you've confirmed (step 1) the Ruby sources
  are byte-identical, copying `week1_baseline/python/<previous>/...` is
  both correct and safer than re-translating (re-deriving risks silently
  dropping a Python-side fix the prior step already made — falsy-`or`,
  `None`-to-string, slice-width, symbol-key formatting, etc.).
- **Verify parity as you go, not just at the end.** After each
  new/changed file, run a quick sanity check (`uv run python -c "import
  boukensha"`, a short inline script exercising the new code) rather than
  waiting until the full example runs to discover a typo.

## 5. Verify

The default acceptance bar is **byte-for-byte diff** between
`bin/<step>` and `bin/<step>_python` against the same
`.boukensha/settings.yaml`:

```bash
diff <(bash week1_baseline/bin/<step>) <(bash week1_baseline/bin/<step>_python) && echo "BYTE-IDENTICAL"
```

If the step's behavior is inherently non-deterministic (a real network
call, a timestamp, randomness), this bar is impossible and the plan should
have already worked out an alternative with the user in step 2 — typically
"one live/real run per language proving success + matching *shape* (not
content), plus deterministic sub-parts (payload construction, error
handling) still byte/behavior-diffed the normal way." Don't silently
relax the acceptance bar without that having been an explicit decision.

**Re-run every prior step's parity check too**, not just the new one —
carried-forward files are shared code; a mistake in the current step could
theoretically be a copy-paste of a change that shouldn't have propagated.
This has always passed so far, but it's a cheap check:

```bash
for step_pair in "01_struct_skeleton 01_struct_skeleton_python" "02_the_registry 02_the_registry_python" ...; do
  read a b <<< "$step_pair"
  diff <(bash week1_baseline/bin/$a) <(bash week1_baseline/bin/$b) && echo "$a: OK"
done
```

## 6. Bin launchers, `.gitignore`, README

Straightforward, mechanical, per the plan — `chmod +x` both new launchers,
verify `.gitignore` coverage with `git status --ignored`, port the README
(same "port the real code's behavior, not the README's aspirational
example" rule as step 1).

## 7. Code review — never skip this

Run the `code-review` skill (via `Workflow`, `name: "code-review"`,
`args: "high ..."`) against the full diff — new Python files, the bin
launchers, the plan doc, and the in-flight Ruby fixes together. This has
found real, non-obvious bugs on every step it's been run on so far (a
missed `register_tool` normalization, a `None`-vs-`"None"` rendering bug,
a socket-leak in `04_api_client`'s HTTP client) that parity/live testing
alone did not catch. Report findings with `ReportFindings`, fix anything
CONFIRMED, then **re-run the step-5 parity check** after fixing — a review
fix can (and has) needed re-verification just like any other code change.

For findings that are genuine judgment calls rather than clear bugs (e.g.
"should this now-reachable behavior change get a guard, or is it
acceptable as-is") — surface them to the user via `AskUserQuestion` rather
than deciding unilaterally, same as step 2.

## 8. Close out

- Update root `CLAUDE.md`'s "Gotchas hit so far" list with anything new
  this step discovered (a new bug pattern, a new Ruby-vs-Python
  translation trap, a new regression). This is the single most valuable
  artifact this process produces for future steps — don't skip it even
  when the step felt routine.
- `docs/journal/1_week1.md` may be worth updating too, following its
  existing Goal/Uncertainty/Hypothesis/Observations/Conclusions structure
  — use judgment on whether this step changed the overall picture enough
  to warrant it.
- **Do not commit unless explicitly asked.** When asked, stage only the
  files this port actually touched — check `git status` first, since the
  user may have unrelated in-progress work sitting in the same working
  tree (e.g. the next Ruby step already scaffolded, not yet ready to
  port).
