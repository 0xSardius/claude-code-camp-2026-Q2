# World Map Notes

Freeform map of rooms discovered so far. Update this whenever a `look`
reveals a new room or exit, so future sessions don't have to re-explore
blindly to get somewhere already visited.

## Known rooms (Midgaard)

- **The Bakery** — exits: s
  - s -> Main Street
  - shop: danish 7g, bread 14g, waybread 74g (all unlimited stock)
- **Main Street** — exits: n e s w
  - n -> The Bakery
  - e -> Market Square
  - s -> Armory (unexplored)
  - w -> unexplored
- **Market Square** — exits: n e s w
  - n -> The Temple Square
  - s -> The Common Square
  - e/w -> Main Street
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
  - w -> Clerics' Guild (unexplored), e -> Grunting Boar Inn (unexplored)
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
- **The Alchemist's Room** (east of Another Corner, behind a door) — exits: (n) w d
  - w -> Another Corner
  - (n) -> closed door, unexplored
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
  - u -> unexplored (open-air balcony)
  - w -> leads back toward the "Bright Hallway" cluster (see note below)
  - mobs seen: "a newbie" NPC that shows as "looking terribly confused" and
    fights as **"the clueless newbie"** — consider: perfect match, easy,
    ~33 exp. This is the one worth killing; the other "newbie" flavor texts
    ("talking a lot", "wandering aimlessly", "quite sure of himself") are
    all "a lot of luck" or worse ("do you feel lucky, punk?") — always
    `consider` a newbie before committing, the flavor text alone is a decent
    hint but confirm with `consider`.
  - note: going `w` from here (after a connection drop + reconnect) landed
    in a room ALSO called "A Bright Hallway" but with different exits
    (`e (w)`) and different flavor text than the one north of A Nexus —
    unclear if this is the same room reached via a shortcut or a second,
    similarly-named room. Needs re-verification on a future visit; don't
    fully trust this one link.
  - "The Statue's Room" / North & South Stairs area has a domed roof and
    balconies "overlooking the area" — reads like it's adjacent to (or
    overlooks) whatever's below the Alchemist's stairway. Worth a cautious
    look from the `u` balcony exits once stronger, but not explored yet.

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
