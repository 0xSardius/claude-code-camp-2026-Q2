from .errors import UnknownToolError
from .tool import Tool


class Registry:
    def __init__(self, context):
        self._context = context

    def tool(self, name, *, description, parameters=None, block):
        # Ruby: parameters: {} default -- Python can't default a mutable
        # dict directly (shared-across-calls footgun), so default None and
        # substitute {} per call instead.
        t = Tool(str(name), description, parameters or {}, block)
        self._context.register_tool(t)
        return t

    def dispatch(self, name, args=None):
        # No transform_keys equivalent -- **dict unpacking in Python is
        # already string-keyed, there's no symbol/string gap to bridge
        # here. See the port plan's "New finding" section for why this is
        # shorter than the Ruby version on purpose, not by omission.
        tool = self._context.tools.get(str(name))
        if tool is None:
            raise UnknownToolError(f"No tool registered as '{name}'")
        return tool.block(**(args or {}))
