"""Port of week1_baseline/ruby/06_the_logger/examples/example.rb.

Makes real, multi-turn API calls -- output isn't byte-diffed against the
Ruby version (the model's tool-call sequence and final wording are
non-deterministic). See docs/plans/python_port/06_the_logger's
acceptance-test section for how parity was actually verified for this
step. Agent itself no longer prints per-iteration/tool-call lines --
that detail moved to the structured JSONL log (.boukensha/sessions/) --
so this script's own stdout stays limited to the config summary and final
response, matching the live Ruby run's observed output.
"""
import os
from pathlib import Path

from boukensha import (
    Agent,
    Anthropic,
    Client,
    Config,
    Context,
    Gemini,
    Logger,
    Ollama,
    OllamaCloud,
    OpenAI,
    Player,
    PromptBuilder,
    Registry,
)

# Same 4-.parent-hops-to-repo-root math as prior steps' example.py.
_here = Path(__file__).resolve().parent
os.environ.setdefault("BOUKENSHA_DIR", str(_here.parent.parent.parent.parent / ".boukensha"))
base_dir = _here.parent

config = Config()
player_settings = config.tasks("player")
system_prompt = Player.system_prompt(
    player_settings,
    user_prompts_dir=config.user_prompts_dir,
    default_prompts_dir=Config.PROMPTS_DIR,
)

ctx = Context(task=Player, system=system_prompt)
registry = Registry(ctx)

provider = Player.provider(player_settings)
model = Player.model(player_settings)

if provider == "anthropic":
    backend = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"], model=model)
elif provider == "openai":
    backend = OpenAI(api_key=os.environ["OPENAI_API_KEY"], model=model)
elif provider == "gemini":
    backend = Gemini(api_key=os.environ["GEMINI_API_KEY"], model=model)
elif provider == "ollama":
    backend = Ollama(model=model)
elif provider == "ollama_cloud":
    backend = OllamaCloud(api_key=os.environ["OLLAMA_API_KEY"], model=model)
else:
    raise ValueError(f"Unsupported provider for player task: {provider}")

builder = PromptBuilder(ctx, backend)
client = Client(builder)
# Writes structured JSONL events to .boukensha/sessions/<session-id>.jsonl.
# Call boukensha.enable_debug() before agent.run() to include the full raw
# API response in those lines.
logger = Logger()
agent = Agent(
    context=ctx,
    registry=registry,
    builder=builder,
    client=client,
    logger=logger,
    task_settings=player_settings,
)


def read_file(path):
    return (base_dir / path).resolve().read_text()


def list_directory(path):
    target = (base_dir / path).resolve()
    return ", ".join(f for f in os.listdir(target) if not f.startswith("."))


registry.tool(
    "read_file",
    description="Read the contents of a file from disk",
    parameters={"path": {"type": "string", "description": "The file path to read"}},
    block=read_file,
)

registry.tool(
    "list_directory",
    description="List the files in a directory",
    parameters={"path": {"type": "string", "description": "The directory path to list"}},
    block=list_directory,
)

ctx.add_message("user", "Read the README.md file and summarise what this MUD player assistant framework can do.")

print("=== BOUKENSHA Step 6: The Logger ===")
print()
print(f"Config: {config}")
print(f"Provider: {provider}")
print(f"Model: {model}")
print(f"Max iterations: {Player.max_iterations(player_settings)}")
print(f"Max output tokens: {Player.max_output_tokens(player_settings)}")
print()

result = agent.run()

print()
print("=== FINAL RESPONSE ===")
print(result)
