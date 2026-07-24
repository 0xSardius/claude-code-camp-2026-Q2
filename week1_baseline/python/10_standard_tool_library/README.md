# A Standard Tool Library (Python)

Python port of [`week1_baseline/ruby/10_standard_tool_library`](../../ruby/10_standard_tool_library)
— see [`docs/plans/python_port/10_standard_tool_library`](../../../docs/plans/python_port/10_standard_tool_library)
for the port plan and decisions. Literal mirror of the Ruby architecture,
running alongside it against the same `.boukensha/` config directory.

**This README documents the actual behavior, not the Ruby step's own
README** — that one describes `Tools::FileSystem` as "the evolution of
step 9's `WorkingDirectory`," but no such module exists anywhere in
`09_global_executable` (that step is pure RubyGems packaging, not ported
to Python at all — see [`docs/plans/python_port/09_global_executable`](../../../docs/plans/python_port/09_global_executable)).
See the port plan for the full list of discrepancies.

## What this step adds

Three new built-in tool modules, registered automatically by
`boukensha.run()`/`.repl()` via new keyword arguments:

### `boukensha.tools.file_system`

Registers automatically when `working_dir=` is set (default: the current
directory; pass `working_dir=False` to opt out entirely):

| Tool | Description |
|------|-------------|
| `pwd` | Return the working directory |
| `list_directory` | List files at a path (default `.`) |
| `read_file` | Read a file's contents |
| `write_file` | Write (or create) a file |
| `delete_file` | Delete a file |
| `search_files` | Regex search across the working tree, returns `path:line:content` matches |

All paths are relative to the working directory. Absolute paths and `..`
traversals that escape the root are rejected with an error string.

### `boukensha.tools.shell`

Registers automatically alongside `file_system` when `working_dir=` is
set:

| Tool | Description |
|------|-------------|
| `run_command` | Run a shell command inside the working directory |

Commands run with a configurable timeout (`shell_timeout=`, default 30s)
and an optional allow-list of permitted executables (`allowed_commands=`).

**Security note (fixed here, not just inherited from a clean Ruby
source):** the Ruby source's first version of this tool's
`allowed_commands` allow-list only checked a command's first whitespace
token, but the command still ran through a real shell — `"git status; rm
-rf ~"` would pass an allow-list containing only `"git"`. Both languages
now reject shell metacharacters (`; & | > < `$` or a newline) outright
whenever an allow-list is set. Verified live in both languages: the
injection is blocked, ordinary single commands still work.

One place Python is *more* correct than Ruby, noted rather than "fixed
backward": `subprocess.run(..., timeout=...)` genuinely kills the child
process on timeout. Ruby's `Timeout.timeout` wrapping `Open3.capture2e`
only interrupts the calling thread — the child keeps running as an orphan
after Ruby reports "command timed out."

### `boukensha.tools.mud`

Registers ~24 MUD gameplay tools (movement, combat, communication,
inventory, magic, shop/practice/save) against a live CircleMUD connection
when `mud=` resolves to a connection dict (explicit `mud={...}`, or
`mud=None` — the default — falling back to `settings.yaml`'s `mud:` block
if a host is configured; `mud=False` disables entirely).

Two new supporting modules back this, since there's no Python equivalent
of this project's own `mud_manager` Ruby gem anywhere in the repo:

- **`boukensha.mud_session`** — a from-scratch port of
  `week0_explore/mud_manager`'s `Session` class: a background-threaded
  telnet connection (IAC stripping, prompt detection, the
  send-then-collect-response pattern every MUD tool call uses).
- **`boukensha.mud_primitives`** — a port of the ~22 (of Ruby's ~50)
  command-builder functions this step's `Tools::Mud` actually calls.

Both are vendored directly in this package rather than split into a
separate installable dependency — see the port plan's placement-decision
section for the reasoning.

### New `boukensha.run`/`.repl` keyword arguments

```python
boukensha.run(
    task="...",
    working_dir="/my/project",
    allowed_commands=["ruby", "git", "bundle"],  # None = allow all (default)
    shell_timeout=30,                             # seconds, default 30
    mud={"host": "localhost", "port": 4000, "name": "...", "password": "..."},
)
```

## Running it

```bash
cd week1_baseline/python/10_standard_tool_library
uv sync
ANTHROPIC_API_KEY=your_key uv run python examples/example.py
```

This connects to whatever character `.boukensha/settings.yaml`'s `mud:`
block configures — **be deliberate about which character that is**. This
project's own testing used a dedicated throwaway character (`boukensha`,
level 1 Warrior) rather than either of the two characters with real
accumulated progress elsewhere in this project (`dummy`, `balthasar`) —
see `docs/journal/1_week1.md`'s `10_standard_tool_library` entry and
`.boukensha/mud_test_character.txt` (gitignored, not in this repo).

Verified live against `week1_baseline/bin/10_standard_tool_library` (the
Ruby version): both languages' `Tools::FileSystem`/`Tools::Shell` produce
byte-identical output for the same inputs (including the injection-blocked
case), both languages' `mud_primitives`/`Primitives` command builders
produce identical raw command strings, and both languages' `Tools::Mud`
successfully connect, log in, and complete a `look`/`move`/`mud_status`
round trip against the same live MUD server and test character.
