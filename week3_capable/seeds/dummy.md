# Prior notes for `dummy`, carried over from week0's play-mud skill

Curated from `week0_explore/explore_architecture/02_agent_skills/.claude/skills/
play-mud/data/{player,world}.md`, which is where this character's first four
levels were earned.

These are CLAIMS, not facts the loop trusts. They land in `facts.md`, which the
model reads and judges, and nothing here is written into `trails.json` — the map
stays built from edges the agent walked itself, so `travel` can still be trusted
mechanically. A route below is a hint about where to walk, not a route the loop
will follow blind.

Anything that turns out to be wrong should be corrected with `remember_learning`
in the normal way. Some of it is already old: the equipment list was accurate on
2026-07-26 and the shop prices were canvassed 2026-07-18.

## Who this character is

- I am Dummy, a Thief. I play like one: backstab as an opener when I am hidden
  and the target has not noticed me, sneak to move without being seen, and I
  pick fights I can win rather than trading blows toe-to-toe.
- Skills known as of week0: sneak (poor), pick lock (awful), backstab (poor).
- Backstab at "poor" missed twice in a row against easy mobs on 2026-07-18. It
  is worth practising further before leaning on it as the main opener.
- This MUD build has no dual-wielding. `wield` allows one weapon only, there is
  no dual-wield skill on the Thief tree, and the DUALWIELD help topic is a stub.

## Equipment (accurate as of 2026-07-26)

- Wielding a shiny newbie dagger (glowing aura); holding a metal staff.
- Wearing a full kit: breast plate, leather cap, bronze leggings, leather boots,
  gloves, sleeves, shield, brown leather cape, old leather belt, two leather
  wristguards, two leather rings, two leather gorgets, a candle for light.
- Spares in inventory: 3 shiny newbie daggers, a glowing newbie mace, cool newbie
  leggings and sleeves, 3 bright green newbie vests, a small sword.
- I carry a scroll of recall (bought for 243g). `recite scroll of recall`
  teleports me back to the hometown sanctuary. It is the emergency escape, and
  it matters because `flee` can fail — "PANIC! You couldn't escape!" has happened.

## Shops

- The Bakery (Main Street east segment, north side): danish 7g, bread 14g,
  waybread 74g, unlimited stock. Cheapest way to clear "You are hungry".
- The Armory (Main Street east segment, south side): armor only. It will not buy
  weapons or junk, and offered 0g for a spare vest. Leather-tier gear I already
  own makes most of its stock a downgrade; the real upgrades are bronze gloves,
  sleeves or cap (222-444g) and chain mail or studded leather (317-1268g).
- The Magic Shop (Main Street west segment, north side): a wizard, but the goods
  work for any class — scrolls via `recite`, potions via `quaff`. Scroll of
  recall 243g, wand of invisibility 486g, potion of see invisible 486g, scroll
  of identify 6078g.
- The Grunting Boar (bar, in the Grunting Boar Inn): ale 11g clears "You are
  thirsty". Local speciality 23g, beer 23g, firebreather 58g.
- No shop haggles or gives credit. `list` for stock, `value <item>` for what they
  would pay, then `buy` or `sell`.

## Fighting and looting

- Loot promptly. A corpse left too long is eaten: "A quivering horde of maggots
  consumes the corpse of the X."
- With several corpses in a room, `get all corpse` keeps grabbing the same first
  match. Use an ordinal: `get all 2.corpse`, `get all 3.corpse`.
- A "newbie monster" in the Newbie Zone is worth roughly 150 exp and often drops
  a vest.
- The zombiefied newbie in The Hallway is worth 670 exp, but it does not reliably
  respawn — treat it as a bonus if it is there, not a plan.
- The Newbie Guard's room forces a fight on entry. Do not walk in casually.
- Someone's little pet dragon wanders the whole maze and has never attacked
  unprovoked, but `consider` says it would take "a lot of luck and great
  equipment". Its presence is safe; fighting it is not.

## Routes worth trying (walk them to confirm — they are hints, not a map)

- Bakery to the Thieves' Guild practice room: s, e, s, e, s, e, s — through Main
  Street, Market Square, Common Square, Dark Alley, Entrance Hall, Thieves' Bar,
  Secret Yard.
- Bakery to the Newbie Zone (A Brighter Hallway): s, e, n, n, n, n, n, n, e, n,
  e, e, s, s, w — 15 hops, each confirmed by a look during the original walk.
