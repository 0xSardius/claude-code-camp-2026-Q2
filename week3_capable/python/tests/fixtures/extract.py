"""Build the fixture corpus from real captured MUD output (week3 harness M1).

    uv run python tests/fixtures/extract.py          # rebuild corpus.jsonl
    uv run python tests/fixtures/extract.py --report # show what's in it

Reads every committed session log and pulls out the tool results the game
actually produced. Deduplicates, tags each distinct shape structurally, and
writes tests/fixtures/corpus.jsonl.

WHY THIS EXISTS. Week 2's parser was written and tested against samples I typed
by hand, which is how it came to reject real room titles and accept gossip
lines: the samples matched my mental model of the format rather than the
server's. The corpus removes that failure mode -- tests assert against text the
game really sent.

The extraction is the easy half. The value is in the TAGS: of 155 captured
`move` replies, 152 are the clean shape everyone imagines and 3 are not. The
rare shapes are the ones that break parsers and the ones nobody invents by
hand, so the tagging exists to make them findable rather than drowned.

Tags are derived STRUCTURALLY -- from what the text does or doesn't contain --
never from a curated list of phrases. A hand-maintained phrase list would
reintroduce exactly the brittleness this corpus is meant to expose
(docs/plans/week3/00_judgment_boundary.md).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent.parent.parent.parent
SESSIONS = REPO_ROOT / ".boukensha" / "sessions"
CORPUS = HERE / "corpus.jsonl"

ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
EXITS = re.compile(r"\[\s*Exits:", re.IGNORECASE)
STATUS_PROMPT = re.compile(r"\d+H\s+\d+M\s+\d+V\b[^>]*>\s*$", re.MULTILINE)


def strip_ansi(text):
    return ANSI.sub("", str(text or ""))


def tag(tool, raw):
    """Structural tags. Each answers a question about the SHAPE of the text,
    not about specific words in it."""
    text = strip_ansi(raw)
    lines = [ln.rstrip() for ln in text.splitlines()]
    non_blank = [ln.strip() for ln in lines if ln.strip()]
    first = non_blank[0] if non_blank else ""
    tags = set()

    if not text.strip():
        tags.add("empty")
    if text.startswith("error:"):
        tags.add("tool_error")          # our layer's text, not the game's
    if ANSI.search(str(raw or "")):
        tags.add("ansi")
    if STATUS_PROMPT.search(text):
        tags.add("status_prompt")
    else:
        tags.add("no_status_prompt")

    if EXITS.search(text):
        tags.add("has_exits")
        # Everything above the exits line that isn't the title is preamble --
        # this is the shape that produced phantom rooms.
        exits_at = next(i for i, ln in enumerate(lines) if EXITS.search(ln))
        above = [ln.strip() for ln in lines[:exits_at] if ln.strip()]
        if not above:
            tags.add("exits_first")
        elif len(above) >= 2 and above[0].endswith((".", "!", "?")):
            tags.add("preamble_before_room")
        if above and len(above[0]) > 60:
            tags.add("long_first_line")
    else:
        tags.add("no_exits")

    # Multi-line replies where something happened before/after the main body.
    if len(non_blank) > 12:
        tags.add("long_reply")

    tags.add(f"tool:{tool}")
    return sorted(tags)


def extract():
    if not SESSIONS.is_dir():
        sys.exit(f"no session logs at {SESSIONS}")

    seen = {}
    order = []
    for path in sorted(SESSIONS.glob("*.jsonl")):
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                e = json.loads(line)
            except json.JSONDecodeError:
                continue           # torn final line from an interrupted run
            if e.get("phase") != "tool_result":
                continue
            tool = e.get("name")
            raw = e.get("result")
            if not tool or raw is None:
                continue
            digest = hashlib.sha1(f"{tool}\x00{raw}".encode("utf-8", "replace")).hexdigest()[:12]
            if digest in seen:
                seen[digest]["seen"] += 1
                continue
            seen[digest] = {
                "id": digest,
                "tool": tool,
                "ok": e.get("ok", True),
                "tags": tag(tool, raw),
                "seen": 1,
                "source": path.name,
                "text": raw,
            }
            order.append(digest)

    records = [seen[d] for d in order]
    CORPUS.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in records) + "\n",
        encoding="utf-8",
    )
    return records


def report(records):
    total_occurrences = sum(r["seen"] for r in records)
    print(f"{len(records)} distinct outputs from {total_occurrences} captured occurrences")
    print(f"written to {CORPUS.relative_to(REPO_ROOT)}\n")

    by_tool = defaultdict(list)
    for r in records:
        by_tool[r["tool"]].append(r)

    print(f"{'tool':18} {'distinct':>8} {'captured':>9}   tags beyond the common case")
    print("-" * 92)
    for tool, rs in sorted(by_tool.items(), key=lambda kv: -sum(x["seen"] for x in kv[1])):
        occ = sum(r["seen"] for r in rs)
        rare = Counter()
        for r in rs:
            for t in r["tags"]:
                if t.startswith("tool:") or t in ("ansi", "status_prompt", "has_exits"):
                    continue
                rare[t] += 1
        notable = ", ".join(f"{k}({v})" for k, v in rare.most_common(4)) or "-"
        print(f"{tool:18} {len(rs):>8} {occ:>9}   {notable}")

    print("\nThe rare shapes -- the ones nobody writes by hand:")
    for t in ("preamble_before_room", "no_exits", "exits_first", "long_first_line", "tool_error"):
        hits = [r for r in records if t in r["tags"] and r["tool"] in ("move", "look")]
        if not hits:
            continue
        print(f"\n  [{t}]  {len(hits)} distinct")
        for r in hits[:2]:
            first = next((l.strip() for l in strip_ansi(r["text"]).splitlines() if l.strip()), "")
            print(f"    {r['id']}  {first[:74]!r}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", action="store_true", help="only report on the existing corpus")
    args = ap.parse_args()
    if args.report and CORPUS.is_file():
        recs = [json.loads(l) for l in CORPUS.read_text(encoding="utf-8").splitlines() if l.strip()]
    else:
        recs = extract()
    report(recs)
