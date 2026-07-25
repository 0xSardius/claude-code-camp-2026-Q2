"""Port of week1_baseline/ruby/12_context/lib/boukensha/agent.rb -- the
largest rewrite this step. No more task_settings (Tasks::Base/Player
removed in Ruby; callers now resolve max_iterations/max_output_tokens
themselves via Config and pass fully-resolved values directly). New:
max_turn_tokens (a second, independent spend-budget ceiling alongside
max_iterations), auto-compaction at the start of every turn, reasoning-
block logging, and a restored multi-provider usage-field fallback in
record_usage (see below -- a real bug fix, not a straight port).

interrupt_event (Python-only, no Ruby counterpart -- see
docs/plans/python_port/11_tui) is unaffected by this step's changes:
still checked once per loop iteration, still None for every non-TUI
caller.
"""
from .errors import ApiError, TurnInterrupted
from .logger import Logger


class Agent:
    MAX_ITERATIONS = 25

    WRAP_UP_OUTPUT_TOKENS = 400
    WRAP_UP_DIRECTIVE = (
        "You have reached your action limit for this turn. Do not call any more tools.\n"
        "Briefly summarize what you accomplished, what is still unfinished, and the\n"
        "single next action you would take."
    )

    def __init__(
        self,
        *,
        context,
        registry,
        builder,
        client,
        logger=None,
        max_iterations=None,
        max_turn_tokens=None,
        max_output_tokens=None,
        interrupt_event=None,
    ):
        self._context = context
        self._registry = registry
        self._builder = builder
        self._client = client
        # Ruby's `logger: Logger.new` default is a fresh expression
        # evaluated on every call; Python only evaluates a default VALUE
        # once, at def-time -- logger=None + lazy-construct is the only
        # way to get Ruby's actual per-call-fresh-instance semantics.
        self._logger = logger if logger is not None else Logger()
        self._max_iterations = int(max_iterations) if max_iterations is not None else self.MAX_ITERATIONS
        self._max_turn_tokens = int(max_turn_tokens) if max_turn_tokens is not None else 0  # 0 = disabled
        self._max_output_tokens = max_output_tokens
        self._interrupt_event = interrupt_event
        self._iteration = 0

    def run(self):
        self._context.reset_turn_tokens()
        self._compact_if_needed()

        while True:
            # Cooperative-cancellation checkpoint (Python-only, see module
            # docstring) -- checked before starting a new iteration, not
            # mid-call.
            if self._interrupt_event is not None and self._interrupt_event.is_set():
                raise TurnInterrupted()

            # Two independent ceilings; stop at whichever trips first.
            # Limits are *trigger thresholds*, not hard caps: when one is
            # reached we stop starting new work iterations and make
            # exactly one terminal wind-down call (counted in tokens, but
            # not as another iteration).
            if self._iteration_limit_reached():
                self._logger.limit_reached(kind="max_iterations", n=self._iteration, max=self._max_iterations)
                return self._wrap_up("max_iterations")
            if self._token_limit_reached():
                self._logger.limit_reached(kind="max_tokens", n=self._context.turn_tokens, max=self._max_turn_tokens)
                return self._wrap_up("max_tokens")

            self._iteration += 1
            self._logger.iteration(n=self._iteration, max=self._max_iterations)
            self._logger.prompt(messages=self._context.messages, tools=self._context.tools, context_window=self._context.context_window)

            response = self._client.call(**self._call_opts())
            self._logger.raw(data=response)
            parsed = self._builder.parse_response(response)
            self._record_usage(response)
            self._log_reasoning(parsed["content"])

            if parsed["stop_reason"] == "tool_use":
                self._handle_tool_calls(parsed["content"], response)
            else:
                text = self._extract_text(parsed["content"])
                self._logger.response(text=text, usage=response.get("usage"), stop_reason=parsed["stop_reason"])
                self._logger.turn_end(reason="completed", iterations=self._iteration, tokens=self._context.turn_tokens)
                self._context.add_message("assistant", text)
                return text

    def _iteration_limit_reached(self):
        return self._max_iterations > 0 and self._iteration >= self._max_iterations

    def _token_limit_reached(self):
        return self._max_turn_tokens > 0 and self._context.turn_tokens >= self._max_turn_tokens

    def _call_opts(self):
        return {"max_output_tokens": self._max_output_tokens} if self._max_output_tokens is not None else {}

    # Add this call's input+output to the cumulative turn total (the spend
    # budget) and refresh the known context size from input_tokens
    # (compaction pressure).
    #
    # Restores the multi-provider usage-field fallback (usageMetadata for
    # Gemini, prompt_eval_count/eval_count for Ollama) that Ruby's 12_context
    # source dropped along with the cost-estimation code it used to live
    # inside of -- a real bug (not scope-narrowing), fixed in Ruby too:
    # without it, current_tokens silently stays 0 for non-Anthropic
    # backends, so needs_compaction() never trips no matter how full the
    # real context window gets.
    def _record_usage(self, response):
        tokens = self._usage_tokens(response)
        self._context.add_turn_tokens(tokens["input"], tokens["output"])
        self._context.update_tokens(tokens["input"])

    def _usage_tokens(self, response):
        # Ruby: `response["usage"] || response["usageMetadata"] || response`
        # -- `||` only falls through on nil/false, so a present-but-empty
        # {} usage dict is KEPT, not skipped. A bare Python `or` chain
        # treats {} as falsy and falls all the way through to the raw
        # response, picking up wrong keys. Explicit None-checks, not `or`
        # -- found by code review (CONFIRMED), the exact gotcha this
        # method's restoration was supposed to guard against.
        usage = response.get("usage")
        if usage is None:
            usage = response.get("usageMetadata")
        if usage is None:
            usage = response
        return {
            "input": self._first_integer(usage, "input_tokens", "prompt_tokens", "promptTokenCount", "prompt_eval_count"),
            "output": self._first_integer(usage, "output_tokens", "completion_tokens", "candidatesTokenCount", "eval_count"),
        }

    def _first_integer(self, d, *keys):
        for key in keys:
            value = d.get(key)
            if value is not None:
                try:
                    return int(value)
                except (ValueError, TypeError):
                    return None
        return None

    def _compact_if_needed(self):
        if not self._context.needs_compaction():
            return
        before = self._context.current_tokens
        dropped = self._context.compact_messages()
        self._logger.compaction(before=before, dropped=dropped, context_window=self._context.context_window)

    # One final, tools-disabled model call so the agent ends the turn in
    # character rather than aborting. Runs *outside* the counted loop.
    def _wrap_up(self, reason):
        self._context.add_message("user", self.WRAP_UP_DIRECTIVE)
        try:
            response = self._client.call(tools=[], max_output_tokens=self.WRAP_UP_OUTPUT_TOKENS)
            parsed_wrap = self._builder.parse_response(response)
            text = self._extract_text(parsed_wrap["content"])
            if text.strip() == "":
                text = self._fallback_message(reason)
            self._record_usage(response)
            # No _log_reasoning call here -- Ruby's wrap_up never makes one
            # (only run()'s main loop does). Found by code review
            # (CONFIRMED): an extra call here logged a spurious "reasoning"
            # event whenever the wind-down call returned reasoning content,
            # breaking the byte-for-byte transcript parity with Ruby.
            self._logger.response(text=text, usage=response.get("usage"), stop_reason=parsed_wrap["stop_reason"])
            self._logger.turn_end(reason=reason, iterations=self._iteration, tokens=self._context.turn_tokens)
            self._context.add_message("assistant", text)
            return text
        except ApiError:
            msg = self._fallback_message(reason)
            self._logger.turn_end(reason=reason, iterations=self._iteration, tokens=self._context.turn_tokens)
            self._context.add_message("assistant", msg)
            return msg

    def _fallback_message(self, reason):
        return (
            f"I reached my {self._max_iterations}-action limit for this turn before finishing "
            f"({reason}). Ask me to continue and I'll pick up from here."
        )

    def _extract_text(self, content):
        return "\n".join(b["text"] for b in content if b.get("type") == "text")

    # Emit one `reasoning` event per reasoning content block so the viewer
    # can show the model's thinking as a first-class step. Empty,
    # non-redacted blocks are skipped to avoid noise (a redacted/omitted
    # block still renders, since it tells the viewer "the model thought
    # here").
    def _log_reasoning(self, content):
        for block in content:
            if block.get("type") != "reasoning":
                continue
            redacted = block.get("redacted") is True
            text = str(block.get("text") or "")
            if text.strip() == "" and not redacted:
                continue
            self._logger.reasoning(text=text, redacted=redacted)

    def _handle_tool_calls(self, content, response):
        tool_calls = [b for b in content if b.get("type") == "tool_use"]

        # Log any preamble text that accompanied the tool call (carries no
        # usage -- the placeholder response() below owns the turn's usage
        # chip), then the placeholder.
        preamble = self._extract_text(content)
        if preamble.strip() != "":
            self._logger.plan(text=preamble)
        calls_suffix = "s" if len(tool_calls) != 1 else ""
        self._logger.response(
            text=f"(tool use — {len(tool_calls)} call{calls_suffix})",
            usage=response.get("usage"),
            stop_reason="tool_use",
        )

        self._context.add_message("assistant", content)

        for block in tool_calls:
            name = block["name"]
            args = block["input"]
            use_id = block["id"]

            self._logger.tool_call(name=name, args=args)
            # try/except/else -- the success-path logger call must NOT be
            # covered by the except, or a logging failure after a
            # genuinely successful dispatch gets misreported to the model
            # as a tool failure, discarding the real result.
            try:
                result = self._registry.dispatch(name, args)
            except Exception as e:
                result = f"ERROR: {type(e).__name__}: {e}"
                self._logger.tool_result(name=name, result=result, ok=False, error=str(e))
            else:
                self._logger.tool_result(name=name, result=result, ok=True)

            self._context.add_message("tool_result", str(result), tool_use_id=use_id)
