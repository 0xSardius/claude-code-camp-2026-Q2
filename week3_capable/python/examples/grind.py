"""Turn the agent loose (week3 M4).

    ../bin/grind --dry-run          offline, no model calls, proves the wiring
    ../bin/grind --cycles 6         live, on the disposable test character
    ../bin/grind --live-character   live, on `dummy` (the one with real progress)

WHAT THIS IS. Week 2's agent could act and remember but could not sequence: you
gave it a task, it did that task, it stopped. This runs the Driver over a
Harness, so one conversation stays alive across many cycles and the loop
decides what the next task should be.

WHAT IT PRINTS. The judgment ratio -- what fraction of cycles needed a model
call -- is week 3's acceptance number. Read it as a description, not a score to
minimise: a loop that never reasons walks into the lava pit, and a loop that
reasons about standing up is wasting money. See
docs/plans/week3/00_judgment_boundary.md.

SAFETY. The hunt task tells the agent to `consider` before attacking and to
flee when hurt, and the driver rests it before health gets low. That is not a
guarantee. Default to the disposable character; --live-character is opt-in on
purpose, because `dummy` carries every level this project has earned.
"""
import argparse
import os
import re
import sys
from pathlib import Path

import boukensha
from boukensha.driver import Policy
from boukensha.harness import Harness
from boukensha.memory import Memory

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
os.environ.setdefault("BOUKENSHA_DIR", str(REPO_ROOT / ".boukensha"))

LIVE_CHARACTER = {"name": "dummy", "password": "helloworld"}


def test_character():
    path = Path(os.environ["BOUKENSHA_DIR"]) / "mud_test_character.txt"
    if not path.is_file():
        sys.exit(f"missing {path}")
    txt = path.read_text()
    return {k: re.search(rf"^{k}:\s*(.+?)\s*$", txt, re.M).group(1)
            for k in ("name", "password")}


def report(result, *, dry):
    print("-" * 72)
    print(f"stopped because : {result.stopped_because}")
    print(f"cycles          : {len(result.cycles)}")
    ratio = result.judgment_ratio
    print(f"judgment ratio  : {'n/a' if ratio is None else f'{ratio:.0%}'}"
          + ("   (dry run -- the model was never called)" if dry else ""))
    gained = result.experience_gained
    print(f"experience      : {result.starting_exp} -> {result.ending_exp}"
          + (f"  (+{gained})" if gained is not None else ""))
    print()
    for i, c in enumerate(result.cycles, 1):
        kind = "model" if c.used_model else "mechanical"
        print(f"  {i:>3}. {c.action:<12} {kind:<11} {c.note}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--goal", default="gain experience and reach the next level")
    ap.add_argument("--cycles", type=int, default=6)
    ap.add_argument("--dry-run", action="store_true",
                    help="offline: fake connection, stub model. Proves the wiring "
                         "without a server or a bill.")
    ap.add_argument("--live-character", action="store_true",
                    help=f"play as {LIVE_CHARACTER['name']} instead of the disposable "
                         "test character")
    args = ap.parse_args()

    char = LIVE_CHARACTER if args.live_character else test_character()
    mud = {"host": "localhost", "port": 4000,
           "name": char["name"], "password": char["password"]}

    if args.dry_run:
        # The offline stand-in, so this exercises the real tool layer, the real
        # memory pipeline and the real driver against captured game text.
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
        from tests.fake_mud import FakeSession
        mud["session"] = FakeSession()
    elif not os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit("ANTHROPIC_API_KEY not set — run via ../bin/grind")

    log = Path(os.environ["BOUKENSHA_DIR"]) / "sessions" / "grind.jsonl"
    log.unlink(missing_ok=True)

    cfg = boukensha.config()
    mem = Memory(char["name"])
    print(f"character  : {char['name']}    model: {'(none, dry run)' if args.dry_run else cfg.model}")
    print(f"memory     : {len(mem.rooms())} rooms, {len(mem._map()['edges'])} routes")
    print(f"goal       : {args.goal}")
    print(f"log        : {log.name}")
    print("-" * 72)

    h = Harness.build(
        working_dir=False, mud=mud, memory=mem, log=str(log),
        max_output_tokens=cfg.agent_max_output_tokens(),
    )
    try:
        h.registry.dispatch("mud_connect", {})
        driver = h.driver(goal=args.goal, policy=Policy())

        if args.dry_run:
            # Stub the model out entirely. Every cycle this run classifies as
            # mechanical therefore PROVES it is mechanical -- there is nothing
            # else it could have used.
            calls = []

            def no_model(task):
                calls.append(task)
                return "(dry run: no model call)"

            driver.run_turn = no_model

        result = driver.run(max_cycles=args.cycles)
    finally:
        h.close()

    report(result, dry=args.dry_run)


if __name__ == "__main__":
    main()
