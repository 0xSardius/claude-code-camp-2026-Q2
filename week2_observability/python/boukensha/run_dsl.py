"""Port of week1_baseline/ruby/07_the_run_dsl/lib/boukensha/run_dsl.rb --
the object a `boukensha.run(..., setup=...)` callback receives, exposing
only `tool`. Ruby's instance_eval-based "self becomes RunDSL inside the
block" has no Python equivalent -- the callback receives this object
explicitly instead. See the port plan's dedicated section on this.
"""


class RunDSL:
    def __init__(self, registry):
        self._registry = registry

    def tool(self, name, *, description, parameters=None, block):
        self._registry.tool(name, description=description, parameters=parameters, block=block)
