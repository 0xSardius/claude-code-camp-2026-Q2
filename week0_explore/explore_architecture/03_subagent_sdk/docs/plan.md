# 03_subagent_sdk — Plan

## Goal

Prove out the **Claude Agent SDK** as an alternative to `02`'s "Claude Code
Skill + hand-maintained markdown memory" architecture, driving the MUD
autonomously from a standalone program instead of an interactive chat
session — and, unlike `02`, be able to run **multiple character agents
concurrently in one process**.

`02` stays completely frozen and untouched (`dummy` the thief, level 3+).
`03` uses its own character(s) (`balthasar` the wizard to start) and its
own code, ported from — not dependent on — `02`'s connection logic.

## Why this is architecturally different from 02

| | 02 (Agent Skills) | 03 (Subagent SDK) |
|---|---|---|
| Who drives play | Me, in this live chat, one `Bash` tool call per command | A standalone Node/TS program, running its own agent loop(s) outside the chat |
| Control flow | Serial — one conversation, one character at a time | Parallel-capable — each character is an independent `query()` loop; N can run concurrently via `Promise.all` |
| Connection persistence | Background daemon + Unix socket, because each Bash call is a fresh subprocess | In-process socket — the orchestrator itself is long-running, so no daemon/IPC needed |
| Memory | I read/write `player.md`/`world.md` by hand each turn | The agent's own tool calls read/write its memory file, autonomously, as part of its loop |
| Autonomy | Bounded by conversation turns — nothing happens unless prompted | Bounded by a turn/time/token budget baked into the run, then it stops and persists state on its own |

## Tech stack

- **TypeScript on Node** (`node --version` confirmed v24.10.0 available).
- **`@anthropic-ai/claude-agent-sdk`** (confirmed on the npm registry,
  latest `0.3.214`; peer deps `zod ^4.0.0`, `@anthropic-ai/sdk >=0.93.0`,
  `@modelcontextprotocol/sdk ^1.29.0`). Uses the same auth as the `claude`
  CLI already logged in for this session — **no separate API key needed**.
- `tsx` for running TypeScript directly without a separate build step.

## Directory structure

```
03_subagent_sdk/
  package.json
  tsconfig.json
  docs/
    plan.md                  <- this file
  src/
    mud/
      connection.ts          # ported MudConnection (telnet/IAC-stripping/login/
                              # read_until*/reconnect-resilience) from 02's
                              # mud_daemon.py — same hard-won behavior, no shared code
      tools.ts                # SDK tool definitions (mud_send, mud_status, mud_save)
                              # bound to one connection instance per character
    agents/
      characterAgent.ts       # runs one character's SDK query() loop: system
                              # prompt + tools + memory dir + turn budget
    memory.ts                 # read/write a character's data/<name>/player.md
                              # and world.md — same pattern as 02, namespaced
                              # per character so agents never collide
    characters.ts             # character registry: name/password/personality/
                              # goal per character (starts with balthasar)
    orchestrator.ts            # entry point — launches one or more character
                              # agents concurrently, waits for all to finish
  data/
    balthasar/
      player.md
      world.md
```

## Connection layer

Port `MudConnection` from `02/scripts/mud_daemon.py` to TypeScript
(`net.Socket`, IAC stripping, `readUntil`/`readUntilQuiet`/`readUntilPrompt`,
the login dance, and the "claim the buffer before sending" fix that solved
02's stale-response race). Because the TS orchestrator process itself stays
alive for the whole run (unlike Claude Code's per-call `Bash` subprocesses),
there's no need for 02's background-daemon-over-Unix-socket indirection —
each character's connection just lives as a plain in-process object.

## Tools exposed to each agent

- `mud_send({ command, mode?: "prompt" | "quiet", timeoutMs?, quietMs? })`
  — send one raw MUD command, return its output. Mirrors `mud.py send`.
- `mud_save()` — convenience wrapper for the `save` command, so the agent
  can be nudged to always save after leveling up.
- `memory_read()` / `memory_write(section, content)` — read/update this
  character's own `player.md`/`world.md`, scoped to its own `data/<name>/`
  directory only.

Each character agent gets its own bound instances of these tools (closures
over its own `MudConnection`), so concurrent agents never cross-talk on
sockets or memory files.

## Agent loop

For each character: `query()` with a system prompt carrying personality +
goal (mirroring what worked for Dummy-the-thief in `02` — the journal notes
personality framing measurably improved play), the tools above, and a
bounded turn/time budget so an autonomous run can't loop forever. On
finishing (goal progress made, or budget exhausted), the agent is expected
to `save` and write its memory before exiting.

## Concurrency

`orchestrator.ts` accepts a list of character configs and runs
`runCharacterAgent(config)` for each concurrently via `Promise.all` —
directly enabling "multiple character agents in the same session," which
`02`'s single-conversation model structurally cannot do.

## Milestones

1. ✅ Scaffold project (`package.json`, `tsconfig.json`, deps installed).
2. ✅ Port `MudConnection` to TS; smoke-tested raw connect/login/send
   against the live MUD as Balthasar — worked cleanly (see
   `src/mud/smokeTest.ts`, `npm run smoke-test`).
3. ✅ Wire up SDK tools + one character agent (Balthasar), run it fully
   autonomously (`npm run play`) with a 30-turn budget. Real result,
   unattended, no human steering: it read its (empty) memory, explored the
   Temple Of Midgaard, found free starting gear from a donation-room NPC on
   its own initiative (AC 90 -> 29), located the Guild of Magic Users,
   spent both practice sessions on `magic missile` (-> superb), found a
   "beastly fido," `consider`ed it first, killed it with a ranged spell
   rather than melee (correct instinct for a fragile caster), and was
   mid-loot when it **hit the 30-turn ceiling** and errored out
   (`Reached maximum number of turns (30)`) before it could call
   `mud_save` or `memory_write`.
   - **Finding**: despite never calling `mud_save`, a follow-up diagnostic
     connection confirmed the game state persisted anyway (exp 1->62, gold
     0->10, AC 90->29, spell rank, gear all stuck) — tbaMUD appears to
     autosave core progression continuously, not only on explicit
     `save`/`quit`. So the run did NOT lose game progress; the only real
     casualty was our own memory files staying stale, which the
     orchestrating session filled in by hand from the tool-call transcript
     (see `data/balthasar/player.md` / `world.md`).
   - **Open problem to fix before the next run**: 30 turns is not enough
     for a full explore+guild+practice+fight+loot+wrap-up session, and the
     system prompt's "budget your turns" instruction alone wasn't enough
     to make the agent reserve turns for its own memory_write/mud_save
     ending. Next iteration should either raise `maxTurns`, or restructure
     the prompt/loop with an explicit checkpoint (e.g. a turn-count
     reminder tool, or a forced two-phase "play" then "wrap up" split) —
     undecided yet, worth another run to see if a bigger budget alone
     fixes it before adding more structure.
   - **Fix that worked (session 2, same day)**: added `MUD_TASK` and
     `MUD_MAX_TURNS` env-var overrides to `characterAgent.ts` (mirrors
     `02`'s play-mud skill taking fresh `ARGUMENTS` each invocation — same
     character, new directive, no code edits needed), gave it an
     explicit strict-priority-order task ("finish looting and save FIRST,
     before any exploration; stop with 6-8 turns left and write memory
     regardless of progress"), and raised the budget to 45. Result: it
     looted, saved twice, explored westward (found and correctly ruled out
     a dead-end forest route), backtracked, found the real lead (Temple
     Square -> temple gate north), and wrapped up cleanly with a full
     self-written memory update — using only 20 of its 45 turns. Verified
     via `npm run smoke-test` that its self-reported end state (location,
     HP/mana/moves, exp, gold) matched the live server exactly. This was
     the first run where the agent wrote its own `player.md`/`world.md`
     end-to-end without any manual patch-up from the orchestrating
     session. Front-loading the critical action + an explicit
     turns-remaining checkpoint, rather than a vague "budget wisely"
     instruction, appears to be what made the difference.
4. Extend `orchestrator.ts` to support N concurrent characters (even if
   only Balthasar is registered today — the second character is what
   proves the concurrency claim, so this gets exercised, not just built).
   **Deferred by user choice**: validate the single-agent path solidly
   first (done above), add a second character afterward once the
   turn-budget issue is sorted.
5. Record findings back into `data/balthasar/player.md` and this plan doc.
   ✅ done for this first run — repeat after each future run.
