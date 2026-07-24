"""Port of week1_baseline/ruby/11_tui/lib/boukensha/repl.rb -- refactored
for composability so a Tui (or any other front-end) can drive it instead
of hard-coding print()/input(). See docs/plans/python_port/11_tui.

Changes from 10_standard_tool_library's version:
- on_output(callback): route all output through a callback instead of
  stdout when set.
- handle_command(text): extracted as a public method (was inlined in
  start()'s loop). Returns "quit", "command", or None (Ruby: :quit,
  :command, nil -- no Python symbol type, plain strings play the same
  sentinel role, same "nothing to translate" reasoning as 07_the_run_dsl's
  RunDSL).
- run_turn(text): renamed from the private _run_turn, now public, routes
  output through the same output() helper handle_command uses.
- banner(): renamed from _banner, now public.
- logger/context/model/version: now public attributes (Ruby: attr_reader),
  dropping the leading underscore for exactly these four -- everything
  else Ruby doesn't expose a reader for stays private-by-convention.
- /quiet and /loud are REMOVED (Ruby deleted Boukensha.quiet!/.loud!/
  .quiet? entirely at the module level this step, not just from the REPL
  -- confirmed via diff, a deliberate cleanup, not a regression to
  restore).
- interrupt_event: new, no Ruby counterpart -- forwarded into every Agent
  this Repl constructs. See agent.py's module docstring.
"""
import sys
from pathlib import Path

from .agent import Agent
from .errors import ApiError, LoopError


class Repl:
    PROMPT = "boukensha> "

    HELP = (
        "Commands:\n"
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
        interrupt_event=None,
    ):
        self.context = context
        self.logger = logger
        self.model = model
        self.version = version
        self._registry = registry
        self._builder = builder
        self._client = client
        self._task_settings = task_settings
        self._max_iterations = max_iterations
        self._max_output_tokens = max_output_tokens
        self._config_dir = config_dir
        self._provider = provider
        self._api_key = api_key
        self._mud = mud
        self._interrupt_event = interrupt_event
        self._turn = 0
        self._output_cb = None

    def on_output(self, callback):
        """Register a callback that receives every string the REPL would
        otherwise print to stdout. When set, print() is suppressed
        entirely and all output routes through the callback instead.
        Used by Tui."""
        self._output_cb = callback

    def banner(self):
        if self._api_key is None or self._api_key.strip() == "":
            key_status = "✗ API key not set"
        else:
            key_status = "✓ API key set"

        provider = self._provider if self._provider is not None else "default"
        model = self.model if self.model is not None else "default"
        provider_line = f"{provider} ({model})  {key_status}"

        config_exists = self._config_dir is not None and Path(self._config_dir).is_dir()
        if config_exists:
            config_line = self._config_dir
        else:
            config_dir_display = self._config_dir if self._config_dir is not None else "(default)"
            config_line = f"{config_dir_display}  ✗ directory not found"

        ver = self.version if self.version is not None else "?.?.?"
        # Ruby's " " * (9 - ver.length) raises on ver longer than 9 chars;
        # Python's " " * negative silently returns "" instead. VERSION is a
        # hardcoded 6-char constant ("0.11.0"), so this never actually
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
            "  /clear           reset conversation history\n"
            "  /exit or /quit    leave the REPL\n"
        )

    def handle_command(self, text):
        """Handle a slash command. Returns "quit", "command", or None (not
        a command). Output is routed through the registered on_output
        callback if present."""
        if text in ("/exit", "/quit"):
            self.output("Goodbye.")
            return "quit"
        elif text == "/help":
            self.output(self.HELP)
            return "command"
        elif text == "/clear":
            self.context.clear_messages()
            self._turn = 0
            self.output("(conversation history cleared)")
            return "command"
        return None

    def run_turn(self, text):
        self._turn += 1
        self.logger.turn(n=self._turn)

        self.context.add_message("user", text)

        agent = Agent(
            context=self.context,
            registry=self._registry,
            builder=self._builder,
            client=self._client,
            logger=self.logger,
            task_settings=self._task_settings,
            max_iterations=self._max_iterations,
            max_output_tokens=self._max_output_tokens,
            interrupt_event=self._interrupt_event,
        )
        try:
            result = agent.run()
        except LoopError as e:
            self.output(f"\n[error] {e}")
            return
        except ApiError as e:
            self.output(f"\n[error] API call failed: {e}")
            return

        self.output("")
        self.output(result)

    def start(self):
        self.output(self.banner())
        while True:
            if self._output_cb is None:
                print(self.PROMPT, end="")
                sys.stdout.flush()

            line = sys.stdin.readline()
            if not line:  # EOF / Ctrl-D
                break

            text = line.strip()
            if not text:
                continue

            result = self.handle_command(text)
            if result == "quit":
                break
            if result:
                continue

            self.run_turn(text)

    def output(self, str_):
        if self._output_cb is not None:
            self._output_cb(str(str_))
        else:
            print(str_)

    # Build the mud status string shown in the banner. Only checks TCP
    # reachability -- the tool session auto-connects at startup (in
    # tools/mud.py's register()), so probing login here would cause a
    # double-login.
    def _mud_status_string(self):
        if not self._mud:
            return "(not configured)"

        host = self._mud.get("host") or "localhost"
        port = self._mud.get("port") or 4000
        name = self._mud.get("name")
        password = self._mud.get("password")

        return f"{host}:{port}  {self._probe_mud(host, port, name, password)}"

    def _probe_mud(self, host, port, name, password):
        import socket

        try:
            with socket.create_connection((host, port), timeout=3):
                pass
        except OSError:
            return "✗ not reachable"

        return "(Reachable)" if name and str(name).strip() else "(Reachable, no credentials)"
