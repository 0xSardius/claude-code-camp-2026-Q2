"""Regression tests for the per-character memory store (week2 memory M1).

Run:  uv run python tests/test_memory.py   (or ../bin/test)

Offline; every test uses a temp directory, so nothing touches the real
.boukensha/memory.
"""
import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("BOUKENSHA_DIR", str(Path(__file__).resolve().parent.parent.parent.parent / ".boukensha"))

from boukensha.memory import Memory  # noqa: E402


def store(name="dummy"):
    return Memory(name, dir=Path(tempfile.mkdtemp()))


TESTS = []


def test(fn):
    TESTS.append(fn)
    return fn


# --------------------------------------------------------------------------
# Keying and normalization
# --------------------------------------------------------------------------

@test
def character_names_normalize_at_the_stores_boundary():
    """The register_tool lesson from week1: normalize inside the structure, not
    at each caller. Two code paths reach this store -- lifecycle hooks and
    model-facing tools -- and whichever one forgot would be a silent bypass."""
    base = Path(tempfile.mkdtemp())
    a = Memory("Dummy", dir=base)
    b = Memory("  dummy  ", dir=base)
    assert a.character == b.character == "dummy"
    a.add_fact("shared")
    assert "shared" in b.facts()


@test
def unusable_character_names_are_rejected():
    for bad in ("", "   ", "..", "/", None):
        try:
            Memory(bad, dir=Path(tempfile.mkdtemp()))
        except ValueError:
            continue
        raise AssertionError(f"{bad!r} should have been rejected")


@test
def room_names_alone_do_not_identify_a_room():
    """tbaMUD reuses names -- 'A Dark Alley' recurs, and the corpus has three
    different 'Main Street' segments. Two rooms sharing a name must not
    collapse into one, or the map corrupts silently: walking `dummy` to the
    Bakery produced a map claiming north from Main Street led to both the
    general store and the bakery."""
    a = Memory.room_key("A Dark Alley", ["north", "south"], "Rubbish everywhere.")
    b = Memory.room_key("A Dark Alley", ["north", "south"], "A clean, quiet alley.")
    assert a != b, (a, b)

    # The same room seen twice is one key, whatever the exits looked like that
    # time. Exits are NOT identity -- the corpus has one 'Another Corner' whose
    # exits parsed two different ways, and it is one room.
    assert Memory.room_key("A Dark Alley", ["south"], "Rubbish everywhere.") == a
    assert Memory.room_key("  a dark ALLEY ", [], "  RUBBISH   everywhere. ") == a


# --------------------------------------------------------------------------
# State
# --------------------------------------------------------------------------

@test
def state_merges_and_ignores_none():
    """A parse that failed to find HP must not erase the HP we already knew."""
    m = store()
    m.update_state(level=3, hp="20/20")
    m.update_state(level=4, hp=None)
    assert m.state["level"] == 4
    assert m.state["hp"] == "20/20"


@test
def goal_and_position_round_trip():
    m = store()
    m.set_goal("Find the Bakery and list its menu")
    m.set_position("temple square#abc123")
    assert m.goal == "Find the Bakery and list its menu"
    assert m.position == "temple square#abc123"


@test
def a_torn_state_file_does_not_make_the_agent_unrunnable():
    """Losing memory is bad; refusing to start is worse."""
    m = store()
    m.update_state(level=2)
    (m.path / "state.json").write_text('{"level": 2', encoding="utf-8")  # truncated
    assert m.state == {}
    m.update_state(level=3)          # and it recovers on next write
    assert m.state["level"] == 3


@test
def writes_are_atomic():
    """Write-then-rename: a crash mid-write must not truncate the real file.

    Code review flagged the earlier version as asserting nothing about
    atomicity -- it wrote a value, read it back, and checked no .tmp remained,
    all of which a plain in-place write would also satisfy. This version makes
    the rename itself fail, which is the only way to tell the two apart: with
    write-then-rename the original survives intact; with an in-place write it
    would already be clobbered."""
    import boukensha.memory as memory_mod

    m = store()
    m.update_state(level=5, hp="20/20")
    original = (m.path / "state.json").read_text()

    real_replace = memory_mod.os.replace
    calls = []

    def exploding_replace(src, dst):
        # Let the quarantine path through; blow up on the real commit.
        if str(dst).endswith("state.json"):
            calls.append((src, dst))
            raise OSError("simulated crash between write and rename")
        return real_replace(src, dst)

    memory_mod.os.replace = exploding_replace
    try:
        try:
            m.update_state(level=99)
        except OSError:
            pass
    finally:
        memory_mod.os.replace = real_replace

    assert calls, "os.replace was never used -- write is not rename-based"
    assert (m.path / "state.json").read_text() == original, "original was clobbered"
    assert m.state["level"] == 5, m.state
    for tmp in m.path.glob("*.tmp"):
        tmp.unlink()


# --------------------------------------------------------------------------
# Facts and learnings
# --------------------------------------------------------------------------

@test
def facts_deduplicate():
    """Facts are written on observation, and the agent re-observes constantly.
    Without dedup the file grows without bound and the injected context with
    it -- and context is paid for on every iteration."""
    m = store()
    assert m.add_fact("The Bakery sells bread.") is True
    assert m.add_fact("The Bakery sells bread.") is False
    assert m.add_fact("  the bakery sells bread.  ") is False
    assert m.facts().count("Bakery") == 1


@test
def empty_facts_and_learnings_are_ignored():
    m = store()
    assert m.add_fact("") is False and m.add_fact("   ") is False
    assert m.add_learning("") is False
    assert m.facts() == "" and m.learnings() == ""


@test
def learnings_are_dated_and_appended():
    m = store()
    m.add_learning("Rats give more xp per turn than beggars.")
    m.add_learning("The guard one-shots me at level 1.")
    lines = m.learnings().splitlines()
    assert len(lines) == 2
    assert all(ln.startswith("- [20") for ln in lines), lines


# --------------------------------------------------------------------------
# The map
# --------------------------------------------------------------------------

@test
def remembering_a_room_is_idempotent():
    m = store()
    k1 = m.remember_room("Temple Square", ["north", "east"], description="A big square.")
    k2 = m.remember_room("Temple Square", ["east", "north"], description="A big square.")
    assert k1 == k2
    assert len(m.rooms()) == 1
    assert m.knows_room("Temple Square", ["north", "east"], "A big square.")
    assert not m.knows_room("Somewhere Else", [], "Elsewhere.")


@test
def a_room_first_seen_without_a_description_is_rekeyed_when_it_is_read():
    """The known cost of keying on the description. A room we could not read --
    an unlit one -- falls back to its bare name, and gets its real key once we
    see it properly. Edges recorded under the nameless key are then orphaned.

    Left this way deliberately: the alternative is a key that never improves,
    so every unlit room merges with every other room of that name forever. An
    orphaned edge costs one re-walk; a permanently merged room corrupts every
    route through it."""
    m = store()
    dark = m.remember_room("Temple Square", ["north"])
    lit = m.remember_room("Temple Square", ["north"], description="A big square.")
    assert dark != lit, (dark, lit)
    assert dark == "temple square", dark          # bare name, no discriminator
    assert "#" in lit


@test
def route_uses_only_observed_edges():
    """Composition across two separately-walked journeys is the payoff of
    storing edges rather than flat paths."""
    m = store()
    a = m.remember_room("Temple Square", ["north"])
    b = m.remember_room("Market Square", ["north", "south"])
    c = m.remember_room("The Bakery", ["south"])
    m.record_move(a, "north", b)
    m.record_move(b, "north", c)
    assert m.route(a, c) == ["north", "north"]     # composed, never walked end-to-end
    assert m.route(a, a) == []
    assert m.route(c, a) is None                   # reverse never observed


@test
def reverse_edges_are_not_assumed():
    """CircleMUD has one-way exits, so inverting a direction is wrong in the
    general case. The reverse is known only once it is walked."""
    m = store()
    a = m.remember_room("Cliff Top", ["down"])
    b = m.remember_room("Ravine Floor", ["up"])
    m.record_move(a, "down", b)
    assert m.route(b, a) is None
    m.record_move(b, "up", a)
    assert m.route(b, a) == ["up"]


@test
def no_route_is_a_useful_answer_not_a_failure():
    """'I don't know the way' is what makes navigation provably non-random --
    it means go explore, rather than guess."""
    m = store()
    a = m.remember_room("Temple Square", ["north"])
    b = m.remember_room("The Bakery", ["south"])
    assert m.route(a, b) is None


@test
def edges_deduplicate_and_reject_nonsense():
    m = store()
    a = m.remember_room("A", ["north"])
    b = m.remember_room("B", ["south"])
    assert m.record_move(a, "north", b) is True
    assert m.record_move(a, "north", b) is False   # same edge twice
    assert m.record_move(a, "north", a) is False   # self-loop
    assert m.record_move(a, "", b) is False        # no direction
    assert m.record_move("", "north", b) is False


@test
def rooms_are_findable_by_loose_name():
    m = store()
    m.remember_room("Temple Square", ["north"])
    key = m.remember_room("The Bakery", ["south"])
    assert m.find_room("The Bakery") == key
    assert m.find_room("bakery") == key            # partial, case-insensitive
    assert m.find_room("armoury") is None


# --------------------------------------------------------------------------
# Injection and the player file
# --------------------------------------------------------------------------

@test
def context_block_carries_what_the_agent_needs_to_not_wander():
    m = store()
    m.set_goal("Find the Bakery")
    m.update_state(level=4, hp="30/30")
    a = m.remember_room("Temple Square", ["north"])
    m.set_position(a)
    m.add_fact("The Bakery is north of Market Square.")
    m.add_learning("Rats are better xp than beggars.")
    block = m.context_block()
    for expected in ("Find the Bakery", "level=4", "Temple Square",
                     "1 rooms known", "north of Market Square", "Rats are better"):
        assert expected in block, (expected, block)


@test
def context_block_is_truncated():
    """Every line is re-read on every iteration of the turn, so this cannot
    grow without bound as the store does."""
    m = store()
    for i in range(200):
        m.add_fact(f"Fact number {i}.")
    block = m.context_block(max_facts=10)
    assert block.count("Fact number") == 10
    assert "Fact number 199." in block      # keeps the most recent
    assert "Fact number 0." not in block


@test
def journal_separates_generated_numbers_from_the_agents_account():
    """The numbers are rendered from recorded state so they cannot fabricate
    progress; the narrative is marked as unverified."""
    m = store()
    m.update_state(level=4, exp=5018)
    m.remember_room("Temple Square", ["north"])
    text = m.render_journal(narrative="I nearly died to the guard, so I avoid that room.")
    assert "**Level:** 4" in text
    assert "Rooms known:** 1" in text
    assert "nearly died to the guard" in text
    assert "not verified against recorded state" in text
    assert (m.path / "journal.md").is_file()


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
