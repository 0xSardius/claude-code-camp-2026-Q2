"""Parsers for CircleMUD output (week2 memory M3).

`mud_primitives.py` builds commands; nothing until now read the replies. These
turn raw telnet text into the facts the memory store records.

DESIGN RULE: be conservative and return None when unsure. A wrong fact is worse
than a missing one — a misparsed room name corrupts the map silently (two rooms
merge, or one splits) and every later route built on it inherits the error. A
missing one just means the agent looks again.
"""
from __future__ import annotations

import re

# CircleMUD colours everything; strip before matching on anything.
ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")

# Trailing status prompt, e.g. "25H 100M 85V (news) (motd) > "
STATUS_PROMPT = re.compile(
    r"(?P<hp>\d+)H\s+(?P<mana>\d+)M\s+(?P<moves>\d+)V\b[^>]*>\s*$",
    re.MULTILINE,
)

EXITS_LINE = re.compile(r"\[\s*Exits:\s*(?P<exits>[^\]]*?)\s*\]", re.IGNORECASE)

DIRECTION_WORDS = {
    "n": "north", "e": "east", "s": "south", "w": "west", "u": "up", "d": "down",
    "north": "north", "east": "east", "south": "south", "west": "west",
    "up": "up", "down": "down",
}

# The server marks room titles with its own colour code. We read that marker
# instead of guessing which line looks like a title.
#
# The week 2 version guessed: first non-blank line, unless over 60 characters,
# unless it ends in sentence punctuation, unless it holds two quote marks,
# unless it starts with one of a list of phrases. Every bug found added another
# guess -- which is the "brittle logic" failure the week 3 red-flag list names
# (regex on content, stop words, number thresholds standing in for a judgment).
#
# Measured over the full fixture corpus: all 243 real room-bearing replies wrap
# the title in this code, and the markup rule agrees with the old guessing rule
# on every one of them -- including both cases where narration ("You are
# hungry.", "The cityguard has arrived.") precedes the room.
#
# The same colour also marks mobs and players, but those are listed BELOW the
# exits block, so position disambiguates. Both signals come from the server;
# neither is an assumption about what room names look like.
TITLE_MARKUP = re.compile(r"\x1b\[0;33m([^\x1b\r\n]*)")
EXITS_MARKER = re.compile(r"(?:\x1b\[[0-9;]*m)?\[\s*Exits:", re.IGNORECASE)


def strip_ansi(text):
    return ANSI.sub("", str(text or ""))


def parse_status(text):
    """Current hit/mana/movement from the trailing prompt. Present on almost
    every reply, which makes it the cheapest vitals source available."""
    m = None
    for m in STATUS_PROMPT.finditer(strip_ansi(text)):
        pass  # keep the LAST prompt -- earlier ones are stale by the time we read
    if not m:
        return None
    return {"hp": int(m.group("hp")), "mana": int(m.group("mana")), "moves": int(m.group("moves"))}


def parse_exits(text):
    m = EXITS_LINE.search(strip_ansi(text))
    if not m:
        return None
    out = []
    for token in re.split(r"[\s,]+", m.group("exits").strip().lower()):
        if token in DIRECTION_WORDS:
            out.append(DIRECTION_WORDS[token])
    return sorted(set(out))


def parse_room(text):
    """Extract {name, exits, description} from a look/move reply.

    Two structural signals from the server, no guesses about content:

      1. The `[ Exits: ... ]` block -- without it this is not a room
         description at all, so we decline.
      2. The server's own title colour, taken from ABOVE the exits block. The
         same colour marks mobs and players, but those are always listed below
         the exits, so position separates them.

    Returns None rather than guessing. A wrong room name is worse than a
    missing one: it writes a phantom node into the map permanently, and every
    later route built on it inherits the error. A missing one just means the
    agent looks again.
    """
    exits = parse_exits(text)
    if exits is None:
        return None

    raw = str(text or "")
    cut = EXITS_MARKER.search(raw)
    if cut is None:
        return None
    head = raw[:cut.start()]

    marked = TITLE_MARKUP.search(head)
    if marked is None:
        # The server sent a room but no title markup -- colour is off, or this
        # is an output mode we have never seen. Decline loudly rather than fall
        # back to guessing: a silent guess is how phantom rooms got written in
        # the first place, and a decline shows up in the logs as a parse gap we
        # can go and look at.
        return None
    title = marked.group(1).strip()
    if not title:
        return None

    # Description is whatever sits between the title and the exits block.
    lines = strip_ansi(head).splitlines()
    body = [ln.strip() for ln in lines if ln.strip() and ln.strip() != title]
    # Drop anything above the title (narration that arrived before the room).
    if title in [ln.strip() for ln in lines]:
        at = [ln.strip() for ln in lines].index(title)
        body = [ln.strip() for ln in lines[at + 1:] if ln.strip()]

    return {"name": title, "exits": exits, "description": " ".join(body).strip() or None}


def parse_score(text):
    """Vitals from a `score` reply. Every field is optional — a partial parse
    returns what it found, and Memory.update_state ignores None so a missing
    field never erases a known one."""
    clean = strip_ansi(text)
    out = {}

    m = re.search(r"(\d+)\((\d+)\)\s*hit", clean, re.IGNORECASE)
    if m:
        out["hp"] = f"{m.group(1)}/{m.group(2)}"
    m = re.search(r"(\d+)\((\d+)\)\s*mana", clean, re.IGNORECASE)
    if m:
        out["mana"] = f"{m.group(1)}/{m.group(2)}"
    m = re.search(r"(\d+)\((\d+)\)\s*movement", clean, re.IGNORECASE)
    if m:
        out["moves"] = f"{m.group(1)}/{m.group(2)}"

    m = re.search(r"You have\s+([\d,]+)\s+exp", clean, re.IGNORECASE)
    if m:
        out["exp"] = int(m.group(1).replace(",", ""))
    m = re.search(r"([\d,]+)\s+gold coins", clean, re.IGNORECASE)
    if m:
        out["gold"] = int(m.group(1).replace(",", ""))
    m = re.search(r"You need\s+([\d,]+)\s+exp", clean, re.IGNORECASE)
    if m:
        out["exp_to_level"] = int(m.group(1).replace(",", ""))

    # "This ranks you as Boukensha the Swordpupil (level 1)."
    m = re.search(r"ranks you as\s+(?P<title>.+?)\s*\(level\s+(?P<level>\d+)\)", clean, re.IGNORECASE)
    if m:
        out["level"] = int(m.group("level"))
        out["title"] = m.group("title").strip()

    m = re.search(r"You are (standing|sitting|resting|sleeping|fighting)", clean, re.IGNORECASE)
    if m:
        out["position_state"] = m.group(1).lower()

    return out or None


def parse_practice(text):
    """Unspent practice sessions from a `practice` reply, or None.

    Why this exists at all: the driver used to decide it was time to train from
    `exp_to_level <= 0`, which never happens. CircleMUD levels you the moment
    you earn the experience -- the counter falls to the next threshold and
    resets, so nothing ever observes it at zero, and the whole training branch
    was unreachable. Checked live 2026-08-05: `dummy` was sitting on an
    unspent session with backstab still at "poor", which is the skill its best
    kills depend on.

    Sessions are what actually gates training, so read those instead. "You have
    no practice sessions remaining." is a real zero, not a failed parse, which
    is why the no-match case is handled explicitly rather than falling through.
    """
    clean = strip_ansi(text)
    m = re.search(r"You have\s+(\d+)\s+practice session", clean, re.IGNORECASE)
    if m:
        return int(m.group(1))
    if re.search(r"You have no practice sessions", clean, re.IGNORECASE):
        return 0
    return None
