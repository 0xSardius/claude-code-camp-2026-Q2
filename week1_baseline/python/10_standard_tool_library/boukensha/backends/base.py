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

    def estimate_cost(self, *, input_tokens, output_tokens):
        in_cost = self.input_token_cost_per_million
        out_cost = self.output_token_cost_per_million
        if in_cost is None or out_cost is None:
            return None
        return ((input_tokens * in_cost) + (output_tokens * out_cost)) / 1_000_000.0

    def _configure_model(self, model) -> None:
        self.model = self.__class__.validate_model(model)
        self._model_info = self.__class__.find_model_info(self.model)
