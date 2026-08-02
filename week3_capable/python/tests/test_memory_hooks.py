"""Regression tests for MUD output parsing and the memory lifecycle handlers
(week2 memory M3).

Run:  uv run python tests/test_memory_hooks.py   (or ../bin/test)

The room/score samples below are REAL output captured from the live server
during the week2 smoke run, ANSI codes and all -- not invented. A parser tested
only against hand-written samples tends to encode the author's idea of the
format rather than the server's.
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
from boukensha.mud_parse import parse_exits, parse_room, parse_score, parse_status  # noqa: E402

LOOK = (
    "\x1b[0;33mThe Temple Of Midgaard\x1b[0m\n"
    "   You are in the southern end of the temple hall in the Temple of Midgaard.\n"
    "The temple has been constructed from giant marble blocks, eternal in\n"
    "appearance, and most of the walls are covered by ancient wall paintings.\n"
    "\x1b[0;36m[ Exits: n e s w d ]\x1b[0m\n"
    "\x1b[0;32mAn automatic teller machine has been installed in the wall here.\n"
    "\x1b[0m\n"
    "25H 100M 85V (news) (motd) > "
)

SCORE = (
    "You are 17 years old.\n"
    "You have 25(25) hit, 100(100) mana and 85(85) movement points.\n"
    "Your armor class is 100/10, and your alignment is 0.\n"
    "You have 1 exp, 0 gold coins, and 0 questpoints.\n"
    "You need 1999 exp to reach your next level.\n"
    "This ranks you as Boukensha the Swordpupil (level 1).\n"
    "You are standing.\n\n"
    "25H 100M 85V (news) (motd) >"
)


def store():
    return Memory("dummy", dir=Path(tempfile.mkdtemp()))


def fire_tool(hooks, name, args, result, ok=True, context=None, registry=None):
    p = HookPayload(Hook.AFTER_TOOL, context=context, registry=registry, logger=None,
                    name=name, args=args, result=result, ok=ok, error=None)
    return hooks.fire(Hook.AFTER_TOOL, p)


TESTS = []


def test(fn):
    TESTS.append(fn)
    return fn


# --------------------------------------------------------------------------
# Parsing
# --------------------------------------------------------------------------

@test
def parses_a_real_room():
    r = parse_room(LOOK)
    assert r["name"] == "The Temple Of Midgaard", r
    assert r["exits"] == ["down", "east", "north", "south", "west"], r
    assert "southern end of the temple hall" in r["description"]


@test
def parses_a_real_score():
    s = parse_score(SCORE)
    assert s["level"] == 1 and s["hp"] == "25/25" and s["exp"] == 1
    assert s["gold"] == 0 and s["exp_to_level"] == 1999
    assert s["title"] == "Boukensha the Swordpupil"
    assert s["position_state"] == "standing"


@test
def parses_vitals_off_the_trailing_prompt():
    """Nearly every reply carries the status prompt, which makes it the
    cheapest vitals source there is."""
    assert parse_status(LOOK) == {"hp": 25, "mana": 100, "moves": 85}


@test
def keeps_the_last_status_prompt_not_the_first():
    """Earlier prompts in a multi-command reply are already stale."""
    two = "10H 5M 5V > \nYou quaff a potion.\n25H 100M 85V > "
    assert parse_status(two)["hp"] == 25


@test
def parsers_decline_rather_than_guess():
    """A wrong fact is worse than a missing one: a misparsed room name corrupts
    the map silently and every later route inherits the error."""
    for junk in ("", None, "error: not connected — call mud_connect first",
                 "You walk north.\n\n25H 100M 85V > ",
                 "The Temple Of Midgaard\n  prose\n25H 100M 85V > "):   # no exits line
        assert parse_room(junk) is None, junk
    assert parse_score("nothing useful here") is None
    assert parse_exits("no exits here") is None


@test
def exit_abbreviations_expand():
    assert parse_exits("[ Exits: n e s w u d ]") == ["down", "east", "north", "south", "up", "west"]
    assert parse_exits("[ Exits: North, South ]") == ["north", "south"]
    assert parse_exits("[ Exits: none ]") == []


# --------------------------------------------------------------------------
# Handlers
# --------------------------------------------------------------------------

@test
def walking_into_a_room_records_it_without_being_asked():
    """The point of doing this in a hook rather than a tool: it happens whether
    or not the model remembered to ask for it."""
    mem, hooks = store(), Hooks()
    MemoryHooks(mem).install(hooks)
    fire_tool(hooks, "look", {}, LOOK)
    assert len(mem.rooms()) == 1
    assert mem.position == Memory.room_key("The Temple Of Midgaard",
                                           ["down", "east", "north", "south", "west"])


@test
def moving_records_the_edge_it_walked():
    mem, hooks = store(), Hooks()
    MemoryHooks(mem).install(hooks)
    fire_tool(hooks, "look", {}, LOOK)
    fire_tool(hooks, "move", {"direction": "north"},
              LOOK.replace("The Temple Of Midgaard", "The Temple Square"))
    a = mem.find_room("The Temple Of Midgaard")
    b = mem.find_room("The Temple Square")
    assert mem.route(a, b) == ["north"]
    assert mem.route(b, a) is None, "reverse must not be inferred"


@test
def a_score_check_updates_vitals():
    mem, hooks = store(), Hooks()
    MemoryHooks(mem).install(hooks)
    fire_tool(hooks, "check", {"kind": "score"}, SCORE)
    assert mem.state["level"] == 1 and mem.state["exp"] == 1


@test
def a_failed_tool_records_nothing():
    mem, hooks = store(), Hooks()
    MemoryHooks(mem).install(hooks)
    fire_tool(hooks, "look", {}, "error: not connected", ok=False)
    assert mem.rooms() == {} and mem.position is None


@test
def flee_marks_position_unknown():
    """flee goes in a RANDOM direction, so afterwards we genuinely do not know
    where we are. This is the case that most needs a real look."""
    mem, hooks = store(), Hooks()
    mh = MemoryHooks(mem).install(hooks)
    fire_tool(hooks, "look", {}, LOOK)
    mh._needs_look = False
    fire_tool(hooks, "flee", {}, "You flee head over heels.\n25H 100M 85V > ")
    assert mh._needs_look is True


@test
def memory_is_injected_as_a_message_never_into_the_system_prompt():
    """The system prompt is the cached prefix. Putting per-turn content there
    would invalidate the cache every turn and cancel out the token pillar."""
    mem, hooks = store(), Hooks()
    MemoryHooks(mem).install(hooks)
    mem.set_goal("Find the Bakery")
    ctx = Context(system="STABLE SYSTEM PROMPT", context_window=1_000_000)
    hooks.fire(Hook.BEFORE_TURN, HookPayload(Hook.BEFORE_TURN, context=ctx,
                                             registry=None, logger=None))
    assert ctx.system == "STABLE SYSTEM PROMPT", "system prompt was modified"
    assert len(ctx.messages) == 1
    assert "Find the Bakery" in str(ctx.messages[0].content)


@test
def before_model_tracks_rather_than_polls():
    """A real `look` only when the belief is stale -- otherwise ~119 extra round
    trips in a session the size of week1's longest."""
    calls = []

    class FakeRegistry:
        def dispatch(self, name, args):
            calls.append(name)
            return LOOK

    mem, hooks = store(), Hooks()
    mh = MemoryHooks(mem, registry=FakeRegistry()).install(hooks)
    ctx = Context(system="s", context_window=1_000_000)

    def before_model():
        hooks.fire(Hook.BEFORE_MODEL, HookPayload(Hook.BEFORE_MODEL, context=ctx,
                                                  registry=None, logger=None, iteration=1))

    mh._needs_look = True
    before_model()          # stale -> looks
    before_model()          # belief fresh -> must NOT look again
    before_model()
    assert calls == ["look"], calls


@test
def a_disconnected_look_does_not_spin_or_crash():
    class Broken:
        def dispatch(self, name, args):
            raise RuntimeError("not connected")

    mem, hooks = store(), Hooks()
    mh = MemoryHooks(mem, registry=Broken()).install(hooks)
    ctx = Context(system="s", context_window=1_000_000)
    mh._needs_look = True
    hooks.fire(Hook.BEFORE_MODEL, HookPayload(Hook.BEFORE_MODEL, context=ctx,
                                              registry=None, logger=None, iteration=1))
    assert mh._needs_look is False, "must clear the flag so it doesn't retry every iteration"


@test
def after_turn_writes_the_player_file():
    mem, hooks = store(), Hooks()
    MemoryHooks(mem).install(hooks)
    fire_tool(hooks, "check", {"kind": "score"}, SCORE)
    hooks.fire(Hook.AFTER_TURN, HookPayload(Hook.AFTER_TURN, context=None, registry=None,
                                            logger=None, reason="completed", text="done",
                                            iterations=1, tokens=10))
    journal = (mem.path / "journal.md").read_text()
    assert "**Level:** 1" in journal


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
