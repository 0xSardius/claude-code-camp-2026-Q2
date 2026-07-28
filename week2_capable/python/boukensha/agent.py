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
from .hooks import Hook, HookPayload, Hooks
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
        hooks=None,
    ):
        self._context = context
        self._registry = registry
        self._builder = builder
        self._client = client
        # Same lazy-construct reasoning as `logger` below: a `hooks=Hooks()`
        # default would be evaluated once at def-time and silently SHARED by
        # every Agent that didn't pass one -- so handlers registered for one
        # turn would leak into every later turn. (Repl builds a fresh Agent per
        # turn, which makes that leak both easy to hit and hard to see.)
        self._hooks = hooks if hooks is not None else Hooks()
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

    # Build a payload carrying the three things every handler needs (context,
    # registry, logger) plus this hook's own fields.
    def _payload(self, hook, **extra):
        return HookPayload(
            hook,
            context=self._context,
            registry=self._registry,
            logger=self._logger,
            agent=self,
            **extra,
        )

    def _fire(self, hook, **extra):
        return self._hooks.fire(hook, self._payload(hook, **extra))

    # Single funnel for every way a turn can end. `run()` returns from one
    # place and `_wrap_up` from two more, so firing `after_turn` at each
    # `return` site would be three chances to miss one -- and from the week1
    # session logs, EVERY turn in the longest grind session left through a
    # `_wrap_up` path, so a happy-path-only hook would have reported nothing at
    # all. Handlers may rewrite `payload.text` to change what the turn returns.
    def _finish_turn(self, text, *, reason):
        payload = self._fire(
            Hook.AFTER_TURN,
            reason=reason,
            text=text,
            iterations=self._iteration,
            tokens=self._context.turn_tokens,
        )
        return payload.text

    def run(self):
        self._context.reset_turn_tokens()
        self._compact_if_needed()
        self._fire(Hook.BEFORE_TURN)

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

            self._fire(Hook.BEFORE_MODEL, iteration=self._iteration)

            response = self._client.call(**self._call_opts())
            self._logger.raw(data=response)
            parsed = self._builder.parse_response(response)
            self._record_usage(response)
            self._log_reasoning(parsed["content"])

            if parsed["stop_reason"] == "tool_use":
                self._handle_tool_calls(parsed["content"], response)
            else:
                truncated = parsed["stop_reason"] == "max_tokens"
                if truncated:
                    self._note_truncation(response)

                text = self._extract_text(parsed["content"])
                self._logger.response(
                    text=text, usage=response.get("usage"), stop_reason=parsed["stop_reason"],
                    **self._cost_fields(response),
                )
                # The partial text is still added and returned -- it is better
                # than nothing and the model can be asked to continue -- but the
                # turn is reported as "truncated", not "completed", so downstream
                # consumers (and after_turn handlers) can tell the difference.
                reason = "truncated" if truncated else "completed"
                self._logger.turn_end(reason=reason, iterations=self._iteration, tokens=self._context.turn_tokens)
                self._context.add_message("assistant", text)
                return self._finish_turn(text, reason=reason)

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
        # max_turn_tokens is a SPEND ceiling (see this class's docstring), so
        # the turn budget is charged the billable input only -- cache reads are
        # deliberately excluded. With caching off, billable_input == the old
        # input_tokens, so this is a no-op today; with caching on it stops the
        # budget being eaten by tokens we barely pay for.
        #
        # That interaction matters more than it sounds. Measured over the
        # committed week1 logs: ~59,890 input tokens per turn against a 60,000
        # default ceiling, and 56 of 68 recorded turns ended on `max_tokens`
        # rather than `completed`. The budget was being consumed by re-sending
        # the conversation, not by doing work -- so turns were being cut off
        # mid-task. Caching should convert most of those into completed turns,
        # which makes it a capability fix and not only a cost one.
        #
        # Simplification accepted: cache reads DO still cost ~0.1x, so charging
        # them at zero slightly under-counts spend. Weighting them is not worth
        # the complexity until the reporter shows it mattering.
        self._context.add_turn_tokens(tokens["billable_input"], tokens["output"])
        # CACHE-AWARE (week2, and a real bug fix): `usage.input_tokens` is the
        # UNCACHED REMAINDER only -- the true prompt size is
        # input + cache_creation + cache_read. Passing the remainder here means
        # that the moment prompt caching is enabled, current_tokens collapses to
        # a small number, usage_fraction collapses with it, and
        # needs_compaction() stops firing no matter how full the real context
        # window gets. A long run then dies of a full window with no error to
        # point at.
        #
        # Same failure shape as the multi-provider usage-fallback bug this
        # method's own comment already documents (without which current_tokens
        # silently stays 0 for non-Anthropic backends) -- arriving by a new
        # route. Landed BEFORE caching is switched on, deliberately.
        self._context.update_tokens(tokens["context_size"])

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
        fresh_input = self._first_integer(usage, "input_tokens", "prompt_tokens", "promptTokenCount", "prompt_eval_count")
        output = self._first_integer(usage, "output_tokens", "completion_tokens", "candidatesTokenCount", "eval_count")
        cache_read = self._first_integer(usage, "cache_read_input_tokens")
        cache_write = self._first_integer(usage, "cache_creation_input_tokens")

        # Three different numbers, kept apart on purpose -- conflating any two
        # of them produces a plausible-looking wrong answer:
        #   context_size    what the model actually READ (drives compaction)
        #   billable_input  what we PAY full rate for (drives the spend budget)
        #   cache_*         priced separately (0.1x read / 1.25x write)
        return {
            "billable_input": fresh_input,
            "output": output,
            "cache_read": cache_read,
            "cache_write": cache_write,
            "context_size": (fresh_input or 0) + (cache_read or 0) + (cache_write or 0),
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

    # Everything Logger.response needs to record cost alongside usage. Kept in
    # one place so the four response() call sites can't drift apart on it.
    #
    # estimate_cost returns None when the model's rates are unknown (Ollama,
    # or an unpriced entry) -- reported as None rather than 0.0, because "free"
    # and "unknown" are different facts and a dashboard that renders unknown as
    # $0.00 quietly under-reports.
    def _cost_fields(self, response):
        backend = getattr(self._builder, "backend", None)
        if backend is None:
            return {}
        tokens = self._usage_tokens(response)
        try:
            cost = backend.estimate_cost(
                input_tokens=tokens["billable_input"],
                output_tokens=tokens["output"],
                cache_read_tokens=tokens["cache_read"],
                cache_write_tokens=tokens["cache_write"],
            )
        except Exception:  # noqa: BLE001 -- cost reporting must never break a turn
            cost = None
        return {
            "cost": cost,
            "provider": type(backend).__name__.lower(),
            "model": getattr(backend, "model", None),
            "usage_unit": getattr(backend, "usage_unit", None),
        }

    # The API cut the response off at the token ceiling. Logged loudly rather
    # than acted on: at the measured rate (1 of 404 responses in the week1
    # logs) retry machinery would be more risk than the problem. Once it is
    # visible we will have real data on whether that rate climbs.
    def _note_truncation(self, response):
        tokens = self._usage_tokens(response)
        self._logger.truncated(
            iteration=self._iteration,
            output_tokens=tokens["output"],
            max_output_tokens=self._max_output_tokens,
        )

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
            self._logger.response(
                text=text, usage=response.get("usage"), stop_reason=parsed_wrap["stop_reason"],
                **self._cost_fields(response),
            )
            self._logger.turn_end(reason=reason, iterations=self._iteration, tokens=self._context.turn_tokens)
            self._context.add_message("assistant", text)
            return self._finish_turn(text, reason=reason)
        except ApiError:
            msg = self._fallback_message(reason)
            self._logger.turn_end(reason=reason, iterations=self._iteration, tokens=self._context.turn_tokens)
            self._context.add_message("assistant", msg)
            return self._finish_turn(msg, reason=reason)

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
            **self._cost_fields(response),
        )

        self._context.add_message("assistant", content)

        self._fire(Hook.BEFORE_TOOLS, tool_calls=tool_calls)

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
                ok, error = False, str(e)
                self._logger.tool_result(name=name, result=result, ok=False, error=error)
            else:
                ok, error = True, None
                self._logger.tool_result(name=name, result=result, ok=True)

            # after_tool fires OUTSIDE the try/except above for the same reason
            # the success-path logger call is: a handler that raises must not
            # be mistaken for the tool having failed. Hooks.fire swallows and
            # logs handler exceptions, so `result` survives regardless.
            #
            # The payload is what lands in the message list, not `result` --
            # that is the mutation contract, and it is what lets a handler
            # replace a raw room dump with a compact summary (week2's token
            # pillar) while the full text still reaches memory (the memory
            # pillar). Logged above with the ORIGINAL result on purpose: the
            # session log should record what the tool actually returned, not
            # the trimmed version the model was shown.
            payload = self._fire(
                Hook.AFTER_TOOL, name=name, args=args, result=result, ok=ok, error=error
            )

            self._context.add_message("tool_result", str(payload.result), tool_use_id=use_id)
