"""Port of week1_baseline/ruby/08_the_repl_loop/examples/example.rb.

Interactive: boukensha.repl() reads tasks from stdin in a loop. For
scripted/non-interactive verification, pipe input followed by /exit --
see docs/plans/python_port/08_the_repl_loop's acceptance-test section.
"""
import os
from pathlib import Path

import boukensha

# Same 4-.parent-hops-to-repo-root math as prior steps' example.py.
_here = Path(__file__).resolve().parent
os.environ.setdefault("BOUKENSHA_DIR", str(_here.parent.parent.parent.parent / ".boukensha"))

print(f"Config: {boukensha.config()}")
print()

# The step 7 (07_the_run_dsl) folder makes a good playground -- it already
# has source files to read.
base_dir = (_here.parent.parent / "07_the_run_dsl").resolve()


def read_file(path):
    return (base_dir / path).resolve().read_text()


def list_directory(path):
    target = (base_dir / path).resolve()
    return ", ".join(sorted(f for f in os.listdir(target) if not f.startswith(".")))


def setup(dsl):
    dsl.tool(
        "read_file",
        description="Read the contents of a file from disk",
        parameters={"path": {"type": "string", "description": "File path (relative to the working directory)"}},
        block=read_file,
    )
    dsl.tool(
        "list_directory",
        description="List the files in a directory",
        parameters={
            "path": {
                "type": "string",
                "description": "Directory path (relative to the working directory, or '.' for root)",
            }
        },
        block=list_directory,
    )


boukensha.repl(setup=setup)
