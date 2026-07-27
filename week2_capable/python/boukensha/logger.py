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

    def turn_end(self, *, reason, iterations, tokens=None):
        self._write_log({"phase": "turn_end", "reason": reason, "iterations": iterations, "tokens": tokens})

    def prompt(self, *, messages, tools, context_window):
        self._write_log(
            {
                "phase": "prompt",
                "message_count": len(messages),
                "messages": [self._serialize_message(m) for m in messages],
                "tool_count": len(tools),
                "tools": list(tools.keys()),
                "context_window": context_window,
            }
        )

    def compaction(self, *, before, dropped, context_window):
        self._write_log({"phase": "compaction", "before": before, "dropped": dropped, "context_window": context_window})

    def tool_call(self, *, name, args):
        self._write_log({"phase": "tool_call", "name": name, "args": args})

    def tool_result(self, *, name, result, ok=True, error=None):
        self._write_log({"phase": "tool_result", "name": name, "result": str(result), "ok": ok, "error": error})

    def response(self, *, text, usage=None, stop_reason=None):
        self._write_log({"phase": "response", "text": str(text).strip(), "usage": usage, "stop_reason": stop_reason})

    def reasoning(self, *, text, redacted=False):
        self._write_log({"phase": "reasoning", "text": str(text), "redacted": redacted})

    def plan(self, *, text):
        self._write_log({"phase": "plan", "text": str(text).strip()})

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
