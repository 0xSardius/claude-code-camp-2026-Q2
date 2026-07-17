# Player State

Freeform memory for the `dummy` character. Read this at the start of every
session before connecting; update it after anything that changes (level,
location, goal progress, inventory). This is what lets a goal like "get to
level 7" survive across many separate turns/sessions instead of restarting
from zero context each time.

## Current goal

Reach level 7, then find and fight the massive Minotaur in the Newbie Zone
(see `week0_explore/CHALLENGES.md`). Sub-goals "reach level 2" and "reach
level 3" are DONE — next sub-goal is level 4, then keep climbing toward 7.

## Character

- Name: Dummy
- Class: Thief (level 3 title: "the Filcher")
- Level: 3 (leveled up 2026-07-17, saved immediately after)
- HP: 37/44 max (regenerates over time/rest)
- Exp: 2821 (2179 more needed for level 4)
- Practice sessions remaining: **0** (both spent on backstab, see below)
- Gold: 233
- Wielding: a shiny newbie dagger (has a glowing aura, likely enchanted —
  swapped from the starting small sword; no way to confirm exact stats,
  thief has no identify)

## Skills known

- sneak (poor)
- pick lock (awful)
- **backstab (poor)** — practiced twice (2026-07-17) with both banked
  sessions; went awful -> poor after the first, display didn't visibly
  advance further after the second (may need more practice or a level-up
  for the next tier to show) — this is the thief's real combat skill

## Location

Standing in: The Secret Yard (thieves' guild practice room), back in
Midgaard — see `world.md` for the path in from the Newbie Zone if we head
out again.

## Inventory

- 3x bright green newbie vest (looted, not yet worn — already wearing a
  breast plate in that slot, these are just sell/junk items)
- a small sword (unwielded, swapped out for the dagger)
- a shiny newbie dagger (wielded)
- a danish pastry (unclear origin, probably starting inventory)
- (rest not yet recorded — run `inventory` and fill this in)

## Progress log

- 2026-07-17: Explored from The Bakery to the Thieves' Guild (see `world.md`
  for the path). Confirmed class is Thief, only skill is sneak (poor), and
  practice sessions are at 0 — leveling up is required before we can
  practice further.
- 2026-07-17: Found the Newbie Zone north of the city (via Temple of
  Midgaard -> Temple Altar -> countryside -> Great Field -> Entrance to the
  Newbie Zone). Killed 3 mobs as requested: 2x "creepy crawling thing" (33
  exp, 10g each) and 1x "the newbie monster" (150 exp, 20g, dropped a vest).
  Looted every corpse with `get all corpse`. Now at 672/1250 exp for level
  1->2, 22/24 HP, 73 gold.
- 2026-07-17: Kept grinding per user request ("keep grinding, exploring the
  newbie zone, until we get to level 2 ... larger goal is level 7 and
  fighting the minotaur"). Explored the full maze loop (it's a loop, not a
  dead end — west exit from the passage leads back out to the Great Field).
  Killed 3 more mobs: another "newbie monster" (149 exp, vest), a "creepy
  crawling thing" x2 (33 exp each, one in the guard's Small Room, one in "A
  Bright Hallway"), plus a "clueless newbie" variant (33 exp, the kill that
  triggered LEVEL 2). Reached level 2 at 1301 exp. Also: opened several
  closed doors revealing new rooms (see `world.md` for the extended map,
  including the Alchemist's Room and the level-7-warning sign guarding a
  stairway down — presumably toward the Minotaur).
  Near-miss: after killing a newbie monster in the guard's Small Room, the
  Newbie Guard auto-joined combat (like the city Peacekeepers do) even
  though it considers as "a lot of luck" — had to `flee`, which worked and
  cost no HP. Lesson: killing anything while an NPC guard/Peacekeeper is in
  the room can drag it into the fight even if you never targeted it.
  Also hit one non-code failure mode: a `send` occasionally comes back with
  `error: mud session is closed` (the daemon's connection died mid-request,
  a different failure mode than the ping-based auto-reconnect in `mud.py`
  catches) — recovered each time with a plain `mud.py start` + retry. Fixed
  this properly in `mud.py`'s `_send_with_reconnect`: it now also retries
  (with a forced daemon kill+restart) on that specific error shape, not
  just on outright connection failures.
- 2026-07-17: Ran `save` after reaching level 2 (per user request) —
  confirmed "Saving Dummy." Level 2 / 1301 exp / 123 gold is now persisted
  server-side, not just held in the live (flaky) connection.
- 2026-07-17: More grinding. Discovered the maze connects to a second
  cluster past A Nexus's north door: A Bright Hallway -> The Statue's Room
  -> The Hallway -> North/South Stairs (domed, decorated, has balcony `u`
  exits, unexplored) -> a Narrow Passage -> loops back into the Alchemist's
  Room from a second door. Killed: a "newbie monster" at the zone entrance
  (133 exp), a "clueless newbie" at South Stairs (33 exp), and picked up a
  "shiny newbie dagger" + a third vest as loot (dagger equipped, replacing
  the starting sword). Discovered a new dangerous mob: **"a VERY gaunt
  looking newbie... it looks like a zombie!"** in The Hallway — it's
  AGGRESSIVE (attacks unprovoked just for entering/lingering in the room),
  considers as "a lot of luck". First encounter: took 2 HP from the initial
  surprise hit, then fled successfully (2nd flee attempt; 1st failed with
  "PANIC! You couldn't escape!") while taking no further net damage.
  Second encounter: fought it all the way instead of fleeing, since combat
  trades looked favorable (no net HP loss for many rounds) — won it clean,
  dropping from 33 HP the whole fight to 31 HP, for **670 exp** (way more
  than any other single kill) and **this kill triggered LEVEL 3**. Also
  bought nothing yet but confirmed the shop/food situation is still
  low-priority (see below). Saved again after hitting level 3.
- 2026-07-17: Walked the full route back from deep in the Newbie Zone (The
  Hallway) to The Secret Yard per user request (~15 hops: through the
  Statue's Room/Nexus/Dirty Hallway/Beginning of Passage/Entrance, out to
  the Great Field, south through the Temple complex, into Midgaard, Common
  Square -> Dark Alley -> guild). Practiced backstab twice (both banked
  sessions) — awful -> poor. Ran `save` again to lock in the practice.

## Next steps

- 2179 exp needed for level 4. The zombiefied newbie is now a known
  high-value target (670 exp for one kill vs ~33-150 for everything else)
  — worth deliberately hunting in The Hallway if HP is full going in, but
  treat it seriously: `consider` still says "a lot of luck", we just got a
  clean run. Flee immediately if HP drops much below ~60%, and flee may
  need 2 attempts ("PANIC!" can fail once).
- Otherwise keep farming the known safe spawns: "a creepy little crawling
  thing" (perfect match, 33 exp) and the newbie-NPC variants — flavor text
  hints, but always `consider` to confirm: "looking terribly confused" (->
  "the clueless newbie" once engaged) and the plain "newbie monster" at the
  zone entrance/hallway = safe; "talking a lot", "wandering about
  aimlessly", "quite sure of himself", "annoying the hell out of you" = too
  strong ("a lot of luck" or worse) — skip these.
- AVOID: someone's little pet dragon ("a lot of luck and great equipment"),
  the Newbie Guard in the Small Room (a lot of luck, AND auto-joins fights
  in its room), the Newbie Alchemist ("do you feel lucky, punk?" — top
  tier). Do not go down the stairway behind the Alchemist's Room sign
  ("below level 7 and alone, or below level 4... bugger off") — that's
  almost certainly the Minotaur's territory and we are nowhere near ready.
- Backstab practice is DONE for now (0 sessions left, poor tier) — next
  practice opportunity comes with the next level-up's new session(s). Try
  using `backstab <target>` on the next tough fight (works best as a
  surprise opener before regular combat) to see how it performs in
  practice, and note the result here.
- We're back in Midgaard/The Secret Yard now — need to walk all the way
  back out to the Newbie Zone to resume grinding (see `world.md` quick
  path). Consider a quick Bakery stop on the way for food, since we're
  already in the city (see hunger/thirst note below) — cheap to bundle in
  now rather than a special trip later.
- Getting hungry/thirsty repeatedly during fights (ambient messages) —
  still hasn't visibly cost HP/stats, still low priority, but if it starts
  causing real penalties, buy food at the Bakery on the same trip back for
  practice (kill two birds with one walk).
- Re-check `score` after fights to keep level/hp/exp here current.
