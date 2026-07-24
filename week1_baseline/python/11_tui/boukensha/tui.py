"""Textual-based terminal UI wrapping a Repl -- see
docs/plans/python_port/11_tui for why this isn't a literal port of
week1_baseline/ruby/11_tui/lib/boukensha/tui.rb (no Python equivalent to
charm/bubbletea exists). Replicates the same four-zone layout and live
progress behavior using Textual's own widget/worker model instead of
mirroring bubbletea's init/update/view architecture.
"""
import queue
import threading
import time

from textual import work
from textual.app import App, ComposeResult
from textual.widgets import Input, RichLog, Static

from .agent import Agent  # for Agent.MAX_ITERATIONS in the progress line
from .errors import ApiError, LoopError, TurnInterrupted

TICK_SECONDS = 0.06  # matches Ruby's TICK_MS = 60
SPINNER_FRAMES = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"


class Tui(App):
    CSS = """
    RichLog { height: 1fr; }
    #progress, #status { height: 1; }
    Input { height: 1; }
    """
    BINDINGS = [
        ("ctrl+l", "clear_history", "Clear"),
        ("escape", "interrupt_turn", "Interrupt"),
        ("pageup", "scroll_up_page", "Scroll up"),
        ("pagedown", "scroll_down_page", "Scroll down"),
    ]

    def __init__(self, repl, interrupt_event):
        super().__init__()
        self._repl = repl
        # NOT self._context -- textual.app.App already has an internal
        # _context attribute (confirmed: hasattr(App(), "_context") is
        # True). Silently overwriting it with the boukensha Context object
        # hung app.run_test()/the real app indefinitely with no error
        # raised -- found by bisecting a minimal reproduction after the
        # full Tui hung at mount with zero diagnostic output. A genuine
        # Python-side naming collision Ruby's version has no equivalent
        # of (Tui#initialize's @context in Ruby doesn't collide with
        # anything bubbletea defines).
        self._boukensha_context = repl.context
        self._interrupt_event = interrupt_event
        self._events = queue.Queue()

        self._turn_count = 0
        self._session_input_tokens = 0
        self._session_output_tokens = 0
        self._turn_running = False

        self._live = self._fresh_live_state()

    def compose(self) -> ComposeResult:
        yield RichLog(id="conversation", wrap=True, markup=False)
        yield Static(id="progress")
        yield Input(placeholder="Type a message…", id="input_box")
        yield Static(id="status")

    def on_mount(self) -> None:
        log = self.query_one("#conversation", RichLog)
        log.write(self._repl.banner())

        self._repl.on_output(self._write_output)
        self._repl.logger.subscribe(self._events.put)

        self.query_one(Input).focus()
        self.set_interval(TICK_SECONDS, self._on_tick)
        self._render_status()
        self._render_progress()

    # ── input & commands ──────────────────────────────────────────────

    def on_input_submitted(self, event: Input.Submitted) -> None:
        text = event.value.strip()
        self.query_one(Input).value = ""
        if not text:
            return

        if text.startswith("/"):
            result = self._repl.handle_command(text)
            if result == "quit":
                self.exit()
                return
            if text == "/clear":
                self._turn_count = 0
            return

        self.query_one("#conversation", RichLog).write(f"> {text}")
        self._launch_turn(text)

    def action_clear_history(self) -> None:
        self._repl.handle_command("/clear")
        self._turn_count = 0

    def action_interrupt_turn(self) -> None:
        if self._turn_running:
            self._interrupt_event.set()

    def action_scroll_up_page(self) -> None:
        self.query_one("#conversation", RichLog).scroll_page_up()

    def action_scroll_down_page(self) -> None:
        self.query_one("#conversation", RichLog).scroll_page_down()

    # Repl.on_output's callback -- called from TWO different threads
    # depending on the caller: handle_command() (slash commands) runs
    # synchronously on the app's own thread (from on_input_submitted),
    # while run_turn() runs on the worker thread spawned by
    # _run_turn_worker. Textual's call_from_thread() raises RuntimeError
    # if called from the app's OWN thread ("must run in a different
    # thread from the app") -- a real bug found live (not by review):
    # unconditionally wrapping every write in call_from_thread crashed on
    # the very first /help command, which never touches the worker
    # thread at all. Comparing against Textual's own recorded
    # self._thread_id (the same check call_from_thread makes internally)
    # picks the safe path for either caller.
    def _write_output(self, s):
        log = self.query_one("#conversation", RichLog)
        if threading.get_ident() == self._thread_id:
            log.write(s)
        else:
            self.call_from_thread(log.write, s)

    # ── background turn ───────────────────────────────────────────────

    def _launch_turn(self, text):
        self._interrupt_event.clear()
        self._turn_running = True
        self._live = self._fresh_live_state()
        self._live["active"] = True
        self._live["start_time"] = time.monotonic()
        self._run_turn_worker(text)

    @work(thread=True, exclusive=True, group="turn")
    def _run_turn_worker(self, text):
        try:
            self._repl.run_turn(text)
        except TurnInterrupted:
            self._events.put({"phase": "turn_interrupted"})
        except (LoopError, ApiError) as e:
            self._events.put({"phase": "turn_error", "error": str(e)})
        finally:
            self._events.put({"phase": "turn_complete"})

    # ── tick / event draining ─────────────────────────────────────────

    def _on_tick(self) -> None:
        self._drain_events()
        if self._live["active"]:
            self._live["spinner_idx"] = (self._live["spinner_idx"] + 1) % len(SPINNER_FRAMES)
            if self._live["start_time"] is not None:
                self._live["elapsed"] = time.monotonic() - self._live["start_time"]
        self._render_progress()
        self._render_status()

    def _drain_events(self) -> None:
        while True:
            try:
                event = self._events.get_nowait()
            except queue.Empty:
                break
            self._handle_event(event)

    def _handle_event(self, event) -> None:
        phase = str(event.get("phase", ""))
        log = self.query_one("#conversation", RichLog)

        if phase == "iteration":
            self._live["iteration"] = int(event.get("n") or 0)
            self._live["current_action"] = "Thinking…"
        elif phase == "tool_call":
            self._live["current_action"] = f"Calling tool: {event.get('name')}"
            self._live["tool_call_count"] += 1
        elif phase == "tool_result":
            self._live["current_action"] = "Awaiting result…"
        elif phase == "response":
            usage = event.get("usage")
            if usage:
                itu = int(usage.get("input_tokens") or 0)
                otu = int(usage.get("output_tokens") or 0)
                self._live["turn_input_tokens"] += itu
                self._live["turn_output_tokens"] += otu
                self._session_input_tokens += itu
                self._session_output_tokens += otu
        elif phase == "turn_complete":
            self._live["active"] = False
            self._turn_running = False
            self._turn_count += 1
        elif phase == "turn_interrupted":
            log.write("[interrupted]")
        elif phase == "turn_error":
            self._live["active"] = False
            self._turn_running = False
            log.write(f"[error] {event.get('error')}")

    # ── rendering ──────────────────────────────────────────────────────

    def _render_progress(self) -> None:
        bar = self.query_one("#progress", Static)
        if self._live["active"]:
            frame = SPINNER_FRAMES[self._live["spinner_idx"]]
            secs = int(self._live["elapsed"])
            itok = self._fmt_tokens(self._live["turn_input_tokens"])
            otok = self._fmt_tokens(self._live["turn_output_tokens"])
            calls = self._live["tool_call_count"]
            iteration = self._live["iteration"]
            bar.update(
                f"{frame} {self._live['current_action']}  "
                f"(iter {iteration}/{Agent.MAX_ITERATIONS} · {secs}s · "
                f"↑ {itok} · ↓ {otok} · {calls} calls)"
            )
        else:
            used = self._fmt_tokens(self._session_input_tokens)
            bar.update(f"  [ready]   ctx {used}   {self._turn_count} turns")

    def _render_status(self) -> None:
        status = self.query_one("#status", Static)
        ver = self._repl.version or "?.?.?"
        model = self._repl.model or "(model)"
        used = self._fmt_tokens(self._session_input_tokens)
        tools = self._boukensha_context.tool_count
        clock = time.strftime("%H:%M:%S")
        status.update(f" boukensha v{ver} · {model}  ·  ctx {used}  ·  {tools} tools  ·  {clock} ")

    def _fresh_live_state(self):
        return {
            "active": False,
            "spinner_idx": 0,
            "start_time": None,
            "elapsed": 0,
            "current_action": "idle",
            "iteration": 0,
            "tool_call_count": 0,
            "turn_input_tokens": 0,
            "turn_output_tokens": 0,
        }

    def _fmt_tokens(self, n):
        n = int(n)
        return f"{round(n / 1000.0, 1)}k" if n >= 1000 else str(n)
