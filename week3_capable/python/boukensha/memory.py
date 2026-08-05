"""Per-character persistent memory (week2 memory M1).

Replaces the hand-maintained `player.md` / `world.md` that week0's play-mud
Skill relied on. Those were curated by a human, for one character, for one
architecture. This is the same content model, maintained by the agent itself.

    .boukensha/memory/<character>/
      state.json     level, hp, position belief, current goal   (harness)
      trails.json    observed room edges + room records          (harness)
      facts.md       world/character observations                (agent)
      learnings.md   efficiency observations about its own play  (agent)
      journal.md     human-readable narrative                    (agent + generated)

Split by WHO WRITES IT, which keeps the two write paths from tangling. JSON for
the harness-owned files (nothing reads them in a prompt); Markdown for the
agent-owned ones (they get injected into context, and Markdown is what the
model writes well).

WHY THIS IS NOT ONE FILE. Today's player.md does four jobs at once: character
state, world knowledge, a progress narrative, and standing playstyle. Week2
splits them because of PROMPT CACHING, not tidiness -- a file that rewrites
itself every turn cannot live in the system prompt, since any byte change to
the cached prefix invalidates the whole cache, and caching is ~94% of this
workload's spend. So the stable half (playstyle, personality) stays in
.boukensha/prompts/player/system.md and stays cached, and everything volatile
is injected as a MESSAGE, after the cache breakpoint. context_block() below is
that injection; it must never be spliced into the system prompt.

ROOM IDENTITY is the hard part and is handled conservatively. tbaMUD room names
are not unique ("A Dark Alley" recurs), so a room key is the name plus a short
hash of its sorted exits. A wrong key corrupts the map silently -- two rooms
merge, or one splits. The design contains that risk with an asymmetry: replaying
a recorded trail is robust to a bad key (you are following directions you
already walked), while composing a new route across two journeys is not. So
route() does exact-edge BFS over what was actually observed, and nothing
infers an edge it has not seen.

EXITS ARE NOT ASSUMED SYMMETRIC. CircleMUD supports one-way exits, so "reverse
the path by inverting each direction" is wrong in the general case. An edge is
recorded in one direction only; the reverse is recorded when it is observed.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from collections import deque
from datetime import datetime
from pathlib import Path

from ._module_state import config as boukensha_config

DIRECTIONS = ("north", "east", "south", "west", "up", "down")


class Memory:
    DEFAULT_SUBDIR = "memory"

    # ---- construction ----------------------------------------------------

    def __init__(self, character, *, dir=None):
        # Normalized HERE, at the store's own boundary, not at each call site.
        # This is the register_tool lesson from week1 (root CLAUDE.md): when two
        # code paths can both reach a shared structure, normalizing per-caller
        # leaves whichever path forgets as a silent bypass. Here the two paths
        # are the lifecycle hooks and the model-facing tools.
        self.character = self._normalize_name(character)
        base = Path(dir) if dir is not None else Path(boukensha_config().dir) / self.DEFAULT_SUBDIR
        self.path = base / self.character
        self.path.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _normalize_name(name):
        n = re.sub(r"\s+", "_", str(name or "").strip().lower())
        n = re.sub(r"[^a-z0-9_.-]", "", n)
        if not n or n in (".", ".."):
            raise ValueError(f"unusable character name for a memory store: {name!r}")
        return n

    # ---- room identity ---------------------------------------------------

    @classmethod
    def room_key(cls, name, exits=(), description=None):
        """Identifier for a room: normalized name + a short hash of its
        DESCRIPTION. Names alone collide constantly in tbaMUD.

        WHY THE DESCRIPTION AND NOT THE EXITS, which is what this used to hash.
        Measured against the captured corpus (tests/fixtures/corpus.jsonl, 23
        distinct room names), the two disagree in both directions:

          Main Street        3 descriptions, 1 exit set -- three different
                             street segments collapsing onto ONE key
          Another Corner     1 description, 2 exit sets -- one real room split
                             across TWO keys

        So exits both over- and under-merge, and the description does neither:
        only 2 of 23 names carry more than one description, and both of those
        are genuinely more than one room (the two Great Field tiles).

        The collision was not theoretical. Walking `dummy` to the Bakery on
        2026-08-04 produced a map claiming north from Main Street led to both
        the general store AND the bakery, because two street segments shared a
        key. The agent noticed before we did and wrote it in its own learnings:
        check the description, it names the nearby shops.

        The exits stay recorded on the room, they just no longer decide its
        identity -- what a room IS does not change because a door shut.
        """
        clean = re.sub(r"\s+", " ", str(name or "").strip()).lower()
        if not clean:
            return ""
        desc = re.sub(r"\s+", " ", str(description or "").strip()).lower()
        if not desc:
            # No description to go on -- a dark room, or a reply we could only
            # half-read. Fall back to the bare name rather than inventing a
            # discriminator: merging two rooms is recoverable, and a key that
            # changes once the description IS seen would strand every edge
            # already recorded under it.
            return clean
        digest = hashlib.sha1(desc.encode("utf-8")).hexdigest()[:6]
        return f"{clean}#{digest}"

    # ---- low-level file helpers ------------------------------------------

    def _read_json(self, name, default):
        p = self.path / name
        if not p.is_file():
            return default
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            # A run killed mid-write can leave a torn file. Losing memory is
            # bad; refusing to start is worse -- and the alternative (crash on
            # load) would make the agent unrunnable until a human intervened.
            return default

    def _write_json(self, name, data):
        # Write-then-rename so a crash mid-write can't truncate the real file.
        #
        # Code review: _read_json returns {} on a torn file, so without this
        # the next write would silently overwrite a corrupt-but-recoverable
        # trails.json with an empty one, destroying the whole learned map.
        # Side the damaged file rather than clobbering it -- a human can
        # salvage a truncated JSON file, but not a deleted one.
        p = self.path / name
        if p.is_file():
            try:
                json.loads(p.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                salvage = p.with_suffix(p.suffix + ".corrupt")
                try:
                    os.replace(p, salvage)
                except OSError:
                    pass
        tmp = p.with_suffix(p.suffix + ".tmp")
        tmp.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        os.replace(tmp, p)

    def _read_text(self, name):
        p = self.path / name
        return p.read_text(encoding="utf-8") if p.is_file() else ""

    def _append_line(self, name, line):
        p = self.path / name
        prefix = "" if (not p.is_file() or self._read_text(name).endswith("\n")) else "\n"
        with p.open("a", encoding="utf-8") as fh:
            fh.write(prefix + line.rstrip() + "\n")

    @staticmethod
    def _today():
        return datetime.now().astimezone().strftime("%Y-%m-%d")

    # ---- state -----------------------------------------------------------

    @property
    def state(self):
        return self._read_json("state.json", {})

    def update_state(self, **fields):
        """Merge fields into state. None values are ignored rather than stored,
        so a parse that failed to find HP doesn't erase the HP we already knew."""
        s = self.state
        s.update({k: v for k, v in fields.items() if v is not None})
        s["updated_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
        self._write_json("state.json", s)
        return s

    @property
    def goal(self):
        return self.state.get("goal")

    def set_goal(self, goal):
        return self.update_state(goal=goal)

    def live_hp(self):
        """Current HP, preferring the live value over the last `score`.

        Code review found this as a dead write: `hp_now` (an int, read off the
        status prompt that rides on nearly EVERY reply) was recorded and never
        read, while `hp` (a "cur/max" string, written only when the model calls
        `check`) was what got injected. So the memory block told the agent it
        was at full health while it was at 6/30 -- directly undercutting the
        system prompt's "flee below half HP" rule, and worse after a compaction
        or /clear, where the regenerated block is the only surviving vitals.

        Returns "cur/max" when the maximum is known, "cur" when only the live
        value is, and the last `score` reading when there is no live value.
        """
        s = self.state
        now, scored = s.get("hp_now"), s.get("hp")
        if now is None:
            return scored
        maximum = None
        if isinstance(scored, str) and "/" in scored:
            maximum = scored.split("/", 1)[1].strip() or None
        return f"{now}/{maximum}" if maximum else str(now)

    @property
    def position(self):
        return self.state.get("position")

    def set_position(self, room_key):
        return self.update_state(position=room_key)

    def clear_position(self):
        """Forget where we think we are.

        update_state ignores None (so a failed parse cannot erase a known
        value), which means callers need an explicit way to say "this is now
        unknown". Used on a fresh start: MemoryHooks declines to trust a stored
        position because anything could have happened to the character while we
        were not running -- but that rule only covered its own in-process
        belief, while context_block, render_journal and find_route all kept
        reading the stale stored value. Found by code review.
        """
        s = self.state
        s.pop("position", None)
        s["updated_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
        self._write_json("state.json", s)
        return s

    def live_moves(self):
        """Movement points, live value preferred -- same shape as live_hp."""
        s = self.state
        now, scored = s.get("moves_now"), s.get("moves")
        if now is None:
            return scored
        maximum = None
        if isinstance(scored, str) and "/" in scored:
            maximum = scored.split("/", 1)[1].strip() or None
        return f"{now}/{maximum}" if maximum else str(now)

    # ---- facts and learnings (agent-written, Markdown) -------------------

    def facts(self):
        return self._read_text("facts.md").strip()

    @staticmethod
    def _fact_key(text):
        # Collapse whitespace (including newlines) and strip the leading bullet
        # so a multi-line fact, or one the model wrote starting with "- ",
        # compares equal to its stored single-line form.
        #
        # Code review: the previous version compared the raw text against
        # per-LINE entries, so any fact containing a newline could never match
        # and duplicated on every write -- and duplicates are paid for on every
        # iteration, since facts are injected into the conversation.
        s = re.sub(r"\s+", " ", str(text or "")).strip()
        return re.sub(r"^[-*]\s*", "", s).strip().lower()

    def add_fact(self, text):
        text = re.sub(r"\s+", " ", str(text or "")).strip()
        if not text:
            return False
        key = self._fact_key(text)
        existing = {self._fact_key(line) for line in self._read_text("facts.md").splitlines()}
        if key in existing:
            return False  # already known; don't grow the file with duplicates
        self._append_line("facts.md", f"- {text}")
        return True

    def learnings(self):
        return self._read_text("learnings.md").strip()

    def add_learning(self, text):
        text = str(text or "").strip()
        if not text:
            return False
        self._append_line("learnings.md", f"- [{self._today()}] {text}")
        return True

    # ---- the map: rooms and observed edges -------------------------------

    def _map(self):
        return self._read_json("trails.json", {"rooms": {}, "edges": []})

    def rooms(self):
        return self._map()["rooms"]

    def knows_room(self, name, exits=(), description=None):
        return self.room_key(name, exits, description) in self._map()["rooms"]

    def remember_room(self, name, exits=(), description=None):
        """Record a room. Returns its key. Idempotent."""
        key = self.room_key(name, exits, description)
        if not key:
            return ""
        m = self._map()
        room = m["rooms"].get(key, {})
        room["name"] = str(name).strip()
        room["exits"] = sorted({str(e).strip().lower() for e in (exits or ()) if str(e).strip()})
        if description:
            room.setdefault("description", str(description).strip())
        room["first_seen"] = room.get("first_seen") or self._today()
        m["rooms"][key] = room
        self._write_json("trails.json", m)
        return key

    def record_move(self, from_key, direction, to_key):
        """Record one observed edge. Directed: the reverse is only recorded if
        and when it is actually walked (CircleMUD has one-way exits)."""
        d = str(direction or "").strip().lower()
        if not (from_key and to_key and d) or from_key == to_key:
            return False
        m = self._map()
        edge = [from_key, d, to_key]
        if edge in m["edges"]:
            return False
        m["edges"].append(edge)
        self._write_json("trails.json", m)
        return True

    def exits_from(self, key):
        return {d: to for f, d, to in self._map()["edges"] if f == key}

    def route(self, from_key, to_key):
        """Shortest sequence of directions from one room to another, using only
        edges actually observed. Returns None if no known path exists -- which
        is a legitimate and useful answer: it means "go explore", and it is what
        makes navigation provably non-random rather than lucky."""
        if not from_key or not to_key:
            return None
        if from_key == to_key:
            return []
        adjacency = {}
        for f, d, t in self._map()["edges"]:
            adjacency.setdefault(f, []).append((d, t))
        seen, queue = {from_key}, deque([(from_key, [])])
        while queue:
            node, path = queue.popleft()
            for d, nxt in adjacency.get(node, ()):
                if nxt in seen:
                    continue
                if nxt == to_key:
                    return path + [d]
                seen.add(nxt)
                queue.append((nxt, path + [d]))
        return None

    def find_room(self, needle):
        """Look up a room key by a loose name match ('bakery'). Returns the key
        of the first match, preferring an exact name."""
        n = str(needle or "").strip().lower()
        if not n:
            return None
        rooms = self._map()["rooms"]
        for key, room in rooms.items():
            if room.get("name", "").strip().lower() == n:
                return key
        for key, room in rooms.items():
            if n in room.get("name", "").strip().lower():
                return key
        return None

    # ---- what gets injected into the conversation ------------------------

    def context_block(self, *, max_facts=40, max_learnings=15):
        """Compact summary for injection AS A MESSAGE.

        Never put this in the system prompt: it changes every turn, and the
        system prompt is the cached prefix. Doing so would invalidate the cache
        on every single turn and make the memory and token pillars cancel each
        other out exactly.

        Truncated because every line is re-read on every iteration of the turn.
        """
        s = self.state
        out = [f"## Memory for {self.character}"]

        if s.get("goal"):
            out.append(f"\n**Current goal:** {s['goal']}")

        vitals = []
        for k in ("level", "hp", "moves", "exp", "gold"):
            v = self.live_hp() if k == "hp" else self.live_moves() if k == "moves" else s.get(k)
            if v is not None:
                vitals.append(f"{k}={v}")
        if vitals:
            out.append(f"**Character:** {', '.join(vitals)}")

        m = self._map()
        if s.get("position"):
            here = m["rooms"].get(s["position"], {})
            out.append(f"**Last known position:** {here.get('name', s['position'])}")
        out.append(f"**Map:** {len(m['rooms'])} rooms known, {len(m['edges'])} routes walked")

        if m["rooms"]:
            names = sorted({r.get("name", "") for r in m["rooms"].values() if r.get("name")})
            out.append("**Places known:** " + ", ".join(names[:25])
                       + (" ..." if len(names) > 25 else ""))

        facts = [ln for ln in self.facts().splitlines() if ln.strip()]
        if facts:
            out.append("\n### What I know\n" + "\n".join(facts[-max_facts:]))

        learnings = [ln for ln in self.learnings().splitlines() if ln.strip()]
        if learnings:
            out.append("\n### What I've learned about playing\n"
                       + "\n".join(learnings[-max_learnings:]))

        out.append(
            "\nConsult this before exploring. If a place you need is already listed, "
            "use the route you know instead of wandering."
        )
        return "\n".join(out)

    # ---- the human-readable player file ----------------------------------

    def render_journal(self, *, narrative=None):
        """Hybrid player file: the numbers are RENDERED from recorded state, so
        they structurally cannot fabricate progress; the narrative is the
        agent's own account, clearly marked as such.

        Generation cannot produce "I nearly died to the guard, so I avoid that
        room" -- and that is the part that makes today's hand-written player.md
        worth reading. Never sent to the model; this is for humans only.
        """
        s, m = self.state, self._map()
        lines = [
            f"# {self.character}",
            "",
            f"_Generated {self._today()} from recorded state. "
            "Numbers in this section are rendered from the store, not written by the agent._",
            "",
            "## Status",
        ]
        for label, key in (("Level", "level"), ("HP", "hp"), ("Experience", "exp"),
                           ("Gold", "gold"), ("Goal", "goal")):
            # HP prefers the live status-prompt value over the last `score`,
            # same reasoning as context_block -- see live_hp().
            value = self.live_hp() if key == "hp" else s.get(key)
            if value is not None:
                lines.append(f"- **{label}:** {value}")
        if s.get("position"):
            here = m["rooms"].get(s["position"], {})
            lines.append(f"- **Last seen:** {here.get('name', s['position'])}")
        lines.append(f"- **Rooms known:** {len(m['rooms'])}")
        lines.append(f"- **Routes walked:** {len(m['edges'])}")

        if self.facts():
            lines += ["", "## What it knows", "", self.facts()]
        if self.learnings():
            lines += ["", "## What it has learned", "", self.learnings()]
        if narrative:
            lines += ["", "## The agent's own account", "",
                      "_Written by the agent. Unlike the Status section above, "
                      "this is not verified against recorded state._", "",
                      str(narrative).strip()]

        text = "\n".join(lines) + "\n"
        (self.path / "journal.md").write_text(text, encoding="utf-8")
        return text

    def __repr__(self):
        m = self._map()
        return (f"#<Memory {self.character} rooms={len(m['rooms'])} "
                f"edges={len(m['edges'])} goal={self.state.get('goal')!r}>")
