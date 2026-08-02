"""Loader for the real-output fixture corpus (week3 harness M1).

    from tests.fixtures import Fixtures

    Fixtures.all()                      # every distinct captured output
    Fixtures.for_tool("move")           # by tool
    Fixtures.tagged("preamble_before_room")
    Fixtures.rooms()                    # move/look replies that carry a room

Every record is text the MUD really sent, pulled from the committed session
logs by extract.py and deduplicated. Nothing here is hand-written, which is the
point: week 2's parser was tested against samples that matched my mental model
of the format rather than the server's.
"""
from __future__ import annotations

import json
from pathlib import Path

CORPUS = Path(__file__).resolve().parent / "corpus.jsonl"


class Fixture:
    __slots__ = ("id", "tool", "ok", "tags", "seen", "source", "text")

    def __init__(self, record):
        for k in self.__slots__:
            setattr(self, k, record.get(k))

    def first_line(self):
        from boukensha.mud_parse import strip_ansi
        return next((ln.strip() for ln in strip_ansi(self.text).splitlines() if ln.strip()), "")

    def __repr__(self):
        return f"#<Fixture {self.id} {self.tool} seen={self.seen} {self.first_line()[:40]!r}>"


class Fixtures:
    _cache = None

    @classmethod
    def all(cls):
        if cls._cache is None:
            if not CORPUS.is_file():
                raise FileNotFoundError(
                    f"{CORPUS} missing -- run: uv run python tests/fixtures/extract.py"
                )
            cls._cache = [
                Fixture(json.loads(line))
                for line in CORPUS.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
        return cls._cache

    @classmethod
    def for_tool(cls, *tools):
        return [f for f in cls.all() if f.tool in tools]

    @classmethod
    def tagged(cls, *tags):
        want = set(tags)
        return [f for f in cls.all() if want.issubset(set(f.tags or ()))]

    @classmethod
    def rooms(cls):
        """Replies that actually carry a room description. `look <target>` and
        combat results share the same tool names but are not rooms."""
        return [f for f in cls.for_tool("move", "look") if "has_exits" in (f.tags or ())]

    @classmethod
    def get(cls, fixture_id):
        return next((f for f in cls.all() if f.id == fixture_id), None)
