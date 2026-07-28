"""Port of week1_baseline/ruby/03_prompt_builder/lib/boukensha/backends/base.rb.

Ruby's `self.model_info(model)` (class method, 1-arg MODELS lookup) and
`#model_info` (instance method, 0-arg getter of @model_info) share one name
because Ruby class methods and instance methods live in separate method
tables. Python has no such split -- defining both under the name
`model_info` in one class body would just have the second definition
silently clobber the first, so the class-side lookup is named
`find_model_info` here instead, leaving `model_info` for the instance
property. Not a fidelity gap: `model_info` itself isn't part of this
class's documented public API (the README lists context_window,
input_token_cost_per_million, output_token_cost_per_million, usage_unit,
usage_level, estimate_cost -- not model_info).

Ruby's `validate_model!` bang suffix is a naming convention (flags
"raises"), not a language feature -- no Python equivalent, dropped like any
other Ruby bang method would be.
"""
from __future__ import annotations

from ..errors import UnsupportedModelError


class Base:
    @classmethod
    def models(cls):
        try:
            return cls.MODELS
        except AttributeError:
            raise NotImplementedError(f"{cls.__name__} must define MODELS")

    @classmethod
    def find_model_info(cls, model):
        return cls.models().get(str(model))

    @classmethod
    def validate_model(cls, model):
        model = str(model)
        if cls.find_model_info(model):
            return model

        supported = ", ".join(sorted(cls.models().keys()))
        # Ruby's Class#name here is the fully qualified
        # "Boukensha::Backends::Anthropic"; Python's __name__ is the bare
        # "Anthropic". Not part of any parity-tested output (the example
        # never triggers this path), so no attempt to reconstruct the
        # Ruby-style qualified form.
        raise UnsupportedModelError(
            f"{cls.__name__} does not support model {model!r}. Supported models: {supported}"
        )

    def __init__(self) -> None:
        self.model = None
        self._model_info = None

    @property
    def model_info(self):
        return self._model_info

    @property
    def context_window(self):
        return self.model_info["context_window"]

    @property
    def input_token_cost_per_million(self):
        return self.model_info["cost_per_million"]["input"]

    @property
    def output_token_cost_per_million(self):
        return self.model_info["cost_per_million"]["output"]

    @property
    def usage_unit(self):
        return self.model_info["usage_unit"]

    @property
    def usage_level(self):
        return self.model_info.get("usage_level")

    # Cached tokens are not priced like fresh input. Multipliers are against
    # the model's own input rate: a read is ~0.1x, a write ~1.25x at the
    # default 5-minute TTL (~2x at 1h, which this project doesn't use).
    #
    # This matters more than it looks. An estimate_cost() that ignored the
    # cache fields would overstate spend *most* exactly when caching is working
    # best -- which would make the token pillar's whole reason for existing
    # look like a regression on the very dashboard meant to prove it worked.
    CACHE_READ_MULTIPLIER = 0.1
    CACHE_WRITE_MULTIPLIER = 1.25

    def estimate_cost(self, *, input_tokens, output_tokens, cache_read_tokens=0, cache_write_tokens=0):
        in_cost = self.input_token_cost_per_million
        out_cost = self.output_token_cost_per_million
        if in_cost is None or out_cost is None:
            return None
        # None and 0 both mean "no tokens of this kind" for a token count, so
        # `or 0` is safe here -- unlike the falsy-vs-None cases elsewhere in
        # this codebase, there is no valid falsy value with a different meaning.
        billed = (
            (input_tokens or 0) * in_cost
            + (output_tokens or 0) * out_cost
            + (cache_read_tokens or 0) * in_cost * self.CACHE_READ_MULTIPLIER
            + (cache_write_tokens or 0) * in_cost * self.CACHE_WRITE_MULTIPLIER
        )
        return billed / 1_000_000.0

    @property
    def supports_thinking(self):
        """Whether this model accepts `thinking: {"type": "adaptive"}`.

        Data-driven off MODELS rather than a name check: adaptive thinking is
        a 4.6-and-later feature, and sending it to a model that predates it is
        a 400, not a graceful no-op. Absent key => don't send it.
        """
        info = self.model_info or {}
        return bool(info.get("thinking"))

    def _configure_model(self, model) -> None:
        self.model = self.__class__.validate_model(model)
        self._model_info = self.__class__.find_model_info(self.model)
