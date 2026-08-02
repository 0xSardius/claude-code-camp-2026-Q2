"""The offline stand-in, and the real system running against it (week3 M2/M3).

    uv run python tests/test_fake_mud.py   (or ../bin/test)

The first few tests check the stand-in itself. The ones that matter are the
last group: the real memory pipeline driven through reproducible failures --
the situations you cannot summon against a live server, and where every one of
week 2's worst bugs lived.
"""
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("BOUKENSHA_DIR", str(Path(__file__).resolve().parent.parent.parent.parent / ".boukensha"))

from boukensha.context import Context  # noqa: E402
from boukensha.hooks import Hook, HookPayload, Hooks  # noqa: E402
from boukensha.memory import Memory  # noqa: E402
from boukensha.memory_hooks import MemoryHooks  # noqa: E402
from boukensha.mud_parse import parse_room  # noqa: E402
from boukensha.registry import Registry  # noqa: E402
from boukensha.tools import mud as mud_tools  # noqa: E402
from tests.fake_mud import FakeDisconnect, FakeSession  # noqa: E402

TESTS = []


def test(fn):
    TESTS.append(fn)
    return fn


def wired():
    """The REAL tool layer and memory pipeline, on a fake connection."""
    fake = FakeSession()
    ctx = Context(system="s", context_window=1_000_000)
    registry = Registry(ctx)
    mud_tools.register(registry, name="boukensha", password="x", session=fake)
    memory = Memory("t", dir=Path(tempfile.mkdtemp()))
    hooks = Hooks()
    mh = MemoryHooks(memory, registry=registry).install(hooks)
    return fake, registry, memory, hooks, mh


def after_tool(hooks, name, args, result, ok=True):
    hooks.fire(Hook.AFTER_TOOL, HookPayload(Hook.AFTER_TOOL, context=None, registry=None,
                                            logger=None, name=name, args=args,
                                            result=result, ok=ok, error=None))


# ---- the stand-in itself --------------------------------------------------

@test
def it_serves_real_captured_text():
    """Not invented game text -- every room body is what the server sent."""
    s = FakeSession()
    s.open()
    s.login("boukensha", "x")
    room = parse_room(s.read_until_prompt())
    assert room and room["name"] == "The Temple Of Midgaard", room


@test
def movement_composes_over_the_real_topology():
    """The route the agent actually walked in the bakery run, offline."""
    s = FakeSession()
    s.open()
    s.login("boukensha", "x")
    s.drain()
    names = []
    for d in ("south", "south", "west", "north"):
        s.send_command(d)
        names.append(parse_room(s.read_until_prompt())["name"])
    assert names == ["The Temple Square", "Market Square", "Main Street", "The Bakery"], names


@test
def it_refuses_to_invent_game_text():
    """A command it has not been taught gets CircleMUD's own fallback or a real
    captured reply -- never something made up. The moment it starts computing
    outcomes it has become a MUD."""
    s = FakeSession()
    s.open()
    s.login("boukensha", "x")
    s.drain()
    s.send_command("flibbertigibbet")
    assert "Huh?!?" in s.read_until_prompt()


@test
def every_failure_mode_fires_on_demand():
    for kind in ("refuse_move", "no_movement", "attacked", "death"):
        s = FakeSession()
        s.open()
        s.login("boukensha", "x")
        s.drain()
        s.fail_next(kind)
        s.send_command("south")
        assert s.read_until_prompt(), kind

    s = FakeSession()
    s.open()
    s.login("boukensha", "x")
    s.fail_next("disconnect")
    try:
        s.send_command("south")
    except FakeDisconnect:
        assert not s.is_open()
    else:
        raise AssertionError("disconnect did not raise")


# ---- the real system, driven through those failures -----------------------

@test
def the_real_tool_layer_runs_unchanged_against_it():
    """tools/mud.py is the shipping code, not a copy. If this passes, offline
    tests are exercising the same path a live run does."""
    fake, registry, _, _, _ = wired()
    assert "connected" in registry.dispatch("mud_connect", {}).lower()
    assert parse_room(registry.dispatch("look", {}))["name"] == "The Temple Of Midgaard"
    registry.dispatch("move", {"direction": "south"})
    assert fake.room == "The Temple Square"


@test
def walking_the_map_records_it_correctly():
    fake, registry, memory, hooks, _ = wired()
    registry.dispatch("mud_connect", {})
    after_tool(hooks, "look", {}, registry.dispatch("look", {}))
    for d in ("south", "south", "west", "north"):
        after_tool(hooks, "move", {"direction": d}, registry.dispatch("move", {"direction": d}))

    start = memory.find_room("The Temple Of Midgaard")
    bakery = memory.find_room("The Bakery")
    assert memory.route(start, bakery) == ["south", "south", "west", "north"]


@test
def a_refused_move_does_not_fabricate_an_edge():
    """The bug class that cost us a permanent map corruption in week 2: an
    unparseable move reply left the position stale, so the NEXT successful move
    recorded an edge between two rooms that are not adjacent. Reproducible here
    on demand; not reproducible at all against a live server."""
    fake, registry, memory, hooks, _ = wired()
    registry.dispatch("mud_connect", {})
    after_tool(hooks, "look", {}, registry.dispatch("look", {}))

    fake.fail_next("refuse_move")
    after_tool(hooks, "move", {"direction": "north"}, registry.dispatch("move", {"direction": "north"}))
    after_tool(hooks, "move", {"direction": "south"}, registry.dispatch("move", {"direction": "south"}))

    for frm, direction, to in memory._map()["edges"]:
        assert not (frm == memory.find_room("The Temple Of Midgaard") and direction == "south"
                    and to == memory.find_room("Market Square")), "fabricated a non-adjacent edge"


@test
def death_relocates_and_the_map_is_not_corrupted():
    """Death teleports you to the temple. Nothing should record an edge from
    wherever you died to where you respawned."""
    fake, registry, memory, hooks, _ = wired()
    registry.dispatch("mud_connect", {})
    after_tool(hooks, "look", {}, registry.dispatch("look", {}))
    after_tool(hooks, "move", {"direction": "south"}, registry.dispatch("move", {"direction": "south"}))
    before = list(memory._map()["edges"])

    fake.fail_next("death")
    after_tool(hooks, "move", {"direction": "south"}, registry.dispatch("move", {"direction": "south"}))

    new = [e for e in memory._map()["edges"] if e not in before]
    assert not new, f"death invented an edge: {new}"


@test
def a_disconnect_mid_turn_does_not_kill_the_turn():
    """The connection drops constantly in real play. The tool layer must turn
    that into an error string the agent can act on, not an exception that
    unwinds the turn."""
    fake, registry, _, _, mh = wired()
    registry.dispatch("mud_connect", {})
    fake.fail_next("disconnect")
    result = registry.dispatch("move", {"direction": "south"})
    assert isinstance(result, str) and "error" in result.lower(), result
    assert not fake.is_open()


@test
def exhaustion_is_visible_rather_than_silent():
    """Running out of movement is the commonest thing that stalls a grind. It
    has to be legible to whatever decides to rest."""
    fake, registry, memory, hooks, _ = wired()
    registry.dispatch("mud_connect", {})
    fake.fail_next("no_movement")
    out = registry.dispatch("move", {"direction": "south"})
    after_tool(hooks, "move", {"direction": "south"}, out)
    assert "exhausted" in out.lower()
    assert memory.state.get("moves_now") == 0, memory.state


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
