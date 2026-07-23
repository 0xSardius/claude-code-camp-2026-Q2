"""Port of week1_baseline/ruby/06_the_logger/lib/boukensha/logger.rb.

Two load-bearing instances of the Ruby-nil-vs-Python-falsy gotcha beyond
the now-familiar ones: _execution_metadata's early return (an explicitly
empty `usage={}` is truthy in Ruby, falsy in Python) and
_normalized_usage's response-field checks (same issue on an empty
`response["usage"]`/`response["usageMetadata"]`). Both use `is not None`,
never a bare truthy check.
"""
import json
import re
import secrets
from datetime import datetime, timezone
from pathlib import Path

from ._module_state import config as boukensha_config
from ._module_state import is_debug


class Logger:
    DEFAULT_SESSION_DIR = "sessions"

    def __init__(self, *, session_id=None, dir=None, log=None, snapshot=None):
        self.session_id = session_id if session_id is not None else self._generate_session_id()
        # Ruby's `log || File.join(dir || default_dir, ...)` short-circuits:
        # dir/default_dir are never evaluated when log is given. Mirrored
        # here with an if/else, not an eager `base_dir = ...` computed
        # unconditionally -- _default_dir() lazily constructs the global
        # Config singleton (real file I/O reading settings.yaml/.env),
        # which an explicit log= path should never trigger.
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

    def limit_reached(self, *, kind, n, max):
        self._write_log({"phase": "limit_reached", "kind": kind, "n": n, "max": max})

    def turn_end(self, *, reason, iterations, tokens=None):
        self._write_log({"phase": "turn_end", "reason": reason, "iterations": iterations, "tokens": tokens})

    def prompt(self, *, messages, tools):
        self._write_log(
            {
                "phase": "prompt",
                "message_count": len(messages),
                "messages": [self._serialize_message(m) for m in messages],
                "tool_count": len(tools),
                "tools": list(tools.keys()),
            }
        )

    def tool_call(self, *, name, args):
        self._write_log({"phase": "tool_call", "name": name, "args": args})

    def tool_result(self, *, name, result, ok=True, error=None):
        self._write_log({"phase": "tool_result", "name": name, "result": str(result), "ok": ok, "error": error})

    def response(self, *, text, usage=None, stop_reason=None, task=None, backend=None):
        event = {"phase": "response", "text": str(text).strip(), "usage": usage, "stop_reason": stop_reason}
        event.update(self._execution_metadata(task=task, backend=backend, usage=usage))
        self._write_log(event)

    def raw(self, *, data):
        if not is_debug():
            return
        self._write_log({"phase": "raw", "data": data})

    def close(self):
        if self._log_io:
            self._log_io.close()

    def _default_dir(self):
        return str(Path(boukensha_config().dir) / self.DEFAULT_SESSION_DIR)

    def _write_log(self, event):
        # Ruby's Time.now.iso8601 has no fractional-second component by
        # default; Python's isoformat() would include microseconds unless
        # timespec="seconds" is passed.
        record = {
            **event,
            "session_id": self.session_id,
            "at": datetime.now().astimezone().isoformat(timespec="seconds"),
        }
        self._log_io.write(json.dumps(record) + "\n")
        self._log_io.flush()

    def _generate_session_id(self):
        return f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{secrets.token_hex(4)}"

    def _serialize_message(self, msg):
        return {"role": msg.role, "content": msg.content}

    def _execution_metadata(self, *, task, backend, usage):
        if task is None and backend is None and usage is None:
            return {}

        tokens = self._usage_tokens(usage)
        metadata = {
            "task": self._task_name(task),
            "provider": self._provider_name(backend),
            "model": backend.model if backend is not None else None,
            "usage_unit": getattr(backend, "usage_unit", None) if backend is not None else None,
            "usage_level": getattr(backend, "usage_level", None) if backend is not None else None,
            "input_tokens": tokens["input"],
            "output_tokens": tokens["output"],
            "cost_usd": self._estimate_cost(backend, tokens),
        }
        return {k: v for k, v in metadata.items() if v is not None}

    def _task_name(self, task):
        if task is None:
            return None
        return task.task_name() if hasattr(task, "task_name") else str(task)

    # Ruby: backend.class.name.split("::").last.gsub(/([a-z\d])([A-Z])/,
    # '\1_\2').downcase -- a real quirk: "OpenAI" -> "open_ai" (verified
    # empirically), not "openai". Ported with the identical regex, not
    # "corrected" -- see the port plan's dedicated section on this.
    def _provider_name(self, backend):
        if backend is None:
            return None
        return re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", type(backend).__name__).lower()

    def _usage_tokens(self, usage):
        usage = usage or {}
        return {
            "input": self._first_integer(
                usage, "input_tokens", "prompt_tokens", "promptTokenCount", "prompt_eval_count"
            ),
            "output": self._first_integer(
                usage, "output_tokens", "completion_tokens", "candidatesTokenCount", "eval_count"
            ),
        }

    def _first_integer(self, d, *keys):
        # Ruby's method-level rescue means a key that resolves to a
        # non-nil-but-unparseable value returns nil immediately, without
        # trying later keys -- ported as-is, not "improved" to keep trying.
        for key in keys:
            value = d.get(key)
            if value is not None:
                try:
                    return int(value)
                except (ValueError, TypeError):
                    return None
        return None

    def _estimate_cost(self, backend, tokens):
        if backend is None or not hasattr(backend, "estimate_cost"):
            return None
        if tokens["input"] is None or tokens["output"] is None:
            return None
        return backend.estimate_cost(input_tokens=tokens["input"], output_tokens=tokens["output"])
