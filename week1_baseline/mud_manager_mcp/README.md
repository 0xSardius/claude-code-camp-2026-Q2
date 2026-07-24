# mud_manager_mcp

An MCP server wrapping [`week0_explore/mud_manager`](../../week0_explore/mud_manager)
(the `Session`/`Primitives` classes), plus a small Python MCP client that
drives it. See [`docs/plans/mud_manager_mcp`](../../docs/plans/mud_manager_mcp)
for the full plan and the decisions behind it.

**This is additive, not a replacement.** `week1_baseline/ruby/10_standard_tool_library`'s
and `week1_baseline/python/10_standard_tool_library`'s `Tools::Mud` are
untouched by this and keep working exactly as before — each still opens
its own independent MUD session, in-process. This project is a separate
exploration: hands-on experience with MCP as an architecture, and a first
step toward a session other agents could eventually share (see the plan
doc's "explicitly out of scope" section for what that would actually
require — it isn't this).

## What's here

- `lib/mud_manager_mcp/server.rb` — the MCP server. One `MudManager::Session`
  is opened and logged in once, at server startup, and shared by every
  tool call (the same "connect once, reuse the connection" design as
  `Tools::Mud`, just now living in a process that outlives any one
  client). Exposes 12 tools: `mud_connect`, `mud_disconnect`,
  `mud_status`, `look`, `examine`, `check`, `consider`, `move`, `flee`,
  `attack`, `get_item`, `say` — a representative subset of `Tools::Mud`'s
  ~24, not full parity (see the plan doc for why).
- `bin/mud_manager_mcp_server` — runs the server over **Streamable HTTP**
  (not stdio — the point is a persistent server independently-launched
  clients connect to, not a per-client child process).
- `python_client/example.py` — a single-file Python MCP client demo (PEP
  723 inline dependency metadata, run via `uv run`, not a full
  `pyproject.toml` package — there's no importable module here, just one
  script). Connects, lists tools, calls `mud_status`/`look`/`check`.

## Running it

Uses the dedicated `boukensha` test character (see
`.boukensha/mud_test_character.txt`, gitignored) — **not** `dummy` or
`balthasar`, which have real accumulated progress elsewhere in this
project.

```bash
cd week1_baseline/mud_manager_mcp
bundle config set --local path 'vendor/bundle'
bundle install

MUD_NAME=boukensha MUD_PASSWORD=<see .boukensha/mud_test_character.txt> \
  bin/mud_manager_mcp_server
# Starts on http://localhost:8000/ (override with MCP_HTTP_PORT).
# Ctrl-C to stop.
```

In another terminal, with the server running:

```bash
cd week1_baseline/mud_manager_mcp/python_client
uv run example.py
```

Verified this session: the tool round trip works end-to-end (Python
client → streamable HTTP → Ruby MCP server → `MudManager::Session` → real
MUD → same path back), and — the actual point of this exercise — **the
session survives across two independent client processes**: running
`example.py` twice in a row, as two separate `uv run` invocations, both
saw the same live session and the same character state, because the
session lives in the server, not in either client.

## Why an MCP server here instead of just calling `Tools::Mud` from Python

Python's `Tools::Mud` equivalent (`boukensha/mud_session.py` +
`boukensha/mud_primitives.py` in `10_standard_tool_library`) is a
from-scratch reimplementation of the same telnet/session logic
`mud_manager` already has in Ruby — necessary duplication given this
project's per-language port methodology, but duplication all the same.
This server is the alternate answer: one implementation, wrapped once,
callable by any MCP client regardless of language. Whether that trade-off
is worth adopting more broadly (i.e. migrating the existing `Tools::Mud`s
onto this instead of their own direct sessions) is a separate, larger,
deliberately deferred decision — see the plan doc.
