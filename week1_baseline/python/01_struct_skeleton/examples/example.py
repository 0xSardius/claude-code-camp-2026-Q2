"""Port of week1_baseline/ruby/01_struct_skeleton/examples/example.rb --
smoke test. Output should be equivalent to the Ruby version's when pointed
at the same .boukensha/settings.yaml (see docs/plans/python_port/01_struct_skeleton).
"""
import os
from pathlib import Path

from boukensha import Config, Context, Player, Tool

# Same 4-.parent-hops-to-repo-root math as 00_config's example.py.
_here = Path(__file__).resolve().parent
os.environ.setdefault("BOUKENSHA_DIR", str(_here.parent.parent.parent.parent / ".boukensha"))

config = Config()
player_settings = config.tasks("player")
system_prompt = Player.system_prompt(player_settings, user_prompts_dir=config.user_prompts_dir)

ctx = Context(task=Player, system=system_prompt)

ctx.register_tool(
    Tool(
        "move",
        "Move the player in a direction (north, south, east, west, up, down)",
        {"direction": {"type": "string", "description": "The direction to move"}},
        lambda direction: f"You move {direction} into a torch-lit corridor.",
    )
)

ctx.add_message("user", "Explore north and tell me what you find.")
ctx.add_message("assistant", "Sure, let me head north and take a look.")

print("=== Boukensha Step 1: Struct Skeleton ===")
print()
print(f"Config:   {config}")
print(f"Context:  {ctx}")
print(f"Tool:     {ctx.tools['move']}")
print("Messages:")
for m in ctx.messages:
    print(f"  {m}")
