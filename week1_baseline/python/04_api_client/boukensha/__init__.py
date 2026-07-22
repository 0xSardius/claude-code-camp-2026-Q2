"""Port of week1_baseline/ruby/04_api_client/lib/boukensha.rb -- now
aggregates Config, Player (and transitively Base), Tool, Message, Context,
Registry, UnknownToolError, UnsupportedModelError, ApiError, PromptBuilder,
Client, and the five API backends.
"""
from .backends.anthropic import Anthropic
from .backends.gemini import Gemini
from .backends.ollama import Ollama
from .backends.ollama_cloud import OllamaCloud
from .backends.openai import OpenAI
from .client import Client
from .config import Config
from .context import Context
from .errors import ApiError, UnknownToolError, UnsupportedModelError
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
    "Anthropic",
    "Gemini",
    "Ollama",
    "OllamaCloud",
    "OpenAI",
]
