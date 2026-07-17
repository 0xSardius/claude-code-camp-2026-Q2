---
name: play-mud
description: Connect to and play the local CircleMUD/tbaMUD instance running at localhost:4000. Use when the user asks to play the MUD, log into the MUD, explore the MUD world, fight monsters, level up a character, or run any in-game command (look, north, kill, buy, score, etc.).
---

## What this is

The MUD is a telnet-based game with a stateful session (you log in once,
then stay connected while you move around, fight, chat, etc.). A fresh
`Bash` call can't hold a TCP socket open across separate tool invocations,
so this skill runs a small background daemon (`scripts/mud_daemon.py`)
that owns the actual telnet connection and login session. You talk to it
through `scripts/mud.py`, a short-lived CLI you call once per turn.

Connection defaults (override with flags or `MUD_HOST` / `MUD_PORT` /
`MUD_USERNAME` / `MUD_PASSWORD` env vars if the user says otherwise):

- host/port: `localhost:4000`
- credentials: `dummy` / `helloworld`

## Memory: `data/player.md` and `data/world.md`

The MUD server has no memory of your intent between sessions — only the
character's raw state (level, location, inventory). Long-running goals like
"get to level 7" span far more turns than fit in one context window, so
this skill keeps its own memory on disk instead of relying on conversation
history:

- **`data/player.md`** — the character's current goal, level, skills,
  practice sessions, gold, location, a running progress log, and next
  steps. This is the file to check "are we done yet" against.
- **`data/world.md`** — the map: rooms discovered, their exits, and known
  points of interest (shops, the guild practice room, etc.), so later
  sessions don't have to re-explore blindly to get somewhere already found.

**Always read both files before connecting**, so you resume the standing
goal and known map instead of starting cold. **Always update `player.md`**
after anything goal-relevant happens — a level up, a location change, a
goal being set or completed, a notable inventory change — and add a short
dated line to its progress log. **Update `world.md`** whenever `look`
reveals a room or exit not already recorded there.

When the user hands you a long-running goal ("get to level 7"), write it
into `player.md`'s **Current goal** section immediately, then work in
whatever increment fits this turn (explore a bit, fight a bit, practice a
bit) — update the file, and stop. The next invocation of this skill picks
up exactly where the log left off, so the goal doesn't need to be re-stated
or re-explained by the user each time.

## Workflow

0. **Read `data/player.md` and `data/world.md` first** to recall the
   current goal, character state, and known map before doing anything else.

1. **Connect once per session**, before sending any commands:
   ```
   python3 scripts/mud.py start
   ```
   This spawns the daemon if it isn't already running, waits for it to
   connect and finish the login dance, and prints a confirmation. If it's
   already running it just prints `already running` — safe to call again.

2. **Send a command, get its output**:
   ```
   python3 scripts/mud.py send "look"
   python3 scripts/mud.py send "north"
   python3 scripts/mud.py send "kill rat"
   ```
   This blocks until the MUD's `> ` prompt reappears (or up to `--timeout`
   seconds, default 10), then prints everything the MUD sent back.

3. **During combat or when a command triggers a burst of async lines**
   (multiple rounds, other players talking), the prompt can be noisy or
   delayed. Prefer reading by idle-time instead:
   ```
   python3 scripts/mud.py send "kill rat" --quiet 1.0 --timeout 15
   ```
   Or after sending, poll for trailing output that arrived late:
   ```
   python3 scripts/mud.py drain
   ```

4. **Stop when done** (or leave it running between turns — it's cheap and
   the user may want to keep playing):
   ```
   python3 scripts/mud.py stop
   ```

5. **Check connection health** any time with `python3 scripts/mud.py status`.

6. **Before finishing this turn, write back to `data/player.md`** (and
   `data/world.md` if new rooms were found): current level/gold/skills,
   location, a progress-log line, and updated next steps toward the goal.

## Notes

- Run these from the skill directory, or use the full path to `scripts/mud.py` — it locates the daemon and its own runtime files (`run/mud.sock`, `run/mud.pid`, `run/mud.log`) relative to itself, so cwd doesn't matter.
- If `start` times out or errors, check `run/mud.log` for what happened (e.g. MUD not running — `docker compose up` in `week0_explore/infrastructure`, or wrong credentials).
- Commands are raw MUD text — send exactly what a human would type (`get all corpse`, `practice kick`, `consider rat`, etc.). There's no command whitelist here; the MUD itself will reject anything invalid.
- If you quit and reconnect mid-session, `dummy` starts back at the temple altar unless `offer`/`rent` was used at an inn to persist location — see `week0_explore/HOW_TO_PLAY.md` for the map and early-game guidance. Note that in `player.md` if it happens, so the recorded location doesn't go stale.
- Run `score` periodically (e.g. after fights) and reconcile the result against `player.md` — it's the source of truth for level/hp/gold, the memory file is just a cache of it.
- This MUD's connection has been observed to drop unpredictably (anywhere from ~10 seconds to a few minutes after connecting) independent of anything this skill does. `send`/`drain` auto-reconnect on a dropped connection and retry once, so a single stray "daemon not running" error mid-sequence is expected and self-heals — no need to treat it as a real failure unless it repeats after the retry.
