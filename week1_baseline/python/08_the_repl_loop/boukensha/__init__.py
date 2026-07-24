"""Port of week1_baseline/ruby/08_the_repl_loop/lib/boukensha.rb -- adds
`repl()`, the interactive counterpart to `run()`.

`repl()` shares almost all of `run()`'s setup logic (config/system/model/
backend/api_key resolution, RunDSL setup, backend construction) -- the
only structural difference is building a Repl and calling .start() instead
of calling agent.run() once, plus catching KeyboardInterrupt (Ruby's
`rescue Interrupt`) around the outer call. Deliberately NOT factored into
a shared helper: Ruby doesn't share this logic between self.run/self.repl
either (confirmed near-total duplication between the two Ruby methods),
and this project mirrors Ruby's own duplication rather than deduplicate on
its behalf -- same precedent as week1_baseline/ruby's own steps
duplicating code rather than sharing a lib. See
docs/plans/python_port/08_the_repl_loop.
"""
import os

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
from .errors import ApiError, LoopError, UnknownToolError, UnsupportedModelError
from .logger import Logger
from .message import Message
from .prompt_builder import PromptBuilder
from .registry import Registry
from .repl import Repl
from .run_dsl import RunDSL
from .tasks.base import Base
from .tasks.player import Player
from .tool import Tool
from .version import VERSION

__all__ = [
    "Config",
    "Base",
    "Player",
    "Tool",
    "Message",
    "Context",
    "Registry",
    "UnknownToolError",
    "UnsupportedModelError",
    "ApiError",
    "LoopError",
    "PromptBuilder",
    "Client",
    "Agent",
    "Logger",
    "RunDSL",
    "Repl",
    "VERSION",
    "Anthropic",
    "Gemini",
    "Ollama",
    "OllamaCloud",
    "OpenAI",
    "config",
    "enable_debug",
    "is_debug",
    "enable_quiet",
    "disable_quiet",
    "is_quiet",
    "run",
    "repl",
]


def run(
    *,
    task,
    system=None,
    model=None,
    backend=None,
    api_key=None,
    ollama_host="http://localhost:11434",
    log=None,
    max_output_tokens=None,
    setup=None,
):
    cfg = config()  # loads .env; populates os.environ
    task_class = Player
    task_settings = cfg.tasks(task_class.task_name())

    if system is None:
        system = task_class.system_prompt(
            task_settings, user_prompts_dir=cfg.user_prompts_dir, default_prompts_dir=Config.PROMPTS_DIR
        )
    if model is None:
        model = task_class.model(task_settings)
    if backend is None:
        # Ruby: task_class.provider(task_settings).to_sym -- Player.provider
        # already returns a plain string here, there's no symbol to convert
        # to (Python has no symbol type; backend is just a string throughout).
        backend = task_class.provider(task_settings)
    if api_key is None:
        api_key = {
            "anthropic": os.environ.get("ANTHROPIC_API_KEY"),
            "openai": os.environ.get("OPENAI_API_KEY"),
            "gemini": os.environ.get("GEMINI_API_KEY"),
            "ollama_cloud": os.environ.get("OLLAMA_API_KEY"),
        }.get(backend)

    ctx = Context(task=task_class, system=system)
    registry = Registry(ctx)

    if setup is not None:
        setup(RunDSL(registry))

    if backend == "anthropic":
        be = Anthropic(api_key=api_key, model=model)
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
    effective_max_iterations = task_class.max_iterations(task_settings)
    effective_max_output_tokens = (
        max_output_tokens if max_output_tokens is not None else task_class.max_output_tokens(task_settings)
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
                "task": task_class.task_name(),
                "max_iterations": effective_max_iterations,
                "max_output_tokens": effective_max_output_tokens,
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
            task_settings=task_settings,
            max_iterations=effective_max_iterations,
            max_output_tokens=effective_max_output_tokens,
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
    max_output_tokens=None,
    setup=None,
):
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
        task_class = Player
        task_settings = cfg.tasks(task_class.task_name())

        if system is None:
            system = task_class.system_prompt(
                task_settings, user_prompts_dir=cfg.user_prompts_dir, default_prompts_dir=Config.PROMPTS_DIR
            )
        if model is None:
            model = task_class.model(task_settings)
        if backend is None:
            backend = task_class.provider(task_settings)
        if api_key is None:
            api_key = {
                "anthropic": os.environ.get("ANTHROPIC_API_KEY"),
                "openai": os.environ.get("OPENAI_API_KEY"),
                "gemini": os.environ.get("GEMINI_API_KEY"),
                "ollama_cloud": os.environ.get("OLLAMA_API_KEY"),
            }.get(backend)

        ctx = Context(task=task_class, system=system)
        registry = Registry(ctx)

        if setup is not None:
            setup(RunDSL(registry))

        if backend == "anthropic":
            be = Anthropic(api_key=api_key, model=model)
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
        effective_max_iterations = task_class.max_iterations(task_settings)
        effective_max_output_tokens = (
            max_output_tokens if max_output_tokens is not None else task_class.max_output_tokens(task_settings)
        )

        logger = Logger(
            log=log,
            snapshot={
                "task": task_class.task_name(),
                "max_iterations": effective_max_iterations,
                "max_output_tokens": effective_max_output_tokens,
                "model": model,
                "provider": backend,
            },
        )
        Repl(
            context=ctx,
            registry=registry,
            builder=builder,
            client=client,
            logger=logger,
            task_settings=task_settings,
            max_iterations=effective_max_iterations,
            max_output_tokens=effective_max_output_tokens,
            config_dir=cfg.dir,
            provider=backend,
            model=model,
            version=VERSION,
            api_key=api_key,
        ).start()
    except KeyboardInterrupt:
        print("\nInterrupted.")
    finally:
        if logger is not None:
            logger.close()
