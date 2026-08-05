"""A long-lived agent with no human at the keyboard (week3).

`boukensha.run()` does one turn and tears everything down. `Repl` does many
turns, but only ever driven by someone typing. Week 3 needs the third case:
many turns, driven by code -- which is what an unattended agent IS.

    h = Harness.build(mud={...}, memory="dummy", log="grind.jsonl")
    driver = h.driver(goal="reach level 5")
    result = driver.run(max_cycles=40)
    h.close()

WHY ONE HARNESS AND NOT A LOOP AROUND run(). Calling run() forty times would
build forty conversations, forty memory-hook objects and forty loggers. Three
things break at once:

  the cache      every turn would re-send an uncached prompt. Week 2 measured
                 the prefix at ~11.5k tokens; paying full price for it forty
                 times is most of the run's cost.
  position       MemoryHooks tracks where the character is as a per-process
                 belief (see its docstring on why it distrusts a stored one).
                 A fresh object each turn means a real `look` every turn.
  continuity     the agent would have no idea what it just tried.

FRESH AGENT, SHARED EVERYTHING ELSE -- copied from Repl.run_turn deliberately.
Agent counts iterations per instance and never resets the counter, so reusing
one across turns would have turn 2 start already at its limit. Context,
registry, hooks, memory and logger are all constructed once and handed to each
Agent, because handler state that must survive across turns (the position
belief, cumulative spend, the stall counter) cannot live on an object that is
thrown away every turn.
"""
from __future__ import annotations

import os

from . import models
from ._module_state import config
from .agent import Agent
from .backends.anthropic import Anthropic
from .backends.gemini import Gemini
from .backends.ollama import Ollama
from .backends.ollama_cloud import OllamaCloud
from .backends.openai import OpenAI
from .client import Client
from .context import Context
from .driver import Driver
from .errors import ApiError, LoopError
from .hooks import Hooks
from .logger import Logger
from .memory import Memory
from . import memory_hooks as _memory_hooks
from .prompt_builder import PromptBuilder
from .registry import Registry
from .run_dsl import RunDSL
from .tools import file_system as _file_system_tools
from .tools import memory as _memory_tools
from .tools import mud as _mud_tools
from .tools import shell as _shell_tools


def _backend(name, *, api_key, model, ollama_host, cache):
    if name == "anthropic":
        return Anthropic(api_key=api_key, model=model, cache=cache)
    if name == "openai":
        return OpenAI(api_key=api_key, model=model)
    if name == "gemini":
        return Gemini(api_key=api_key, model=model)
    if name == "ollama":
        return Ollama(host=ollama_host, model=model)
    if name == "ollama_cloud":
        return OllamaCloud(api_key=api_key, model=model)
    raise ValueError(
        f"Unknown backend {name!r}. Use 'anthropic', 'openai', 'gemini', 'ollama', or 'ollama_cloud'."
    )


def _mud_opts_from_config(cfg):
    if not cfg.mud_host or not cfg.mud_username:
        return None
    return {
        "host": cfg.mud_host,
        "port": cfg.mud_port,
        "name": cfg.mud_username,
        "password": cfg.mud_password,
    }


class Harness:
    def __init__(self, *, context, registry, builder, client, logger, hooks,
                 memory=None, max_iterations=None, max_turn_tokens=None,
                 max_output_tokens=None, model=None):
        self.context = context
        self.registry = registry
        self.logger = logger
        self.hooks = hooks
        self.memory = memory
        self.model = model
        self._builder = builder
        self._client = client
        self._max_iterations = max_iterations
        self._max_turn_tokens = max_turn_tokens
        self._max_output_tokens = max_output_tokens
        self._turn = 0

    # ---- construction ----------------------------------------------------

    @classmethod
    def build(cls, *, system=None, model=None, backend=None, api_key=None,
              ollama_host="http://localhost:11434", log=None, context_window=None,
              max_output_tokens=None, working_dir=None, allowed_commands=None,
              shell_timeout=30, mud=None, setup=None, hooks=None, memory=None):
        """Assemble the whole stack. Same options as boukensha.run()."""
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

        # `if working_dir` is a deliberate truthy check: working_dir=False is
        # the explicit opt-out sentinel. Same everywhere in this codebase.
        if working_dir:
            _file_system_tools.register(registry, working_dir=working_dir)
            _shell_tools.register(registry, working_dir=working_dir,
                                  timeout=shell_timeout, allowed_commands=allowed_commands)

        # mud=None means "use config if a host is set"; mud=False means "skip".
        # `is not None`, not `or` -- an explicit mud={} is falsy in Python.
        resolved_mud = None if mud is False else (mud if mud is not None else _mud_opts_from_config(cfg))
        if resolved_mud:
            _mud_tools.register(registry, **resolved_mud)

        mem = None
        if memory is not False:
            if isinstance(memory, Memory):
                mem = memory
            else:
                char = memory if isinstance(memory, str) else (resolved_mud or {}).get("name")
                if char:
                    mem = Memory(char)
        if hooks is None:
            hooks = Hooks()
        if mem is not None:
            _memory_tools.register(registry, memory=mem)
            _memory_hooks.install(hooks, mem, registry=registry)

        if setup is not None:
            setup(RunDSL(registry))

        be = _backend(backend, api_key=api_key, model=model,
                      ollama_host=ollama_host, cache=cfg.agent_prompt_caching())
        builder = PromptBuilder(ctx, be)
        client = Client(builder)

        max_iterations = cfg.agent_max_iterations()
        max_turn_tokens = cfg.agent_max_turn_tokens()
        effective_max_output = (
            max_output_tokens if max_output_tokens is not None else cfg.agent_max_output_tokens()
        )

        logger = Logger(
            log=log,
            snapshot={
                "max_iterations": max_iterations,
                "max_turn_tokens": max_turn_tokens,
                "max_output_tokens": effective_max_output,
                "context_window": context_window,
                "model": model,
                "provider": backend,
            },
        )

        return cls(
            context=ctx, registry=registry, builder=builder, client=client,
            logger=logger, hooks=hooks, memory=mem, model=model,
            max_iterations=max_iterations, max_turn_tokens=max_turn_tokens,
            max_output_tokens=effective_max_output,
        )

    # ---- driving ---------------------------------------------------------

    def start_turn(self, task):
        """Log the turn, queue the task, and hand back an Agent ready to run.

        Split out from run_turn so a one-shot caller (boukensha.run) can share
        this exact wiring while still letting an exception propagate, which is
        the right behaviour when there is no loop to keep going.
        """
        self._turn += 1
        self.logger.turn(n=self._turn)
        self.context.add_message("user", task)
        return Agent(
            context=self.context,
            registry=self.registry,
            builder=self._builder,
            client=self._client,
            logger=self.logger,
            max_iterations=self._max_iterations,
            max_turn_tokens=self._max_turn_tokens,
            max_output_tokens=self._max_output_tokens,
            hooks=self.hooks,
        )

    def run_turn(self, task):
        """One user input plus the complete agent run needed to answer it.

        Returns the agent's final text. A LoopError or ApiError is returned as
        a string rather than raised: this is called from an unattended loop,
        and one failed turn out of forty must not end the run. The driver
        reads the return value; it does not parse it, so an error string
        simply becomes a cycle that made no progress -- which is exactly what
        it was.
        """
        try:
            return self.start_turn(task).run()
        except (LoopError, ApiError) as e:
            return f"[error] {type(e).__name__}: {e}"

    def driver(self, *, goal, policy=None, task=None):
        """A Driver wired to this harness. Needs memory -- the driver assesses
        state by reading it, so a harness built with memory=False has nothing
        to decide from."""
        if self.memory is None:
            raise ValueError("driver() needs memory; build the harness with memory=<character>")
        d = Driver(goal=goal, memory=self.memory, registry=self.registry,
                   run_turn=self.run_turn, policy=policy, logger=self.logger,
                   hooks=self.hooks, task=task)
        # The driver's mechanical routines become tools the model can call, so
        # a whole fight costs one model call instead of one per swing.
        return d.install_tools()

    # ---- teardown --------------------------------------------------------

    def close(self):
        if self.logger is not None:
            self.logger.close()
        try:
            self.registry.dispatch("mud_disconnect", {})
        except Exception:  # noqa: BLE001 -- already gone, or no MUD registered
            pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
        return False
