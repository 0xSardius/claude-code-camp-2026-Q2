"""Port of week1_baseline/ruby/10_standard_tool_library/lib/boukensha/repl.rb --
the interactive session loop. Gains a mud= parameter and a MUD status
banner line this step (see docs/plans/python_port/10_standard_tool_library).

It wraps the same primitives as a single boukensha.run() call, but instead
of running once it stays alive: it reads a task from the user, runs the
agent, prints the reply, and loops back to the prompt.

The Context is shared across every turn so conversation history
accumulates naturally -- the agent sees the full transcript each time it
is called. A NEW Agent is constructed every turn (see _run_turn) --
matches Ruby exactly: this resets the per-turn iteration counter (a
tool-calling budget for *this* turn) while conversation history persists
via the shared Context, which is a separate object.

Ruby's `$stdin.gets` returns nil at EOF; Python's sys.stdin.readline()
returns "" at EOF (never None) -- `if not line: break` correctly
distinguishes a true EOF ("") from a blank line typed by the user ("\\n",
which is truthy/non-empty in Python), so this needs no special-casing
beyond the natural translation.
"""
import sys
from pathlib import Path

from .agent import Agent
from .errors import ApiError, LoopError
from ._module_state import disable_quiet, enable_quiet


class Repl:
    PROMPT = "boukensha> "

    HELP = (
        "Commands:\n"
        "  /quiet   suppress logging output\n"
        "  /loud    re-enable logging output\n"
        "  /clear   wipe conversation history (tools stay)\n"
        "  /exit    leave the REPL\n"
        "  /help    show this message"
    )

    def __init__(
        self,
        *,
        context,
        registry,
        builder,
        client,
        logger,
        config_dir=None,
        provider=None,
        model=None,
        version=None,
        api_key=None,
        mud=None,
        task_settings=None,
        max_iterations=None,
        max_output_tokens=None,
    ):
        self._context = context
        self._registry = registry
        self._builder = builder
        self._client = client
        self._logger = logger
        self._task_settings = task_settings
        self._max_iterations = max_iterations
        self._max_output_tokens = max_output_tokens
        self._config_dir = config_dir
        self._provider = provider
        self._model = model
        self._version = version
        self._api_key = api_key
        self._mud = mud
        self._turn = 0

    def start(self):
        print(self._banner())

        while True:
            print(self.PROMPT, end="")
            sys.stdout.flush()

            line = sys.stdin.readline()
            if not line:  # EOF / Ctrl-D
                break

            text = line.strip()
            if not text:
                continue

            if text in ("/exit", "/quit"):
                print("Goodbye.")
                break
            elif text == "/help":
                print(self.HELP)
                continue
            elif text == "/quiet":
                enable_quiet()
                print("(logging suppressed — type /loud to re-enable)")
                continue
            elif text == "/loud":
                disable_quiet()
                print("(logging enabled)")
                continue
            elif text == "/clear":
                self._context.clear_messages()
                self._turn = 0
                print("(conversation history cleared)")
                continue

            self._run_turn(text)

    def _banner(self):
        if self._api_key is None or self._api_key.strip() == "":
            key_status = "✗ API key not set"
        else:
            key_status = "✓ API key set"

        provider = self._provider if self._provider is not None else "default"
        model = self._model if self._model is not None else "default"
        provider_line = f"{provider} ({model})  {key_status}"

        config_exists = self._config_dir is not None and Path(self._config_dir).is_dir()
        if config_exists:
            config_line = self._config_dir
        else:
            config_dir_display = self._config_dir if self._config_dir is not None else "(default)"
            config_line = f"{config_dir_display}  ✗ directory not found"

        ver = self._version if self._version is not None else "?.?.?"
        # Ruby's " " * (9 - ver.length) raises on ver longer than 9 chars;
        # Python's " " * negative silently returns "" instead. VERSION is a
        # hardcoded 6-char constant ("0.10.0"), so this never actually
        # triggers -- noted, not defensively guarded.
        padding = " " * (9 - len(ver))
        mud_stat = self._mud_status_string()

        return (
            "\n"
            "╔══════════════════════════════════════╗\n"
            f"║  BOUKENSHA MUD Assistant (v{ver}){padding}║\n"
            "╚══════════════════════════════════════╝\n"
            f"  config:    {config_line}\n"
            f"  provider:  {provider_line}\n"
            f"  mud:       {mud_stat}\n"
            "\n"
            "  /quiet or /loud   toggle logging\n"
            "  /clear           reset conversation history\n"
            "  /exit or /quit    leave the REPL\n"
        )

    # Build the mud status string shown in the banner. Only checks TCP
    # reachability -- the tool session auto-connects at startup (in
    # tools/mud.py's register()), so probing login here would cause a
    # double-login.
    def _mud_status_string(self):
        try:
            if not self._mud:
                return "(not configured)"
            # Ruby: `@mud[:host] || "localhost"` -- falls back only on nil,
            # not on any falsy value. `is not None`, not `or`, so an
            # explicit host="" or port=0 is preserved rather than silently
            # replaced (the same mud.port: 0 example CLAUDE.md names).
            mud_host = self._mud.get("host")
            host = mud_host if mud_host is not None else "localhost"
            mud_port = self._mud.get("port")
            port = mud_port if mud_port is not None else 4000
            name = self._mud.get("name")
            return f"{host}:{port}  {self._probe_mud(host, port, name)}"
        except Exception as e:
            # Ruby wraps the whole method in `rescue StandardError => e`;
            # mirrored here with a broad except for the same reason -- not
            # because a specific new failure mode is expected beyond what
            # _probe_mud's own narrower except already covers.
            return f"✗ probe error: {e}"

    def _probe_mud(self, host, port, name):
        import socket

        try:
            with socket.create_connection((host, port), timeout=3):
                pass
        except OSError:
            return "✗ not reachable"
        return "(Reachable)" if name and str(name).strip() else "(Reachable, no credentials)"

    def _run_turn(self, text):
        # Ruby's rescue clauses are method-level, covering the whole
        # method body (turn increment, logger.turn, add_message, Agent
        # construction, AND agent.run) -- matched here with one try
        # wrapping everything, not just agent.run().
        #
        # rollback_point + truncating messages on failure fixes a real bug
        # found in the Ruby source too (same structure there): without it,
        # a failed turn leaves an orphaned user message with no assistant
        # reply, so the NEXT turn's user message lands right after it --
        # two consecutive user-role messages, which the real API rejects,
        # permanently breaking the session until /clear. Fixed in Ruby too,
        # not just mirrored here.
        rollback_point = len(self._context.messages)
        try:
            self._turn += 1
            self._logger.turn(n=self._turn)

            self._context.add_message("user", text)

            agent = Agent(
                context=self._context,
                registry=self._registry,
                builder=self._builder,
                client=self._client,
                logger=self._logger,
                task_settings=self._task_settings,
                max_iterations=self._max_iterations,
                max_output_tokens=self._max_output_tokens,
            )
            result = agent.run()
        except LoopError as e:
            print(f"\n[error] {e}")
            del self._context.messages[rollback_point:]
            return
        except ApiError as e:
            print(f"\n[error] API call failed: {e}")
            del self._context.messages[rollback_point:]
            return

        print()
        print(result)
