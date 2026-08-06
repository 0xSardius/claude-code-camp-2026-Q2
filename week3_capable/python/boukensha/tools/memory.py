"""Model-facing memory tools (week2 memory M2).

Registers a small surface the agent can use to consult and record what it
knows. Complements — does not replace — the automatic injection the lifecycle
hooks do: `before_turn` loads the store into context without being asked, and
these tools let the agent record deliberately and re-check mid-turn.

Two paths now reach the same store (hooks and these tools). That is exactly the
shape of week1's `register_tool` bug, where a second path bypassed
normalization that only one call site performed. Handled by normalizing inside
Memory itself rather than here — see memory.py's constructor.

The surface is deliberately small. Every tool's schema sits in the cached
prompt prefix and, more importantly, in the model's decision space: more tools
means more chances to pick the wrong one.
"""
from ..memory import Memory


def register(registry, *, memory=None, character=None, dir=None):
    """Register memory tools. Pass either an existing Memory or a character
    name to build one for."""
    if memory is None:
        if not character:
            raise ValueError("memory tools need either memory= or character=")
        memory = Memory(character, dir=dir)

    def recall():
        block = memory.context_block()
        return block or "(memory is empty — nothing recorded yet)"

    def remember_fact(fact):
        return ("recorded" if memory.add_fact(fact)
                else "already known (not recorded again)")

    def remember_learning(learning):
        return ("recorded" if memory.add_learning(learning)
                else "nothing to record")

    def revise_learning(old, new):
        """Correcting a lesson, rather than adding a second one beside it.

        Without this the only way to disagree with an old note was to append a
        new one, so learnings.md ended up holding "avoid the pet dragon" and
        "the pet dragon is a good farm target" at the same time, and the model
        read both every turn."""
        ok, message = memory.revise_learning(old, new)
        return message

    def set_goal(goal):
        memory.set_goal(goal)
        return f"goal set: {goal}"

    def find_route(destination):
        """The read-before-explore primitive. Note that 'no known route' is a
        real answer, not an error: it tells the agent to explore deliberately
        rather than pretend to know."""
        target = memory.find_room(destination)
        if target is None:
            known = sorted({r.get("name", "") for r in memory.rooms().values() if r.get("name")})
            return (f"'{destination}' is not in memory. Known places: "
                    f"{', '.join(known) if known else '(none yet)'}. "
                    "You will need to explore to find it.")
        here = memory.position
        if not here:
            return (f"'{destination}' is known, but current position is not — "
                    "look around first, then ask again.")
        path = memory.route(here, target)
        if path is None:
            return (f"'{destination}' is known, but no route has been walked from "
                    "here to there yet. Explore toward it.")
        if not path:
            return f"You are already at '{destination}'."
        return f"Route to '{destination}': {', '.join(path)} ({len(path)} moves)"

    registry.tool(
        "recall",
        description=(
            "Read everything you remember about this character: current goal, "
            "vitals, places you know, routes you have walked, facts, and lessons. "
            "Check this BEFORE exploring — if you already know where something is, "
            "go there instead of wandering."
        ),
        parameters={},
        block=recall,
    )
    registry.tool(
        "find_route",
        description=(
            "Ask whether you already know the way to a place, by name (e.g. 'the "
            "bakery'). Returns the directions to walk, or tells you the place or "
            "route is unknown so you can explore deliberately. Use this before "
            "moving toward any named destination."
        ),
        parameters={"destination": {"type": "string", "description": "Place name, e.g. 'The Bakery'"}},
        block=find_route,
    )
    registry.tool(
        "remember_fact",
        description=(
            "Record a durable fact about the world or your character — where a "
            "place is, what a shop sells, which mob is dangerous. Facts persist "
            "across sessions. Record anything you would be annoyed to have to "
            "rediscover."
        ),
        parameters={"fact": {"type": "string", "description": "One specific fact, stated plainly"}},
        block=remember_fact,
    )
    registry.tool(
        "remember_learning",
        description=(
            "Record something you learned about HOW TO PLAY better — which mobs "
            "give the best experience per turn, which tactics worked, what to "
            "avoid. Distinct from a fact: this is about your own play, and you "
            "should consult it when choosing what to do next."
        ),
        parameters={"learning": {"type": "string", "description": "One lesson about playing effectively"}},
        block=remember_learning,
    )
    registry.tool(
        "revise_learning",
        description=(
            "Replace a lesson that has stopped being true. Use this INSTEAD of "
            "recording a second lesson that contradicts an older one — otherwise "
            "your notes end up holding both and you have to work out which still "
            "applies every time you read them. Good reasons to revise: you have "
            "levelled and a mob you avoided is now easy, a hunting ground has been "
            "farmed out, or a tactic stopped working. Quote enough of the old "
            "lesson to identify it uniquely; if it matches more than one, nothing "
            "changes and you will be asked for more. The old wording is kept out "
            "of the way, not thrown away."
        ),
        parameters={
            "old": {"type": "string",
                    "description": "A distinctive piece of the lesson to replace"},
            "new": {"type": "string",
                    "description": "What you now believe, and ideally what changed"},
        },
        block=revise_learning,
    )
    registry.tool(
        "set_goal",
        description=(
            "Record what you are currently trying to accomplish, so it survives "
            "across turns and sessions. Update it when the objective changes."
        ),
        parameters={"goal": {"type": "string", "description": "The current objective"}},
        block=set_goal,
    )

    return memory
