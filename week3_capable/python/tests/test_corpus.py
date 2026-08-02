"""Run the perception layer against every real captured output (week3 M1).

    uv run python tests/test_corpus.py   (or ../bin/test)

This is the test week 2 should have had. Its parser tests asserted against
strings I typed by hand, which matched my idea of CircleMUD's format rather
than the server's -- so `_plausible_title` shipped believing room titles are
short, unpunctuated, and never preceded by anything.

These assert against 437 distinct outputs the game really sent. When a live run
surfaces a shape the corpus lacks, it gets captured back in (rerun extract.py)
and this file starts covering it automatically.
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("BOUKENSHA_DIR", str(Path(__file__).resolve().parent.parent.parent.parent / ".boukensha"))

from boukensha.mud_parse import parse_exits, parse_room, parse_score, parse_status, strip_ansi  # noqa: E402
from tests.fixtures import Fixtures  # noqa: E402

TESTS = []


def test(fn):
    TESTS.append(fn)
    return fn


@test
def the_corpus_is_present_and_plausible():
    all_ = Fixtures.all()
    assert len(all_) > 400, f"only {len(all_)} fixtures -- rerun extract.py?"
    assert len(Fixtures.rooms()) > 200
    assert Fixtures.for_tool("attack") and Fixtures.for_tool("check")


@test
def every_room_bearing_reply_parses():
    """No silent declines. A decline means memory records nothing for that
    move, and week 2 showed that a missed room is how a fabricated map edge
    gets created two moves later."""
    failures = []
    for f in Fixtures.rooms():
        if parse_room(f.text) is None:
            failures.append((f.id, f.first_line()[:60]))
    assert not failures, f"{len(failures)} room replies declined: {failures[:5]}"


@test
def no_parsed_room_name_is_prose():
    """The phantom-room failure: a line of narration becomes the room NAME and
    a fake node is written to the map permanently. Detected structurally --
    real CircleMUD titles are title-case labels, not sentences."""
    bad = []
    for f in Fixtures.rooms():
        name = parse_room(f.text)["name"]
        if name.endswith((".", "!", "?", ",", ";", ":")) or len(name) > 60:
            bad.append((f.id, name[:60]))
    assert not bad, f"prose parsed as a room name: {bad[:5]}"


@test
def narration_before_a_room_does_not_become_the_room():
    """The specific shape that breaks naive first-line parsing. Both real
    occurrences are in the corpus: a hunger/thirst tick, and a mob arriving.
    Neither is invented -- and neither is one I would have thought to write."""
    cases = Fixtures.tagged("preamble_before_room")
    assert cases, "corpus lost its preamble cases -- rerun extract.py"
    for f in cases:
        room = parse_room(f.text)
        assert room, f.id
        first = f.first_line()
        assert room["name"] != first, (
            f"{f.id}: narration {first[:40]!r} became the room name"
        )


@test
def exits_parse_wherever_the_game_emits_them():
    for f in Fixtures.rooms():
        exits = parse_exits(f.text)
        assert exits is not None, f.id
        assert all(e in ("north", "east", "south", "west", "up", "down") for e in exits), (f.id, exits)


@test
def vitals_come_off_the_status_prompt_wherever_it_appears():
    """Nearly every reply carries the trailing prompt, which makes it the
    cheapest vitals source there is -- and the one that keeps HP live between
    `score` calls."""
    withprompt = [f for f in Fixtures.all() if "status_prompt" in (f.tags or ())]
    assert len(withprompt) > 300, len(withprompt)
    for f in withprompt:
        s = parse_status(f.text)
        assert s and s["hp"] >= 0 and s["moves"] >= 0, (f.id, s)


@test
def every_score_reply_yields_a_level():
    scores = [f for f in Fixtures.for_tool("check") if "hit," in strip_ansi(f.text)]
    assert scores, "no score replies in the corpus"
    for f in scores:
        parsed = parse_score(f.text)
        assert parsed and "level" in parsed and "hp" in parsed, (f.id, parsed)


@test
def non_room_replies_are_declined_not_guessed():
    """`attack`, `consider` and `get_item` share tool names with nothing, but a
    parser that guessed a room out of combat text would poison the map."""
    for f in Fixtures.for_tool("attack", "consider", "get_item", "set_position"):
        assert parse_room(f.text) is None, (f.tool, f.id, f.first_line()[:50])


if __name__ == "__main__":
    failures = 0
    for fn in TESTS:
        try:
            fn()
        except Exception as e:  # noqa: BLE001
            failures += 1
            print(f"FAIL  {fn.__name__}: {type(e).__name__}: {e}")
        else:
            print(f"ok    {fn.__name__}")
    print(f"\n{len(TESTS) - failures}/{len(TESTS)} passed")
    sys.exit(1 if failures else 0)
