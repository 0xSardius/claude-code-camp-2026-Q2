"""Port of week1_baseline/ruby/01_struct_skeleton/lib/boukensha/tool.rb.

Ruby's Struct.new(...) is a lightweight named-field value object with room
for custom methods -- the README says explicitly this is chosen for being
"lightweight" and "readable for learning," not because Structs are the
"real" design choice. Python's direct analogue with the same properties is
@dataclass.

Slice-width note: Ruby's description.to_s[0..40] is an *inclusive* range --
41 characters. Python's str(x)[:40] would be 40 -- one short. Use [:41].

Ruby's `parameters` uses symbol keys, so `parameters.keys` inspects as
`[:direction]`. Python's dict here is naturally string-keyed (no symbol
equivalent), which would print as `['direction']` -- a real, discovered
mismatch during the parity test, not anticipated in the port plan. Rendered
manually below to match Ruby's symbol-array format exactly, since we
already hit true byte-for-byte parity on 00_config and this is cheap to
match rather than accept as a gap.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


@dataclass
class Tool:
    name: str
    description: str
    parameters: dict[str, Any]
    block: Callable[..., Any]

    def __repr__(self) -> str:
        params_repr = "[" + ", ".join(f":{k}" for k in self.parameters.keys()) + "]"
        # Ruby's nil.to_s is "", not the text "None" -- match that instead
        # of Python's str(None).
        description_str = "" if self.description is None else str(self.description)
        return f"#<Tool name={self.name} description={description_str[:41]} params={params_repr}>"

    __str__ = __repr__
