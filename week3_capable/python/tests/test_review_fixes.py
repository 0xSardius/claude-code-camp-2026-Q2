"""Regression tests for the defects found by the week2 code review.

Run:  uv run python tests/test_review_fixes.py   (or ../bin/test)

One test per confirmed finding that was fixed. Kept in their own file rather
than scattered into the existing suites, because as a set they are the evidence
that the review was acted on -- and because every one of them describes a bug
the original tests were happy with.

That last point is the reason the review was worth running at all: 69 tests
passed against every one of these.
"""
import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("BOUKENSHA_DIR", str(Path(__file__).resolve().parent.parent.parent.parent / ".boukensha"))

from boukensha.agent import Agent  # noqa: E402
from boukensha.backends.anthropic import Anthropic  # noqa: E402
from boukensha.context import Context  # noqa: E402
from boukensha.errors import ApiError, TurnInterrupted  # noqa: E402
from boukensha.hooks import Hook, HookPayload, Hooks  # noqa: E402
from boukensha.logger import Logger  # noqa: E402
from boukensha.memory import Memory  # noqa: E402
from boukensha.memory_hooks import MemoryHooks  # noqa: E402
from boukensha.mud_parse import parse_room  # noqa: E402
from boukensha.prompt_builder import PromptBuilder  # noqa: E402
from boukensha.registry import Registry  # noqa: E402
from boukensha.report import SessionReport  # noqa: E402

ROOM = "The Temple Of Midgaard\n   prose here.\n[ Exits: n e s ]\n25H 100M 85V > "
MARKET = ROOM.replace("The Temple Of Midgaard", "The Market Square")


def store():
    return Memory("t", dir=Path(tempfile.mkdtemp()))


def fire_tool(hooks, name, args, result, ok=True):
    hooks.fire(Hook.AFTER_TOOL, HookPayload(Hook.AFTER_TOOL, context=None, registry=None,
                                            logger=None, name=name, args=args,
                                            result=result, ok=ok, error=None))


TESTS = []


def test(fn):
    TESTS.append(fn)
    return fn


# ---- HIGH -----------------------------------------------------------------

@test
def injected_hp_is_live_not_the_last_score():
    """hp_now was written on nearly every reply and read by nothing, so the
    memory block reported the HP from the last `check` -- telling the agent it
    was at full health at 6/30, and directly undercutting the system prompt's
    flee-below-half rule."""
    m = store()
    m.update_state(level=3, hp="30/30")     # from `check`
    m.update_state(hp_now=6)                # from a combat reply's status prompt
    assert "hp=6/30" in m.context_block()
    assert "- **HP:** 6/30" in m.render_journal()


@test
def live_hp_works_before_any_score_call():
    """The commoner manifestation was absence, not staleness: with no `check`
    ever called, the vitals line was omitted entirely while hp_now sat
    recorded."""
    m = store()
    m.update_state(hp_now=25)
    assert "hp=25" in m.context_block()


@test
def an_unparseable_move_does_not_fabricate_an_edge():
    """A dark room has no exits line, so parse_room declines and _position was
    left on the room already left -- letting the NEXT move record an edge
    between two non-adjacent rooms, persisted forever and handed back by
    find_route as a confident wrong direction."""
    m, h = store(), Hooks()
    MemoryHooks(m).install(h)
    fire_tool(h, "look", {}, ROOM)
    fire_tool(h, "move", {"direction": "north"}, "It is pitch black...\n25H 100M 85V > ")
    fire_tool(h, "move", {"direction": "east"}, MARKET)
    assert m._map()["edges"] == [], m._map()["edges"]


@test
def two_unparseable_moves_in_one_batch_still_record_nothing():
    """_needs_look alone would not have been enough: after_tool fires per tool
    while before_model fires per iteration, so a repair look cannot run between
    two moves in the same batch. Clearing _position is what makes it safe."""
    m, h = store(), Hooks()
    MemoryHooks(m).install(h)
    fire_tool(h, "look", {}, ROOM)
    fire_tool(h, "move", {"direction": "north"}, "It is pitch black...")
    fire_tool(h, "move", {"direction": "east"}, "It is pitch black...")
    fire_tool(h, "move", {"direction": "south"}, MARKET)
    assert m._map()["edges"] == []


@test
def speech_and_connect_lines_are_not_mistaken_for_rooms():
    """parse_room took the first non-blank line above the exits block and only
    then validated it, so anything printed just before a room -- a mob talking,
    a gossip line, mud_connect's own banner -- became the room NAME, and a
    phantom room and its edges were written permanently."""
    for prefix in ("Puff says, 'What a lovely day this is.'\n",
                   "Bob gossips, 'anyone selling a longsword'\n",
                   "connected to localhost:4000\nWelcome back!\n"):
        r = parse_room(prefix + ROOM)
        assert r and r["name"] == "The Temple Of Midgaard", (prefix, r)


@test
def turn_budget_charges_cache_writes():
    """Cache writes bill at 1.25x -- MORE than fresh input -- and were charged
    zero. Every iteration extends the prefix, so every iteration writes: a long
    turn could spend six figures of token-equivalents while turn_tokens read a
    few thousand and the budget never tripped."""
    ctx = Context(system="s", context_window=1_000_000)
    a = Agent(context=ctx, registry=Registry(ctx),
              builder=PromptBuilder(ctx, Anthropic(api_key="x", model="claude-sonnet-5")),
              client=None, logger=Logger(dir=tempfile.mkdtemp()))
    a._record_usage({"usage": {"input_tokens": 4, "output_tokens": 200,
                               "cache_creation_input_tokens": 20_000,
                               "cache_read_input_tokens": 0}})
    assert ctx.turn_tokens == 20_204, ctx.turn_tokens
    a._logger.close()


@test
def a_tools_less_call_writes_no_message_cache_entry():
    """_wrap_up's tools=[] call has a different prefix from every normal call,
    so it could never READ their cache -- but it still wrote the whole
    end-of-turn conversation at 1.25x, costing ~25% more than not caching, on
    the biggest context of the turn, for nothing to ever read."""
    ctx = Context(system="s" * 800, context_window=1_000_000)
    reg = Registry(ctx)
    reg.tool("move", description="m", parameters={}, block=lambda: "")
    ctx.add_message("user", "hello")
    be = Anthropic(api_key="x", model="claude-sonnet-5", cache=True)

    def msg_breakpoints(p):
        n = 0
        for msg in p["messages"]:
            c = msg.get("content")
            if isinstance(c, list):
                n += sum(isinstance(b, dict) and "cache_control" in b for b in c)
        return n

    assert msg_breakpoints(be.to_payload(ctx)) == 1
    assert msg_breakpoints(be.to_payload(ctx, tools=[])) == 0


@test
def after_turn_fires_when_the_turn_raises():
    """The class comment claimed all exits were covered, and the three `return`
    paths were. TurnInterrupted and a main-loop ApiError were not -- so a
    handler counting turns or spend would miss exactly the turns worth
    counting."""
    import threading

    def build(script, interrupt=None):
        ctx = Context(system="s", context_window=1_000_000)
        hooks, seen = Hooks(), []
        hooks.on(Hook.AFTER_TURN, lambda p: seen.append(p.reason))

        class C:
            def call(self, **_k):
                item = script.pop(0)
                raise item

        return Agent(context=ctx, registry=Registry(ctx),
                     builder=PromptBuilder(ctx, Anthropic(api_key="x", model="claude-sonnet-5")),
                     client=C(), logger=Logger(dir=tempfile.mkdtemp()),
                     hooks=hooks, interrupt_event=interrupt), seen

    ev = threading.Event()
    ev.set()
    a, seen = build([], interrupt=ev)
    try:
        a.run()
    except TurnInterrupted:
        pass
    assert seen == ["TurnInterrupted"], seen
    a._logger.close()

    a, seen = build([ApiError("boom")])
    try:
        a.run()
    except ApiError:
        pass
    assert seen == ["ApiError"], seen
    a._logger.close()


@test
def turn_count_is_per_session_not_aggregate():
    """`turn` comes from Repl, `turn_end` from Agent, so any Agent-driven
    session logs one and not the other. Applying the fallback across the whole
    aggregate meant a turn-less session added its iterations and costs to the
    numerator while adding nothing to the denominator -- silently inflating
    both cost_per_turn and iterations_per_turn."""
    d = Path(tempfile.mkdtemp())
    (d / "repl.jsonl").write_text(
        json.dumps({"phase": "turn", "n": 1}) + "\n"
        + json.dumps({"phase": "turn_end", "reason": "completed"}) + "\n")
    (d / "agent.jsonl").write_text(
        json.dumps({"phase": "turn_end", "reason": "completed"}) + "\n")
    s = SessionReport.from_paths([d / "repl.jsonl", d / "agent.jsonl"]).summary()
    assert s["turns"] == 2, s["turns"]   # was 1: agent.jsonl contributed nothing


# ---- MEDIUM ---------------------------------------------------------------

@test
def a_corrupt_json_file_is_sidelined_not_clobbered():
    """_read_json returns {} on a torn file, so the next write silently
    replaced a recoverable trails.json with an empty one -- destroying the
    whole learned map. A human can salvage truncated JSON, not a deleted file."""
    m = store()
    m.remember_room("Temple Square", ["north"])
    (m.path / "trails.json").write_text('{"rooms": {"a": ', encoding="utf-8")
    m.remember_room("Market Square", ["south"])
    assert (m.path / "trails.json.corrupt").is_file(), "damaged file was destroyed"
    assert "rooms" in (m.path / "trails.json.corrupt").read_text()


@test
def multi_line_and_bulleted_facts_deduplicate():
    """Dedup compared whole text against per-LINE entries, so any fact
    containing a newline could never match and duplicated on every write --
    and duplicates are paid for on every iteration, since facts are injected."""
    m = store()
    assert m.add_fact("The Bakery\n is north of Market Square.") is True
    assert m.add_fact("The Bakery is north of Market Square.") is False
    assert m.add_fact("- the bakery is NORTH of market square.") is False
    assert len([ln for ln in m.facts().splitlines() if ln.strip()]) == 1


@test
def hook_payload_getattr_does_not_recurse():
    """__getattr__ read self.extra, which is itself resolved through
    __getattr__ before __init__ has run (or after an unpickle) -- so copy,
    pickle or inspect on a payload hung instead of raising."""
    import copy
    p = HookPayload(Hook.AFTER_TOOL, context=None, registry=None, logger=None, result="x")
    clone = copy.copy(p)                       # would previously hang
    assert clone.result == "x"
    bare = HookPayload.__new__(HookPayload)    # __init__ skipped, like unpickling
    try:
        bare.extra
    except AttributeError:
        pass
    else:
        raise AssertionError("expected AttributeError, not a value")


# ---- second pass: findings the first fix round missed ----------------------

@test
def a_fresh_start_does_not_trust_the_stored_position():
    """MemoryHooks declined to trust a stored position on startup, but only for
    its own in-process belief -- context_block, render_journal and find_route
    all kept reading the stale stored value, so find_route could hand back a
    route computed from where the character was LAST session."""
    d = Path(tempfile.mkdtemp())
    m = Memory("t", dir=d)
    m.set_position("somewhere#abc123")
    MemoryHooks(Memory("t", dir=d))
    assert Memory("t", dir=d).position is None


@test
def movement_points_are_rendered_from_the_live_value():
    """moves_now was the other half of the dead-write finding: recorded on
    nearly every reply, read by nothing, and not rendered at all."""
    m = store()
    m.update_state(moves="85/85")
    m.update_state(moves_now=12)
    assert "moves=12/85" in m.context_block()


@test
def the_wind_down_call_does_not_understate_context_size():
    """_wrap_up builds its request with tools=[], so its prompt size omits the
    whole tool-schema block. It is the LAST thing a turn does, so letting it
    win left current_tokens understated for the NEXT turn's compaction check."""
    ctx = Context(system="s", context_window=1_000_000)
    a = Agent(context=ctx, registry=Registry(ctx),
              builder=PromptBuilder(ctx, Anthropic(api_key="x", model="claude-sonnet-5")),
              client=None, logger=Logger(dir=tempfile.mkdtemp()))
    a._record_usage({"usage": {"input_tokens": 50_000, "output_tokens": 10}})
    assert ctx.current_tokens == 50_000
    a._record_usage({"usage": {"input_tokens": 900, "output_tokens": 10}},
                    update_context_size=False)
    assert ctx.current_tokens == 50_000, ctx.current_tokens   # not overwritten by the tools-less call
    assert ctx.turn_tokens == 50_920                          # but still charged for spend
    a._logger.close()


@test
def the_reporter_reads_week1_cost_under_its_own_key():
    """06_the_logger..11_tui wrote cost as `cost_usd`; reading only `cost`
    reported genuinely recorded week1 spend as 'unknown'."""
    d = Path(tempfile.mkdtemp())
    (d / "old.jsonl").write_text(
        json.dumps({"phase": "turn_end", "reason": "completed"}) + "\n"
        + json.dumps({"phase": "response", "cost_usd": 0.25,
                      "usage": {"input_tokens": 10, "output_tokens": 2}}) + "\n")
    s = SessionReport.from_paths([d / "old.jsonl"]).summary()
    assert s["cost_total"] == 0.25, s["cost_total"]


@test
def the_prompt_log_reflects_what_was_actually_sent():
    """The prompt event was logged BEFORE before_model fired, so any message a
    handler appended (the position block) was missing from the record of the
    request that carried it."""
    import inspect
    src = inspect.getsource(Agent._run_loop)
    fire_at = src.index("Hook.BEFORE_MODEL")
    log_at = src.index("self._logger.prompt(")
    assert fire_at < log_at, "prompt is still logged before before_model fires"


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
