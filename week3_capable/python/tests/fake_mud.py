"""A stand-in for the MUD connection (week3 harness M2).

NOT a MUD. It replays text the real server sent us and tracks which room you
are in. It never calculates a game outcome — no combat maths, no monster
behaviour, no inventory rules. The moment it needs to decide whether an attack
lands, it has turned into a MUD and has gone too far; test that against the
real server instead.

What it buys, now that we know the whole project has cost $10 in model calls
and cost is not the constraint:

  speed           an offline check is milliseconds; a live run is 60-90s and
                  needs the server up. You run combat logic hundreds of times
                  while building it.
  reproducibility you cannot ask a real server to drop the connection mid-turn,
                  or have a mob attack on a chosen tick. Every one of week 2's
                  worst bugs lived on a path like that.
  safety          a buggy combat loop turned loose on `dummy` can get it
                  killed, and that character carries the real progress.

    from tests.fake_mud import FakeSession
    s = FakeSession()
    s.open(); s.login("boukensha", "x")
    s.send_command("north"); s.read_until_prompt()   # real captured room text

    s.fail_next("disconnect")     # or: refuse_move, no_movement, attacked, death
"""
from __future__ import annotations

import re
from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from boukensha.mud_parse import parse_room  # noqa: E402
from tests.fixtures import Fixtures  # noqa: E402

PROMPT = "\r\n{hp}H 100M {mv}V (news) (motd) > "

# A small connected map, wired by hand from rooms the agent really visited.
# Directions come from the edges it actually walked (see the committed
# .boukensha/memory/boukensha/trails.json), so the topology is real too.
MAP = {
    "The Temple Of Midgaard": {"south": "The Temple Square"},
    "The Temple Square": {"north": "The Temple Of Midgaard", "south": "Market Square"},
    "Market Square": {"north": "The Temple Square", "west": "Main Street"},
    "Main Street": {"east": "Market Square", "north": "The Bakery"},
    "The Bakery": {"south": "Main Street"},
}
START = "The Temple Of Midgaard"

DIRECTIONS = {"north", "east", "south", "west", "up", "down",
              "n", "e", "s", "w", "u", "d"}
LONG = {"n": "north", "e": "east", "s": "south", "w": "west", "u": "up", "d": "down"}


class FakeDisconnect(Exception):
    """Raised where the real Session would raise on a dead socket."""


def _room_texts():
    """Real captured text for each room in MAP, keyed by room name."""
    out = {}
    for f in Fixtures.rooms():
        room = parse_room(f.text)
        if room and room["name"] in MAP and room["name"] not in out:
            out[room["name"]] = f.text
    missing = set(MAP) - set(out)
    if missing:
        raise RuntimeError(f"no captured text for {missing} -- rerun extract.py")
    return out


class FakeSession:
    """Same surface as boukensha.mud_session.Session, replaying fixtures."""

    def __init__(self, *, host="localhost", port=4000, start=START):
        self.host, self.port = host, port
        self._open = False
        self._rooms = _room_texts()
        self.room = start
        self.hp, self.max_hp = 30, 30
        self.moves, self.max_moves = 85, 85
        self.dead = False
        self._pending = ""
        self._fail = None
        self.sent = []          # every command, for assertions

    # ---- failure injection ----------------------------------------------

    def fail_next(self, kind):
        """Arm a failure for the next command. The whole point of this class:
        these are the situations you cannot summon against a live server, and
        they are where week 2's real bugs were."""
        if kind not in ("disconnect", "refuse_move", "no_movement", "attacked", "death"):
            raise ValueError(f"unknown failure {kind!r}")
        self._fail = kind

    # ---- Session surface -------------------------------------------------

    def open(self):
        self._open = True
        self._pending = "Welcome to CircleMUD!\r\n"
        return self

    def is_open(self):
        return self._open

    def close(self):
        self._open = False

    def login(self, username, password):
        if not self._open:
            raise FakeDisconnect("session not open")
        self._pending = self._render(self.room)
        return self._pending

    def drain(self):
        out, self._pending = self._pending, ""
        return out

    def send_command(self, command):
        if not self._open:
            raise FakeDisconnect("session not open")
        line = getattr(command, "raw", command)
        line = "" if line is None else str(line)
        self.sent.append(line)
        self._pending = self._respond(line.strip().lower())
        return line

    send = send_command

    def read_until_prompt(self, timeout=None, quiet_seconds=0.3):
        return self.drain()

    def read_until_quiet(self, quiet_seconds=1.0, timeout=None):
        return self.drain()

    # ---- responses -------------------------------------------------------

    def _render(self, room_name, prefix=""):
        text = self._rooms[room_name]
        # Swap in live vitals so the status prompt reflects our state; the room
        # body itself stays exactly as the server sent it.
        text = re.sub(r"\r?\n\d+H \d+M \d+V[^>]*>\s*$", "", text)
        return prefix + text + PROMPT.format(hp=self.hp, mv=self.moves)

    def _respond(self, cmd):
        fail, self._fail = self._fail, None

        if fail == "disconnect":
            self._open = False
            raise FakeDisconnect("connection reset by peer")
        if fail == "death":
            self.dead, self.hp = True, 0
            self.room = START
            return self._render(START, "You are dead!  Sorry...\r\n")
        if fail == "attacked":
            return ("The newbie monster hits you hard!\r\n"
                    + PROMPT.format(hp=max(self.hp - 12, 1), mv=self.moves))
        if fail == "no_movement":
            self.moves = 0
            return "You are too exhausted." + PROMPT.format(hp=self.hp, mv=0)
        if fail == "refuse_move":
            return "Alas, you cannot go that way." + PROMPT.format(hp=self.hp, mv=self.moves)

        if cmd in DIRECTIONS:
            direction = LONG.get(cmd, cmd)
            dest = MAP[self.room].get(direction)
            if dest is None:
                return "Alas, you cannot go that way." + PROMPT.format(hp=self.hp, mv=self.moves)
            if self.moves <= 0:
                return "You are too exhausted." + PROMPT.format(hp=self.hp, mv=0)
            self.room = dest
            self.moves -= 1
            return self._render(dest)

        if cmd.startswith("look") or cmd == "l":
            return self._render(self.room)

        if cmd in ("rest", "sleep", "sit"):
            self.moves = min(self.moves + 20, self.max_moves)
            return "You sit down and rest your tired bones." + PROMPT.format(hp=self.hp, mv=self.moves)
        if cmd in ("stand", "wake"):
            return "You stand up." + PROMPT.format(hp=self.hp, mv=self.moves)

        # Anything we have not taught it: replay a real captured reply for that
        # command family if we have one, else CircleMUD's own fallback. It must
        # never invent game text.
        for tool, verb in (("check", "score"), ("consider", "consider"),
                           ("attack", "kill"), ("shop", "list")):
            if cmd.startswith(verb):
                got = Fixtures.for_tool(tool)
                if got:
                    return got[0].text
        return "Huh?!?" + PROMPT.format(hp=self.hp, mv=self.moves)
