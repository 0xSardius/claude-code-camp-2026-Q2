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
    def judgment_ratio(self):
        """Fraction of cycles that needed the model. Week 3's headline metric.
        A ratio to understand, not to minimise: 0 is the lava-pit walker, 1 is
        the loop that reasons about standing up."""
        if not self.cycles:
            return None
        return sum(1 for c in self.cycles if c.used_model) / len(self.cycles)


class Driver:
    def __init__(self, *, goal, memory, registry, run_turn, policy=None, logger=None):
        self.goal = goal
        self.memory = memory
        self.registry = registry
        self.run_turn = run_turn          # callable(task_text) -> str
        self.policy = policy or Policy()
        self.logger = logger
        self._resting = 0
        self._no_progress = 0

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
        """Run a tool directly. No model call -- this is the mechanical half."""
        try:
            return self.registry.dispatch(tool, args or {})
        except Exception as e:  # noqa: BLE001 -- a dead connection must not end the run
            return f"error: {type(e).__name__}: {e}"

    # ---- one cycle -------------------------------------------------------

    def step(self):
        a = self.assess()

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
        return (
            f"Goal: {self.goal}.\n\n"
            "Find something safe to fight nearby and kill it for experience.\n"
            "- Use `consider` before attacking anything, and skip it if the answer "
            "suggests you would lose.\n"
            "- You are a thief: prefer backstab from hiding where you can.\n"
            "- Loot the corpse.\n"
            "- Do not leave the zone you are in, and do not attack guards or "
            "anything the memory notes say is dangerous.\n"
            "- If you take heavy damage, flee. Staying alive matters more than "
            "one kill."
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
        result = RunResult(starting_exp=self.assess().exp)
        for _ in range(max_cycles):
            cycle = self.step()
            result.cycles.append(cycle)
            if self.logger is not None:
                self.logger.driver_cycle(
                    action=cycle.action, used_model=cycle.used_model, note=cycle.note
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
