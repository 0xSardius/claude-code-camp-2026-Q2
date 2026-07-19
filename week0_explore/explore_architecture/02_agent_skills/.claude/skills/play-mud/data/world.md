# World Map Notes

Freeform map of rooms discovered so far. Update this whenever a `look`
reveals a new room or exit, so future sessions don't have to re-explore
blindly to get somewhere already visited.

## Known rooms (Midgaard)

- **The Bakery** — exits: s
  - s -> Main Street
  - shop: danish 7g, bread 14g, waybread 74g (all unlimited stock)
- **Main Street** (east segment, near Market Square) — exits: n e s w
  - n -> The Bakery
  - e -> Market Square
  - s -> **The Armory** (shop, see below)
  - w -> Main Street (west segment)
- **Main Street** (west segment, near the city gate) — exits: n e s w
  - n -> **The Magic Shop** (shop, see below)
  - e -> Main Street (east segment)
  - s -> Guild of Magic Users entrance (not our guild, thief has no reason
    to go in)
  - w -> Inside The West Gate Of Midgaard -> leads to a forest/Wall Road,
    NOT toward the Newbie Zone (dead end for our purposes)
  - mobs seen: "a beastly fido" wanders through here
- **The Armory** (south of Main Street east segment) — exits: n
  - shop (armorer, "only buy armors", no haggling, no credit): see
    `## Shops` below for the full price list
- **The Magic Shop** (north of Main Street west segment) — exits: s
  - shop (a wizard): scrolls/wands/potions — see `## Shops` below. Usable
    by any class via `recite`/`quaff`/etc., not guild-restricted, worth
    checking even though it's a "magic" shop.
- **Market Square** — exits: n e s w
  - n -> The Temple Square
  - s -> The Common Square
  - e/w -> Main Street (east segment)
- **The Common Square** — exits: n e s w
  - n -> Market Square
  - e -> The Dark Alley
  - w -> The Poor Alley (unexplored)
  - s -> unexplored ("nasty smell")
  - note: east from here also reaches "The Dump" per one room description —
    the dark alley and the dump may both sit east of here; if `east` lands
    somewhere unexpected, `look` to confirm before continuing.
- **The Dark Alley** — exits: e s w
  - w -> The Common Square
  - s -> The Entrance Hall To The Guild Of Thieves
  - e -> unexplored
- **The Entrance Hall To The Guild Of Thieves** — exits: n e
  - n -> The Dark Alley
  - e -> The Thieves' Bar
  - note: `practice` fails here ("You can only practice skills in your guild")
- **The Thieves' Bar** — exits: s w
  - w -> Entrance Hall
  - s -> The Secret Yard
- **The Secret Yard** — exits: n d
  - n -> The Thieves' Bar
  - d (down) -> well into darkness (unexplored)
  - **this is the actual thieves' guild practice room** — `practice` works here
- **The Temple Square** — exits: n e s w
  - s -> Market Square
  - n -> The Temple Of Midgaard
  - w -> Clerics' Guild (unexplored)
  - e -> The Entrance Hall Of The Grunting Boar Inn
- **The Entrance Hall Of The Grunting Boar Inn** — exits: n e w u
  - w -> Temple Square
  - e -> **The Grunting Boar** (bar, see `## Shops` below)
  - n -> Post Office (unexplored)
  - u -> reception (unexplored, presumably `rent` for persisting location)
- **The Grunting Boar** (the bar itself) — exits: w
  - w -> Entrance Hall Of The Grunting Boar Inn
  - shop (a bartender): drinks — see `## Shops` below
- **The Temple Of Midgaard** — exits: n e s w d
  - s -> Temple Square
  - n -> By The Temple Altar
  - w -> Reading Room (unexplored), e -> donation room (unexplored), d -> unexplored
- **By The Temple Altar** — exits: n s
  - s -> Temple Of Midgaard
  - n -> Behind The Temple Altar (path out of the city)
- **Behind The Temple Altar** — exits: n s
  - s -> By The Temple Altar
  - n -> The Great Field Of Midgaard
- **The Great Field Of Midgaard** — exits: n s (first room) / n e s w (further
  in, one tile further north)
  - s -> back toward the city
  - e (from the second field room) -> The Entrance To The Newbie Zone
  - n/w from the field -> unexplored (open countryside, "Dragonhelm
    Mountains far off to the north")

## Newbie Zone (entered via the field east of the countryside path)

The hallway maze **loops** — it is not a dead end. Going far enough west
(through A Brighter Hallway -> The End Of The Passage) pops back out into
an open field that connects north to The Great Field Of Midgaard, i.e.
back to the entrance approach. Useful for a second lap without backtracking.

- **The Entrance To The Newbie Zone** — exits: n w
  - w -> The Great Field Of Midgaard
  - n -> The Beginning Of The Passage (into the zone proper)
- **The Beginning Of The Passage** — exits: e s
  - s -> Entrance To The Newbie Zone
  - e -> The Dirty Hallway
  - mobs seen: "a creepy little crawling thing" (consider: perfect match, ~33 exp, drops ~10g)
- **The Dirty Hallway** — exits: e s w (s door now opened, was closed)
  - w -> Beginning Of The Passage
  - e -> A Nexus
  - s -> **A Small Room** (see below — dangerous, avoid)
  - mobs seen: "a newbie" (talking NPC, consider: "a lot of luck" — too strong, skip; wanders around the maze)
- **A Small Room** (south of Dirty Hallway, behind a door) — exits: n (e) (d)
  - n -> Dirty Hallway
  - (e)/(d) -> closed door / grated-over well, unexplored
  - **AVOID**: "The Newbie Guard" is here (consider: "a lot of luck") and
    auto-joins combat against you the moment you kill anything else in the
    room (like the city Peacekeepers). Safe to farm the weaker mobs that
    also spawn here (creepy crawler, newbie monster) IF you `flee`
    immediately after any single kill, before the guard notices — but
    simplest is to just avoid this room until much stronger.
- **A Nexus** — exits: n (e) s w (n door now opened, was closed)
  - w -> The Dirty Hallway
  - s -> More Of The Hallway
  - n -> A Bright Hallway (see below)
  - (e) -> closed door, unexplored
  - mobs seen: "a newbie" NPC wanders through here too
- **More Of The Hallway** — exits: n s (w)
  - n -> A Nexus
  - s -> Another Corner
  - (w) -> closed door, unexplored
  - mobs seen: "someone's little pet dragon" (consider: "a lot of luck and
    great equipment" — too strong, skip; it wanders the whole maze)
- **Another Corner** — exits: n e w (e door now opened, was closed)
  - n -> More Of The Hallway
  - w -> A Brighter Hallway
  - e -> The Alchemist's Room (see below)
  - mobs seen: "a creepy little crawling thing" (same as above, easy kill)
- **A Brighter Hallway** — exits: e w
  - e -> Another Corner
  - w -> The End Of The Passage
  - mobs seen: "the newbie monster" (consider: "some luck" — winnable at
    full HP, ~150 exp, drops gold + a bright green newbie vest; text
    literally says "Kill him! Kill him!" — this is clearly an intended
    newbie fight, respawns here on repeat visits)
- **The End Of The Passage** — exits: e w
  - e -> A Brighter Hallway
  - w -> An Open Field By The Great Field (**exits the maze**)
  - mobs seen: "the newbie monster" also spawns here sometimes
- **An Open Field By The Great Field** — exits: n e
  - e -> The End Of The Passage
  - n -> The Great Field Of Midgaard (loops back to the entrance approach)
- **The Alchemist's Room** (east of Another Corner, behind a door) — exits: n w d
  - w -> Another Corner
  - n -> A Narrow Passage -> The South Stairs (confirmed 2026-07-18 — this
    room connects the two halves of the maze; a shortcut between the
    Another-Corner side and the Statue's-Room/Stairs side, if the door's open)
  - d -> a stairway down, guarded by a sign: *"If you are below level 7 and
    alone, or below level 4 then bugger off! Or else don't blame me if you
    die..."* — almost certainly the way to the massive Minotaur from
    CHALLENGES.md. **Do not go down until much higher level / grouped.**
  - **AVOID**: "The Newbie Alchemist" is here (consider: "Do you feel lucky,
    punk?" — top-tier danger, do not engage)
- **A Bright Hallway** (north of A Nexus, behind a door) — exits: n s
  - s -> A Nexus
  - n -> The Statue's Room
  - mobs seen: two "newbie" NPCs, "talking a lot" and "wandering about
    aimlessly" — both considered "a lot of luck", too strong, skip both
- **The Statue's Room** — exits: e s
  - s -> A Bright Hallway
  - e -> The Hallway
- **The Hallway** (decorated, distinct from "The Dirty Hallway") — exits: e w
  - w -> The Statue's Room
  - e -> The North Stairs
- **The North Stairs** — exits: s w u
  - w -> The Hallway
  - s -> The South Stairs
  - u -> unexplored (open-air balcony)
- **The South Stairs** — exits: n s w u
  - n -> The North Stairs
  - s -> A Narrow Passage (confirmed 2026-07-18)
  - u -> unexplored (open-air balcony)
  - w -> **A Second Bright Hallway** — CONFIRMED 2026-07-18 as a real,
    repeatable connection (not a reconnect artifact): South Stairs <-> w/e
    <-> this room. See its own entry below.
  - mobs seen: "a newbie" NPC that shows as "looking terribly confused" and
    fights as **"the clueless newbie"** — consider: perfect match/easy,
    ~33-35 exp, drops ~10g. This is the one worth killing; the other
    "newbie" flavor texts ("talking a lot", "wandering aimlessly", "quite
    sure of himself", "annoying the hell out of you") are all "a lot of
    luck" or worse ("do you feel lucky, punk?") — always `consider` a
    newbie before committing, the flavor text alone is a decent hint but
    confirm with `consider`.
  - "The Statue's Room" / North & South Stairs area has a domed roof and
    balconies "overlooking the area" — reads like it's adjacent to (or
    overlooks) whatever's below the Alchemist's stairway. Worth a cautious
    look from the `u` balcony exits once stronger, but not explored yet.
- **A Second Bright Hallway** (west of The South Stairs — distinct room
  from "A Bright Hallway" north of A Nexus, same generic name) — exits: e (w)
  - e -> The South Stairs
  - (w) -> closed door, unexplored
  - mobs seen: "a newbie" showing as "quite sure of himself" (too strong,
    skip) and "a creepy little crawling thing" (easy, same as elsewhere)
- **A Narrow Passage** (south of The South Stairs) — exits: n s
  - n -> The South Stairs
  - s -> The Alchemist's Room (this is the "(n)" door mentioned in that
    room's entry above — now confirmed, both sides connect here)
  - mobs seen: the same "looking terribly confused" -> "clueless newbie"
    spawn as South Stairs — this pocket (South Stairs <-> Narrow Passage)
    seems to be the clueless-newbie's usual territory.

## Shops

All shops so far follow the same rules: no haggling, no credit. `list` for
inventory, `value <item>` to check what they'd pay for something of ours,
`buy`/`sell` to transact.

- **The Bakery** (Main St east segment, north): danish 7g, bread 14g,
  waybread 74g. All unlimited stock. Good cheap hunger fix.
- **The Armory** (Main St east segment, south) — armor only, "only buy
  armors" (won't buy weapons/junk; even offered 0g for a spare vest, so
  our vest stockpile is worthless here). Canvassed 2026-07-18:
  | Item | Cost |
  |---|---|
  | A pair of leather sleeves | 95 |
  | A pair of bronze sleeves | 222 |
  | A pair of leather pants | 190 |
  | A pair of bronze leggings | 444 |
  | A leather cap | 190 |
  | A bronze helmet | 444 |
  | A pair of leather gloves | 95 |
  | A pair of bronze gauntlets | 222 |
  | A bronze breast plate | 888 |
  | A scale mail jacket | 1268 |
  | A studded leather jacket | 634 |
  | A leather jacket | 253 |
  | A shield | 126 |
  | A chain mail shirt | 317 |
  | A breast plate | 228 |

  We already own leather-tier (or better — bronze leggings) versions of
  most slots for free from Newbie Zone loot/starting kit, so most of this
  list is a downgrade or duplicate. The real upgrade path is leather ->
  bronze on gloves/sleeves/cap (222-444g each), or breast plate -> chain
  mail/scale mail/studded leather (317-1268g) once we have the gold.
- **The Magic Shop** (Main St west segment, north) — a wizard, but goods
  are usable by any class (scrolls via `recite`, potions via `quaff`,
  etc.), not guild-restricted. Canvassed 2026-07-18:
  | Item | Cost |
  |---|---|
  | A gnarled staff | 851 |
  | A gray wand of invisibility | 486 |
  | A scroll of recall | 243 |
  | A yellow potion of see invisible | 486 |
  | A scroll of identify | 6078 |

  **Bought the scroll of recall 2026-07-18** — `recite scroll of recall`
  teleports back to hometown sanctuary, confirmed usable by non-casters
  via `help recall`/`help scroll`. This is our emergency-escape backup
  now that we know `flee` can fail ("PANIC! You couldn't escape!").
  The scroll of identify (6078g) would finally answer whether the shiny
  newbie dagger actually beats the small sword — wildly unaffordable now,
  but worth remembering once gold is much higher.
- **The Grunting Boar** (bar, Grunting Boar Inn) — cheap drinks, fixes
  thirst. Canvassed 2026-07-18:
  | Item | Cost |
  |---|---|
  | A bottle of local speciality | 23 |
  | A bottle of firebreather | 58 |
  | A bottle of ale | 11 |
  | A bottle of beer | 23 |
  | A barrel of beer | 348 |

  **Bought + drank a bottle of ale 2026-07-18** — confirmed this clears
  the "You are thirsty" status line. Combined with eating any food item
  (cleared "You are hungry"), both nag messages are gone for now — cheap
  (~18g total) and worth repeating whenever they come back.

## General tips

- When multiple corpses are in a room, `get all corpse` keeps grabbing the
  *first* match (often one already looted) instead of cycling through all
  of them. Use the ordinal prefix to target a specific one: `get all
  2.corpse`, `get all 3.corpse`, etc.
- Corpses left too long get eaten: "A quivering horde of maggots consumes
  the corpse of the X." — loot promptly rather than fighting something
  else first and coming back.
- Someone's little pet dragon (wanders the whole maze) does not appear to
  be aggressive on its own — it's been in the same room repeatedly without
  ever attacking. Still don't engage it directly (consider says "a lot of
  luck and great equipment"), but its mere presence doesn't force a fight
  the way the Newbie Guard's room does.
- The zombiefied newbie in The Hallway (670 exp, see player.md) does not
  reliably respawn every session — went a full session (2026-07-18)
  without it appearing at all despite repeated laps. Treat it as a bonus
  target, not something to plan a whole session around.

## Quick paths

- Bakery -> Thieves' Guild practice room:
  `s, e, s, e, s, e, s` (Bakery -> Main St -> Market Sq -> Common Sq -> Dark
  Alley -> Entrance Hall -> Thieves' Bar -> Secret Yard)
- Bakery -> Newbie Zone (A Brighter Hallway):
  `s, e, n, n, n, n, n, n, e, n, e, e, s, s, w` (Bakery -> Main St -> Market
  Sq -> Temple Sq -> Temple Of Midgaard -> By The Temple Altar -> Behind
  The Temple Altar -> Great Field (1st tile) -> Great Field (2nd tile) ->
  Entrance To The Newbie Zone -> Beginning Of The Passage -> Dirty Hallway
  -> A Nexus -> More Of The Hallway -> Another Corner -> A Brighter Hallway)
  — 15 hops, each one confirmed by an actual `look` during the walk.
