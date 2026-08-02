"""The grind loop (week3 driver).

    uv run python tests/test_driver.py   (or ../bin/test)

Offline. `run_turn` is a stub, so these assert what the driver DECIDES without
paying a model to decide it -- which is also how we check the judgment
boundary: anything classified as mechanical has to work with the model stub
never being called at all.
"""
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("BOUKENSHA_DIR", str(Path(__file__).resolve().parent.parent.parent.parent / ".boukensha"))

from boukensha.context import Context  # noqa: E402
from boukensha.driver import Driver, Policy  # noqa: E402
from boukensha.memory import Memory  # noqa: E402
from boukensha.registry import Registry  # noqa: E402
from boukensha.tools import mud as mud_tools  # noqa: E402
from tests.fake_mud import FakeSession  # noqa: E402

TESTS = []


def test(fn):
    TESTS.append(fn)
    return fn


def build(*, exp=100, exp_to_level=500, hp="30/30", moves="85/85", level=3):
    fake = FakeSession()
    ctx = Context(system="s", context_window=1_000_000)
    registry = Registry(ctx)
    mud_tools.register(registry, name="boukensha", password="x", session=fake)
    registry.dispatch("mud_connect", {})

    memory = Memory("t", dir=Path(tempfile.mkdtemp()))
    memory.update_state(level=level, exp=exp, exp_to_level=exp_to_level, hp=hp, moves=moves)

    turns = []

    def run_turn(task):
        turns.append(task)
        return "ok"

    driver = Driver(goal="reach level 5", memory=memory, registry=registry, run_turn=run_turn)
    return fake, memory, driver, turns


# ---- mechanical decisions cost no model call ------------------------------

@test
def resting_never_calls_the_model():
    """Reasoning about whether to sit down when exhausted is the definition of
    reasoning on rails. If this needs the model, the boundary is wrong."""
    fake, memory, driver, turns = build(hp="5/30")
    cycle = driver.step()
    assert cycle.action == "resting" and cycle.used_model is False, cycle
    assert turns == [], "resting called the model"
    assert "rest" in " ".join(fake.sent).lower()


@test
def it_stands_up_once_recovered():
    fake, memory, driver, turns = build(hp="5/30")
    driver.step()                                  # starts resting
    memory.update_state(hp="30/30", hp_now=30)     # healed
    cycle = driver.step()
    assert cycle.action == "stood_up" and cycle.used_model is False, cycle
    assert turns == []


@test
def low_movement_triggers_rest_just_like_low_health():
    """Running out of movement is the commonest thing that stalls a grind."""
    _, _, driver, turns = build(moves="5/85")
    cycle = driver.step()
    assert cycle.action == "resting" and cycle.note == "low movement", cycle
    assert turns == []


@test
def resting_gives_up_rather_than_looping_forever():
    """If health never recovers -- poison, a mob chewing on us -- the loop must
    not sit down for the rest of the night."""
    _, _, driver, _ = build(hp="5/30")
    driver.policy = Policy(max_rest_cycles=3)
    actions = [driver.step().action for _ in range(5)]
    assert "stood_up" in actions, actions


# ---- judgment goes to the model -------------------------------------------

@test
def hunting_asks_the_model():
    """What is safe to attack depends on `consider`, on current health, and on
    what past fights taught us. That is judgment, not routine."""
    _, _, driver, turns = build()
    cycle = driver.step()
    assert cycle.action == "hunted" and cycle.used_model is True, cycle
    assert len(turns) == 1
    task = turns[0].lower()
    assert "consider" in task and "backstab" in task and "flee" in task


@test
def a_available_level_sends_it_to_train():
    _, _, driver, turns = build(exp_to_level=0)
    cycle = driver.step()
    assert cycle.action == "trained" and cycle.used_model is True, cycle
    assert "practise" in turns[0].lower() and "thief" in turns[0].lower()


# ---- the recover half ------------------------------------------------------

@test
def it_notices_when_it_is_getting_nowhere():
    """Week 2 planned stall detection and never built it. An unattended agent
    that is stuck will otherwise burn an entire night doing nothing."""
    _, _, driver, _ = build()
    driver.policy = Policy(stall_cycles=3)
    result = driver.run(max_cycles=20)
    assert result.stopped_because == "stalled", result.stopped_because
    assert len(result.cycles) == 3, len(result.cycles)


@test
def progress_resets_the_stall_counter():
    """Experience arrives DURING the turn -- the agent kills something while
    the model has control. An earlier version of this test bumped it between
    cycles, which the driver correctly read as no progress: it compares state
    before and after the turn, not across turns."""
    _, memory, driver, _ = build()
    driver.step()                                  # nothing died
    assert driver._no_progress == 1

    original = driver.run_turn

    def kill_something(task):
        memory.update_state(exp=400)               # gained mid-turn
        return original(task)

    driver.run_turn = kill_something
    driver.step()
    assert driver._no_progress == 0


@test
def it_stops_when_the_goal_is_met():
    _, memory, driver, _ = build()
    memory.update_state(exp=999)
    result = driver.run(max_cycles=20, until=lambda a: (a.exp or 0) >= 999)
    assert result.stopped_because == "goal_met", result.stopped_because


@test
def a_dead_connection_does_not_end_the_run():
    """The MUD drops constantly. A mechanical action that fails must degrade,
    not raise out of the loop."""
    fake, _, driver, _ = build(hp="5/30")
    fake.close()
    cycle = driver.step()                           # tries to rest on a dead socket
    assert cycle.action == "resting", cycle


# ---- the metric ------------------------------------------------------------

@test
def it_reports_the_judgment_ratio():
    """Week 3's acceptance number: what fraction of cycles needed the model."""
    _, memory, driver, _ = build(hp="5/30")
    result = driver.run(max_cycles=4)
    assert result.judgment_ratio is not None
    assert 0.0 <= result.judgment_ratio <= 1.0
    # This run opens with two mechanical recovery cycles, so it cannot be all model.
    assert result.judgment_ratio < 1.0, result.judgment_ratio


@test
def it_reports_experience_gained():
    _, memory, driver, _ = build(exp=100)
    memory.update_state(exp=100)
    result = driver.run(max_cycles=2)
    memory.update_state(exp=350)
    result.ending_exp = driver.assess().exp
    assert result.experience_gained == 250, result.experience_gained


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
