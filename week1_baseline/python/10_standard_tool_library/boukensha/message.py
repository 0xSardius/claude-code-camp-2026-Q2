"""Port of week1_baseline/ruby/01_struct_skeleton/lib/boukensha/message.rb.

Same Struct -> @dataclass rationale as tool.py. Ruby's content.to_s[0..60]
is an inclusive range (61 chars) -- use [:61], not [:60].
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Message:
    role: str
    content: str
    tool_use_id: str | None = None

    def __repr__(self) -> str:
        id_tag = f" [{self.tool_use_id}]" if self.tool_use_id else ""
        # Ruby's nil.to_s is "", not the text "None" -- match that instead
        # of Python's str(None).
        content_str = "" if self.content is None else str(self.content)
        return f"#<Message role={self.role}{id_tag} content={content_str[:61]}...>"

    __str__ = __repr__
