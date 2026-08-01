"""Live MUD smoke test for the week2 build.

    ../bin/smoke

Purpose: everything in week2 so far has been verified offline (34 tests with a
FakeClient) plus two isolated API calls. The harness has not connected to the
real game once since the fork -- and in between we changed the request payload
(prompt caching), added a `thinking` parameter, raised the output ceiling, and
inserted five hook points into the main loop. This exercises all of it against
a live server.

Deliberately narrow. It connects, looks, checks the character sheet, and stops.
No movement, no combat, no picking anything up.

Runs as `boukensha` -- the dedicated test character created 2026-07-24 for
exactly this, NOT `dummy`. settings.yaml still points at `dummy`, which carries
all the real accumulated progress; the mud= override below leaves that block
untouched. Running a never-before-run build against the character holding the
week's progress is the setup that goes wrong.
"""
import os
import re
import sys
from pathlib import Path

import boukensha

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
os.environ.setdefault("BOUKENSHA_DIR", str(REPO_ROOT / ".boukensha"))


def test_character():
    """Read the dedicated test character's credentials off disk.

    Never inlined into this file: mud_test_character.txt is gitignored, and
    this example is committed.
    """
    path = Path(os.environ["BOUKENSHA_DIR"]) / "mud_test_character.txt"
    if not path.is_file():
        sys.exit(f"missing {path} -- see the week1 notes on the boukensha test character")
    fields = {}
    for line in path.read_text().splitlines():
        m = re.match(r"^(name|password):\s*(.+?)\s*$", line)
        if m:
            fields.setdefault(m.group(1), m.group(2))
    missing = {"name", "password"} - fields.keys()
    if missing:
        sys.exit(f"{path} is missing: {', '.join(sorted(missing))}")
    return fields


TASK = """\
This is a connectivity smoke test, not a play session. Do exactly the following
and nothing else:

1. Connect to the MUD.
2. Look at your surroundings. Report the room name and the visible exits.
3. Check your score. Report your level, hit points, and experience.

Do NOT move in any direction. Do NOT attack anything. Do NOT pick anything up.
Do NOT practice or train. If anything looks unexpected, say so rather than
acting on it.

Finish with a two-sentence summary of what you observed.
"""


def main():
    char = test_character()
    cfg = boukensha.config()

    if not os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit("ANTHROPIC_API_KEY not set -- run via ../bin/smoke, which sources the repo-root .env")

    log_path = Path(os.environ["BOUKENSHA_DIR"]) / "sessions" / "week2-smoke.jsonl"
    log_path.unlink(missing_ok=True)  # fresh each run so the report is about THIS run

    print(f"model      : {cfg.model}")
    print(f"caching    : {cfg.agent_prompt_caching()}")
    print(f"max output : {cfg.agent_max_output_tokens()}")
    print(f"character  : {char['name']}  (settings.yaml still points at dummy -- untouched)")
    print(f"log        : {log_path}")
    print("-" * 72)

    result = boukensha.run(
        task=TASK,
        # working_dir=False drops the filesystem/shell tools; the MUD tools are
        # the ones under test, and it matches the documented usage for this
        # character. Note it also shrinks the cached prefix, so the hit rate
        # here is a floor, not a ceiling.
        working_dir=False,
        mud={
            "host": "localhost",
            "port": 4000,
            "name": char["name"],
            "password": char["password"],
        },
        log=str(log_path),
        max_output_tokens=cfg.agent_max_output_tokens(),
    )

    print("-" * 72)
    print(result)
    print("-" * 72)
    print(f"\nnow run:  ../bin/report {log_path}")


if __name__ == "__main__":
    main()
