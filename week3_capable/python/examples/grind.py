"""Turn the agent loose (week3 M4).

    ../bin/grind --dry-run          offline, no model calls, proves the wiring
    ../bin/grind --cycles 6         live, on the disposable test character
    ../bin/grind --live-character   live, on `dummy` (the one with real progress)

WHAT THIS IS. Week 2's agent could act and remember but could not sequence: you
gave it a task, it did that task, it stopped. This runs the Driver over a
Harness, so one conversation stays alive across many cycles and the loop
decides what the next task should be.

WHAT IT PRINTS. The judgment ratio -- what fraction of ACTIONS needed a model
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
from datetime import datetime, timezone
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
    if ratio is None:
        print("judgment ratio  : n/a — no actions were taken")
    else:
        print(f"judgment ratio  : {ratio:.0%} of actions needed the model "
              f"({result.model_actions} model, {result.mechanical_actions} mechanical)")
    by_cycle = result.cycle_judgment_ratio
    if by_cycle is not None:
        print(f"  by cycle      : {by_cycle:.0%} of cycles needed it at all"
              + ("   (dry run — the model was stubbed out)" if dry else ""))
    gained = result.experience_gained
    print(f"experience      : {result.starting_exp} -> {result.ending_exp}"
          + (f"  (+{gained})" if gained is not None else ""))
    if result.task_summary:
        print(f"task result     : {result.task_summary}")
    print()
    for i, c in enumerate(result.cycles, 1):
        kind = "model" if c.used_model else "mechanical"
        print(f"  {i:>3}. {c.action:<12} {kind:<11} "
              f"{c.model_actions:>2}m/{c.mechanical_actions:<3} {c.note}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--goal", default="gain experience and reach the next level")
    ap.add_argument("--task", default=None,
                    help="a specific job to do instead of grinding, in your own "
                         "words, e.g. \"go to the Armory and buy a better weapon\". "
                         "The run ends when the agent reports it finished.")
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

    # ONE FILE PER LIVE RUN, and never deleted.
    #
    # This used to be a fixed name per character with an unlink() in front of
    # it. That was meant to stop a dry run clobbering a live one, and it did --
    # while quietly making every live run destroy the PREVIOUS live run's log.
    # It cost the best run of the week: on 2026-08-05 a run gained 1557
    # experience and produced the only cost-per-experience figure we had, and
    # the next run wiped the record of it before anything had been reported
    # from it. The loss was permanent, because the wiped file was then
    # committed over the good one.
    #
    # A session log is evidence. Evidence does not get an unlink() in front of
    # it just to keep a directory tidy -- the reporter already reads every file
    # in there and aggregates, so more files is the format working, not clutter.
    #
    # Dry runs stay on one overwritable name: they cost nothing, reproduce on
    # demand, and are not evidence of anything that happened in the world.
    sessions = Path(os.environ["BOUKENSHA_DIR"]) / "sessions"
    sessions.mkdir(parents=True, exist_ok=True)
    if args.dry_run:
        log = sessions / "grind-dry.jsonl"
        log.unlink(missing_ok=True)
    else:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        log = sessions / f"grind-{char['name']}-{stamp}.jsonl"

    cfg = boukensha.config()
    mem = Memory(char["name"])
    print(f"character  : {char['name']}    model: {'(none, dry run)' if args.dry_run else cfg.model}")
    print(f"memory     : {len(mem.rooms())} rooms, {len(mem._map()['edges'])} routes")
    print(f"goal       : {args.goal}")
    if args.task:
        print(f"task       : {args.task}")
    print(f"log        : {log.name}")
    print("-" * 72)

    h = Harness.build(
        working_dir=False, mud=mud, memory=mem, log=str(log),
        max_output_tokens=cfg.agent_max_output_tokens(),
    )
    try:
        h.registry.dispatch("mud_connect", {})
        driver = h.driver(goal=args.goal, policy=Policy(), task=args.task)

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
