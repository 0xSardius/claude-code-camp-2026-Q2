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
- Level: 3 (leveled up 2026-07-17; next sub-goal is level 4)
- HP: 44/44 max (regenerates over time/rest)
- Moves: 51/90 — fine, not a concern
- Exp: 4445 (**555 more needed for level 4** — very close)
- Practice sessions remaining: **0** (both spent on backstab; more will
  come with the next level-up)
- Gold: 139
- Wielding: a shiny newbie dagger (has a glowing aura, likely enchanted —
  swapped from the starting small sword; no way to confirm exact stats,
  thief has no identify). Have two more unwielded shiny newbie daggers now
  (3 total, third one looted 2026-07-18) — spares/sell fodder. **Confirmed
  2026-07-18: this MUD build does not support dual-wielding** — `wield`
  only allows one weapon ("You're already wielding a weapon"), no
  dual-wield skill exists on the Thief tree (`help skills` shows:
  Sneak/Pick Lock/Backstab/Steal/Hide/Track only), and the DUALWIELD help
  topic is an unimplemented stub.
- **A scroll of recall** (bought 2026-07-18, 243g) — `recite scroll of
  recall` teleports back to hometown sanctuary. Emergency-escape backup
  now that we know `flee` can fail once before succeeding. Not yet tested
  in an actual emergency.
- **AC audit (2026-07-18, real tested numbers, not guesses)**: baseline
  AC 9/10 with full gear on. Leather gloves = -3 AC, leather sleeves =
  -2 AC, leather cap = -6 AC, breast plate = **-21 AC** (by far our
  biggest piece). See Next steps for what this means for future Armory
  purchases.

## Skills known

- sneak (poor)
- pick lock (awful)
- **backstab (poor)** — tried a couple of times as a combat opener
  (2026-07-18) and missed both times ("quickly avoids your backstab and
  you nearly cut your own finger") — at "poor" tier it doesn't seem
  reliable yet against even easy mobs. Worth more practice sessions before
  leaning on it as a real opener.

## Location

Standing in: The End Of The Passage, Newbie Zone (west end of the main
hallway loop, near the field exit) — see `world.md` for the path back to
Midgaard/the guild if needed. Logged out cleanly here 2026-07-18 (`save`
confirmed, then `mud.py stop`), so this is exactly where the next session
picks up.

## Inventory

- 3x bright green newbie vest (looted, not yet worn — already wearing a
  breast plate in that slot, and the Armory confirmed these are worthless
  to sell too: "I'll give you 0 gold coins for that!" — pure junk/RP
  trophies at this point, consider just dropping them)
- a small sword (unwielded, swapped out for the dagger)
- a shiny newbie dagger (wielded)
- two more shiny newbie daggers (unwielded, spares — can't dual-wield, see above)
- a scroll of recall
- an empty bottle (from the ale, junk, can drop)
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
- 2026-07-18: Logged Balthasar (the `03_subagent_sdk` character) out and
  switched back to Dummy per user request, to resume the level-4 grind.
  Walked the full route back out from The Secret Yard to the Newbie Zone
  (same ~15-hop path, still accurate). Went hunting for the zombiefied
  newbie specifically (670 exp target) — checked The Hallway repeatedly
  across several laps of the maze and it never respawned this whole
  session; only saw the two "too strong" newbie flavor variants there
  each time. Gave up waiting on it and farmed the reliable safe spawns
  instead: 2x creepy crawler, 3x newbie monster, 1x clueless newbie (found
  via the previously-unexplored Narrow Passage south of The South Stairs).
  Tried `backstab` twice as a fight opener — missed both times at "poor"
  tier, not reliable yet. Discovered `get all <N>.corpse` (ordinal prefix)
  to loot a *specific* corpse when multiple are in the room and `get all
  corpse` keeps grabbing the same (often already-empty) one. Also noted
  corpses get eaten by "a quivering horde of maggots" after a while if not
  looted promptly. Net this session: 2821 -> 3730 exp (+909), 233 -> 313
  gold (+80), picked up a second shiny newbie dagger. Did not level up or
  reach the zombie this time — pure incremental grind session.
- 2026-07-18: Market-and-train loop per user request. 0 practice sessions
  available (no level-up since last check), so no backstab training this
  trip — noted for when sessions come back. Canvassed every merchant found
  in Midgaard: The Bakery (already known), **The Armory** (armor only,
  full price list recorded), **The Magic Shop** (scrolls/wands/potions,
  usable by any class, full price list recorded), **The Grunting Boar**
  bar (drinks, full price list recorded). Full listings in `world.md`
  `## Shops`. Top-5 analysis against our current gear/goals:
  1. **Scroll of recall (243g, Magic Shop)** — bought. Best value: backup
     escape plan now that we know `flee` can fail once.
  2. Bronze gauntlets (222g, Armory) — real upgrade over our current
     leather gloves. Didn't buy (budget conflicted with the scroll this
     trip) — next gold windfall.
  3. Chain mail shirt / scale mail / studded leather (317-1268g, Armory,
     body slot) — real upgrade over our current breast plate if the price
     tier reflects actual AC (unconfirmed, no identify) — longer-term goal.
  4. Gray wand of invisibility (486g, Magic Shop) — could let us slip past
     guarded rooms (Newbie Guard, Alchemist) without a fight, thief-
     appropriate and relevant to eventually reaching the Minotaur —
     longer-term goal.
  5. Cheap food/drink (danish 7g Bakery + ale 11g Grunting Boar, ~18g
     total) — bought/consumed (used an already-owned danish + bought one
     ale). Confirmed this clears both the "You are hungry" and "You are
     thirsty" status lines.
  Also confirmed dual-wielding is NOT possible in this build (see
  Character section above) while checking whether the spare dagger was
  worth wielding as a second weapon. Also confirmed the Armory won't buy
  our vest stockpile (offered 0g). Spent 254g total (243 scroll + 11 ale):
  313 -> 59 gold. Saved after the shopping trip.
- 2026-07-18: User asked whether the Armory upgrades are "definite"
  upgrades — they're not, we have no way to inspect shop-stock stats
  (`examine`/`compare` on shop items just says "nothing special";
  `compare` is an unimplemented stub like `dualwield`; identify scroll is
  6078g, unaffordable). Instead ran a free empirical test: removed each
  currently-worn piece one at a time and diffed `score`'s AC line
  (baseline 9/10), then re-wore it immediately. Real, confirmed AC values
  for our CURRENT gear:
  - leather gloves: **-3 AC**
  - leather sleeves: **-2 AC**
  - leather cap: **-6 AC**
  - breast plate: **-21 AC** (dominates everything else combined)
  Didn't isolate the rest of the kit (rings/gorgets/leggings/boots/
  shield/cape/belt/wristguards) — same technique works if we want those
  numbers later. Conclusion: our current (free, looted) gear is already
  contributing a lot of AC, so the accessory-slot bronze upgrades
  (gloves/sleeves, 222g each) are probably a mediocre AC-per-gold trade;
  the body slot is by far the highest-leverage place to spend if/when we
  test an Armory upgrade, since it's already worth -21 AC alone and the
  price tiers above it (chain mail 317g, studded leather 634g, bronze
  breast plate 888g, scale mail 1268g) all target the same slot.
- 2026-07-18: Resumed grinding toward level 4 after the shopping/AC-audit
  detour. Killed: a newbie monster (135 exp) near the zone entrance, a
  creepy crawler (33 exp) at A Nexus, a newbie monster (138 exp) at
  Another Corner (picked up a 3rd shiny newbie dagger), a creepy crawler
  (33 exp) at The End Of The Passage, and a clueless newbie (33 exp) at
  The North Stairs. Then hit a genuinely dry stretch — several full laps
  of the maze with nothing but tough "skip" mobs and the wandering dragon
  (confirmed again: the dragon has never once been aggressive across many
  sightings, safe to ignore). Tried the Newbie Guard's Small Room again as
  a deliberate risk: two creepy crawlers were there, killed both back to
  back (the second kill auto-chained from the first) without the guard
  ever reacting, then fled immediately after per our safety rule (68 exp,
  10g). This dropped us from 682 to 555 exp needed for level 4. Also
  confirmed a real (not just reconnect-artifact) shortcut: The South
  Stairs connects directly to a second "A Bright Hallway" room to its
  west (distinct from the one north of A Nexus) — the ambiguity noted in
  an earlier session is resolved, this is a real, repeatable connection.
  Paused here per user request: `save` confirmed ("Saving Dummy."), then
  `mud.py stop` for a clean logout. Net this session (including the
  market/AC-audit detour): 3730 -> 4445 exp (+715), 313 -> 139 gold
  (net -174 after the scroll/ale purchases and all the loot from grinding).

## Next steps

- 555 exp needed for level 4 — very close, should take just 2-4 more easy
  kills next session. Keep farming the reliable safe spawns
  ("creepy crawling thing" = perfect/easy match, the "newbie monster" /
  "looking terribly confused" -> "clueless newbie" variants = easy/fairly
  easy). Always `consider` first regardless of flavor text.
- The zombiefied newbie (670 exp, in The Hallway) is still the best payout
  in the zone if found, but it did NOT respawn at all during a full
  2026-07-18 session of repeated laps — its respawn timer may be much
  longer than the regular trash mobs, or it's on some other trigger. Don't
  bank on finding it every session; treat regular farming as the reliable
  baseline and the zombie as a bonus if it happens to be up.
- AVOID: someone's little pet dragon ("a lot of luck and great equipment"
  — seen wandering the maze constantly this session but never engaged, it
  doesn't appear to be aggressive on its own), the Newbie Guard in the
  Small Room (a lot of luck, AND auto-joins fights in its room), the
  Newbie Alchemist ("do you feel lucky, punk?" — top tier). Do not go down
  the stairway behind the Alchemist's Room sign ("below level 7 and alone,
  or below level 4... bugger off") — that's almost certainly the
  Minotaur's territory and we are nowhere near ready.
- Backstab at "poor" tier missed both attempts this session — don't rely
  on it yet as an opener; regular `kill` is still the workhorse. Revisit
  once more practice sessions are available (next level-up) and it's had
  a chance to reach at least "fair".
- Moves are at 83/90 — regenerated well, no concern.
- Currently at 59 gold. Save-toward wishlist, RE-RANKED after the AC audit
  above (see `world.md` `## Shops` for full price lists): chain mail shirt
  (317g, Armory, body slot — highest leverage since our current breast
  plate alone is worth -21 AC, more than every other tested piece
  combined) > gray wand of invisibility (486g, Magic Shop, could bypass
  guarded rooms without a fight) > bronze gauntlets (222g, Armory —
  deprioritized: our leather gloves are only worth -3 AC, so the
  ceiling on this upgrade is small no matter what bronze offers) > scroll
  of identify (6078g, Magic Shop, would finally confirm the dagger's real
  stats — long shot). Grinding for exp naturally generates gold too, so
  this mostly resolves itself while working toward level 4.
- Hunger/thirst nags are cleared for now (ale + danish, 2026-07-18) — will
  come back eventually; cheap fix (~18g at the Bakery/Grunting Boar) when
  they do.
- We're at The Magic Shop (Main Street west segment) — need to walk back
  out to the Newbie Zone to resume grinding (see `world.md` quick path;
  note the path now starts from a different point in Midgaard than the
  Bakery-based one recorded there).
- Re-check `score` after fights to keep level/hp/exp here current.
