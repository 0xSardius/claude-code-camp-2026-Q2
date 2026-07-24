"""Port of week1_baseline/ruby/07_the_run_dsl/examples/example.rb.

Makes real, multi-turn API calls via boukensha.run() -- output isn't
byte-diffed against the Ruby version (non-deterministic tool-call sequence
and final wording). See docs/plans/python_port/07_the_run_dsl's
acceptance-test section.
"""
import os
from pathlib import Path

import boukensha

# Same 4-.parent-hops-to-repo-root math as prior steps' example.py.
_here = Path(__file__).resolve().parent
os.environ.setdefault("BOUKENSHA_DIR", str(_here.parent.parent.parent.parent / ".boukensha"))
base_dir = _here.parent

print("=== BOUKENSHA Step 7: The Boukensha.run DSL ===")
print()
print(f"Config: {boukensha.config()}")
print()


def read_file(path):
    return (base_dir / path).resolve().read_text()


def list_directory(path):
    target = (base_dir / path).resolve()
    return ", ".join(f for f in os.listdir(target) if not f.startswith("."))


def setup(dsl):
    dsl.tool(
        "read_file",
        description="Read the contents of a file from disk",
        parameters={"path": {"type": "string", "description": "The file path to read"}},
        block=read_file,
    )
    dsl.tool(
        "list_directory",
        description="List the files in a directory",
        parameters={"path": {"type": "string", "description": "The directory path to list"}},
        block=list_directory,
    )


result = boukensha.run(
    task="Read the README.md file and summarise what this MUD player assistant framework can do.",
    setup=setup,
)

print()
print("=== FINAL RESPONSE ===")
print(result)
