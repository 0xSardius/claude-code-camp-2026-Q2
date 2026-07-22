"""Port of week1_baseline/ruby/03_prompt_builder/examples/example.rb --
smoke test. Output should be equivalent to the Ruby version's when pointed
at the same .boukensha/settings.yaml (see docs/plans/python_port/03_prompt_builder).
"""
import json
import os
from pathlib import Path


def ruby_pretty_json(obj, depth=0):
    """Mirrors Ruby's JSON.pretty_generate exactly -- not just Python's
    json.dumps(indent=2). Two real divergences discovered while porting:

    1. Empty containers: Ruby emits ONE newline for an empty object
       (`{\\n}`) but TWO for an empty array (`[\\n\\n]`) -- a genuine,
       long-standing asymmetry in Ruby's json gem, confirmed empirically
       (`JSON.pretty_generate({})` vs `JSON.pretty_generate([])`).
       Python's json.dumps collapses both to a single line (`{}`/`[]`)
       regardless of indent, so it can't produce this by itself.
    2. Non-ASCII: Ruby's JSON.generate passes UTF-8 straight through by
       default; Python's json.dumps defaults to ensure_ascii=True (escaping
       to \\uXXXX). Matched here with ensure_ascii=False.

    Lives only here, not in the boukensha package, because Ruby doesn't
    define this in lib/boukensha either -- it's stdlib JSON.pretty_generate,
    called only from examples/example.rb.
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

from boukensha import (
    Anthropic,
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
    "look",
    description="Look around the current room for details",
    parameters={},
    block=lambda: "A damp stone corridor stretches north. Torches flicker on the walls.",
)

registry.tool(
    "move",
    description="Move the player in a direction (north, south, east, west, up, down)",
    parameters={"direction": {"type": "string", "description": "The direction to move"}},
    block=lambda direction: f"You move {direction} into a torch-lit corridor.",
)

ctx.add_message("user", "I just arrived in the dungeon. What's around me, and can you move north?")
ctx.add_message("assistant", "Let me take a look around first.")
ctx.add_message(
    "tool_result",
    "A damp stone corridor stretches north. Torches flicker on the walls.",
    tool_use_id="toolu_01X",
)

print("=== BOUKENSHA Step 3: Prompt Builder ===")
provider = Player.provider(player_settings)
model = Player.model(player_settings)

if provider == "anthropic":
    backend = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"], model=model)
elif provider == "ollama":
    backend = Ollama(model=model)
elif provider == "ollama_cloud":
    backend = OllamaCloud(api_key=os.environ["OLLAMA_API_KEY"], model=model)
elif provider == "openai":
    backend = OpenAI(api_key=os.environ["OPENAI_API_KEY"], model=model)
elif provider == "gemini":
    backend = Gemini(api_key=os.environ["GEMINI_API_KEY"], model=model)
else:
    raise ValueError(f"Unsupported provider for player task: {provider}")

builder = PromptBuilder(ctx, backend)

print()
print(f"Config: {config}")
print(f"Provider: {provider}")
print(f"Model: {model}")
print(ruby_pretty_json(builder.to_api_payload()))
