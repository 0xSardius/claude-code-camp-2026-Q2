"""Port of week1_baseline/ruby/06_the_logger/lib/boukensha.rb -- now
aggregates Config, Player (and transitively Base), Tool, Message, Context,
Registry, UnknownToolError, UnsupportedModelError, ApiError, PromptBuilder,
Client, Agent, Logger, and the five API backends, plus re-exports the
module-level singleton functions from _module_state (config(),
enable_debug(), is_debug(), enable_quiet(), disable_quiet(), is_quiet())
so the public call shape matches Ruby's Boukensha.config/Boukensha.debug!
exactly even though the implementation lives in its own file -- see
docs/plans/python_port/06_the_logger.
"""
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
from .errors import ApiError, UnknownToolError, UnsupportedModelError
from .logger import Logger
from .message import Message
from .prompt_builder import PromptBuilder
from .registry import Registry
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
    "PromptBuilder",
    "Client",
    "Agent",
    "Logger",
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
]
