class UnknownToolError(Exception):
    pass


class ApiError(Exception):
    pass


class LoopError(Exception):
    pass


class UnsupportedModelError(Exception):
    pass


class TurnInterrupted(Exception):
    """Raised by Agent.run() when interrupt_event is set between
    iterations -- the Python-side answer to Ruby's Thread#raise(Interrupt)
    (no safe equivalent exists in Python; see docs/plans/python_port/11_tui's
    dedicated section on this). Only ever raised, and only ever meaningful,
    when a caller explicitly passes an interrupt_event to Agent -- the
    plain non-TUI REPL and boukensha.run() never do, so this can't fire
    for them.
    """

    pass
