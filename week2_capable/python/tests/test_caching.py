"""Regression tests for prompt caching (week2 token M2).

Run:  uv run python tests/test_caching.py   (or ../bin/test)

Offline: these assert the PAYLOAD SHAPE, which is the part we control. Whether
the cache actually hits is a live-API fact and is verified separately by making
a real call and reading usage.cache_read_input_tokens -- see
docs/plans/week2/token_optimization.md.

The failure mode worth guarding is silence. A misplaced breakpoint, a prefix
that drifts byte-for-byte between requests, or a prefix under the 1024-token
minimum all produce exactly the same symptom: no error, and
cache_creation_input_tokens: 0 forever.
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("BOUKENSHA_DIR", str(Path(__file__).resolve().parent.parent.parent.parent / ".boukensha"))

from boukensha.backends.anthropic import Anthropic  # noqa: E402
from boukensha.config import Config  # noqa: E402
from boukensha.context import Context  # noqa: E402
from boukensha.registry import Registry  # noqa: E402

CC = {"type": "ephemeral"}


def ctx_with(messages=True, system="You are Dummy the thief."):
    ctx = Context(system=system, context_window=1_000_000)
    reg = Registry(ctx)
    reg.tool("move", description="Move", parameters={"direction": {"type": "string"}},
             block=lambda direction: "")
    if messages:
        ctx.add_message("user", "go north")
        ctx.add_message("assistant", [{"type": "tool_use", "name": "move",
                                       "input": {"direction": "n"}, "id": "t1"}])
        ctx.add_message("tool_result", "You walk north.", tool_use_id="t1")
    return ctx


def breakpoints(payload):
    n = 0
    system = payload.get("system")
    if isinstance(system, list):
        n += sum("cache_control" in b for b in system)
    for m in payload.get("messages", []):
        c = m.get("content")
        if isinstance(c, list):
            n += sum(isinstance(b, dict) and "cache_control" in b for b in c)
    return n


TESTS = []


def test(fn):
    TESTS.append(fn)
    return fn


@test
def system_block_carries_a_breakpoint():
    """Render order is tools -> system -> messages, so a breakpoint on the last
    system block caches tools AND system. The tool schemas are also what carry
    this prefix over the 1024-token minimum -- the system prompt is ~600 tokens
    and would silently never cache on its own."""
    p = Anthropic(api_key="x", model="claude-sonnet-5", cache=True).to_payload(ctx_with())
    assert isinstance(p["system"], list), p["system"]
    assert p["system"][0]["cache_control"] == CC
    assert p["system"][0]["text"] == "You are Dummy the thief."


@test
def last_message_block_carries_a_breakpoint():
    """Grows with the conversation: each request writes a slightly longer
    prefix and reads the one the previous request wrote."""
    p = Anthropic(api_key="x", model="claude-sonnet-5", cache=True).to_payload(ctx_with())
    assert p["messages"][-1]["content"][-1]["cache_control"] == CC


@test
def string_content_is_promoted_to_a_text_block():
    """cache_control lives on a content BLOCK, so a bare string has to become
    one first."""
    ctx = ctx_with(messages=False)      # needs tools -- see the tools-less test below
    ctx.add_message("user", "hello")
    p = Anthropic(api_key="x", model="claude-sonnet-5", cache=True).to_payload(ctx)
    assert p["messages"][-1]["content"] == [
        {"type": "text", "text": "hello", "cache_control": CC}
    ], p["messages"][-1]


@test
def a_tools_less_call_gets_no_message_breakpoint():
    """Caching is a prefix match and tools render FIRST, so a tools=[] call has
    a different prefix from every normal call and can never read their cache.
    Marking its last message wrote the whole end-of-turn conversation as a
    fresh entry at 1.25x -- ~25% MORE than not caching -- on the biggest
    context of the turn, for nothing to ever read. That is _wrap_up, which 82%
    of week1 turns went through. Found by code review."""
    be = Anthropic(api_key="x", model="claude-sonnet-5", cache=True)
    ctx = ctx_with()
    normal = be.to_payload(ctx)
    wrapup = be.to_payload(ctx, tools=[])
    assert breakpoints(normal) == 2, breakpoints(normal)
    assert breakpoints(wrapup) == 1, breakpoints(wrapup)   # system anchor only
    assert not any(
        isinstance(b, dict) and "cache_control" in b
        for m in wrapup["messages"] for b in (m.get("content") or [])
        if isinstance(m.get("content"), list)
    )


@test
def caching_off_reproduces_the_pre_week2_payload():
    """The kill-switch has to be a true no-op, not 'mostly the same'."""
    p = Anthropic(api_key="x", model="claude-sonnet-5", cache=False).to_payload(ctx_with())
    assert p["system"] == "You are Dummy the thief."
    assert breakpoints(p) == 0
    assert p["messages"][-1]["content"][-1] == {
        "type": "tool_result", "tool_use_id": "t1", "content": "You walk north."
    }


@test
def marking_does_not_mutate_the_context():
    """to_messages passes some content through BY REFERENCE. Mutating it would
    corrupt the conversation itself, and the corruption would only show up as a
    cache that never hits.

    Code review flagged the earlier version of this test as not testing what it
    claimed: it ended on a tool_result, whose content to_messages rebuilds into
    a fresh list, so the by-reference path was never exercised and the test
    would have passed even with a mutating implementation. This version ends on
    an assistant message carrying a LIST, which to_messages passes through
    without copying -- the actual risk."""
    ctx = ctx_with(messages=False)
    blocks = [{"type": "text", "text": "thinking about it"}]
    ctx.add_message("assistant", blocks)
    snapshot = [dict(b) for b in blocks]

    Anthropic(api_key="x", model="claude-sonnet-5", cache=True).to_payload(ctx)

    assert ctx.messages[-1].content is blocks, "content object was replaced"
    assert blocks == snapshot, f"Context's own blocks were mutated: {blocks}"
    assert "cache_control" not in blocks[-1]


@test
def stays_within_the_four_breakpoint_limit():
    p = Anthropic(api_key="x", model="claude-sonnet-5", cache=True).to_payload(ctx_with())
    assert breakpoints(p) == 2, breakpoints(p)


@test
def empty_conversation_and_empty_system_are_safe():
    be = Anthropic(api_key="x", model="claude-sonnet-5", cache=True)
    p = be.to_payload(ctx_with(messages=False))
    assert p["messages"] == []
    p2 = be.to_payload(ctx_with(messages=False, system=None))
    assert p2["system"] is None, p2["system"]


@test
def prefix_is_byte_stable_across_requests():
    """The whole mechanism rests on the prefix not drifting. A timestamp, a
    UUID, or non-deterministic tool ordering anywhere ahead of a breakpoint
    silently drops the hit rate to zero with no error."""
    import json
    be = Anthropic(api_key="x", model="claude-sonnet-5", cache=True)
    ctx = ctx_with()
    a = be.to_payload(ctx)
    b = be.to_payload(ctx)
    assert json.dumps(a["system"]) == json.dumps(b["system"])
    assert json.dumps(a["tools"]) == json.dumps(b["tools"])


@test
def caching_defaults_on_but_is_configurable():
    assert Anthropic(api_key="x", model="claude-sonnet-5").cache_enabled is True
    assert Config().agent_prompt_caching() is True


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
