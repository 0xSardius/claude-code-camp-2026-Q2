"""Port of week1_baseline/ruby/12_context/lib/boukensha/logger.rb --
narrower than 11_tui's version: response() loses task=/backend=, and
_execution_metadata/_task_name/_provider_name/_usage_tokens/_first_integer/
_estimate_cost are all gone. Gained reasoning()/plan()/compaction();
prompt() gains context_window=.

This is a real, deliberate regression in per-response cost/provider
observability relative to what 06_the_logger through 11_tui built up --
mirrored faithfully because it's clean and symmetric on both the Agent
call sites and this signature (not a half-finished refactor), and because
Backends::Base still fully defines estimate_cost/usage_unit/usage_level
(nothing deleted from backends, just disconnected from this call site --
same "declared but currently unused" pattern as LoopError/quiet!). See
docs/plans/python_port/12_context.
"""
import json
import secrets
from datetime import datetime, timezone
from pathlib import Path

from ._module_state import config as boukensha_config
from ._module_state import is_debug


class Logger:
    DEFAULT_SESSION_DIR = "sessions"

    def __init__(self, *, session_id=None, dir=None, log=None, snapshot=None):
        self._subscribers = []
        self.session_id = session_id if session_id is not None else self._generate_session_id()
        if log is not None:
            self.path = log
        else:
            base_dir = dir if dir is not None else self._default_dir()
            self.path = str(Path(base_dir) / f"{self.session_id}.jsonl")

        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._log_io = open(self.path, "a", encoding="utf-8")
        self._write_log({"phase": "session_start", **(snapshot or {})})

    def iteration(self, *, n, max):
        self._write_log({"phase": "iteration", "n": n, "max": max})

    def turn(self, *, n):
        self._write_log({"phase": "turn", "n": n})

    def limit_reached(self, *, kind, n, max):
        self._write_log({"phase": "limit_reached", "kind": kind, "n": n, "max": max})

    def turn_end(self, *, reason, iterations, tokens=None, seconds=None):
        # `seconds` so a turn that took an abnormally long time is visible
        # afterwards. A run hung for 22 hours on 2026-08-05 and the log gave no
        # way to see it: every line looked normal, there were just no more of
        # them. Duration is what makes "it stopped" different from "it is slow".
        self._write_log({"phase": "turn_end", "reason": reason, "iterations": iterations,
                         "tokens": tokens, "seconds": seconds})

    # week2 M6: log a DIGEST of the message list, not the whole thing.
    #
    # This method used to serialize every message on every iteration, so log
    # size grew quadratically with conversation length. Measured across the 25
    # committed week1 sessions: `prompt` events were 4.3 MB of a single 4.56 MB
    # file (94%), and session logs overall were 11 MB of a 17 MB repo. Since
    # week2 commits logs for evaluation AND runs much longer grind sessions --
    # with hooks injecting still more messages -- that curve had to be broken
    # before the long runs start, not after.
    #
    # The digest keeps what analysis actually needs (how many messages, of what
    # roles, how big) and drops the part that was pure repetition: the contents,
    # which are already recorded once each by the response/tool_result events
    # that produced them. Full fidelity remains available behind BOUKENSHA_DEBUG,
    # same escape hatch as raw().
    def prompt(self, *, messages, tools, context_window):
        event = {
            "phase": "prompt",
            "message_count": len(messages),
            "digest": self._digest_messages(messages),
            "tool_count": len(tools),
            "tools": list(tools.keys()),
            "context_window": context_window,
        }
        if is_debug():
            event["messages"] = [self._serialize_message(m) for m in messages]
        self._write_log(event)

    # Roles in order plus a total character count -- enough to reconstruct the
    # shape of the conversation (and spot an orphaned leading tool_result, the
    # failure that cost 15 dead turns in week1) without reprinting its text.
    def _digest_messages(self, messages):
        roles = []
        chars = 0
        for m in messages:
            roles.append(m.role)
            chars += len(str(m.content))
        return {"roles": roles, "content_chars": chars}

    def compaction(self, *, before, dropped, context_window):
        self._write_log({"phase": "compaction", "before": before, "dropped": dropped, "context_window": context_window})

    def tool_call(self, *, name, args):
        self._write_log({"phase": "tool_call", "name": name, "args": args})

    def tool_result(self, *, name, result, ok=True, error=None):
        self._write_log({"phase": "tool_result", "name": name, "result": str(result), "ok": ok, "error": error})

    # week2: cost/provider/model restored. 12_context dropped these relative to
    # 06_the_logger..11_tui while leaving Backends::Base.estimate_cost fully
    # implemented but uncalled; this reconnects that. `cost` is a float in USD
    # or None when the model's rates are unknown (Ollama et al).
    def response(
        self, *, text, usage=None, stop_reason=None,
        cost=None, provider=None, model=None, usage_unit=None,
    ):
        self._write_log({
            "phase": "response",
            "text": str(text).strip(),
            "usage": usage,
            "stop_reason": stop_reason,
            "cost": cost,
            "provider": provider,
            "model": model,
            "usage_unit": usage_unit,
        })

    # week2: the API cut this response off at max_tokens. Emitted as its own
    # phase rather than folded into `response` so it is greppable and countable
    # -- the whole problem with the previous behavior was that truncation was
    # indistinguishable from a normal completion.
    def truncated(self, *, iteration, output_tokens=None, max_output_tokens=None):
        self._write_log({
            "phase": "truncated",
            "iteration": iteration,
            "output_tokens": output_tokens,
            "max_output_tokens": max_output_tokens,
        })

    def reasoning(self, *, text, redacted=False):
        self._write_log({"phase": "reasoning", "text": str(text), "redacted": redacted})

    def plan(self, *, text):
        self._write_log({"phase": "plan", "text": str(text).strip()})

    # week2: a lifecycle handler raised. Logged rather than propagated -- a
    # crashing observer must never cost a turn (or, at after_tool, a real tool
    # result). See hooks.py's Hooks.fire.
    def hook_error(self, *, hook, handler, error):
        self._write_log({"phase": "hook_error", "hook": hook, "handler": handler, "error": error})

    # week3: one line per driver cycle -- what it did, whether it cost a model
    # call, and how many actions fell on each side of the judgment boundary.
    # The judgment ratio (week3's acceptance metric) is computed from these,
    # which is why the action counts are logged and not just derived at the end
    # of a run: a run that dies halfway still leaves the numbers on disk.
    def driver_cycle(self, *, action, used_model, note="",
                     mechanical_actions=0, model_actions=0):
        self._write_log({"phase": "driver_cycle", "action": action,
                         "used_model": bool(used_model), "note": note,
                         "mechanical_actions": int(mechanical_actions),
                         "model_actions": int(model_actions)})

    # week3: a turn that raised instead of finishing. Separate from turn_end,
    # which only covers turns that completed -- so a failed turn used to leave
    # no trace at all beyond a prompt with no response after it.
    def turn_failed(self, *, n, error):
        self._write_log({"phase": "turn_failed", "n": n, "error": error})

    # week3: one line per driver RUN, written when it ends. The per-cycle lines
    # cannot answer "what did this cost per unit of progress" on their own,
    # because experience is only meaningful as a delta across the whole run.
    def driver_run(self, *, goal, task=None, cycles, stopped_because,
                   starting_exp=None, ending_exp=None):
        self._write_log({"phase": "driver_run", "goal": goal, "task": task,
                         "cycles": int(cycles), "stopped_because": stopped_because,
                         "starting_exp": starting_exp, "ending_exp": ending_exp})

    def raw(self, *, data):
        if not is_debug():
            return
        self._write_log({"phase": "raw", "data": data})

    def subscribe(self, callback):
        self._subscribers.append(callback)

    def close(self):
        if self._log_io:
            self._log_io.close()

    def _default_dir(self):
        return str(Path(boukensha_config().dir) / self.DEFAULT_SESSION_DIR)

    def _write_log(self, event):
        record = {
            **event,
            "session_id": self.session_id,
            "at": datetime.now().astimezone().isoformat(timespec="seconds"),
        }
        self._log_io.write(json.dumps(record) + "\n")
        self._log_io.flush()
        # Ruby: @subscribers&.each { |s| s.call(event) } -- the ORIGINAL
        # event, not `record` -- session_id/at are never seen by
        # subscribers, only by the JSONL line on disk.
        for subscriber in self._subscribers:
            subscriber(event)

    def _generate_session_id(self):
        return f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{secrets.token_hex(4)}"

    def _serialize_message(self, msg):
        return {"role": msg.role, "content": msg.content}
