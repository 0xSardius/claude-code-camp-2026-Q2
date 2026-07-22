"""Port of week1_baseline/ruby/04_api_client/examples/example.rb.

Unlike prior steps, this one makes a REAL network call -- there's no tool
loop yet (that's step 5), so read_file/list_directory are registered but
never dispatched here; only their schemas end up in the request payload.
Output isn't byte-diffed against the Ruby version the way prior steps were:
a live API response has a fresh response ID and freshly-generated model
text every call. See docs/plans/python_port/04_api_client's acceptance-test
section for how parity was actually verified for this step.
"""
import json
import os
from pathlib import Path

from boukensha import (
    Anthropic,
    ApiError,
    Client,
    Config,
    Context,
    Gemini,
    Ollama,
    OllamaCloud,
    OpenAI,
    Player,
    PromptBuilder,
    Registry,
)


def ruby_pretty_json(obj, depth=0):
    """Mirrors Ruby's JSON.pretty_generate exactly -- see
    03_prompt_builder/examples/example.py for the full explanation (empty-
    container newline asymmetry + non-ASCII passthrough). Carried forward
    unchanged; still just for output-style consistency here, since the
    actual response content is non-deterministic and isn't byte-diffed for
    this step.
    """
    pad = "  " * depth
    child_pad = "  " * (depth + 1)
    if isinstance(obj, dict):
        if not obj:
            return "{\n" + pad + "}"
        lines = [f'{child_pad}{json.dumps(k)}: {ruby_pretty_json(v, depth + 1)}' for k, v in obj.items()]
        return "{\n" + ",\n".join(lines) + "\n" + pad + "}"
    if isinstance(obj, list):
        if not obj:
            return "[\n\n" + pad + "]"
        lines = [child_pad + ruby_pretty_json(v, depth + 1) for v in obj]
        return "[\n" + ",\n".join(lines) + "\n" + pad + "]"
    return json.dumps(obj, ensure_ascii=False)


def read_file(path):
    return Path(path).read_text()


def list_directory(path):
    return "\n".join(f for f in os.listdir(path) if not f.startswith("."))


# Same 4-.parent-hops-to-repo-root math as prior steps' example.py.
_here = Path(__file__).resolve().parent
os.environ.setdefault("BOUKENSHA_DIR", str(_here.parent.parent.parent.parent / ".boukensha"))

config = Config()
player_settings = config.tasks("player")
system_prompt = Player.system_prompt(
    player_settings,
    user_prompts_dir=config.user_prompts_dir,
    default_prompts_dir=Config.PROMPTS_DIR,
)

ctx = Context(task=Player, system=system_prompt)
registry = Registry(ctx)

registry.tool(
    "read_file",
    description="Read the contents of a file from disk",
    parameters={"path": {"type": "string", "description": "The file path to read"}},
    block=read_file,
)

registry.tool(
    "list_directory",
    description="List files in a directory",
    parameters={"path": {"type": "string", "description": "The directory path to list"}},
    block=list_directory,
)

ctx.add_message("user", "What files are in the current directory?")

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

print("=== BOUKENSHA Step 4: API Client ===")
print()
print(f"Config: {config}")
print(f"Provider: {provider}")
print(f"Model: {model}")
print(f"Sending request to {builder.url()}...")
print()

response = client.call()
print("Raw response:")
print(ruby_pretty_json(response))
