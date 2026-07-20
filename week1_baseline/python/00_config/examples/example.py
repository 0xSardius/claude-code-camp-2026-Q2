"""Port of week1_baseline/ruby/00_config/examples/example.rb -- smoke test /
diagnostic script. Output should be equivalent to the Ruby version's when
pointed at the same .boukensha/settings.yaml (see docs/plans/python_port/00_config,
milestone 6 -- this equivalence is the acceptance test for the port).
"""
import os
from pathlib import Path

from boukensha import Config, Player

# Override the config directory so the example works from the repo root.
# In real usage a user's ~/.boukensha is picked up automatically.
# _here == examples/ dir, the same reference point as Ruby's __dir__; 4
# .parent hops up from there reaches the repo root, same as Ruby's 4 "../".
_here = Path(__file__).resolve().parent
os.environ.setdefault("BOUKENSHA_DIR", str(_here.parent.parent.parent.parent / ".boukensha"))

config = Config()
player_settings = config.tasks("player")

print("=== Boukensha Step 0: Configuration ===")
print()
print(f"Config dir:     {config.dir}")
print(f"Tasks:          {', '.join(config.tasks().keys())}")
print()
print("-- player task --")
print(f"Provider:       {Player.provider(player_settings)}")
print(f"Model:          {Player.model(player_settings)}")
print(f"Prompt override?{str(Player.prompt_override(player_settings, 'system')).lower()}")
system_prompt = Player.system_prompt(
    player_settings,
    user_prompts_dir=config.user_prompts_dir,
    default_prompts_dir=Config.PROMPTS_DIR,
)
print(f"System prompt:  {(system_prompt or '')[:60]}...")
print()
print(f"MUD host:       {config.mud_host}:{config.mud_port}")
print(f"MUD user:       {config.mud_username}")
print()
print(f"API key set?    {str(os.environ.get('ANTHROPIC_API_KEY') is not None).lower()}")
print()
print(config)
