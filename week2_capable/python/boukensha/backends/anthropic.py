"""Port of week1_baseline/ruby/12_context/lib/boukensha/backends/anthropic.rb --
adds reasoning-block normalization (thinking/redacted_thinking <->
"reasoning", with a signature round-tripped opaquely). MODELS table no
longer has a claude-haiku-4-5-20251001 variant -- matches Ruby's current
source, not "restored" from 11_tui (a genuine table change in the
source, not a regression in the established checklist sense).
"""
from .base import Base


class Anthropic(Base):
    BASE_URL = "https://api.anthropic.com/v1/messages"

    # `thinking: true` means the model accepts adaptive thinking
    # (`{"type": "adaptive"}`). It is a 4.6-and-later feature; sending it to an
    # older model is a 400, not a graceful no-op, so haiku-4-5 is deliberately
    # left without the key. See Backends::Base.supports_thinking.
    MODELS = {
        "claude-haiku-4-5": {
            "context_window": 200_000,
            "cost_per_million": {"input": 1.0, "output": 5.0},
            "usage_unit": "tokens",
        },
        "claude-sonnet-4-6": {
            "context_window": 1_000_000,
            "cost_per_million": {"input": 3.0, "output": 15.0},
            "usage_unit": "tokens",
            "thinking": True,
        },
        "claude-opus-4-8": {
            "context_window": 1_000_000,
            "cost_per_million": {"input": 5.0, "output": 25.0},
            "usage_unit": "tokens",
            "thinking": True,
        },
        "claude-sonnet-5": {
            "context_window": 1_000_000,
            # INTRODUCTORY PRICING, in effect through 2026-08-31. Standard
            # rates are input 3.0 / output 15.0 and resume 2026-09-01 -- update
            # this entry then, or every cost figure the observability pillar
            # reports will read ~33% LOW.
            #
            # Corrected 2026-07-27: the table previously carried the standard
            # 3.0/15.0 while this project has been running on intro pricing the
            # whole time, so a straight re-connect of estimate_cost would have
            # reported ~50% HIGH for the entire week. Deliberately hardcoded
            # rather than date-modelled: a date-dependent price table is
            # awkward to test and the revert is a one-line edit on a known day.
            "cost_per_million": {"input": 2.0, "output": 10.0},
            "usage_unit": "tokens",
            "thinking": True,
        },
    }

    def __init__(self, *, api_key, model):
        super().__init__()
        self._api_key = api_key
        self._configure_model(model)

    def to_messages(self, system, messages):
        result = []
        for msg in messages:
            if msg.role == "tool_result":
                result.append(
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": msg.tool_use_id,
                                "content": msg.content,
                            }
                        ],
                    }
                )
            elif msg.role == "assistant":
                result.append({"role": "assistant", "content": self._assistant_content(msg.content)})
            else:
                result.append({"role": msg.role, "content": msg.content})
        return result

    def to_tools(self, tools):
        return [
            {
                "name": tool.name,
                "description": tool.description,
                "input_schema": {
                    "type": "object",
                    "properties": tool.parameters,
                    "required": tool.required_params(),
                },
            }
            for tool in tools.values()
        ]

    def to_payload(self, context, *, max_output_tokens=1024, tools=None):
        payload = {
            "model": self.model,
            "system": context.system,
            "max_tokens": max_output_tokens,
            "tools": self.to_tools(context.tools) if tools is None else tools,
            "messages": self.to_messages(context.system, context.messages),
        }
        # Ask for a readable summary of the model's reasoning.
        #
        # Without this the harness has a complete, correct reasoning pipeline
        # that has NEVER produced a single event: `display` defaults to
        # "omitted" on these models, so thinking blocks arrive with empty text
        # and Agent._log_reasoning skips every empty non-redacted block. The
        # code was right, wired right, and silent -- invisible precisely
        # because nothing errored.
        #
        # Costs nothing extra: thinking is billed identically under every
        # display setting, and output tokens are ~6% of this workload's spend
        # (see docs/plans/week2/token_optimization.md's measured baseline).
        #
        # Caching note: toggling `thinking` invalidates the MESSAGES cache but
        # not the tools+system prefix, so this is safe to set once and leave
        # alone. Do not flip it per-request.
        if self.supports_thinking:
            payload["thinking"] = {"type": "adaptive", "display": "summarized"}
        return payload

    def headers(self):
        return {
            "Content-Type": "application/json",
            "x-api-key": self._api_key,
            "anthropic-version": "2023-06-01",
        }

    def url(self):
        return self.BASE_URL

    # Normalizes an Anthropic Messages API response into the common shape
    # (see Backends::Base's docstring for the full content-block
    # contract). Native thinking/redacted_thinking blocks map to
    # "reasoning" blocks, preserving the signature so they can be echoed
    # back unchanged (the API rejects modified thinking blocks when
    # continuing on the same model).
    # Stop reasons this harness understands. Everything else still collapses
    # to "end_turn" (the agent loop only branches on tool_use vs not), but
    # `max_tokens` is preserved so truncation stays VISIBLE.
    #
    # Previously every non-tool_use reason -- including max_tokens -- was
    # rewritten to "end_turn", so a response the API cut off at the token
    # ceiling was handed to the loop as a normally completed turn and its
    # half-finished text was appended to the conversation as a finished
    # assistant message. Measured at 1 of 404 responses in the week1 logs, so
    # rare rather than systemic, but silent -- and expected to climb as week2's
    # turns get longer and thinking tokens count against the same ceiling.
    KNOWN_STOP_REASONS = ("tool_use", "max_tokens")

    def parse_response(self, response):
        raw = response.get("stop_reason")
        stop_reason = raw if raw in self.KNOWN_STOP_REASONS else "end_turn"
        content = [self._normalize_block(block) for block in (response.get("content") or [])]
        return {"stop_reason": stop_reason, "content": content}

    def _normalize_block(self, block):
        if block.get("type") == "thinking":
            return {"type": "reasoning", "text": str(block.get("thinking") or ""), "signature": block.get("signature")}
        if block.get("type") == "redacted_thinking":
            return {"type": "reasoning", "text": "", "redacted": True, "signature": block.get("data")}
        return block

    # Rebuilds Anthropic assistant content from normalized blocks (the
    # inverse of parse_response). Text-only turns are stored as a bare
    # string and pass through unchanged; "reasoning" blocks are
    # re-emitted as native thinking/redacted_thinking blocks so
    # signatures round-trip intact.
    def _assistant_content(self, content):
        if isinstance(content, str):
            return content
        return [self._denormalize_block(block) for block in content]

    def _denormalize_block(self, block):
        if block.get("type") != "reasoning":
            return block
        if block.get("redacted"):
            return {"type": "redacted_thinking", "data": block.get("signature")}
        return {"type": "thinking", "thinking": str(block.get("text") or ""), "signature": block.get("signature")}
