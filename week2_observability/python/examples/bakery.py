"""The bakery proof run (week2 memory M4).

    ../bin/bakery          # run it
    ../bin/bakery --fresh  # wipe this character's memory first (run 1)

THE BAR IS PROVABILITY, NOT SUCCESS. A run that finds the bakery by luck proves
nothing. The test is two runs:

  run 1 (--fresh)  explores, finds the bakery, records what it learned
  run 2            already knows, and goes there

and run 2 must show a memory consultation BEFORE its movement decisions. A
successful run 2 with no memory read in the log is a FAILED milestone, not a
pass -- it means the agent guessed again and happened to be right.

The script prints the comparison at the end so the claim is checkable rather
than asserted.

Runs as `boukensha`, the disposable test character. Safety rules are in the
task prompt: no combat, and stay inside the city.
"""
import argparse
import json
import os
import re
import shutil
import sys
from pathlib import Path

import boukensha
from boukensha.memory import Memory

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
os.environ.setdefault("BOUKENSHA_DIR", str(REPO_ROOT / ".boukensha"))

TASK = """\
Your goal: find the Bakery in the city of Midgaard and report exactly what it
sells.

Before you move anywhere, check what you already know. You have a `recall` tool
and a `find_route` tool. If you already know where the Bakery is and how to get
there, follow that route directly instead of exploring. If you do not, explore
deliberately: read the exits in each room, pick a direction for a reason, and
say what that reason is.

When you find it, use the shop's list command to read the menu and report the
items and prices.

Record what you learn as you go with `remember_fact` -- especially where the
Bakery is relative to somewhere recognisable, so a later run does not have to
search again.

SAFETY, these are hard limits:
- Do not attack anything. Do not fight. If something attacks you, flee.
- Do not leave the city.
- Do not pick anything up and do not buy anything.
- If you cannot find it within your action budget, stop and report how far you
  got and what you recorded. Running out of budget is an acceptable outcome;
  inventing a result is not.
"""


def character():
    path = Path(os.environ["BOUKENSHA_DIR"]) / "mud_test_character.txt"
    if not path.is_file():
        sys.exit(f"missing {path}")
    txt = path.read_text()
    return {k: re.search(rf"^{k}:\s*(.+?)\s*$", txt, re.M).group(1)
            for k in ("name", "password")}


OPPOSITE = {"north": "south", "south": "north", "east": "west",
            "west": "east", "up": "down", "down": "up"}

START_ROOM = "The Temple Of Midgaard"


def send_home(char, memory):
    """TEST FIXTURE, not agent behaviour: walk the character back to the start
    room so run 2 actually has to navigate.

    Without this the proof is vacuous. The MUD persists where a character is
    standing, so after run 1 finds the Bakery, run 2 begins *inside* the
    Bakery -- it can read the menu without moving, and navigation is never
    exercised. (That is exactly what happened on the first attempt.)

    This inverts the recorded route, which the agent's own code deliberately
    never does (CircleMUD has one-way exits, so a reverse is only trustworthy
    once walked). It is safe here because a human is asserting these particular
    city streets are two-way, and because nothing this function does is
    recorded into memory.
    """
    from boukensha.mud_session import Session

    start = memory.find_room(START_ROOM)
    here = memory.position
    if not (start and here):
        return "cannot reset position: start room or current position unknown"
    if here == start:
        return "already at the start room"
    forward = memory.route(start, here)
    if forward is None:
        return "no recorded route from the start room; leaving position as-is"

    back = [OPPOSITE[d] for d in reversed(forward) if d in OPPOSITE]
    s = Session(host="localhost", port=4000)
    try:
        s.open()
        s.login(char["name"], char["password"])
        for d in back:
            s.send_command(d)
            s.read_until_prompt()
        s.send_command("save")
        s.read_until_prompt()
    finally:
        try:
            s.close()
        except Exception:  # noqa: BLE001
            pass
    memory.set_position(start)
    return f"walked home: {', '.join(back)}"


def evidence(log_path, memory):
    """Did memory actually change what the agent did?

    The first version of this asked only "did it call a memory tool", which was
    the wrong question twice over: the lifecycle hook injects memory into the
    conversation automatically, so the agent can use it without ever calling a
    tool -- and it did. What actually matters is whether the agent walked the
    route it had recorded, rather than searching for it again.
    """
    order, directions, injected = [], [], False
    for line in Path(log_path).read_text().splitlines():
        try:
            e = json.loads(line)
        except json.JSONDecodeError:
            continue
        if e.get("phase") == "tool_call":
            order.append(e["name"])
            if e["name"] == "move":
                directions.append((e.get("args") or {}).get("direction"))
        # before_turn appends the <memory> block as an extra leading user
        # message, so a turn that opens with more than one user message had
        # memory delivered without the agent having to ask.
        if e.get("phase") == "prompt" and not injected:
            roles = (e.get("digest") or {}).get("roles") or []
            injected = roles[:2] == ["user", "user"]

    start = memory.find_room(START_ROOM)
    target = memory.find_room("Bakery")
    recorded = memory.route(start, target) if (start and target) else None

    return {
        "tool_order": order,
        "moves": directions,
        "memory_injected": injected,
        "called_memory_tool": any(n in ("recall", "find_route") for n in order),
        "recorded_route": recorded,
        "followed_recorded_route": bool(recorded) and directions == recorded,
        "rooms_known": len(memory.rooms()),
        "routes_known": len(memory._map()["edges"]),
        "facts": len([f for f in memory.facts().splitlines() if f.strip()]),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fresh", action="store_true",
                    help="wipe this character's memory first (use for run 1)")
    ap.add_argument("--home", action="store_true",
                    help="walk the character back to the start room first "
                         "(required for run 2 to actually test navigation)")
    args = ap.parse_args()

    char = character()
    cfg = boukensha.config()
    mem = Memory(char["name"])

    if args.fresh:
        shutil.rmtree(mem.path, ignore_errors=True)
        mem = Memory(char["name"])
        print("memory WIPED — this is run 1 (exploration)")
    else:
        print(f"memory warm — {len(mem.rooms())} rooms, "
              f"{len(mem._map()['edges'])} routes, "
              f"{len([f for f in mem.facts().splitlines() if f.strip()])} facts")

    if args.home:
        print(f"fixture: {send_home(char, mem)}")

    if not os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit("ANTHROPIC_API_KEY not set — run via ../bin/bakery")

    tag = "run1" if args.fresh else "run2"
    log_path = Path(os.environ["BOUKENSHA_DIR"]) / "sessions" / f"bakery-{tag}.jsonl"
    log_path.unlink(missing_ok=True)

    print(f"character  : {char['name']}   model: {cfg.model}   log: {log_path.name}")
    print("-" * 72)

    result = boukensha.run(
        task=TASK,
        working_dir=False,
        mud={"host": "localhost", "port": 4000,
             "name": char["name"], "password": char["password"]},
        memory=char["name"],
        log=str(log_path),
        max_output_tokens=cfg.agent_max_output_tokens(),
    )

    print("-" * 72)
    print(result)
    print("-" * 72)

    ev = evidence(log_path, Memory(char["name"]))
    print(f"\nEVIDENCE ({tag})")
    print(f"  tools called          : {' -> '.join(ev['tool_order'][:14])}"
          + (" ..." if len(ev["tool_order"]) > 14 else ""))
    print(f"  moves made ({len(ev['moves'])})        : {', '.join(d or '?' for d in ev['moves']) or '(none)'}")
    print(f"  recorded route        : {', '.join(ev['recorded_route']) if ev['recorded_route'] else '(none)'}")
    print(f"  memory injected       : {ev['memory_injected']}")
    print(f"  called a memory tool  : {ev['called_memory_tool']}")
    print(f"  rooms known after     : {ev['rooms_known']}")
    print(f"  routes known after    : {ev['routes_known']}")
    print(f"  facts recorded        : {ev['facts']}")
    if not args.fresh:
        ok = ev["followed_recorded_route"]
        print(f"\n  followed the recorded route exactly : {ok}")
        print("  PASS CRITERION: run 2 walks the route it recorded, with no")
        print("  exploratory detours. Reaching the Bakery by searching again")
        print("  is a FAILED milestone even though the answer would be right.")
        print(f"\n  ==> {'PASS' if ok else 'FAIL'}")


if __name__ == "__main__":
    main()
