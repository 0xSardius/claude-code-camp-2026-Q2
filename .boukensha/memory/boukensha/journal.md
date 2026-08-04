# boukensha

_Generated 2026-08-04 from recorded state. Numbers in this section are rendered from the store, not written by the agent._

## Status
- **Level:** 1
- **HP:** 7/25
- **Experience:** 294
- **Gold:** 30
- **Last seen:** Poor Alley
- **Rooms known:** 12
- **Routes walked:** 17

## What it knows

- The Bakery in Midgaard is located north of Main Street, which is west of Market Square (which is south of Temple Square, south of Temple of Midgaard). Route from Temple of Midgaard: south, south, west, north.
- The Bakery in Midgaard sells: a danish pastry (7 coins, unlimited), a bread (14 coins, unlimited), and a waybread (71 coins, unlimited).
- Confirmed again: The Bakery in Midgaard (north of Main Street, which is west of Market Square) sells: a danish pastry (7 coins, unlimited), a bread (14 coins, unlimited), a waybread (71 coins, unlimited).
- The Eastern End Of Poor Alley (west of Common Square, east of Poor Alley) sometimes has an 'odif yltsaeb' mob - a joke/mirror version of the beastly fido (name reversed), full HP, considered 'perfect match' at level 1. Poor Alley itself (further west) has a harmless beggar.
- Poor Alley (west of Eastern End Of Poor Alley) has its own beggar mob following the same escalating stun/revive pattern as the Grubby Inn beggar. Fleeing west from Poor Alley leads to a new room called Wall Road (next to the western city wall, exits north/east/south, with some letters written on the wall).

## What it has learned

- [2026-08-02] Danger: attacking the beastly fido near the city gate (west of Main Street) also draws the cityguard standing in that room into the fight — the guard's hits are brutal (took me from 25 to 4 HP in one exchange). Avoid fighting anything in a room where a cityguard is present; find mobs in guard-free rooms instead.
- [2026-08-02] Fighting bare-fisted (no weapon equipped) leads to very low hit rate - many rounds end in "You wildly punch at the air, missing" against even weak mobs like fidos. Should get a weapon equipped ASAP (buy/find one) to improve combat efficiency and reduce risky prolonged fights.
- [2026-08-02] The odif yltsaeb mob in Grubby Inn (near Poor Alley area) is an easy kill (1-3 rounds bare-fisted, minor damage taken) and gives 2-3 exp; good repeatable target at level 1. It leaves no corpse/loot though.
- [2026-08-02] The beastly fido in Grubby Inn is tougher than expected bare-fisted - 15 rounds without killing it, dropped my health to 64%, and it fled rather than dying. Avoid re-engaging fido bare-handed; needs a weapon or better tactics.
- [2026-08-02] The beggar in Grubby Inn is a repeatable, escalating fight: each "kill" actually just stuns/wounds it further (small exp each time, 1-7), and it keeps reviving and re-engaging in the same room. The final real kill (after several stuns) gave a big +40 exp payout and dropped 10 gold coins. Worth repeating this loop at level 1 - very safe (health stayed 70-100% throughout) and lucrative for a low-level thief.
- [2026-08-02] The odif yltsaeb mob follows the same escalating stun/revive pattern as the beggar: repeated small-exp knockdowns (2-5 exp) followed by a final "mortally wounded" kill worth a big payout (+47 exp seen). Corpse from odif yltsaeb had no lootable items though (unlike the beggar's gold).
- [2026-08-02] A 'Peacekeeper' guard-type NPC can spawn in The Eastern End Of Poor Alley alongside the fido - same danger class as a cityguard. Check the room for guard/peacekeeper NPCs before engaging anything there; retreat if one is present.
- [2026-08-04] The beggar in Grubby Inn is not actually low-risk if you chain engage() calls back-to-back without pausing: 5-6 consecutive rounds took me from 100% to 44% HP before the final 'mortally wounded' kill landed. Consider pausing/resting between stun-rounds rather than chaining engage repeatedly, or stop earlier once below ~60% HP.
- [2026-08-04] Confirmed: the beggar's final death (after the 'mortally wounded' state) pays out its big exp bonus (+47 exp seen) even on a later turn/check after the last engage() call reported only a small per-round gain -- the kill resolves asynchronously, so don't be surprised if score check later shows a big jump you didn't directly trigger.
- [2026-08-04] Decided to skip re-engaging the beastly fido at Eastern End Of Poor Alley while starting HP was only 56% -- even though consider said 'perfect match', past experience shows this fido eats 15+ rounds bare-fisted and doesn't die (flees instead), so it's not worth the HP gamble when not starting at full health. Better to wait for the beggar corpse in Grubby Inn to respawn/revive, or recover HP first.
- [2026-08-04] The Eastern End Of Poor Alley can spawn an 'oozing green gelatinous blob' alongside the fido - consider on the blob returned 'You ARE mad!' (extremely dangerous, avoid). Since multiple hostile mobs in the same room can potentially join a fight, do not engage the fido here while the blob is also present - too risky. Retreat and look elsewhere until the room clears.
- [2026-08-04] The Poor Alley beggar (not just the Grubby Inn one) drops a 'key of dull metal' along with gold on its final kill after the stun/revive sequence - worth checking what that key opens.
- [2026-08-04] Killing 'a fido' at Eastern End of Poor Alley doesn't always clear the room - after an engage() reported KILL and +37 exp, another (or the same) fido was still shown 'fighting YOU' in the room moments later, forcing a flee. There may be multiple fido spawns or the kill message can be stale/misleading. Be ready to flee immediately after any 'KILL' report in this room rather than assuming the fight is over.
- [2026-08-04] The odif yltsaeb follows the exact same stun/revive/final-kill pattern as the beggar - multiple small engage() kills (2-9 exp each) before it finally leaves a corpse. HP stayed rock-steady at 56% through the whole 4-round sequence, so it's very safe to chain-fight even without pausing, unlike the beggar which drained HP faster.
- [2026-08-04] Unlike the odif yltsaeb (HP stayed steady through its stun/revive cycle), the beastly fido's stun/revive cycle at Eastern End of Poor Alley DOES drain HP noticeably each round (56%->52%->48%->44% over 2 engage calls). Treat fido re-engagement more cautiously than odif yltsaeb - flee once below ~45% rather than chaining further.
- [2026-08-04] At Eastern End of Poor Alley, engaging the fido a second time right after a kill is risky if starting HP is already ~40%: it dropped me from 40% to 28% in a couple rounds. Flee threshold of 35% should be respected strictly here rather than trying one more consider+engage.
