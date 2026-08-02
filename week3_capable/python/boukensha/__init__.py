"""Boukensha, week3.

FORKED from week2_observability/python on 2026-08-02, which was itself forked
from week1_baseline/python/12_context on 2026-07-27. The Ruby<->Python
mirror is RETIRED here: there is no Ruby counterpart to this tree and nothing
in it needs to stay in sync with week1_baseline/ruby/12_context. Week 1 is
frozen as a submitted artifact -- do not backport changes into it.

Every module below still opens with a "Port of week1_baseline/ruby/..."
docstring. Those are kept deliberately, as provenance: they record the
Ruby/Python semantic gaps and the decisions behind why this code looks the
way it does (see the gotchas list in the root CLAUDE.md and the per-step
plans in docs/plans/python_port/). Read them as history, not as an
obligation to mirror.

Week 3's plans live in docs/plans/week3/; week 2's in docs/plans/week2/.
Week 2 is a submitted artifact and stays frozen -- including its known
design debt. Retroactive fixes land HERE, not by editing what was handed in.

---

Port of week1_baseline/ruby/12_context/lib/boukensha.rb -- Tasks::Base/
Tasks::Player are gone in Ruby this step; Config absorbs their
responsibilities directly (system_prompt, model, provider_type,
agent_max_*), so run()/repl() resolve system/model/backend/limits
straight from Config instead of through a task class + task_settings
dict. context_window is now resolved via Models.context_window(model)
(models.py) and threaded into Context, Logger's snapshot, and passed
along wherever a backend needs to know it. Agent gains a second,
independent ceiling (max_turn_tokens) alongside max_iterations, resolved
from Config the same way. See docs/plans/python_port/12_context.

`repl()` shares almost all of `run()`'s setup logic (config/system/model/
backend/api_key resolution, RunDSL setup, backend construction, tool
registration) -- the only structural difference is building a Repl and
calling .start() instead of calling agent.run() once, plus catching
KeyboardInterrupt (Ruby's `rescue Interrupt`) around the outer call.
Deliberately NOT factored into a shared helper: Ruby doesn't share this
logic between self.run/self.repl either, and this project mirrors Ruby's
own duplication rather than deduplicate on its behalf -- same precedent as
week1_baseline/ruby's own steps duplicating code rather than sharing a
lib. See docs/plans/python_port/10_standard_tool_library.
"""
import os
import threading

from . import models
from ._module_state import config, disable_quiet, enable_debug, enable_quiet, is_debug, is_quiet
from .agent import Agent
from .backends.anthropic import Anthropic
from .backends.gemini import Gemini
from .backends.ollama import Ollama
from .backends.ollama_cloud import OllamaCloud
from .backends.openai import OpenAI
from .client import Client
from .config import Config
from .context import Context
from .driver import Driver, Policy
from .errors import ApiError, LoopError, TurnInterrupted, UnknownToolError, UnsupportedModelError
from .logger import Logger
from .memory import Memory
from . import memory_hooks as _memory_hooks
from .hooks import Hook, HookPayload, Hooks
from .message import Message
from .prompt_builder import PromptBuilder
from .registry import Registry
from .repl import Repl
from .run_dsl import RunDSL
from .tool import Tool
from .tools import file_system as _file_system_tools
from .tools import memory as _memory_tools
from .tools import mud as _mud_tools
from .tools import shell as _shell_tools
from .version import VERSION

__all__ = [
    "Config",
    "Tool",
    "Message",
    "Context",
    "Registry",
    "UnknownToolError",
    "UnsupportedModelError",
    "ApiError",
    "LoopError",
    "TurnInterrupted",
    "PromptBuilder",
    "Client",
    "Agent",
    "Driver",
    "Policy",
    "Hook",
    "Hooks",
    "HookPayload",
    "Logger",
    "Memory",
    "RunDSL",
    "Repl",
    "VERSION",
    "Anthropic",
    "Gemini",
    "Ollama",
    "OllamaCloud",
    "OpenAI",
    "models",
    "config",
    "enable_debug",
    "is_debug",
    "enable_quiet",
    "disable_quiet",
    "is_quiet",
    "run",
    "repl",
]


def _mud_opts_from_config(cfg):
    """Build a mud options dict from config (used when mud=None is passed
    to run()/repl()). Returns None if no MUD host is configured. Ruby:
    self.mud_opts_from_config, private_class_method -- Python has no
    method-level privacy, leading underscore is this codebase's existing
    convention for "internal helper."
    """
    if not cfg.mud_host or not cfg.mud_username:
        return None
    return {
        "host": cfg.mud_host,
        "port": cfg.mud_port,
        "name": cfg.mud_username,
        "password": cfg.mud_password,
    }


def run(
    *,
    task,
    system=None,
    model=None,
    backend=None,
    api_key=None,
    ollama_host="http://localhost:11434",
    log=None,
    context_window=None,
    max_output_tokens=None,
    working_dir=None,
    allowed_commands=None,
    shell_timeout=30,
    mud=None,
    setup=None,
    hooks=None,
    memory=None,
):
    # working_dir defaults to the current directory (Ruby: working_dir:
    # Dir.pwd), not None -- os.getcwd() evaluated at CALL time via the
    # default below matches Ruby's Dir.pwd-evaluated-per-call semantics
    # (Python function defaults are evaluated once at def-time, so a bare
    # `working_dir=os.getcwd()` in the signature would be wrong -- same
    # class of gotcha as 06_the_logger's Logger.new default; resolved the
    # same way, with None-as-sentinel plus an explicit call inside the body).
    if working_dir is None:
        working_dir = os.getcwd()

    cfg = config()  # loads .env; populates os.environ
    if system is None:
        system = cfg.system_prompt
    if model is None:
        model = cfg.model
    if context_window is None:
        context_window = models.context_window(model)
    if backend is None:
        backend = cfg.provider_type
    if api_key is None:
        api_key = {
            "anthropic": os.environ.get("ANTHROPIC_API_KEY"),
            "openai": os.environ.get("OPENAI_API_KEY"),
            "gemini": os.environ.get("GEMINI_API_KEY"),
            "ollama_cloud": os.environ.get("OLLAMA_API_KEY"),
        }.get(backend)

    ctx = Context(
        system=system,
        context_window=context_window,
        working_dir=working_dir,
        compaction_threshold=cfg.agent_compaction_threshold(),
    )
    registry = Registry(ctx)

    # Ruby: `if working_dir` -- a deliberate truthy check (working_dir:
    # false is the explicit opt-out sentinel; see context.py's dedicated
    # note on why a bare Python `if working_dir:` is correct here, not a
    # bug to fix with `is not None`).
    if working_dir:
        _file_system_tools.register(registry, working_dir=working_dir)
        _shell_tools.register(registry, working_dir=working_dir, timeout=shell_timeout, allowed_commands=allowed_commands)

    # mud=None means "use config if host is set"; mud=False means "skip
    # entirely" -- Ruby: `mud == false ? nil : (mud || mud_opts_from_config(cfg))`.
    # `is not None`, not `or`, for the same reason as every other Ruby-
    # truthy-vs-Python-falsy translation in this codebase (an explicit
    # mud={} is truthy in Ruby but falsy in Python).
    resolved_mud = None if mud is False else (mud if mud is not None else _mud_opts_from_config(cfg))
    if resolved_mud:
        _mud_tools.register(registry, **resolved_mud)

    # Per-character memory (week2). Enabled automatically whenever a MUD
    # character is configured -- an agent that plays but forgets is the gap
    # week1's live playtest ran into. memory=False opts out; a string names a
    # different character; a Memory instance is used as-is.
    mem = None
    if memory is not False:
        if isinstance(memory, Memory):
            mem = memory
        else:
            char = memory if isinstance(memory, str) else (resolved_mud or {}).get("name")
            if char:
                mem = Memory(char)
    if mem is not None:
        _memory_tools.register(registry, memory=mem)
        if hooks is None:
            hooks = Hooks()
        _memory_hooks.install(hooks, mem, registry=registry)

    if setup is not None:
        setup(RunDSL(registry))

    if backend == "anthropic":
        be = Anthropic(api_key=api_key, model=model, cache=cfg.agent_prompt_caching())
    elif backend == "openai":
        be = OpenAI(api_key=api_key, model=model)
    elif backend == "gemini":
        be = Gemini(api_key=api_key, model=model)
    elif backend == "ollama":
        be = Ollama(host=ollama_host, model=model)
    elif backend == "ollama_cloud":
        be = OllamaCloud(api_key=api_key, model=model)
    else:
        raise ValueError(
            f"Unknown backend {backend!r}. Use 'anthropic', 'openai', 'gemini', 'ollama', or 'ollama_cloud'."
        )

    builder = PromptBuilder(ctx, be)
    client = Client(builder)
    effective_max_iterations = cfg.agent_max_iterations()
    effective_max_turn_tokens = cfg.agent_max_turn_tokens()
    effective_max_output_tokens = (
        max_output_tokens if max_output_tokens is not None else cfg.agent_max_output_tokens()
    )

    # Ruby's `ensure`/`logger&.close` wraps the whole method; this only
    # wraps from Logger construction onward -- behaviorally identical,
    # since nothing before this point ever has a logger open to clean up.
    # logger=None first so the finally clause never hits an unbound name.
    logger = None
    try:
        logger = Logger(
            log=log,
            snapshot={
                "max_iterations": effective_max_iterations,
                "max_turn_tokens": effective_max_turn_tokens,
                "max_output_tokens": effective_max_output_tokens,
                "context_window": context_window,
                "model": model,
                "provider": backend,
            },
        )
        agent = Agent(
            context=ctx,
            registry=registry,
            builder=builder,
            client=client,
            logger=logger,
            max_iterations=effective_max_iterations,
            max_turn_tokens=effective_max_turn_tokens,
            max_output_tokens=effective_max_output_tokens,
            hooks=hooks,
        )

        ctx.add_message("user", task)
        return agent.run()
    finally:
        if logger is not None:
            logger.close()


def repl(
    *,
    system=None,
    model=None,
    backend=None,
    api_key=None,
    ollama_host="http://localhost:11434",
    log=None,
    context_window=None,
    max_output_tokens=None,
    working_dir=None,
    allowed_commands=None,
    shell_timeout=30,
    mud=None,
    tui=True,
    setup=None,
    hooks=None,
    memory=None,
):
    # See run()'s matching comment: working_dir defaults to cwd
    # (call-time, not def-time -- the same Ruby-fresh-default-per-call
    # gotcha as 06_the_logger's Logger.new).
    if working_dir is None:
        working_dir = os.getcwd()

    # Ruby's `rescue Interrupt`/`ensure` are method-level, covering the
    # WHOLE method body starting at `cfg = config` -- a single flat
    # try/except/finally here (not a narrower nested try around just the
    # Logger/Repl construction) matches that exactly, including Ctrl-C
    # during config loading or a user-supplied `setup` callback. Python's
    # own except-then-finally ordering (within one try statement) matches
    # Ruby's rescue-then-ensure ordering too. logger=None before the try
    # so finally never hits an unbound name if an early exception fires
    # before Logger() is ever constructed.
    logger = None
    try:
        cfg = config()  # loads .env; populates os.environ
        if system is None:
            system = cfg.system_prompt
        if model is None:
            model = cfg.model
        if context_window is None:
            context_window = models.context_window(model)
        if backend is None:
            backend = cfg.provider_type
        if api_key is None:
            api_key = {
                "anthropic": os.environ.get("ANTHROPIC_API_KEY"),
                "openai": os.environ.get("OPENAI_API_KEY"),
                "gemini": os.environ.get("GEMINI_API_KEY"),
                "ollama_cloud": os.environ.get("OLLAMA_API_KEY"),
            }.get(backend)

        ctx = Context(
            system=system,
            context_window=context_window,
            working_dir=working_dir,
            compaction_threshold=cfg.agent_compaction_threshold(),
        )
        registry = Registry(ctx)

        if working_dir:
            _file_system_tools.register(registry, working_dir=working_dir)
            _shell_tools.register(registry, working_dir=working_dir, timeout=shell_timeout, allowed_commands=allowed_commands)

        # See run()'s matching comment: `mud if mud is not None else ...`,
        # not `mud or ...` -- an explicit mud={} is truthy in Ruby (kept
        # as-is) but falsy in Python.
        resolved_mud = None if mud is False else (mud if mud is not None else _mud_opts_from_config(cfg))
        if resolved_mud:
            _mud_tools.register(registry, **resolved_mud)

        # Per-character memory (week2). Enabled automatically whenever a MUD
        # character is configured -- an agent that plays but forgets is the gap
        # week1's live playtest ran into. memory=False opts out; a string names a
        # different character; a Memory instance is used as-is.
        mem = None
        if memory is not False:
            if isinstance(memory, Memory):
                mem = memory
            else:
                char = memory if isinstance(memory, str) else (resolved_mud or {}).get("name")
                if char:
                    mem = Memory(char)
        if mem is not None:
            _memory_tools.register(registry, memory=mem)
            if hooks is None:
                hooks = Hooks()
            _memory_hooks.install(hooks, mem, registry=registry)

        if setup is not None:
            setup(RunDSL(registry))

        if backend == "anthropic":
            be = Anthropic(api_key=api_key, model=model, cache=cfg.agent_prompt_caching())
        elif backend == "openai":
            be = OpenAI(api_key=api_key, model=model)
        elif backend == "gemini":
            be = Gemini(api_key=api_key, model=model)
        elif backend == "ollama":
            be = Ollama(host=ollama_host, model=model)
        elif backend == "ollama_cloud":
            be = OllamaCloud(api_key=api_key, model=model)
        else:
            raise ValueError(
                f"Unknown backend {backend!r}. Use 'anthropic', 'openai', 'gemini', 'ollama', or 'ollama_cloud'."
            )

        builder = PromptBuilder(ctx, be)
        client = Client(builder)
        effective_max_iterations = cfg.agent_max_iterations()
        effective_max_turn_tokens = cfg.agent_max_turn_tokens()
        effective_max_output_tokens = (
            max_output_tokens if max_output_tokens is not None else cfg.agent_max_output_tokens()
        )

        logger = Logger(
            log=log,
            snapshot={
                "max_iterations": effective_max_iterations,
                "max_turn_tokens": effective_max_turn_tokens,
                "max_output_tokens": effective_max_output_tokens,
                "context_window": context_window,
                "model": model,
                "provider": backend,
            },
        )

        # Only constructed when tui=True -- the plain REPL path never
        # touches threading.Event, matching Ruby's `if tui && defined?(Tui)`
        # guard (no Interrupt-injection plumbing needed for the non-TUI
        # case). See agent.py's module docstring for why this exists at
        # all (Ruby's Thread#raise(Interrupt) has no safe Python
        # equivalent).
        interrupt_event = threading.Event() if tui else None

        repl_obj = Repl(
            context=ctx,
            registry=registry,
            builder=builder,
            client=client,
            logger=logger,
            max_iterations=effective_max_iterations,
            max_turn_tokens=effective_max_turn_tokens,
            max_output_tokens=effective_max_output_tokens,
            config_dir=cfg.dir,
            provider=backend,
            model=model,
            version=VERSION,
            api_key=api_key,
            mud=resolved_mud,
            interrupt_event=interrupt_event,
            hooks=hooks,
        )

        if tui:
            from .tui import Tui  # inline import -- non-TUI callers never pay Textual's import cost

            Tui(repl_obj, interrupt_event).run()
        else:
            repl_obj.start()
    except KeyboardInterrupt:
        print("\nInterrupted.")
    finally:
        if logger is not None:
            logger.close()
