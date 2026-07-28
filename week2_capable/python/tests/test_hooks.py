"""Regression tests for the lifecycle-hook seams (week2 hooks M1 + M2).

Run:  uv run python tests/test_hooks.py

Deliberately dependency-free and self-asserting rather than pytest-based --
this project hand-rolls its HTTP client rather than take a library, and a test
runner would be the first dev dependency in the tree. Plain asserts and a
FakeClient keep the whole suite offline: no API calls, no MUD, no cost.

WHY THIS FILE EXISTS: week1's acceptance bar was a byte-for-byte diff between
the Ruby and Python launchers, and it caught a real bug on nearly every step.
Week2 retires the Ruby mirror (see the package docstring), which retires that
check with it. These tests are the deliberate replacement for the narrow slice
of it that matters most here -- that adding seams to Agent.run() did not change
what the loop does.
"""
import json
import os
import sys
import tempfile
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("BOUKENSHA_DIR", str(Path(__file__).resolve().parent.parent.parent.parent / ".boukensha"))

from boukensha.agent import Agent  # noqa: E402
from boukensha.backends.anthropic import Anthropic  # noqa: E402
from boukensha.context import Context  # noqa: E402
from boukensha.errors import ApiError  # noqa: E402
from boukensha.hooks import Hook, Hooks  # noqa: E402
from boukensha.logger import Logger  # noqa: E402
from boukensha.prompt_builder import PromptBuilder  # noqa: E402
from boukensha.registry import Registry  # noqa: E402

ROOM_DUMP = "A LONG ROOM DUMP " * 20


class FakeClient:
    """Replays a scripted list of responses. An Exception in the script is
    raised instead of returned, which is how the ApiError path gets exercised."""

    def __init__(self, script):
        self.script = list(script)
        self.calls = 0

    def call(self, **_kwargs):
        self.calls += 1
        item = self.script.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def tool_use(name, args, id_="t1"):
    return {
        "stop_reason": "tool_use",
        "content": [{"type": "tool_use", "name": name, "input": args, "id": id_}],
        "usage": {"input_tokens": 10, "output_tokens": 5},
    }


def text(t):
    return {
        "stop_reason": "end_turn",
        "content": [{"type": "text", "text": t}],
        "usage": {"input_tokens": 10, "output_tokens": 5},
    }


def build(script, hooks=None, max_iterations=25):
    log_dir = tempfile.mkdtemp()
    ctx = Context(system="s", context_window=1_000_000)
    registry = Registry(ctx)
    registry.tool("greet", description="greet", parameters={"who": {"type": "string"}},
                  block=lambda who: f"hello {who}")
    registry.tool("room", description="look around", parameters={}, block=lambda: ROOM_DUMP)
    backend = Anthropic(api_key="not-a-real-key", model="claude-sonnet-5")
    logger = Logger(dir=log_dir)
    agent = Agent(
        context=ctx, registry=registry, builder=PromptBuilder(ctx, backend),
        client=FakeClient(script), logger=logger, hooks=hooks, max_iterations=max_iterations,
    )
    return agent, ctx, logger, log_dir


def events(log_dir):
    path = next(Path(log_dir).glob("*.jsonl"))
    return [json.loads(line) for line in path.read_text().splitlines()]


def raiser(exc):
    def handler(_payload):
        raise exc
    return handler


TESTS = []


def test(fn):
    TESTS.append(fn)
    return fn


# --------------------------------------------------------------------------
# M1 -- the seams exist and change nothing on their own
# --------------------------------------------------------------------------

@test
def no_op_parity():
    """Zero handlers registered => the loop behaves exactly as it did before
    hooks existed. This is M1's whole acceptance bar."""
    agent, ctx, logger, _ = build([tool_use("greet", {"who": "world"}), text("done")])
    out = agent.run()
    logger.close()
    assert out == "done", out
    assert [m.role for m in ctx.messages] == ["assistant", "tool_result", "assistant"]
    assert str(ctx.messages[1].content) == "hello world"


@test
def fire_counts_match_loop_shape():
    """A 2-iteration turn with 1 tool call fires each seam the right number of
    times. before_model is per-ITERATION; before_turn/after_turn are per-TURN."""
    hooks, seen = Hooks(), []
    for name in Hook.ALL:
        hooks.on(name, (lambda n: lambda _p: seen.append(n))(name))
    agent, _, logger, _ = build([tool_use("greet", {"who": "x"}), text("fin")], hooks=hooks)
    agent.run()
    logger.close()
    assert Counter(seen) == {
        Hook.BEFORE_TURN: 1, Hook.BEFORE_MODEL: 2, Hook.BEFORE_TOOLS: 1,
        Hook.AFTER_TOOL: 1, Hook.AFTER_TURN: 1,
    }, Counter(seen)


@test
def after_turn_fires_on_wrap_up_path():
    """after_turn has THREE exits -- run()'s and both of _wrap_up's. From the
    week1 session logs every turn in the longest grind session left via a
    _wrap_up path, so a happy-path-only hook would report nothing at all."""
    hooks, ends = Hooks(), []
    hooks.on(Hook.AFTER_TURN, lambda p: ends.append(p.reason))
    agent, _, logger, _ = build(
        [tool_use("greet", {"who": "y"}), text("wrapped")], hooks=hooks, max_iterations=1)
    agent.run()
    logger.close()
    assert ends == ["max_iterations"], ends


@test
def after_turn_fires_on_api_error_path():
    """The third exit: _wrap_up's ApiError fallback."""
    hooks, ends = Hooks(), []
    hooks.on(Hook.AFTER_TURN, lambda p: ends.append(p.reason))
    agent, _, logger, _ = build(
        [tool_use("greet", {"who": "z"}), ApiError("boom")], hooks=hooks, max_iterations=1)
    agent.run()
    logger.close()
    assert ends == ["max_iterations"], ends


# --------------------------------------------------------------------------
# M2 -- the mutation contract
# --------------------------------------------------------------------------

@test
def after_tool_rewrites_what_the_model_sees():
    """The token pillar's trimming lever AND the memory pillar's extraction
    point are the same seam: the model gets the compact result, while the
    session log keeps the full original."""
    hooks = Hooks()
    hooks.on(Hook.AFTER_TOOL, lambda p: setattr(p, "result", "moved north -> Temple Square"))
    agent, ctx, logger, log_dir = build([tool_use("room", {}), text("ok")], hooks=hooks)
    agent.run()
    logger.close()
    assert str(ctx.messages[1].content) == "moved north -> Temple Square"
    logged = [e for e in events(log_dir) if e["phase"] == "tool_result"][0]["result"]
    assert logged.startswith("A LONG ROOM DUMP"), logged[:40]
    assert len(logged) > len("moved north -> Temple Square")


@test
def after_turn_can_rewrite_returned_text():
    hooks = Hooks()
    hooks.on(Hook.AFTER_TURN, lambda p: setattr(p, "text", p.text.upper()))
    agent, _, logger, _ = build([text("quiet victory")], hooks=hooks)
    out = agent.run()
    logger.close()
    assert out == "QUIET VICTORY", out


# --------------------------------------------------------------------------
# Failure policy -- a crashing observer must never cost a turn or a result
# --------------------------------------------------------------------------

@test
def raising_handler_does_not_lose_the_tool_result():
    """Same reasoning as the existing try/except/else around registry.dispatch:
    a failure in observation must not be misreported as the tool failing."""
    hooks = Hooks()
    hooks.on(Hook.AFTER_TOOL, raiser(RuntimeError("handler bug")))
    agent, ctx, logger, log_dir = build([tool_use("room", {}), text("survived")], hooks=hooks)
    out = agent.run()
    logger.close()
    assert out == "survived", out
    assert str(ctx.messages[1].content).startswith("A LONG ROOM DUMP")
    errs = [e for e in events(log_dir) if e["phase"] == "hook_error"]
    assert len(errs) == 1 and errs[0]["hook"] == "after_tool", errs


@test
def handlers_run_in_order_and_are_isolated():
    """One crashing handler must not block the handlers registered after it."""
    hooks, order = Hooks(), []
    hooks.on(Hook.AFTER_TOOL, lambda _p: order.append("first"))
    hooks.on(Hook.AFTER_TOOL, raiser(ValueError("nope")))
    hooks.on(Hook.AFTER_TOOL, lambda _p: order.append("third"))
    agent, _, logger, _ = build([tool_use("room", {}), text("ok")], hooks=hooks)
    agent.run()
    logger.close()
    assert order == ["first", "third"], order


@test
def unknown_hook_name_is_rejected_loudly():
    """A typo'd seam name must fail at registration, not silently never fire."""
    try:
        Hooks().on("after_lunch", lambda _p: None)
    except ValueError as e:
        assert "after_lunch" in str(e)
    else:
        raise AssertionError("expected ValueError for unknown hook name")


@test
def agents_do_not_share_a_default_hooks_registry():
    """Ruby evaluates a keyword default expression per call; Python evaluates a
    default VALUE once at def-time. A `hooks=Hooks()` default would be shared by
    every Agent built without one -- and Repl builds a fresh Agent per TURN, so
    handlers would leak across turns. Same gotcha as 06_the_logger's Logger."""
    a1, _, l1, _ = build([text("a")])
    a2, _, l2, _ = build([text("b")])
    assert a1._hooks is not a2._hooks
    l1.close()
    l2.close()


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
