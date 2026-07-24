"""Port of week1_baseline/ruby/10_standard_tool_library/examples/example.rb
(MUD demo).

Demonstrates boukensha.tools.mud, which registers gameplay tools against a
live CircleMUD connection. Connection credentials come from
~/.boukensha/settings.yaml (mud: host/port/username/password) by default.
Set BOUKENSHA_DIR to point at a different config directory.
"""
import os
from pathlib import Path

import boukensha

# Same 4-.parent-hops-to-repo-root math as prior steps' example.py.
_here = Path(__file__).resolve().parent
os.environ.setdefault("BOUKENSHA_DIR", str(_here.parent.parent.parent.parent / ".boukensha"))

cfg = boukensha.config()
print(f"Config: {cfg}")
print(f"API key set? {os.environ.get('ANTHROPIC_API_KEY') is not None}")
print()

boukensha.run(
    task=(
        "Connect to the MUD, look at your surroundings, check your score, "
        "then look at the available exits and tell me what you see."
    ),
    # system/model/api_key all come from config automatically
    working_dir=False,  # no filesystem tools needed for MUD play
    # mud: comes from config (settings.yaml mud: block) automatically
)
