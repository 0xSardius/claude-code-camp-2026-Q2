"""Port of week1_baseline/ruby/01_struct_skeleton/lib/boukensha/context.rb.

Ruby deliberately uses a plain class here, not a Struct (unlike Tool and
Message) -- Context has real behavior (register_tool, add_message, computed
tool_count/turn_count), not just data. Mirrored here as a plain Python
class, not a @dataclass, to preserve that same architectural signal.

NOTE: the Ruby README describes a token_budget field/usage-tracking that
the actual context.rb code does not have. This port mirrors the actual
code, not the README's aspirational description -- see
docs/plans/python_port/01_struct_skeleton for the full explanation. Don't
add token_budget here until the Ruby source actually has it.
"""
from __future__ import annotations

from .message import Message
from .tool import Tool


class Context:
    def __init__(self, *, task, system: str | None = None) -> None:
        # Ruby: def initialize(task:, system: nil) -- task is a REQUIRED
        # keyword arg (no default), system is optional. Both keyword-only
        # here (the leading `*`) to match; task has no default so a caller
        # who omits it gets Python's own TypeError, mirroring Ruby's
        # ArgumentError: missing keyword: :task instead of silently
        # constructing a task=None Context.
        self.task = task
        self.system = system
        self.messages: list[Message] = []
        self.tools: dict[str, Tool] = {}

    def register_tool(self, tool: Tool) -> None:
        self.tools[tool.name] = tool

    def add_message(self, role: str, content: str, *, tool_use_id: str | None = None) -> None:
        self.messages.append(Message(role, content, tool_use_id))

    @property
    def tool_count(self) -> int:
        return len(self.tools)

    @property
    def turn_count(self) -> int:
        return len(self.messages)

    def __repr__(self) -> str:
        # Ruby: task&.task_name -- safe navigation on a possibly-nil task.
        # task_name is a method call here (Base.task_name() classmethod),
        # not a bare attribute -- don't drop the parens. Ruby's "#{nil}"
        # interpolates as "", not the text "None" -- render "" to match.
        task_name = self.task.task_name() if self.task else ""
        return f"#<Context task={task_name} turns={self.turn_count} tools={self.tool_count}>"

    __str__ = __repr__
