"""Port of week1_baseline/ruby/07_the_run_dsl/lib/boukensha.rb -- adds
`run()`, the top-level entry point that wires together Context, Registry,
a Backend, PromptBuilder, Client, Logger, and Agent so a caller only has
to describe *what* to do.

Ruby's `Boukensha.run(task: ...) do tool ... end` works via instance_eval
rebinding the block's `self` to a RunDSL, so `tool` reads as a bare call.
Python has no instance_eval/blocks equivalent -- the port uses an explicit
`setup` callback that receives the RunDSL object as its argument instead
(decided with the user 2026-07-23; see docs/plans/python_port/07_the_run_dsl
for the alternative considered and why this one was chosen).

`run()` lives directly here, not in its own file: every name it needs
(Agent, Client, Logger, Context, Registry, RunDSL, Player, Config, all
five backends, config()) is already imported below for re-export, so this
causes no new circular-import risk -- unlike _module_state.py, which
exists specifically to avoid one. This also mirrors Ruby's own structure
most closely: self.run lives in the same top-level boukensha.rb file as
the class list, not a separate file.
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
from .run_dsl import RunDSL
from .tasks.base import Base
from .tasks.player import Player
from .tool import Tool

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
