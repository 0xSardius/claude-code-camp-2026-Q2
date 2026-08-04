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
    resume_above_movement: float = 0.60
    stall_cycles: int = 3                # cycles with no progress before we stop
    max_rest_cycles: int = 12            # give up resting rather than loop forever
    flee_below_health: float = 0.30      # break off a fight at this much HP left
    max_fight_rounds: int = 15           # a fight this long is not going our way


@dataclass
class Assessment:
    level: int | None = None
    exp: int | None = None
    exp_to_level: int | None = None
    health: float | None = None          # 0..1
    movement: float | None = None
    position_state: str | None = None
    room: str | None = None


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
                 hooks=None):
        self.goal = goal
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
        )

    # ---- mechanical actions ---------------------------------------------

    def _needs_recovery(self, a):
        if a.health is not None and a.health < self.policy.rest_below_health:
            return "health"
        if a.movement is not None and a.movement < self.policy.rest_below_movement:
            return "movement"
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
        return self

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
        if a.health is not None and a.movement is not None and a.level is not None:
            return a
        self._do("check", {"kind": "score"})
        return self.assess()

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
            self._do("check", {"kind": "score"})     # refresh vitals while waiting
            return CycleResult("resting", False, f"cycle {self._resting}", a)

        why = self._needs_recovery(a)
        if why:
            self._resting = 1
            self._do("set_position", {"position": "rest"})
            return CycleResult("resting", False, f"low {why}", a)

        # 2. Level available -> go train. WHICH skill to practise is a
        #    judgment (it depends on playstyle and what the character lacks),
        #    so the model gets that turn.
        if a.exp_to_level is not None and a.exp_to_level <= 0:
            self.run_turn(
                "You have enough experience to gain a level. Go to your guild and "
                "practise. Choose which skill to improve based on how you actually "
                "play — you are a thief, so backstab, sneak and hide matter more "
                "than raw melee. Report what you trained and why."
            )
            return CycleResult("trained", True, "level available", a)

        # 3. Otherwise: hunt. What is safe to attack is a real judgment -- it
        #    depends on `consider`, on current health, and on what past fights
        #    taught us. That is what the model is for.
        self.run_turn(self._hunt_task(a))
        progressed = self._check_progress(a)
        return CycleResult("hunted", True, "progress" if progressed else "no progress", a)

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
            "- Loot the corpse afterwards.\n"
            "- Record anything surprising with `remember_learning`, especially a mob "
            "that turned out to be far stronger than it looked, or a room where "
            "something else joined the fight.\n\n"
            "DO NOT rest, sleep, or wait for health to come back, and do not poll "
            "`check` repeatedly to watch it regenerate. The loop around you handles "
            "recovery between turns. When you have made a kill or decided this room "
            "has nothing worth fighting, say so and end your turn.\n\n"
            "Do not leave the zone you are in, and do not attack guards or players."
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
        for _ in range(max_cycles):
            cycle = self.step()
            result.cycles.append(cycle)
            if self.logger is not None:
                self.logger.driver_cycle(
                    action=cycle.action, used_model=cycle.used_model, note=cycle.note,
                    mechanical_actions=cycle.mechanical_actions,
                    model_actions=cycle.model_actions,
                )
            if until is not None and until(self.assess()):
                result.stopped_because = "goal_met"
                break
            if self._no_progress >= self.policy.stall_cycles:
                result.stopped_because = "stalled"
                break
        else:
            result.stopped_because = "max_cycles"
        result.ending_exp = self.assess().exp
        return result
