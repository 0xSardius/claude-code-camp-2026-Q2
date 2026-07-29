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

# A room title is short, has no sentence-ending punctuation, and is not the
# status prompt. Anything else and we decline to guess.
_MAX_TITLE_LEN = 60


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

    Anchored on the `[ Exits: ... ]` line: without it we are not confident this
    is a room description at all, and decline. Returns None rather than
    guessing.
    """
    clean = strip_ansi(text)
    exits = parse_exits(clean)
    if exits is None:
        return None

    lines = clean.splitlines()
    exits_at = next((i for i, ln in enumerate(lines) if EXITS_LINE.search(ln)), None)
    if exits_at is None:
        return None

    # The title is the first non-blank line above the exits block.
    title, title_at = None, None
    for i, raw in enumerate(lines[:exits_at]):
        ln = raw.strip()
        if not ln:
            continue
        title, title_at = ln, i
        break

    if not _plausible_title(title):
        return None

    description = " ".join(
        ln.strip() for ln in lines[title_at + 1:exits_at] if ln.strip()
    ).strip()

    return {"name": title, "exits": exits, "description": description or None}


def _plausible_title(title):
    if not title or len(title) > _MAX_TITLE_LEN:
        return False
    if STATUS_PROMPT.search(title):
        return False
    # Room titles are labels, not sentences.
    if title.endswith((".", "!", "?")):
        return False
    # Failure text from our own tool layer, not the game.
    if re.match(r"^(error|already |not connected|disconnected)", title, re.IGNORECASE):
        return False
    return True


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
