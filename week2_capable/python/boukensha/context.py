"""Port of week1_baseline/ruby/12_context/lib/boukensha/context.rb --
gains real context-window tracking (current_tokens/turn_tokens/
compaction_threshold) and compact_messages(); loses the `task` parameter
entirely (Tasks::Base/Tasks::Player removed in Ruby this step -- see
docs/plans/python_port/12_context).
"""
from __future__ import annotations

import math
import os

from .message import Message
from .tool import Tool


class Context:
    def __init__(
        self,
        *,
        system: str | None = None,
        context_window: int = 200_000,
        working_dir: str | bool | None = None,
        compaction_threshold: float = 0.85,
    ) -> None:
        self.system = system
        self.context_window = context_window
        # Ruby: `working_dir ? File.expand_path(working_dir) : nil` -- a
        # deliberate truthy check (working_dir: false is the explicit
        # opt-out sentinel), not a nil-check. See 10_standard_tool_library's
        # context.py for the full reasoning -- unchanged here.
        self.working_dir = os.path.abspath(working_dir) if working_dir else None
        self.compaction_threshold = compaction_threshold
        self.messages: list[Message] = []
        self.tools: dict[str, Tool] = {}
        self.current_tokens = 0
        self.turn_tokens = 0

    def register_tool(self, tool: Tool) -> None:
        self.tools[("" if tool.name is None else str(tool.name))] = tool

    def add_message(self, role: str, content, *, tool_use_id: str | None = None) -> None:
        self.messages.append(Message(role, content, tool_use_id))

    def update_tokens(self, n) -> None:
        self.current_tokens = int(n or 0)

    def reset_turn_tokens(self) -> None:
        self.turn_tokens = 0

    def add_turn_tokens(self, input_tokens, output_tokens) -> None:
        self.turn_tokens += int(input_tokens or 0) + int(output_tokens or 0)

    @property
    def usage_fraction(self) -> float:
        return (self.current_tokens / self.context_window) if self.context_window > 0 else 0.0

    @property
    def usage_pct(self) -> int:
        return round(self.usage_fraction * 100)

    def needs_compaction(self, threshold: float | None = None) -> bool:
        t = threshold if threshold is not None else self.compaction_threshold
        return self.usage_fraction >= t

    # Drop the oldest 40% of messages to free space, keeping at least 2.
    # Resets current_tokens to 0 (refreshed by the next API response).
    # Returns the number of messages dropped.
    #
    # target_fraction is accepted (matching Ruby's signature) but, like
    # Ruby's own compact_messages!, never actually used in the body -- a
    # real, pre-existing oddity in the Ruby source (the name suggests
    # compacting down to some fraction, but the implementation always
    # drops a fixed 40%). Ported faithfully, not "fixed" -- not this
    # port's call to resolve what the source itself hasn't resolved.
    def compact_messages(self, target_fraction: float = 0.60) -> int:
        drop_count = min(math.ceil(len(self.messages) * 0.40), len(self.messages) - 2)
        drop_count = max(drop_count, 0)
        # Never leave an orphaned tool_result as the first retained
        # message. A plain count-based cut has no idea whether it lands
        # between a tool_use and its tool_result -- if it does, the
        # retained history starts with a tool_result that has no matching
        # tool_use anywhere in the (now-truncated) conversation, which the
        # API rejects outright (400: "tool_result.tool_use_id: Input
        # should be a valid string" / no matching tool_use). Since
        # compaction only ever trims the front and nothing ever repairs
        # the middle, one bad cut permanently poisons every future call
        # in the session -- found live (not by review or a short playtest):
        # a real multi-turn grind session hit this exactly once and every
        # turn after it failed instantly, forever, until the session was
        # restarted. Advance past any leading tool_result(s) -- they're
        # orphaned by definition once their preceding tool_use is dropped.
        while drop_count < len(self.messages) and self.messages[drop_count].role == "tool_result":
            drop_count += 1
        self.messages = self.messages[drop_count:]
        self.current_tokens = 0
        return drop_count

    def clear_messages(self) -> None:
        self.messages = []
        self.current_tokens = 0

    @property
    def tool_count(self) -> int:
        return len(self.tools)

    @property
    def turn_count(self) -> int:
        return len(self.messages)

    def __repr__(self) -> str:
        return (
            f"#<Context turns={self.turn_count} tools={self.tool_count} "
            f"window={self.context_window} current={self.current_tokens}>"
        )

    __str__ = __repr__
