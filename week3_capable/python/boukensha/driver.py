"""The grind loop: turn a goal into a next action, and notice when stuck.

This is the "decide" and "recover" half of week 3's goal statement, and the
part week 2 never had. Week 2 could act and remember; it could not sequence.

    driver = Driver(goal="reach level 5", memory=mem, registry=reg, run_turn=fn)
    result = driver.run(max_cycles=40)

WHERE JUDGMENT LIVES (docs/plans/week3/00_judgment_boundary.md). Each cycle the
driver assesses state mechanically and then either acts mechanically or hands
the turn to the model:

  mechanical, no model call      resting when exhausted, standing up, deciding
                                 that experience went up, detecting a stall
  handed to the model            what to fight, where to go, what to train

The point is not to minimise model calls -- an agent that never reasons walks
into the lava pit. It is that routine work should not cost a model call, so
the model's turns are spent on decisions a human would also have to think
about. The ratio between the two is week 3's acceptance metric.

THRESHOLDS HERE ARE POLICY, NOT DISGUISED JUDGMENT. "Rest below 35% health" is
an explicit, auditable decision with a tuning knob on it; if 35 is wrong a
reviewer calls it a bad setting, not a bug. That is the distinction the
judgment-boundary doc draws against thresholds that stand in for a conclusion
the system should have reasoned its way to.
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass, field

from .hooks import Hook, HookPayload


def _ratio(value):
    """'23/57' -> 0.40. Returns None when the shape isn't a fraction."""
    if isinstance(value, (int, float)):
        return None
    m = re.match(r"^\s*(\d+)\s*/\s*(\d+)\s*$", str(value or ""))
    if not m:
        return None
    cur, mx = int(m.group(1)), int(m.group(2))
    return (cur / mx) if mx else None


@dataclass
class Policy:
    """Tuning knobs for decisions that are already explicit. Every one of these
    is a number a reviewer can argue with; none of them stands in for a
    judgment the agent should be making."""

    rest_below_health: float = 0.35      # fraction of max HP
    resume_above_health: float = 0.85
    rest_below_movement: float = 0.15
    # 0.40, not the 0.60 this started at. Movement regenerates slowly -- `dummy`
    # sat at 19/93 after a live run -- and 0.60 meant waiting for 56 points
    # before doing anything. You do not need a full tank to run an errand: at
    # 0.40 a 93-move character has 37 moves, which covers any route in town with
    # room to get back. Lowered on evidence, and still a number to argue with.
    resume_above_movement: float = 0.40
    stall_cycles: int = 3                # cycles with no progress before we stop
    max_rest_cycles: int = 12            # give up resting rather than loop forever
    recover_after_dead_cycles: int = 1   # turns that achieved nothing before we recover
    rest_seconds: float = 20.0           # real seconds to wait between rest checks
    flee_below_health: float = 0.30      # break off a fight at this much HP left
    max_fight_rounds: int = 15           # a fight this long is not going our way
    max_travel_steps: int = 30           # a route longer than this is a loop, not a route


@dataclass
class Assessment:
    level: int | None = None
    exp: int | None = None
    exp_to_level: int | None = None
    health: float | None = None          # 0..1
    movement: float | None = None
    position_state: str | None = None
    room: str | None = None
    practice_sessions: int | None = None


@dataclass
class CycleResult:
    action: str                          # what the driver did
    used_model: bool                     # did this cycle cost a model call?
    note: str = ""
    assessment: Assessment | None = None
    mechanical_actions: int = 0          # tool calls the driver made itself
    model_actions: int = 0               # tool calls the model chose


@dataclass
class RunResult:
    cycles: list = field(default_factory=list)
    stopped_because: str = ""
    starting_exp: int | None = None
    ending_exp: int | None = None
    task_summary: str = ""

    @property
    def experience_gained(self):
        if self.starting_exp is None or self.ending_exp is None:
            return None
        return self.ending_exp - self.starting_exp

    @property
    def mechanical_actions(self):
        return sum(c.mechanical_actions for c in self.cycles)

    @property
    def model_actions(self):
        return sum(c.model_actions for c in self.cycles)

    @property
    def judgment_ratio(self):
        """Fraction of ACTIONS that needed the model. Week 3's headline metric.
        A ratio to understand, not to minimise: 0 is the lava-pit walker, 1 is
        the loop that reasons about standing up.

        Counted per action, not per cycle, and the difference is not cosmetic.
        The first live run scored 100% on the cycle version -- all three cycles
        hunted, so all three called the model -- while `engage` was mechanically
        swinging thirty-odd times inside them. The number argued against the
        exact thing the week built. An action is one tool call: the model
        deciding to fight counts once, and every swing that follows counts on
        the other side of the ledger, which is what "judgment is amortised over
        replay" means when you write it down as a number.
        """
        total = self.mechanical_actions + self.model_actions
        if not total:
            return None
        return self.model_actions / total

    @property
    def cycle_judgment_ratio(self):
        """The same question asked per cycle: how many turns of the loop needed
        the model at all. Kept because it answers something the action ratio
        cannot -- a run of 40 cycles that never once needed the model is a very
        different animal from one that needed it every cycle, even if both do
        most of their ACTIONS mechanically."""
        if not self.cycles:
            return None
        return sum(1 for c in self.cycles if c.used_model) / len(self.cycles)


class Driver:
    def __init__(self, *, goal, memory, registry, run_turn, policy=None, logger=None,
                 hooks=None, sleep=None, task=None):
        # Injectable so the offline tests do not actually wait. Production
        # passes nothing and gets the real clock, which is the only thing that
        # makes resting work -- see the resting branch of _step.
        self._sleep = sleep if sleep is not None else time.sleep
        self.goal = goal
        # A job handed in by a human, worked on instead of the standing goal
        # until the model calls task_done. None means "just pursue the goal".
        self.task = task
        self._task_done = False
        self._task_summary = ""
        self.memory = memory
        self.registry = registry
        self.run_turn = run_turn          # callable(task_text) -> str
        self.policy = policy or Policy()
        self.logger = logger
        # The same Hooks the Agent fires. Without it the driver's own tool
        # calls never reach memory -- see _do.
        self.hooks = hooks
        self._resting = 0
        self._no_progress = 0
        self._mechanical_actions = 0
        self._model_actions = 0
        # Sentinel, not None: None is a real level value on a cold start, and
        # using it here would ask for the practice count twice.
        self._level_when_asked = object()
        # Model-chosen tool calls are counted where they happen -- in the
        # Agent -- rather than inferred from the turn's reply text. after_tool
        # is the one seam both sides pass through, so it is the only place the
        # two halves of the ledger can be compared honestly.
        if hooks is not None:
            hooks.on(Hook.AFTER_TOOL, self._count_model_action)

    def _count_model_action(self, payload):
        """Every tool call that was NOT ours. The driver marks its own dispatches
        `mechanical` in _do; anything else reaching this seam is a tool the model
        chose to call, which is exactly what the metric wants to count."""
        if not getattr(payload, "mechanical", False):
            self._model_actions += 1

    # ---- assess ----------------------------------------------------------

    def assess(self):
        """Read state from memory. Free -- the lifecycle hooks already keep it
        current from the status prompt on nearly every reply, so this costs
        neither a model call nor a MUD round trip."""
        s = self.memory.state
        health = _ratio(self.memory.live_hp())
        movement = _ratio(self.memory.live_moves())
        room = None
        if s.get("position"):
            room = self.memory.rooms().get(s["position"], {}).get("name")
        return Assessment(
            level=s.get("level"),
            exp=s.get("exp"),
            exp_to_level=s.get("exp_to_level"),
            health=health,
            movement=movement,
            position_state=s.get("position_state"),
            room=room,
            practice_sessions=s.get("practice_sessions"),
        )

    # ---- mechanical actions ---------------------------------------------

    def _needs_recovery(self, a):
        # Full phrases, because this string IS the note on the cycle and ends up
        # in the session log. Returning bare "health" and formatting it at the
        # call site produced "low a turn that achieved nothing" in the 2026-08-04
        # log once a third reason existed that was not a noun.
        if a.health is not None and a.health < self.policy.rest_below_health:
            return "low health"
        if a.movement is not None and a.movement < self.policy.rest_below_movement:
            return "low movement"
        # A turn that achieved nothing, and we are not in shape to try again.
        #
        # WHY THIS IS HERE AND NOT A BIGGER NUMBER ON rest_below_health. The
        # first live run deadlocked between 35% and 50% health: the driver
        # would not rest, because policy said 44% was fine, and the model would
        # not fight, because it had decided 44% was not. Two of six cycles went
        # to turns that looked at the room and stopped. Raising the threshold to
        # 50% would close that particular gap and reopen it silently the moment
        # the model's instinct moved -- it is tuning our policy to fit someone
        # else's opinion.
        #
        # The structural fact is better than the number: the last turn produced
        # nothing. That is true whatever the model's reason was, and the two
        # dead cycles had DIFFERENT reasons -- one was hurt, the other judged
        # the room empty of anything worth fighting. Re-asking the identical
        # question after a turn that failed is the actual defect; recovering
        # first changes the situation the next turn is asked about.
        #
        # Same move as experience-rising to detect a kill and movement cost to
        # detect a real walk: read the structural signal, not the wording.
        if (self._no_progress >= self.policy.recover_after_dead_cycles
                and not self._recovered(a)):
            return "a turn that achieved nothing"
        return None

    def _recovered(self, a):
        ok_health = a.health is None or a.health >= self.policy.resume_above_health
        ok_moves = a.movement is None or a.movement >= self.policy.resume_above_movement
        return ok_health and ok_moves

    def _do(self, tool, args=None):
        """Run a tool directly. No model call -- this is the mechanical half.

        Fires after_tool exactly as the Agent does. This is not optional
        bookkeeping: MemoryHooks reads vitals off the status prompt in that
        handler, so a dispatch that skips it is invisible to memory. The first
        version skipped it, and the effect was that `check` while resting never
        updated health -- so the driver could not tell it had recovered and sat
        down until max_rest_cycles bailed it out. Found on the first dry run.
        """
        ok, error, result = True, None, None
        self._mechanical_actions += 1
        try:
            result = self.registry.dispatch(tool, args or {})
        except Exception as e:  # noqa: BLE001 -- a dead connection must not end the run
            ok, error = False, e
            result = f"error: {type(e).__name__}: {e}"
        if self.hooks is not None:
            self.hooks.fire(
                Hook.AFTER_TOOL,
                HookPayload(
                    Hook.AFTER_TOOL,
                    context=None,
                    registry=self.registry,
                    logger=self.logger,
                    name=tool,
                    args=args or {},
                    result=result,
                    ok=ok,
                    error=error,
                    # Marks this side of the ledger. Counted above rather than
                    # in the hook handler on purpose: a driver built without
                    # hooks still has to count its own work, or a run with no
                    # hooks would report every action as the model's.
                    mechanical=True,
                ),
            )
        return result

    # ---- the mechanical fight -------------------------------------------

    def engage(self, target, opener=None):
        """Fight `target` to a conclusion. No model calls at all.

        `opener` is an optional skill to lead with -- backstab, for a thief.
        WHETHER to open with it is judgment and stays with the model: backstab
        needs you hidden and the target unaware, and it is wasted otherwise. So
        the model decides and passes it in; landing it and then grinding out
        the remaining rounds is routine, and happens here.

        THIS IS THE WEEK'S THESIS IN ONE METHOD. The first live run spent 9
        consecutive model calls sending `attack fido` and 7 more sending
        `check score` while waiting to heal -- roughly 16 of one turn's 25
        iterations doing something with no decision in it. Swinging again at
        the thing you already decided to fight is not judgment; picking what
        to fight is. So the model picks, by calling this tool, and the swinging
        happens here for free.

        HOW IT KNOWS THE TARGET DIED: experience went up. Not by matching the
        server's death message -- a phrase match would be one wording change
        away from an infinite loop, and this codebase already chose a
        structural signal over a phrase once before (movement cost, to tell
        walking from being teleported by death; see memory_hooks). Experience
        rising is the definition of something having died.

        Health comes off the status prompt that rides on every combat reply,
        so breaking off is checked every round without a single extra call.

        KNOWN LIMIT, observed live: experience proves SOMETHING died, not that
        it was `target`. CircleMUD resolves combat rounds on its own tick, so a
        fight started earlier can finish while this call is swinging at
        something else, and the gain lands here. The second live run did
        exactly that -- it reported a kill for a target that did not exist,
        while an earlier fido fight finished in the background. The signal is
        still the right one (it is structural, and it never hangs), so the
        wording is what changed: this reports "a kill happened while fighting
        X", not "X died". Attributing it properly would need a real combat-
        state parser, which is a bigger job than this week has room for.
        """
        before = self._ensure_state()
        rounds = 0
        if opener:
            self._do("skill_strike", {"skill": opener, "target": target})
        while rounds < self.policy.max_fight_rounds:
            self._do("attack", {"style": "kill", "target": target})
            rounds += 1

            a = self.assess()
            if a.health is not None and a.health < self.policy.flee_below_health:
                self._do("flee", {})
                return (f"BROKE OFF after {rounds} rounds against {target}: down to "
                        f"{a.health:.0%} health, so I fled. Rest before trying again, "
                        f"and consider whether {target} is too strong.")

            # Mechanical, no model call. The status prompt gives health for
            # free but not experience, so this is the one round trip per round.
            self._do("check", {"kind": "score"})
            after = self.assess()
            if (after.exp is not None and before.exp is not None
                    and after.exp > before.exp):
                gained = after.exp - before.exp
                return (f"KILL after {rounds} rounds fighting {target}. +{gained} "
                        f"experience (now {after.exp}), health {after.health:.0%}. "
                        f"Loot the corpse if it dropped anything.")

        a = self.assess()
        return (f"STILL FIGHTING {target} after {rounds} rounds and it is not dying. "
                f"Health {'unknown' if a.health is None else f'{a.health:.0%}'}. "
                f"Break off and pick a different target.")

    # ---- the mechanical walk ---------------------------------------------

    def travel(self, destination):
        """Walk to a place already in memory. No model calls at all.

        THIS IS THE CASE THE WEEK'S CENTRAL QUESTION IS ABOUT. Walking a route
        is an algorithm -- shortest path over stored edges -- and the plan doc
        asks whether an algorithm doing the walking can be called capable. It
        can, because of where the map came from: every edge here was recorded
        when the agent actually walked it and saw where it came out. Nothing is
        inferred, and reverse directions are only known once walked, because
        CircleMUD has one-way exits. The judgment happened at acquisition; this
        replays it for free. A wall-follower that walks into the lava pit is the
        opposite case and would fail on exactly that distinction.

        WHY IT RECOMPUTES THE ROUTE EVERY STEP instead of walking the list it
        got at the start. Following a fixed list assumes each move lands where
        the map said it would, and the whole reason this codebase records only
        walked edges is that the map is not trusted that far. Recomputing means
        a move that comes out somewhere unexpected re-plans from wherever we
        actually are, rather than continuing to walk directions that no longer
        apply. It costs nothing -- the search is over a map with a few dozen
        edges, in memory.

        THREE WAYS IT STOPS SHORT, all reported rather than pushed through,
        because each one is a decision the model should make:

          unknown place   never been there. "I don't know the way" is a real
                          answer that means go explore, not an error.
          blocked         the move did not change where we are -- a closed
                          door, a mob in the way, or being in combat. Which of
                          those it is, and what to do, is judgment.
          out of movement walking is not free. The driver's own recovery cycle
                          handles resting; travel just stops before it strands
                          the character somewhere with no way home.

        The blocked check is "where we are did not change", which also fires
        when a move DID happen but its reply could not be parsed -- an unlit
        room being the real case. That is a false report of being blocked, and
        it is the safe direction to be wrong in: we stop and hand the situation
        to the model, rather than continuing to walk from a room we are no
        longer in. Telling the two apart needs the room text, and an unlit room
        is precisely where there is none.
        """
        target = self.memory.find_room(destination)
        if target is None:
            known = sorted({r.get("name", "")
                            for r in self.memory.rooms().values() if r.get("name")})
            return (f"NO SUCH PLACE in memory: '{destination}'. Places you know: "
                    f"{', '.join(known) if known else '(none yet)'}. "
                    f"You will have to explore to find it.")

        walked = []
        for _ in range(self.policy.max_travel_steps):
            here = self.memory.position
            if here is None:
                # Position is a belief, and an unparsable move clears it rather
                # than guessing (see memory_hooks). One look re-establishes it.
                self._do("look", {})
                here = self.memory.position
                if here is None:
                    return (f"LOST after {len(walked)} moves ({', '.join(walked) or 'none'}): "
                            f"I cannot tell which room I am in, so I stopped rather than "
                            f"walk blind. Look around and try again.")
            if here == target:
                name = self.memory.rooms().get(target, {}).get("name", destination)
                if not walked:
                    return f"ALREADY at {name}."
                return (f"ARRIVED at {name} after {len(walked)} moves "
                        f"({', '.join(walked)}).")

            route = self.memory.route(here, target)
            if route is None:
                name = self.memory.rooms().get(target, {}).get("name", destination)
                return (f"NO KNOWN ROUTE to {name} from here, after {len(walked)} moves "
                        f"({', '.join(walked) or 'none'}). The place is in memory but no "
                        f"path from here has ever been walked. Explore toward it.")

            a = self.assess()
            if a.movement is not None and a.movement < self.policy.rest_below_movement:
                return (f"STOPPED after {len(walked)} moves ({', '.join(walked) or 'none'}): "
                        f"movement down to {a.movement:.0%} and the route is not finished. "
                        f"Rest, then travel again -- the route will be recomputed from "
                        f"wherever you are.")

            direction = route[0]
            self._do("move", {"direction": direction})
            if self.memory.position == here:
                # Same room after a move means it did not happen. Reported, not
                # retried: retrying a blocked direction is how a mechanical
                # walker spends thirty moves going nowhere.
                room = self.memory.rooms().get(here, {}).get("name", "here")
                return (f"BLOCKED going {direction} from {room} after {len(walked)} moves "
                        f"({', '.join(walked) or 'none'}). Something is in the way -- a "
                        f"closed door, a mob, or you are in combat. Deal with it or find "
                        f"another way.")
            walked.append(direction)

        return (f"GAVE UP after {len(walked)} moves ({', '.join(walked)}) without reaching "
                f"'{destination}'. That is more steps than any real route here, so "
                f"something is wrong with the map or the way is not what memory thinks.")

    def install_tools(self, registry=None):
        """Expose the mechanical routines as tools the model can invoke.

        Registering the fight as a TOOL rather than a driver phase is what
        keeps the judgment boundary honest. The model still decides what to
        attack and when -- it just cannot spend a model call per swing, because
        the swinging is on the other side of a tool call.
        """
        reg = registry if registry is not None else self.registry
        reg.tool(
            "engage",
            description=(
                "Fight a target to a conclusion and report the outcome. Attacks "
                "repeatedly, breaks off automatically if your health gets low, and "
                "stops when the target dies. Use this INSTEAD of calling attack over "
                "and over -- one call covers the whole fight. Use `consider` first to "
                "judge whether the target is safe to fight."
            ),
            parameters={
                "target": {"type": "string",
                           "description": "The mob to fight, e.g. 'fido'"},
                "opener": {"type": "string",
                           "description": "Optional skill to lead with, e.g. 'backstab'. "
                                          "Only worth it if you are hidden and the target "
                                          "has not noticed you."},
            },
            block=self.engage,
        )
        reg.tool(
            "travel",
            description=(
                "Walk all the way to a place you have already been, by name (e.g. 'the "
                "bakery'). One call covers the whole trip. Use this INSTEAD of calling "
                "move over and over. It tells you if the place is unknown, if no route "
                "from here has been walked yet, or if something blocked the way — in "
                "each of those cases it stops and reports rather than guessing, and it "
                "is then your decision what to do."
            ),
            parameters={
                "destination": {"type": "string",
                                "description": "Place name, e.g. 'Market Square'"},
            },
            block=self.travel,
        )
        reg.tool(
            "task_done",
            description=(
                "Declare the task you were given finished, and say what happened. "
                "Call this ONLY when the job is actually complete, or when it turns "
                "out to be impossible and you want to say why. You do not need to "
                "finish inside one turn — the loop will give you more."
            ),
            parameters={
                "summary": {"type": "string",
                            "description": "What happened, in a sentence or two."},
            },
            block=self.finish_task,
        )
        return self

    def finish_task(self, summary=""):
        """The model saying it is done.

        A TOOL rather than a phrase the driver looks for in the reply. Matching
        text would mean inventing a sentinel the model has to reproduce exactly,
        and this codebase has already been bitten once by treating a short
        string as a reliable end-marker -- the `"> "` prompt that also appears
        mid-output (see mud_session.read_until_prompt). A tool call is
        unambiguous, and it cannot be said by accident while narrating.
        """
        if not self.task:
            return ("There is no task in front of you right now — you are working "
                    "the standing goal. Nothing to finish.")
        self._task_done = True
        self._task_summary = str(summary or "").strip()
        return f"Task closed: {self._task_summary or '(no summary given)'}"

    def _ensure_state(self):
        """Learn our own vitals if we do not know them yet.

        Track, don't poll: MemoryHooks keeps health and movement current from
        the status prompt that rides on nearly every reply, so this normally
        costs nothing. But on the very first cycle nothing has replied yet, and
        a driver that does not know its health cannot decide to rest -- the
        first dry run hunted straight past an empty state because every
        threshold compared against None. One mechanical `check` fixes that; it
        is not repeated while the tracked values hold.
        """
        a = self.assess()
        if a.health is None or a.movement is None or a.level is None:
            self._do("check", {"kind": "score"})
            a = self.assess()

        # Practice sessions are not in `score`, so they need their own ask --
        # once at the start, and again whenever the level changes, because
        # levelling is what grants new ones. Not polled every cycle: after a
        # skill is practised the reply carries the new count, and MemoryHooks
        # reads it off any reply, so the number stays current for free.
        if a.practice_sessions is None or a.level != self._level_when_asked:
            self._do("practice", {})
            self._level_when_asked = a.level
            a = self.assess()
        return a

    # ---- one cycle -------------------------------------------------------

    def step(self):
        """One cycle, with its action counts attached.

        The counting wraps _step rather than living inside it because _step has
        six return paths and the interesting work happens underneath them --
        inside `engage`, which the model reaches through a tool call, not
        through anything _step can see.
        """
        before_mech, before_model = self._mechanical_actions, self._model_actions
        cycle = self._step()
        cycle.mechanical_actions = self._mechanical_actions - before_mech
        cycle.model_actions = self._model_actions - before_model
        return cycle

    def _step(self):
        a = self._ensure_state()

        # 1. Recovery. Mechanical: the game states the condition and there is
        #    one correct response. Reasoning about whether to sit down when
        #    exhausted is the definition of reasoning on rails.
        if self._resting:
            if self._recovered(a) or self._resting >= self.policy.max_rest_cycles:
                self._resting = 0
                self._do("set_position", {"position": "stand"})
                return CycleResult("stood_up", False, "recovered", a)
            self._resting += 1
            # WAIT. Regeneration happens on the game's clock, not ours.
            #
            # Without this the rest loop is a busy-loop: the live run on
            # 2026-08-04 sat down and then spun `check score` three times inside
            # ONE SECOND, healing nothing, and ended the run at less health than
            # it started resting with. All twelve max_rest_cycles would have
            # burned in about four seconds, after which it stands up still hurt
            # and walks straight back into the deadlock resting was added to
            # break. The decision to rest was right; resting just did not do
            # anything. Only max_cycles running out first hid it.
            #
            # There is no clever version of this. Real health takes real time,
            # so the loop has to spend some. The interval is policy -- a number
            # a reviewer can argue with -- not a measurement of the server's
            # tick, which we deliberately do not try to infer.
            self._sleep(self.policy.rest_seconds)
            self._do("check", {"kind": "score"})     # refresh vitals while waiting
            return CycleResult("resting", False, f"cycle {self._resting}", a)

        why = self._needs_recovery(a)
        if why:
            self._resting = 1
            self._do("set_position", {"position": "rest"})
            return CycleResult("resting", False, why, a)

        # 2. Everything else is a task, and choosing which one is the driver's
        #    own judgment -- the cheap kind, made from state it already has.
        mode, task = self._next_task(a)
        self.run_turn(task)
        if mode == "trained":
            # Re-ask mechanically instead of trusting the turn to have told us.
            # Live 2026-08-05 the model walked to the guild and practised
            # backstab poor -> average, but the reply it happened to get back
            # did not carry the remaining count, so the driver still believed
            # there was a session to spend and burned a second model cycle
            # rediscovering that there was not. One round trip is cheaper than
            # one turn, and this is a fact we can just look up.
            self._do("practice", {})
        progressed = self._check_progress(a)
        note = "progress" if progressed else "no progress"
        if self._task_done:
            note = "task done"
        return CycleResult(mode, True, note, a)

    # ---- choosing what to do ---------------------------------------------

    def _next_task(self, a):
        """Pick the mode this cycle calls for, and build the turn for it.

        THIS IS THE GOAL DECOMPOSITION. Before it, the driver only knew how to
        hunt: every goal string got interpolated into a combat prompt, so
        "go buy a weapon" produced a turn telling the model to find something to
        kill. That made the loop a grinder rather than something you can point
        at a job.

        The split is the same one the whole week runs on. WHICH mode applies is
        decided here, mechanically, from state the driver already has -- no
        model call, because "you have enough experience to level" is a fact, not
        a judgment. What to DO inside the mode is the model's, because which
        skill to practise or what is safe to fight genuinely depends on how this
        character plays.

        A human-given task outranks the standing goal but not levelling: a level
        waiting to be claimed is free power, and it makes every later task
        easier, so it is worth the one detour first.
        """
        # Unspent practice sessions, NOT `exp_to_level <= 0`, which is what this
        # tested before and could never fire: CircleMUD levels you the moment
        # you earn the experience, so the counter drops to the next threshold
        # and resets without ever being observed at zero. The whole training
        # branch was unreachable, and `dummy` was found on 2026-08-05 sitting
        # on an unspent session with backstab still at "poor" -- the skill its
        # best kills depend on.
        if a.practice_sessions:
            return "trained", self._train_task(a)
        if self.task and not self._task_done:
            return "task", self._given_task(a)
        return "hunted", self._hunt_task(a)

    def _preamble(self, a):
        """What is true right now, in front of every task.

        Repeated per turn on purpose. The conversation persists across cycles,
        so the model can see what it did before -- but health and position move
        underneath it between turns, and a turn that plans around remembered
        vitals plans around stale ones.
        """
        where = f"You are in {a.room}. " if a.room else ""
        health = "" if a.health is None else f"Health {a.health:.0%}. "
        return f"{where}{health}"

    def _tooling_note(self):
        """The mechanical routines, described once, for any task.

        Every task needs to know these exist, or the model spends its turn
        calling `move` and `attack` one at a time -- which is what the first
        live run did, filling its whole budget with work that had no decision
        in it.
        """
        return (
            "- `travel` walks a whole route you already know, in one call. Do not "
            "call `move` step by step for a route you know. If it says the place or "
            "the route is unknown, that is real — explore deliberately.\n"
            "- `engage` fights a target to a conclusion in one call, and breaks off "
            "if your health drops. Do not call `attack` in a loop.\n"
            "- `recall` reads what you already know before you go looking. Your notes "
            "carry knowledge from earlier sessions — treat them as claims worth "
            "checking, not gospel.\n"
            "- `remember_learning` records anything that surprised you, so the next "
            "session starts ahead of this one.\n"
        )

    def _given_task(self, a):
        """A job handed to the loop by a human.

        Deliberately thin. The point is NOT to translate the request into game
        commands -- that is the model's job and it is better at it than any
        phrasing rules we would write. The driver's contribution is the frame:
        what is true now, what the mechanical tools are, and how to say you are
        finished. Everything else is the human's words, passed through.
        """
        return (
            f"TASK: {self.task}\n\n"
            f"{self._preamble(a)}Work on this task. It is the whole job for this "
            f"turn — the standing goal ({self.goal}) can wait.\n\n"
            f"{self._tooling_note()}"
            "- When the task is genuinely finished, call `task_done` with a short "
            "summary of what happened. Do not call it early — the loop will keep "
            "giving you turns, so an unfinished job is fine to continue next turn.\n"
            "- If the task turns out to be impossible, or needs something you do not "
            "have, call `task_done` and say so plainly. Being stuck is a real answer "
            "and a better one than pretending.\n\n"
            "Play in character: you are a thief. Prefer stealth, openers and picking "
            "your fights over trading blows.\n\n"
            "The loop around you handles resting and recovery between turns, so do "
            "not sit and wait for health."
        )

    def _train_task(self, a):
        n = a.practice_sessions or 0
        return (
            f"{self._preamble(a)}You have {n} unspent practice "
            f"session{'' if n == 1 else 's'}. Go to your guild and spend "
            f"{'it' if n == 1 else 'them'}.\n\n"
            f"{self._tooling_note()}"
            "- Choose which skill to improve based on how you actually play — you are "
            "a thief, so backstab, sneak and hide matter more than raw melee. Your "
            "notes may say what is already practised and how well it works.\n"
            "- Report what you trained and why."
        )

    def _hunt_task(self, a):
        """The turn we hand to the model.

        Most of this is telling it what NOT to do, and that is deliberate. The
        first live run showed the model filling its whole iteration budget with
        work that has no decision in it -- swinging at a mob it had already
        chosen, and polling `check score` while waiting to heal. Both now
        happen mechanically, so the turn is spent on the parts that need a
        reason: where to go, what is worth fighting, when something has gone
        wrong.
        """
        where = f"You are in {a.room}. " if a.room else ""
        return (
            f"Goal: {self.goal}.\n\n"
            f"{where}Find one thing worth fighting and kill it.\n\n"
            "- `consider` your target first, and pick something else if the answer "
            "suggests you would lose. Check your memory notes for mobs already known "
            "to be dangerous.\n"
            "- You are a thief. If you can hide first and the target has not noticed "
            "you, pass opener='backstab' -- it is by far your best opening. If you are "
            "already seen, or you have not practised the skill, skip it.\n"
            "- Then call `engage` with that target. ONE call fights the whole thing "
            "and reports what happened. Do not call `attack` in a loop -- `engage` "
            "already does that, and it will flee for you if your health drops.\n"
            "- To go somewhere you have already been, call `travel` with the place name. "
            "ONE call walks the whole way. Do not call `move` step by step for a route "
            "you already know.\n"
            "- Loot the corpse afterwards.\n"
            "- Record anything surprising with `remember_learning`, especially a mob "
            "that turned out to be far stronger than it looked, or a room where "
            "something else joined the fight.\n\n"
            "DO NOT rest, sleep, or wait for health to come back, and do not poll "
            "`check` repeatedly to watch it regenerate. The loop around you handles "
            "recovery between turns. When you have made a kill or decided this room "
            "has nothing worth fighting, say so and end your turn.\n\n"
            # The numbers come from Policy rather than being written out here, so
            # that retuning the policy cannot leave the prompt describing a rule
            # the loop no longer follows. The live run's deadlock was exactly a
            # disagreement about this number; stating it removes the guesswork,
            # and _needs_recovery covers the case where the model disagrees anyway.
            f"About your health: the loop rests you automatically below "
            f"{self.policy.rest_below_health:.0%}, and after any turn that achieves "
            f"nothing it rests you back up to {self.policy.resume_above_health:.0%} "
            f"before asking again. So above {self.policy.rest_below_health:.0%} you "
            f"are expected to fight rather than wait. If you genuinely think you are "
            f"too hurt, end the turn saying so — that counts as a turn that achieved "
            f"nothing, and you will be rested before the next one.\n\n"
            # This used to read "do not leave the zone you are in", which was a
            # rail from when the character was a level-1 throwaway in a newbie
            # alley with nothing worth walking to. For a levelled character it
            # forbids the whole point: city mobs pay 1-6 experience and the
            # Newbie Zone pays 150-670, and they are different zones. A blanket
            # ban was standing in for the real concern, which is not "moving" --
            # it is going somewhere you cannot handle or cannot get back from.
            "Hunt where it is actually worth hunting. Your notes may name grounds "
            "that paid well before; going there is fine and often right. Two rules: "
            "know the way back before you commit to a long walk, and do not pick a "
            "fight you have no reason to think you can win — `consider` first, and "
            "believe it.\n\n"
            "Never attack guards or players."
        )

    def _check_progress(self, before):
        after = self.assess()
        gained = (
            before.exp is not None and after.exp is not None and after.exp > before.exp
        ) or (
            before.level is not None and after.level is not None and after.level > before.level
        )
        if gained:
            self._no_progress = 0
        else:
            self._no_progress += 1
        return gained

    # ---- the run ---------------------------------------------------------

    def run(self, *, max_cycles=25, until=None):
        """Cycle until the goal is met, we stall, or we run out of cycles.

        Stall detection is the 'recover' half of the goal statement and the
        thing week 2 planned and never built: an unattended agent that is stuck
        has no way to notice, and will happily burn an entire night doing
        nothing. Mechanical to detect; what to do about it is the operator's
        call, so we stop and say so rather than guessing.
        """
        # _ensure_state, not assess: on a cold start memory has no experience
        # figure yet, and a starting value of None makes experience_gained
        # unreportable for the whole run.
        result = RunResult(starting_exp=self._ensure_state().exp)
        # max_cycles budgets TURNS OF WORK, not wall-clock ticks. Recovery is
        # overhead: it costs no model call, and counting it here means a
        # character that starts tired spends its whole budget sitting down. The
        # first task run on `dummy` did exactly that -- it began at 3/93
        # movement from a session weeks earlier, correctly decided to rest, and
        # used all six cycles doing it without ever reading the task.
        #
        # The hard cap is the backstop: recovery is bounded by max_rest_cycles,
        # but a loop that rests, stands, fails, and rests again would otherwise
        # have nothing stopping it.
        budget, performed, hard_cap = max_cycles, 0, max_cycles * 4
        while budget > 0 and performed < hard_cap:
            cycle = self.step()
            performed += 1
            if cycle.used_model:
                budget -= 1
            result.cycles.append(cycle)
            if self.logger is not None:
                self.logger.driver_cycle(
                    action=cycle.action, used_model=cycle.used_model, note=cycle.note,
                    mechanical_actions=cycle.mechanical_actions,
                    model_actions=cycle.model_actions,
                )
            # A finished task ends the run. Without this the loop would notice
            # only via the stall counter, three wasted turns later, after handing
            # the model a job it had already reported complete.
            if self._task_done:
                result.stopped_because = "task_done"
                result.task_summary = self._task_summary
                break
            if until is not None and until(self.assess()):
                result.stopped_because = "goal_met"
                break
            if self._no_progress >= self.policy.stall_cycles:
                result.stopped_because = "stalled"
                break
        else:
            # Distinguish "did the work we paid for" from "never got to work".
            # Both end the run, but only one of them is a healthy finish.
            result.stopped_because = "max_cycles" if budget <= 0 else "stuck_recovering"
        result.ending_exp = self.assess().exp
        if self.logger is not None:
            self.logger.driver_run(
                goal=self.goal, task=self.task, cycles=len(result.cycles),
                stopped_because=result.stopped_because,
                starting_exp=result.starting_exp, ending_exp=result.ending_exp,
            )
        return result
