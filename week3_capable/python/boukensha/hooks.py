"""Lifecycle hooks for the agent loop (week2, no week1 counterpart).

Five seams the harness fires as a turn runs, so capabilities attach to the
loop instead of being edited into it. See docs/plans/week2/00_lifecycle_hooks.md.

    before_turn   once, at the start of a turn
    before_model  before each model request
    before_tools  before a model-selected tool batch runs
    after_tool    after each individual tool returns
    after_turn    once, at the end of a turn (ALL exit paths)

Vocabulary, per the week2 course material and already matching Logger's
existing events: a TURN is one user input plus the complete agent run needed
to answer it (one Agent.run()); an ITERATION is one pass through the inner
loop, principally one model request and its response.

Why this exists rather than editing Agent.run() directly: it makes
self-maintenance deterministic. Without seams, "the agent records the room it
walked into" means the model has to *choose* to call a tool -- which it will
do most of the time, and the times it forgets are exactly the long chaotic
turns where the map matters most. With seams, walking into a room records the
room whether the model thought about it or not.
"""


class Hook:
    """The five seam names. Strings, not an enum -- Registry/Logger both use
    plain strings for their own keys, and an enum would be the only one of its
    kind in the package."""

    BEFORE_TURN = "before_turn"
    BEFORE_MODEL = "before_model"
    BEFORE_TOOLS = "before_tools"
    AFTER_TOOL = "after_tool"
    AFTER_TURN = "after_turn"

    ALL = (BEFORE_TURN, BEFORE_MODEL, BEFORE_TOOLS, AFTER_TOOL, AFTER_TURN)


class HookPayload:
    """What a handler receives. Deliberately a mutable object rather than
    positional args, so new fields can be added without breaking handlers
    already written against an older signature.

    Handlers MUTATE this; they do not return a replacement. That is the
    contract, and it is load-bearing for `after_tool`, whose documented job is
    to replace raw movement output with a compact result -- `payload.result`
    is what actually lands in the message list.

    Mutation was chosen over a return-value convention specifically to dodge
    the falsy-vs-None trap this project keeps hitting (see the `||` vs `or`
    gotcha in the root CLAUDE.md): with several handlers on one hook, a
    returned `None` is ambiguous between "replace it with nothing" and "I had
    nothing to say", and the two need opposite handling.
    """

    __slots__ = ("hook", "context", "registry", "logger", "agent", "extra")

    def __init__(self, hook, *, context, registry, logger, agent=None, **extra):
        self.hook = hook
        self.context = context
        self.registry = registry
        self.logger = logger
        self.agent = agent
        self.extra = extra

    # Hook-specific fields live in `extra` and are reached as attributes, so a
    # handler writes `payload.result = "..."` for after_tool without every hook
    # needing to declare every other hook's fields. __slots__ above keeps typos
    # on the FIXED fields loud while leaving the per-hook ones open.
    def __getattr__(self, name):
        # __getattr__ runs only for attributes normal lookup missed -- which
        # includes `extra` itself before __init__ has set it, or after an
        # unpickle that bypasses __init__. Reading self.extra there recurses
        # forever instead of raising AttributeError, so copy/pickle/inspect on
        # a payload would hang rather than fail. Found by code review.
        if name in self.__slots__:
            raise AttributeError(name)
        try:
            return self.extra[name]
        except KeyError:
            raise AttributeError(
                f"{self.hook!r} payload has no field {name!r} "
                f"(available: {', '.join(sorted(self.extra)) or 'none'})"
            ) from None

    def __setattr__(self, name, value):
        if name in self.__slots__:
            object.__setattr__(self, name, value)
        else:
            self.extra[name] = value

    def __repr__(self):
        fields = ", ".join(f"{k}={v!r}" for k, v in sorted(self.extra.items()))
        return f"#<HookPayload {self.hook}{' ' + fields if fields else ''}>"


class Hooks:
    """Registry of handlers per seam. Fires in registration order."""

    def __init__(self):
        self._handlers = {name: [] for name in Hook.ALL}

    def on(self, name, handler):
        if name not in self._handlers:
            raise ValueError(f"unknown hook {name!r}; expected one of {', '.join(Hook.ALL)}")
        self._handlers[name].append(handler)
        return handler

    def handlers(self, name):
        return list(self._handlers.get(name, ()))

    def count(self, name=None):
        if name is None:
            return sum(len(v) for v in self._handlers.values())
        return len(self._handlers.get(name, ()))

    def fire(self, name, payload):
        """Run every handler for `name`, then return the (possibly mutated)
        payload so callers can read fields back out of it.

        A handler that raises must NOT kill the turn -- it is logged and the
        remaining handlers still run. This matters most at `after_tool`: the
        existing try/except/else around registry.dispatch already warns that a
        logging failure after a successful dispatch must not be misreported to
        the model as a tool failure, and the same reasoning applies here. A
        crashing observer must never cost us a real tool result.
        """
        for handler in self._handlers.get(name, ()):
            try:
                handler(payload)
            except Exception as e:  # noqa: BLE001 -- a handler must never kill a turn
                logger = payload.logger
                if logger is not None:
                    logger.hook_error(
                        hook=name,
                        handler=getattr(handler, "__name__", repr(handler)),
                        error=f"{type(e).__name__}: {e}",
                    )
        return payload

    def __repr__(self):
        live = {k: len(v) for k, v in self._handlers.items() if v}
        return f"#<Hooks {live or 'empty'}>"
