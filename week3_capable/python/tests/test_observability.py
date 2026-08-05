"""Regression tests for the observability layer (week2 phase 2).

Run:  uv run python tests/test_observability.py   (or ../bin/test)

Same dependency-free, offline style as test_hooks.py -- FakeClient, no network,
no MUD, no cost.

The bug these mostly guard is a shape this project keeps producing: code that
is present, correct, and wired, but silently never fires or silently reports
the wrong number. Reasoning logging had never emitted an event; truncation was
relabelled as a completed turn; cost estimation was fully implemented and
uncalled; and cache-aware accounting would have broken compaction the moment
caching was switched on. None of those raised an error.
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
from boukensha.logger import Logger  # noqa: E402
from boukensha.prompt_builder import PromptBuilder  # noqa: E402
from boukensha.registry import Registry  # noqa: E402
from boukensha.report import SessionReport  # noqa: E402


class FakeClient:
    def __init__(self, script):
        self.script = list(script)

    def call(self, **_kwargs):
        item = self.script.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def resp(text_, stop="end_turn", **usage):
    return {
        "stop_reason": stop,
        "content": [{"type": "text", "text": text_}],
        "usage": usage or {"input_tokens": 100, "output_tokens": 20},
    }


def build(script, model="claude-sonnet-5"):
    log_dir = tempfile.mkdtemp()
    ctx = Context(system="s", context_window=1_000_000)
    registry = Registry(ctx)
    backend = Anthropic(api_key="not-a-real-key", model=model)
    logger = Logger(dir=log_dir)
    agent = Agent(context=ctx, registry=registry, builder=PromptBuilder(ctx, backend),
                  client=FakeClient(script), logger=logger, max_output_tokens=4096)
    return agent, ctx, logger, log_dir


def events(log_dir):
    path = next(Path(log_dir).glob("*.jsonl"))
    return [json.loads(line) for line in path.read_text().splitlines()]


TESTS = []


def test(fn):
    TESTS.append(fn)
    return fn


# --------------------------------------------------------------------------
# M1 -- cost is reconnected, and priced correctly
# --------------------------------------------------------------------------

@test
def response_events_carry_cost_and_provider():
    agent, _, logger, log_dir = build([resp("done")])
    agent.run()
    logger.close()
    r = [e for e in events(log_dir) if e["phase"] == "response"][0]
    assert isinstance(r["cost"], float), r
    assert r["provider"] == "anthropic" and r["model"] == "claude-sonnet-5", r
    assert r["usage_unit"] == "tokens", r


@test
def sonnet5_uses_introductory_pricing():
    """Standard rates are 3/15; intro (through 2026-08-31) is 2/10. The table
    shipped with 3/15 while the project ran on intro pricing, so a straight
    re-connect would have over-reported by ~50%."""
    be = Anthropic(api_key="x", model="claude-sonnet-5")
    assert be.estimate_cost(input_tokens=1_000_000, output_tokens=1_000_000) == 12.0


@test
def cached_tokens_are_priced_below_fresh_input():
    """A cost estimate that ignored the cache fields would overstate spend most
    exactly when caching works best -- making the token pillar look like a
    regression on the dashboard meant to prove it worked."""
    be = Anthropic(api_key="x", model="claude-sonnet-5")
    fresh = be.estimate_cost(input_tokens=1_000_000, output_tokens=0)
    cached = be.estimate_cost(input_tokens=0, output_tokens=0, cache_read_tokens=1_000_000)
    written = be.estimate_cost(input_tokens=0, output_tokens=0, cache_write_tokens=1_000_000)
    assert cached == fresh * 0.1, (cached, fresh)
    assert written == fresh * 1.25, (written, fresh)


@test
def unknown_pricing_reports_none_not_zero():
    """'free' and 'unmeasured' are different facts; rendering the second as the
    first quietly under-reports."""
    be = Anthropic(api_key="x", model="claude-sonnet-5")
    be._model_info = {"cost_per_million": {"input": None, "output": None}}
    assert be.estimate_cost(input_tokens=1000, output_tokens=1000) is None


# --------------------------------------------------------------------------
# M2 -- cache-aware accounting (blocks caching)
# --------------------------------------------------------------------------

@test
def context_size_counts_cached_tokens():
    """usage.input_tokens is the UNCACHED REMAINDER. Feeding that to
    update_tokens means current_tokens collapses once caching is on, so
    needs_compaction() stops firing and a long run dies of a full window."""
    agent, ctx, logger, _ = build([resp(
        "ok", input_tokens=1_000, output_tokens=50,
        cache_read_input_tokens=40_000, cache_creation_input_tokens=9_000,
    )])
    agent.run()
    logger.close()
    assert ctx.current_tokens == 50_000, ctx.current_tokens


@test
def turn_budget_is_charged_billable_input_only():
    """max_turn_tokens is a SPEND ceiling, so cache reads shouldn't consume it.
    Measured motivation: ~59,890 input tokens/turn against a 60,000 default,
    and 56 of 68 week1 turns ended on max_tokens rather than completed."""
    agent, ctx, logger, _ = build([resp(
        "ok", input_tokens=1_000, output_tokens=50, cache_read_input_tokens=40_000,
    )])
    agent.run()
    logger.close()
    assert ctx.turn_tokens == 1_050, ctx.turn_tokens


@test
def accounting_is_unchanged_when_caching_is_off():
    """No-op guarantee: with no cache fields present, behaviour matches the
    pre-week2 build exactly."""
    agent, ctx, logger, _ = build([resp("ok", input_tokens=500, output_tokens=25)])
    agent.run()
    logger.close()
    assert ctx.current_tokens == 500 and ctx.turn_tokens == 525


# --------------------------------------------------------------------------
# Truncation visibility
# --------------------------------------------------------------------------

@test
def max_tokens_is_not_relabelled_as_end_turn():
    be = Anthropic(api_key="x", model="claude-sonnet-5")
    assert be.parse_response({"stop_reason": "max_tokens", "content": []})["stop_reason"] == "max_tokens"
    assert be.parse_response({"stop_reason": "stop_sequence", "content": []})["stop_reason"] == "end_turn"
    assert be.parse_response({"stop_reason": "tool_use", "content": []})["stop_reason"] == "tool_use"


@test
def truncated_turn_is_logged_and_reported_distinctly():
    agent, _, logger, log_dir = build([resp("half a sen", stop="max_tokens")])
    agent.run()
    logger.close()
    evs = events(log_dir)
    assert [e for e in evs if e["phase"] == "truncated"], "no truncated event"
    end = [e for e in evs if e["phase"] == "turn_end"][0]
    assert end["reason"] == "truncated", end


@test
def truncated_text_is_still_returned():
    """Partial output beats none -- the model can be asked to continue."""
    agent, _, logger, _ = build([resp("half a sen", stop="max_tokens")])
    assert agent.run() == "half a sen"
    logger.close()


# --------------------------------------------------------------------------
# M3a -- thinking / reasoning
# --------------------------------------------------------------------------

@test
def thinking_is_requested_only_where_supported():
    """Adaptive thinking is 4.6+. Sending it to an older model is a 400, not a
    graceful no-op, so this is gated on the MODELS table rather than guessed."""
    ctx = Context(system="s", context_window=1_000_000)
    s5 = Anthropic(api_key="x", model="claude-sonnet-5").to_payload(ctx)
    assert s5["thinking"] == {"type": "adaptive", "display": "summarized"}
    haiku = Anthropic(api_key="x", model="claude-haiku-4-5").to_payload(ctx)
    assert "thinking" not in haiku, haiku.keys()


@test
def reasoning_blocks_reach_the_log():
    """The pipeline that had never once fired. With display omitted the blocks
    arrive empty and _log_reasoning skips them; the fix is asking for a
    summary, so this asserts an actual event lands."""
    agent, _, logger, log_dir = build([{
        "stop_reason": "end_turn",
        "content": [
            {"type": "thinking", "thinking": "I should look around first.", "signature": "sig"},
            {"type": "text", "text": "ok"},
        ],
        "usage": {"input_tokens": 10, "output_tokens": 5},
    }])
    agent.run()
    logger.close()
    r = [e for e in events(log_dir) if e["phase"] == "reasoning"]
    assert len(r) == 1 and "look around" in r[0]["text"], r


# --------------------------------------------------------------------------
# M6 -- prompt log digest
# --------------------------------------------------------------------------

@test
def prompt_events_log_a_digest_not_the_whole_conversation():
    """This was 94% of week1's log volume (4.3 MB of one 4.56 MB file), growing
    quadratically with conversation length."""
    agent, ctx, logger, log_dir = build([resp("ok")])
    ctx.add_message("user", "x" * 5_000)
    agent.run()
    logger.close()
    p = [e for e in events(log_dir) if e["phase"] == "prompt"][0]
    assert "messages" not in p, "full message list still being logged"
    assert p["digest"]["roles"] == ["user"], p["digest"]
    assert p["digest"]["content_chars"] == 5_000, p["digest"]
    assert p["message_count"] == 1


# --------------------------------------------------------------------------
# M5 -- reporter
# --------------------------------------------------------------------------

@test
def reporter_summarizes_a_session():
    agent, _, logger, log_dir = build([resp("done", input_tokens=300, output_tokens=40)])
    agent.run()
    logger.close()
    report = SessionReport.from_paths(sorted(Path(log_dir).glob("*.jsonl")))
    s = report.summary()
    assert s["tokens"]["input_tokens"] == 300, s["tokens"]
    assert isinstance(s["cost_total"], float) and s["cost_total"] > 0
    assert s["turn_end_reasons"] == {"completed": 1}, s["turn_end_reasons"]
    assert "SPEND" in report.render()


@test
def reporter_survives_a_torn_final_line():
    """A run killed mid-write leaves a partial JSON line. Those interrupted
    runs are often the ones worth reading, so refusing to parse the file is
    the wrong failure."""
    d = Path(tempfile.mkdtemp())
    (d / "s.jsonl").write_text(
        json.dumps({"phase": "turn", "n": 1}) + "\n" + '{"phase": "resp'
    )
    s = SessionReport.from_paths([d / "s.jsonl"]).summary()
    assert s["turns"] == 1, s


# ---- the week3 acceptance numbers -------------------------------------------

def _capability_log(dirpath, lines):
    (dirpath / "s.jsonl").write_text("\n".join(json.dumps(x) for x in lines) + "\n")
    return SessionReport.from_paths([dirpath / "s.jsonl"]).summary()


@test
def the_reporter_computes_the_three_acceptance_numbers():
    """docs/plans/week3/README.md says these are computable from the session
    reporter. They were not -- nothing read the driver's lines, so every figure
    was worked out by hand from raw JSONL after each run."""
    d = Path(tempfile.mkdtemp())
    s = _capability_log(d, [
        {"phase": "driver_cycle", "action": "hunted", "used_model": True,
         "note": "progress", "model_actions": 2, "mechanical_actions": 18},
        {"phase": "driver_cycle", "action": "resting", "used_model": False,
         "note": "low health", "model_actions": 0, "mechanical_actions": 1},
        {"phase": "driver_cycle", "action": "resting", "used_model": False,
         "note": "cycle 2", "model_actions": 0, "mechanical_actions": 1},
        {"phase": "driver_cycle", "action": "stood_up", "used_model": False,
         "note": "recovered", "model_actions": 0, "mechanical_actions": 1},
        {"phase": "response", "cost": 0.40},
        {"phase": "driver_run", "goal": "g", "cycles": 4,
         "stopped_because": "max_cycles", "starting_exp": 100, "ending_exp": 180},
    ])
    assert s["model_actions"] == 2 and s["mechanical_actions"] == 21, s
    assert abs(s["judgment_ratio"] - 2 / 23) < 1e-9, s["judgment_ratio"]
    assert s["experience_gained"] == 80, s
    assert abs(s["cost_per_experience"] - 0.40 / 80) < 1e-9, s

    # One sit-down is ONE incident. The follow-on waiting cycles are noted
    # "cycle N" -- counting those would score a single long rest as several.
    assert s["recovery_episodes"] == 1, s
    assert s["recoveries_completed"] == 1, s


@test
def a_run_that_never_got_to_work_is_not_scored_as_a_healthy_finish():
    d = Path(tempfile.mkdtemp())
    s = _capability_log(d, [
        {"phase": "driver_run", "goal": "g", "cycles": 8,
         "stopped_because": "stuck_recovering", "starting_exp": 10, "ending_exp": 10},
        {"phase": "driver_run", "goal": "g", "cycles": 3,
         "stopped_because": "task_done", "starting_exp": 10, "ending_exp": 10},
    ])
    assert s["runs_ended_badly"] == 1, s
    assert s["run_endings"]["stuck_recovering"] == 1, s


@test
def experience_that_went_down_is_not_counted_as_progress():
    """Fleeing costs experience in CircleMUD, so a run can end lower than it
    started. Summing signed deltas would let one bad run cancel a good one and
    report cost-per-experience against a total that never happened."""
    d = Path(tempfile.mkdtemp())
    s = _capability_log(d, [
        {"phase": "driver_run", "goal": "g", "cycles": 1,
         "stopped_because": "max_cycles", "starting_exp": 292, "ending_exp": 291},
    ])
    assert s["experience_gained"] == 0, s
    assert s["cost_per_experience"] is None, s


@test
def logs_with_no_driver_lines_report_nothing_rather_than_zero():
    """Week1 and week2 sessions predate the driver entirely, and they are in the
    same directory. A confident 0% judgment ratio over those would be a lie."""
    d = Path(tempfile.mkdtemp())
    s = _capability_log(d, [{"phase": "turn", "n": 1}, {"phase": "response", "cost": 0.1}])
    assert s["judgment_ratio"] is None, s
    assert s["driver_cycles"] == 0 and s["driver_runs"] == 0, s
    assert "CAPABILITY" not in SessionReport.from_paths([d / "s.jsonl"]).render()


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
