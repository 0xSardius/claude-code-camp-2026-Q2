"""Textual-based terminal UI wrapping a Repl -- see
docs/plans/python_port/11_tui for why this isn't a literal port of
week1_baseline/ruby/*/lib/boukensha/tui.rb (no Python equivalent to
charm/bubbletea exists). Replicates the same four-zone layout and live
progress behavior using Textual's own widget/worker model instead of
mirroring bubbletea's init/update/view architecture.

Changes from 11_tui's version (see ruby/12_context/lib/boukensha/tui.rb):
- session_input_tokens/session_output_tokens are GONE -- the idle status
  line and progress line now read live context-window usage
  (context.current_tokens/context_window/usage_pct) instead of a
  session-lifetime running total, matching Ruby's switch away from
  @session_input_tokens/@session_output_tokens.
- context-usage colour coding: bright_black under 70%, yellow at 70%+,
  red at 85%+ (Static.update()'s `markup=True` default lets Rich markup
  tags like "[red]...[/red]" stand in for lipgloss styles -- Rich's
  "bright_black"/"yellow"/"red"/"white"/"cyan" color names match Ruby's
  ANSI_COLORS entries closely enough that no hex values are needed here).
- new "compaction" event: appends a notice line to the conversation log
  when the agent auto-compacts mid-turn.
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

CTX_WARN_PCT = 70
CTX_ALERT_PCT = 85


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
            # Real configured ceiling for THIS agent (from settings.yaml
            # via Repl.run_turn's max_iterations), not the Agent.MAX_ITERATIONS
            # class default -- a real bug found by code review (the progress
            # line always showed /25 regardless of the actual configured
            # value). Ported from the same fix applied to the Ruby source.
            max_from_event = event.get("max")
            if max_from_event is not None:
                self._live["max_iterations"] = int(max_from_event)
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
        elif phase == "compaction":
            dropped = event.get("dropped")
            log.write(f"[context compacted — {dropped} messages dropped to free space]")
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
            max_iterations = self._live["max_iterations"]
            bar.update(
                f"[cyan]{frame} {self._live['current_action']}  "
                f"(iter {iteration}/{max_iterations} · {secs}s · "
                f"↑ {itok} · ↓ {otok} · {calls} calls)[/cyan]"
            )
        else:
            pct = self._boukensha_context.usage_pct
            color = self._ctx_color(pct)
            used = self._fmt_tokens(self._boukensha_context.current_tokens)
            max_ = self._fmt_tokens(self._boukensha_context.context_window)
            turns = self._turn_count
            bar.update(f"[{color}]  [ready]   ctx {used} / {max_} ({pct}%)   {turns} turns[/{color}]")

    def _render_status(self) -> None:
        status = self.query_one("#status", Static)
        ver = self._repl.version or "?.?.?"
        model = self._repl.model or "(model)"
        pct = self._boukensha_context.usage_pct
        used = self._fmt_tokens(self._boukensha_context.current_tokens)
        max_ = self._fmt_tokens(self._boukensha_context.context_window)
        tools = self._boukensha_context.tool_count
        clock = time.strftime("%H:%M:%S")

        ctx_indicator = " ⚠ " if pct >= CTX_ALERT_PCT else " "
        bar = f" boukensha v{ver} · {model}  ·  ctx {used}/{max_} ({pct}%){ctx_indicator}·  {tools} tools  ·  {clock} "
        status.update(f"[white on bright_black]{bar}[/white on bright_black]")

    def _ctx_color(self, pct):
        if pct >= CTX_ALERT_PCT:
            return "red"
        if pct >= CTX_WARN_PCT:
            return "yellow"
        return "bright_black"

    def _fresh_live_state(self):
        return {
            "active": False,
            "spinner_idx": 0,
            "start_time": None,
            "elapsed": 0,
            "current_action": "idle",
            "iteration": 0,
            "max_iterations": Agent.MAX_ITERATIONS,
            "tool_call_count": 0,
            "turn_input_tokens": 0,
            "turn_output_tokens": 0,
        }

    def _fmt_tokens(self, n):
        n = int(n)
        return f"{round(n / 1000.0, 1)}k" if n >= 1000 else str(n)
