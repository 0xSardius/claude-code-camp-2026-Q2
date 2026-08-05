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
from boukensha.driver import Driver, Policy, RunResult  # noqa: E402
from boukensha.memory import Memory  # noqa: E402
from boukensha.hooks import Hook, HookPayload, Hooks  # noqa: E402
from boukensha.memory_hooks import MemoryHooks  # noqa: E402
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

    # Hooks wired exactly as the Harness wires them: the driver's own tool
    # calls have to reach memory the same way the Agent's do.
    hooks = Hooks()
    MemoryHooks(memory, registry=registry).install(hooks)
    memory.update_state(level=level, exp=exp, exp_to_level=exp_to_level, hp=hp, moves=moves)

    # slept records how long the driver WOULD have waited, so the tests can
    # assert that resting spends real time without any test actually spending it.
    slept = []
    driver = Driver(goal="reach level 5", memory=memory, registry=registry,
                    run_turn=run_turn, hooks=hooks, sleep=slept.append)
    driver.slept = slept
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
    assert "engage" in task


@test
def a_available_level_sends_it_to_train():
    _, _, driver, turns = build(exp_to_level=0)
    cycle = driver.step()
    assert cycle.action == "trained" and cycle.used_model is True, cycle
    assert "practise" in turns[0].lower() and "thief" in turns[0].lower()


# ---- the driver's own tool calls have to reach memory ----------------------

@test
def mechanical_tool_calls_update_memory():
    """The driver dispatches at the registry directly, which does NOT fire the
    lifecycle hooks by itself. The first version relied on that and the effect
    was invisible: `check` while resting never updated health, so the driver
    could not tell it had recovered and sat there until max_rest_cycles bailed
    it out. Found on the first dry run, not by any test that existed then."""
    _, memory, driver, _ = build(hp="5/30")
    memory.update_state(hp_now=-1)              # sentinel: nothing has read a reply yet
    driver._do("check", {"kind": "score"})
    assert memory.state.get("hp_now") != -1, "the driver's dispatch never reached memory"


@test
def it_learns_its_own_vitals_before_deciding():
    """A cold start has nothing in memory, and every threshold compared against
    None means the driver hunts straight past an empty state instead of
    resting. One mechanical `check` fixes it -- and stays mechanical."""
    _, memory, driver, turns = build()
    memory.update_state(hp=None, moves=None, level=None)
    a = driver._ensure_state()
    assert a.health is not None and a.movement is not None, a
    assert turns == [], "bootstrapping vitals called the model"


# ---- the mechanical fight --------------------------------------------------

@test
def a_whole_fight_costs_one_model_call():
    """The finding that motivated engage(): the first live run spent 9
    consecutive model calls sending `attack fido`. The model decides WHAT to
    fight; the swinging is routine and must not cost a turn each."""
    fake, memory, driver, turns = build()
    driver.policy = Policy(max_fight_rounds=4)
    memory.update_state(exp=100)
    driver.engage("fido")
    assert turns == [], "the fight called the model"
    assert sum(1 for c in fake.sent if c.startswith("kill")) >= 1, fake.sent


@test
def it_stops_fighting_when_experience_goes_up():
    """How it knows the target died -- a structural signal, not the server's
    death message. A phrase match would be one wording change from an infinite
    loop; this codebase already chose structure over phrasing once (movement
    cost, to tell walking from being teleported)."""
    _, memory, driver, _ = build(exp=100)
    memory.update_state(exp=100)

    original = driver._do
    rounds = []

    def counting(tool, args=None):
        rounds.append(tool)
        out = original(tool, args)
        # AFTER the real dispatch: `check` fires the memory hooks, which parse
        # the fake's captured score reply and would overwrite this.
        if tool == "check" and rounds.count("attack") >= 2:
            memory.update_state(exp=175)      # it died on round 2
        return out

    driver._do = counting
    out = driver.engage("fido")
    assert "KILL" in out and "+75" in out, out
    assert rounds.count("attack") == 2, rounds


@test
def it_breaks_off_before_dying():
    """Fleeing at a threshold is policy -- an explicit, arguable number -- and
    checking it every round is free, because health rides on the status prompt
    of every combat reply."""
    _, memory, driver, _ = build()
    driver.policy = Policy(flee_below_health=0.5, max_fight_rounds=10)

    original = driver._do

    def wounded(tool, args=None):
        out = original(tool, args)
        if tool == "attack":
            memory.update_state(hp_now=4)     # 4/30 -- well under the threshold
        return out

    driver._do = wounded
    out = driver.engage("cityguard")
    assert "BROKE OFF" in out, out


@test
def a_fight_that_will_not_end_gives_up():
    """Otherwise an unkillable target is an infinite loop with no model call in
    it to notice -- the worst kind, because nothing is watching."""
    _, memory, driver, _ = build()
    driver.policy = Policy(max_fight_rounds=3)
    memory.update_state(exp=100)
    out = driver.engage("statue")
    assert "STILL FIGHTING" in out and "3 rounds" in out, out


@test
def the_model_is_told_to_engage_rather_than_to_swing():
    _, _, driver, turns = build()
    driver.step()
    task = turns[0]
    assert "engage" in task
    assert "Do not call `attack` in a loop" in task
    assert "DO NOT rest" in task, "the model will otherwise poll check while healing"


# ---- the mechanical walk ---------------------------------------------------

def explore(driver, *directions):
    """Walk the fake map by hand, the way the agent first does: each move is
    seen and recorded. Everything travel later replays comes from here."""
    driver._do("look", {})
    for d in directions:
        driver._do("move", {"direction": d})


@test
def walking_a_known_route_costs_no_model_call():
    """The whole explore-then-replay claim in one test. The map is built by
    walking it; the walk back is then an algorithm over what was seen."""
    fake, memory, driver, turns = build()
    explore(driver, "south", "south", "north", "north")   # both directions seen
    assert fake.room == "The Temple Of Midgaard", fake.room

    fake.sent.clear()
    out = driver.travel("Market Square")

    assert "ARRIVED" in out and "2 moves" in out, out
    assert turns == [], "the walk called the model"
    assert fake.room == "Market Square", fake.room
    assert [c for c in fake.sent if c in ("south", "north")] == ["south", "south"], fake.sent


@test
def it_will_not_walk_a_route_it_has_only_seen_one_way():
    """CircleMUD has one-way exits, so memory records the reverse only once it
    is actually walked. Refusing to guess it is the point, not a gap: a guessed
    reverse edge is exactly the kind of unearned knowledge that makes an
    algorithmic walker incapable."""
    _, _, driver, _ = build()
    explore(driver, "south", "south")             # south twice, never back north
    out = driver.travel("The Temple Of Midgaard")
    assert "NO KNOWN ROUTE" in out, out
    assert "Explore" in out, "it should say what to do about it"


@test
def travel_says_so_when_it_has_never_been_there():
    """'I don't know the way' is a real answer that means go explore."""
    _, _, driver, _ = build()
    explore(driver)
    out = driver.travel("Atlantis")
    assert "NO SUCH PLACE" in out, out
    assert "Temple Of Midgaard" in out, "it should list what it does know"


@test
def travel_stops_when_something_blocks_the_way():
    """A blocked move is a decision, not a retry. Retrying is how a mechanical
    walker spends thirty moves going nowhere."""
    fake, _, driver, _ = build()
    explore(driver, "south", "north")
    fake.fail_next("refuse_move")
    out = driver.travel("The Temple Square")
    assert "BLOCKED" in out and "south" in out, out


@test
def travel_stops_before_it_strands_the_character():
    """Walking is not free. Stopping with movement left is what makes the
    driver's next recovery cycle able to fix it."""
    fake, _, driver, _ = build()
    explore(driver, "south", "south", "north", "north")
    fake.moves = 2                                # 2/85, well under the threshold
    driver._do("look", {})                        # status prompt carries the new value
    out = driver.travel("Market Square")
    assert "STOPPED" in out and "movement" in out, out


@test
def travel_replans_from_where_it_actually_is():
    """It recomputes the route every step rather than walking the list it got
    at the start. Being moved mid-route -- which the MUD does on death -- must
    re-plan from the new room, not carry on with stale directions."""
    fake, memory, driver, _ = build()
    explore(driver, "south", "south", "north", "north")

    original = driver._do
    moved = []

    def teleport_once(tool, args=None):
        out = original(tool, args)
        if tool == "move" and not moved:
            moved.append(True)
            fake.room = "The Bakery"              # something else relocated us
            original("look", {})                  # and we notice on the next look
        return out

    driver._do = teleport_once
    out = driver.travel("Market Square")
    # A walker following its original list would have sent the second "south"
    # from The Bakery and ended up somewhere it never intended. Recomputing sees
    # the new room, finds no walked path out of it, and says so.
    assert "NO KNOWN ROUTE" in out, out
    assert "after 1 moves" in out, f"it should stop at the teleport, not walk on: {out}"
    assert fake.room == "The Bakery", fake.room


@test
def travel_and_engage_are_both_tools_the_model_can_call():
    """Registering them as TOOLS is what keeps the boundary honest: the model
    still decides where to go and what to fight, it just cannot spend a call
    per step."""
    _, _, driver, _ = build()
    driver.install_tools()
    registered = driver.registry._context.tools
    assert "travel" in registered and "engage" in registered, sorted(registered)
    assert "Do not call `attack` in a loop" in driver._hunt_task(driver.assess())
    assert "Do not call `move` step by step" in driver._hunt_task(driver.assess())


# ---- a turn that achieved nothing ------------------------------------------

@test
def a_turn_that_achieved_nothing_triggers_recovery():
    """The first live run's deadlock, reproduced. At 44% health the driver
    would not rest (policy says 35%) and the model would not fight (it had
    decided 44% was too low), so two of six cycles went to turns that looked
    at the room and stopped. The driver now reads the structural fact -- the
    last turn produced nothing -- instead of arguing about the number."""
    fake, memory, driver, turns = build(hp="11/25")     # 44%: in the old dead zone
    fake.hp = 11
    a = driver.assess()
    assert 0.35 < a.health < 0.5, f"the test needs to sit in the gap: {a.health}"

    first = driver.step()
    assert first.action == "hunted", first          # nothing wrong yet, so it hunts
    assert driver._no_progress == 1, "the stub turn achieved nothing"

    second = driver.step()
    assert second.action == "resting", f"it re-asked the question instead: {second}"
    assert "achieved nothing" in second.note, second.note
    assert second.used_model is False, "recovering must not cost a model call"


@test
def resting_waits_for_the_game_clock():
    """The live run on 2026-08-04 sat down and then spun `check score` three
    times inside ONE SECOND, healing nothing, and finished with less health
    than it started resting with. Regeneration is on the server's tick, so a
    rest loop that does not spend real time is a busy-loop that burns its whole
    budget in seconds and stands up still hurt."""
    fake, memory, driver, _ = build(hp="5/30")
    fake.hp = 5                     # or the status prompt heals it on the first reply
    driver.policy = Policy(rest_seconds=20.0)

    first = driver.step()
    assert first.action == "resting" and first.note == "low health", first
    assert driver.slept == [], "sitting down is immediate; only the waiting waits"

    second = driver.step()
    assert second.action == "resting", second
    assert driver.slept == [20.0], f"the rest cycle did not spend any time: {driver.slept}"


@test
def recovery_does_not_spend_the_work_budget():
    """max_cycles budgets turns of WORK. The first task run on `dummy` began at
    3/93 movement from a session weeks earlier, correctly decided to rest, and
    spent all six cycles doing it without ever reading the task it was given."""
    fake, memory, driver, turns = build(hp="4/30", moves="2/85")
    fake.hp, fake.moves = 4, 2
    result = driver.run(max_cycles=2)

    worked = [c for c in result.cycles if c.used_model]
    rested = [c for c in result.cycles if not c.used_model]
    assert len(rested) > 0, "the test needs it to actually rest"
    assert len(result.cycles) > 2, f"resting ate the budget again: {result.cycles}"
    assert len(worked) <= 2, f"it overspent the budget: {len(worked)}"


@test
def a_run_that_never_gets_to_work_says_so():
    """Stopping because you never recovered is a different outcome from
    stopping because you did the work you paid for."""
    fake, memory, driver, _ = build(hp="1/30", moves="1/85")
    fake.hp, fake.moves = 1, 1
    driver.policy = Policy(max_rest_cycles=2, resume_above_health=0.99,
                           resume_above_movement=0.99)

    def never_helps(tool, args=None):
        fake.hp, fake.moves = 1, 1          # nothing ever heals
        return "ok"

    driver._do = never_helps
    driver.run_turn = lambda t: "ok"
    result = driver.run(max_cycles=1)
    assert result.stopped_because in ("stuck_recovering", "stalled", "max_cycles"), \
        result.stopped_because


@test
def a_dead_turn_at_full_health_does_not_rest():
    """Resting is the response to being unfit to try again, not to failure as
    such. An agent at full health in a room with nothing to fight must keep
    trying and let stall detection stop it -- otherwise it rests forever in an
    empty room, which is a worse loop than the one this replaced."""
    _, _, driver, _ = build(hp="30/30")
    driver.step()
    assert driver._no_progress == 1
    second = driver.step()
    assert second.action == "hunted", f"nothing to recover from: {second}"


@test
def recovery_after_a_dead_turn_stops_at_the_resume_threshold():
    """It rests back to resume_above_health, then stands up and tries again --
    so the next turn is asked in a different situation than the one that
    failed. That change of situation is the whole point."""
    fake, memory, driver, _ = build(hp="11/25")
    fake.hp = 11
    driver.step()                                   # hunts, achieves nothing
    assert driver.step().action == "resting"
    # Heal in both places. Memory is what the decision reads; the fake is what
    # the NEXT reply's status prompt will say, and the hooks read health back
    # off that -- so healing in only one of the two gets undone a cycle later.
    fake.hp = 24                                    # past 85% of 25
    memory.update_state(hp_now=24)
    third = driver.step()
    assert third.action == "stood_up", third
    assert driver.step().action == "hunted", "it should try again once recovered"


@test
def the_task_tells_the_model_the_policy_it_is_actually_run_under():
    """The numbers are read from Policy rather than written into the prompt, so
    retuning the policy cannot leave the prompt describing a rule the loop no
    longer follows."""
    _, _, driver, _ = build()
    driver.policy = Policy(rest_below_health=0.25, resume_above_health=0.9)
    task = driver._hunt_task(driver.assess())
    assert "25%" in task and "90%" in task, task[-400:]
    assert "35%" not in task, "a hardcoded number survived the retune"


# ---- an arbitrary task from a human ----------------------------------------

@test
def a_human_task_replaces_the_hunt():
    """Before this the driver only knew how to hunt, so 'go buy a weapon'
    became a turn telling the model to find something to kill. A loop you
    cannot point at a job is a grinder, not an agent."""
    _, _, driver, turns = build()
    driver.task = "Go to the Armory and buy a weapon you can actually use."
    driver.step()
    assert "TASK: Go to the Armory" in turns[0], turns[0][:200]
    assert "find one thing worth fighting" not in turns[0].lower(), "it hunted anyway"


@test
def the_task_turn_carries_the_mechanical_tools():
    """Any task needs to know travel and engage exist, or the model spends the
    turn calling move and attack one at a time -- which is exactly what the
    first live run did."""
    _, _, driver, turns = build()
    driver.task = "Find the bakery and buy bread."
    driver.step()
    assert "`travel`" in turns[0] and "`engage`" in turns[0], turns[0]
    assert "thief" in turns[0].lower(), "it should still play in character"


@test
def finishing_the_task_ends_the_run():
    """Done is a TOOL CALL, not a phrase in the reply. Matching text would mean
    inventing a sentinel the model has to reproduce exactly, and this codebase
    has already been bitten by treating a short string as an end-marker."""
    _, _, driver, _ = build()
    driver.task = "Say hello to the shopkeeper."
    driver.install_tools()

    def finish_on_second_turn(task):
        if driver._task_done is False and len(driver.cycles_seen) >= 1:
            driver.registry.dispatch("task_done", {"summary": "Said hello."})
        driver.cycles_seen.append(1)
        return "ok"

    driver.cycles_seen = []
    driver.run_turn = finish_on_second_turn
    result = driver.run(max_cycles=6)
    assert result.stopped_because == "task_done", result.stopped_because
    assert result.task_summary == "Said hello.", result.task_summary
    assert len(result.cycles) == 2, f"it kept going after done: {len(result.cycles)}"


@test
def a_waiting_level_outranks_the_task():
    """A level sitting unclaimed is free power that makes every later task
    easier, so it is worth the one detour first."""
    _, _, driver, turns = build(exp_to_level=0)
    driver.task = "Go and buy bread."
    cycle = driver.step()
    assert cycle.action == "trained", cycle
    assert "gain a level" in turns[0], turns[0][:150]


@test
def no_task_still_hunts():
    """The standing behaviour has to survive the new layer."""
    _, _, driver, turns = build()
    cycle = driver.step()
    assert cycle.action == "hunted", cycle
    assert "worth fighting" in turns[0].lower(), turns[0][:150]


@test
def declaring_done_with_no_task_is_refused():
    """Otherwise a stray call during a normal grind silently ends the run."""
    _, _, driver, _ = build()
    driver.install_tools()
    out = driver.registry.dispatch("task_done", {"summary": "nothing"})
    assert "no task" in out.lower(), out
    assert driver._task_done is False


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
    """Week 3's acceptance number: what fraction of ACTIONS needed the model."""
    _, memory, driver, _ = build(hp="5/30")
    result = driver.run(max_cycles=4)
    assert result.judgment_ratio is not None
    assert 0.0 <= result.judgment_ratio <= 1.0
    # This run opens with two mechanical recovery cycles, so it cannot be all model.
    assert result.judgment_ratio < 1.0, result.judgment_ratio
    assert result.mechanical_actions > 0, result.mechanical_actions


@test
def a_whole_fight_counts_as_one_judgment_not_one_per_swing():
    """The bug this metric had, reproduced. The first live run reported a 100%
    judgment ratio -- every cycle hunted, so every cycle called the model --
    while `engage` swung thirty-odd times inside those cycles for free. Counting
    cycles credited none of that; counting actions does."""
    fake, memory, driver, _ = build()
    driver.policy = Policy(max_fight_rounds=5)
    driver.install_tools()

    def model_calls_engage(task):
        # What the Agent does with a tool the model picked: dispatch it, then
        # fire after_tool WITHOUT the mechanical marker.
        result = driver.registry.dispatch("engage", {"target": "fido"})
        driver.hooks.fire(
            Hook.AFTER_TOOL,
            HookPayload(Hook.AFTER_TOOL, context=None, registry=driver.registry,
                        logger=None, name="engage", args={"target": "fido"},
                        result=result, ok=True, error=None),
        )
        return result

    driver.run_turn = model_calls_engage
    cycle = driver.step()

    assert cycle.used_model is True, cycle
    assert cycle.model_actions == 1, f"the model chose ONE thing: {cycle.model_actions}"
    # Five rounds of attack + check, plus the driver's own state reads.
    assert cycle.mechanical_actions >= 10, cycle.mechanical_actions

    result = RunResult(cycles=[cycle])
    assert result.judgment_ratio < 0.15, result.judgment_ratio
    assert result.cycle_judgment_ratio == 1.0, "the cycle DID need the model"


@test
def a_driver_without_hooks_still_counts_its_own_work():
    """Counting mechanical actions in _do rather than in the hook handler. If
    it were counted in the handler, a hookless driver would report every action
    as the model's -- exactly backwards."""
    ctx = Context(system="s", context_window=1_000_000)
    registry = Registry(ctx)
    mud_tools.register(registry, name="boukensha", password="x", session=FakeSession())
    registry.dispatch("mud_connect", {})
    memory = Memory("t", dir=Path(tempfile.mkdtemp()))
    memory.update_state(level=3, exp=100, exp_to_level=500, hp="5/30", moves="85/85")

    driver = Driver(goal="g", memory=memory, registry=registry,
                    run_turn=lambda task: "ok", hooks=None)
    cycle = driver.step()
    assert cycle.mechanical_actions > 0, cycle
    assert cycle.model_actions == 0, cycle


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
