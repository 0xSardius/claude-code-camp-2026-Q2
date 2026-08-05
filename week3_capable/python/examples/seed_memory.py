"""Hand a character prior notes it did not earn itself (week3).

    ../bin/seed dummy ../seeds/dummy.md          write them
    ../bin/seed dummy ../seeds/dummy.md --dry-run   show what would be written

WHAT THIS IS FOR. A character can have knowledge that predates this harness --
`dummy` reached level 4 under week0's play-mud skill, and everything it learned
doing that lives in a different project's markdown. Starting it here from an
empty memory would throw that away and re-learn it at real cost.

WHERE THE NOTES GO, AND WHY IT MATTERS. Everything imported lands in `facts.md`,
which the model READS and judges. Nothing is written into `trails.json`.

That split is the whole design. The map drives `travel` mechanically -- the loop
walks those edges without asking anyone -- and it is trustworthy precisely
because every edge in it was recorded when the agent walked it and saw where it
came out. Hand-transcribing someone else's map into that structure would put a
person's typing inside a thing the loop trusts blindly, which is the failure the
judgment-boundary doc calls out: an algorithm walking a route nobody verified.

Notes are the opposite. They are claims. A route in a note is a hint about where
to walk; walking it is what turns it into a map edge. So prior knowledge makes
re-acquisition fast without ever being trusted on its own.

WHAT COUNTS AS A NOTE. Every markdown bullet in the file, with its nesting and
`**bold**` flattened. Headings, prose and blank lines are skipped -- headings are
organisation for the human reading the file, not claims. Import is idempotent:
Memory.add_fact drops anything already known, so re-running costs nothing.
"""
import argparse
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent

# Same line grind.py carries, and for the same reason: without it Memory falls
# back to ~/.boukensha and the notes land outside the repo, where the committed
# per-character memory lives. Set before importing Memory, which reads config.
os.environ.setdefault("BOUKENSHA_DIR", str(REPO_ROOT / ".boukensha"))

from boukensha.memory import Memory  # noqa: E402


def notes_from(text):
    """Markdown bullets -> one claim each.

    Continuation lines are joined back on, because a note wrapped across three
    lines is one claim, and importing it as three would store three fragments
    that each read as nonsense on their own.
    """
    out, current = [], None
    for raw in text.splitlines():
        line = raw.rstrip()
        if not line.strip():
            current = None
            continue
        if line.lstrip().startswith("#"):
            current = None
            continue
        m = re.match(r"^\s*[-*]\s+(.*)$", line)
        if m:
            if current:
                out.append(current)
            current = m.group(1).strip()
        elif current is not None and line.startswith((" ", "\t")):
            current += " " + line.strip()
        else:
            current = None
    if current:
        out.append(current)
    return [re.sub(r"\s+", " ", n.replace("**", "")).strip() for n in out if n.strip()]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("character")
    ap.add_argument("notes", help="markdown file of bullets")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    # The launcher cds into the package before running us, so a path the user
    # typed relative to the repo root would otherwise miss. Try both.
    path = Path(args.notes)
    if not path.is_file():
        path = REPO_ROOT / args.notes
    if not path.is_file():
        sys.exit(f"no such notes file: {args.notes}")

    claims = notes_from(path.read_text())
    if not claims:
        sys.exit(f"{path} has no bullets in it — nothing to import")

    print(f"character : {args.character}")
    print(f"notes     : {path}  ({len(claims)} claims)")
    if args.dry_run:
        print("-" * 72)
        for c in claims:
            print(f"  + {c[:110]}")
        print("\n(dry run — nothing written)")
        return

    mem = Memory(args.character)
    added = sum(1 for c in claims if mem.add_fact(c))
    print(f"memory    : {mem.path}")
    print("-" * 72)
    print(f"{added} written, {len(claims) - added} already known")
    print(f"facts now : {len(mem.facts().splitlines())} lines")
    print(f"map       : {len(mem.rooms())} rooms, {len(mem._map()['edges'])} edges "
          f"(untouched — the map is only ever built by walking)")


if __name__ == "__main__":
    main()
