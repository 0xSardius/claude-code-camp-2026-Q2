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

required_params (new, week1_baseline/python/10_standard_tool_library
onward -- see docs/plans/python_port/12_context) mirrors Ruby's Tool
struct gaining the identically-named method: which of `parameters`'s keys
are actually required, determined by introspecting the registered block's
own argument defaults, instead of every backend's to_tools marking every
declared property required regardless of the block's real signature (a
real bug found by code review -- e.g. a `look(target=None,
preposition=None)` block makes both optional, but every backend's
to_tools previously listed both as required unconditionally). Fixed
starting at 10_standard_tool_library/11_tui/12_context only -- not
backported into 02_the_registry through 09_global_executable, which carry
the same long-standing bug undisturbed.
"""
from __future__ import annotations

import inspect
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

    def required_params(self) -> list[str]:
        # Ruby: block.parameters.select { |type,_| type == :keyreq } --
        # Proc#parameters' :keyreq (no default) vs :key (has a default).
        # Python's inspect.Parameter has no direct :keyreq/:key split, but
        # "has no default" (param.default is Parameter.empty) on a
        # keyword-capable parameter is the same test. *args/**kwargs
        # catch-alls (VAR_POSITIONAL/VAR_KEYWORD) are excluded -- they're
        # not concrete required params.
        try:
            sig = inspect.signature(self.block)
        except (TypeError, ValueError):
            return []
        return [
            name
            for name, param in sig.parameters.items()
            if param.kind in (inspect.Parameter.POSITIONAL_OR_KEYWORD, inspect.Parameter.KEYWORD_ONLY)
            and param.default is inspect.Parameter.empty
        ]
