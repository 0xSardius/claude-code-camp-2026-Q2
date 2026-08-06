# Week 2 Technical Documentation

## Technical Goal
Build an agent architecture that can perceive, understand, decide, act, remember, and recover.

## Technical Uncertainty
- If we can brute force pathing using deterministic code, is that capable?
- Do we need to solve all possible tasks first as defined scenarios in our test suite system, because goal decompisition will turn into these task prompts?
- What should tasks look like, how should they be represented?
- How do we reprioritize task as we work?
- Does the mapping of task strongly correlate with real tool call names and availability?


## Technical Hypothesis
- Our existing memory structure will be able to be scaled to create loops for our different systems and reach our goal of hitting level 7 and finding the minotaur
- That hardening 3 critical systems (naviagtion, combat, and recovery) will be enough to ship the MVP agentic loop, and we can scale up with lessons learned if necessary

## Technical Observations
- Note: my initial observations from preweek video are located in the plans/week3/capability.md file
- I chose to initially fix areas with brittle stuff from last week first (deterministic pathing, explicit STOP commands)
- I also chose to harden 3 critical subsystems first (nav, combat, recovery) so I don't go crazy out of scope and bogged down
- getting some ridiculous jargon from claude that makes it hard to understand what it is actually doing, this has been a challenge in this project. Had to make a rule to stop all the slopus witticisms... it was one too "corpus" and "load-bearing spine" too many.
- Ran into some issues with the MUD login breaking that were unrealted to boukensha. I did some tests to confirm this while running overall dry testing of the initial harness.
- Testing Look provided good lessons to the economy tool.
- Changed our dry run suite to count actions instead of cycles, improving and giving more granular data for our test suite
- Improved our walking loop.
- having some challenges with opus 5 just spewing total slop and being afraid to get ambitious and hit goals. Had to course correct and get him on a more... effective track. This model is strange because he seems to be overly cautious, flat out telling me things can't be accomplished. This has been a difficult barrier, and I have to elucidate... more ambitious and specific instructions.
- I was able to apply some of the lessons from week0 to improive the results we were getting in our autonomous loop. He tracked down the bakery, read the list, and bought something. Now to expand and go deeper to do the leveling loop.
- Discovered some errors where resting did nothing but repetitive checking every 3 seconds, burning tokens. Now the loop actually waits 20 seconds between checks, for better observability and recovery.
- RThe loop can be given a real job, and any task in plain english, will report finished by calling a tool to report
- We utilized some of the lessons we gained in week0 from training duymmy in the early loop into memory that helped create a framework for future agentic memory.
- We found a bug in the way we were building maps and memory, and then buidl a rewrite around ti.
- 8/5 focused on perfecting our grind loop, and getting the agent to play as our character.
- We had a great move where in memory it was noticed that backstab worked well on a certain monster (creepy little crawling things) and autonomously created a better hunting loop and skill usage. Great stuff. Levled up to level 5 in this loop alone
- - Two grind runs in a row got us nothing, and it turned out the loop was fine. He swept
  the hunting ground, found it empty, said so, and passed on the one mob that was there
  because it wasn't worth the risk. The actual problem was that he had written himself a
  note days earlier saying the hallway loop was a good safe farm, which was true at the
  time, and then kept going back to it. His own memory put him in a rut.
- Went and read the MUD's world files myself and found the zone has 41 rooms and he only
  knew 8 of them. Everything worth killing spawns in rooms he'd never walked into. Told
  him the ground was farmed out and the good stuff was deeper in, and that was it — no
  code change, +1557 exp on the very next run.
- The training subsystem had been dead code the whole week and nobody noticed. It fired
  on "experience needed to level is zero", which literally never happens in this MUD
  because you level the second you earn it. Switched it to check unspent practice
  sessions instead and it worked first try — backstab went poor to average.
- Lost the best run of the week to a dumb launcher bug that deleted the log every time a
  new run started. 1557 exp and the only cost-per-experience number we had, gone, and
  then committed over the top. Only about $0.45 of roughly $5 spent this week is still on
  disk. Logs are one file per run now and never deleted.
- Found the Minotaur sitting in room 18629, same zone we've been farming this whole time.
- Hit level 5 on the last run. +1683 exp in five cycles, and the judgment ratio finally
  came in at 50% — 105 model actions against 106 mechanical ones. It was 100% at the
  start of the week when I was still counting the wrong thing.
- Best moment of the week: he'd flagged the pet dragon as too dangerous at level 4, which
  was correct at the time. After hitting level 5 he went back, re-checked it, found it
  now considers "fairly easy", killed it for +429 exp, and rewrote his own note to say
  it's a farm target now. That's the stale memory problem solving itself without me doing
  anything.

## Technical Conclusions
- It required significant rigor to get claude to stop assuming things it believed to be true, and then actually verifying them and building systems around them.
- The tests never once caught a real bug. Every single one came from running it live. The
  157 tests are still worth having because they let me change the driver four times in an
  evening without breaking it, but they were never going to tell me the loop deadlocks at
  44% health or that the hunting ground is empty.
- Memory that helped you can start hurting you. The note that sent him back to a farmed-out
  loop was correct when he wrote it. Nothing in the system ages a fact or asks if it's
  still true, and that cost us two runs. He did eventually fix one case of it himself by
  re-checking the dragon after leveling, which is the behaviour you'd want everywhere.
- Deterministic code is fine as long as the knowledge under it was earned. Walking a saved
  route is just an algorithm, but every edge in that map came from actually walking it.
  Seeding his old week0 notes worked great — the bread price was still right. Seeding the
  map would have baked in a bug I hadn't found yet.
- Our substystems all seemed to break for the same reason. Something Claude believed was a fact was something that was
  never checked. The metric, the login, the rest loop, the training trigger, the
  map keys, all had similar problems spaces


## Key Takeaway

Most of building an agent loop turned out to be bookkeeping about what it actually knows.
Getting it to act was never the hard part. The hard part was making sure that what it
believed about its health, where it was standing, whether it was making progress, and
whether its own notes were still true actually matched the world. Every bug this week
lived in that gap.

The five retrospective questions

Was the technical goal possible?
Yes. He perceives, decides, acts, remembers and recovers, and we ran 19 unattended cycles that
included resting autonomously, and then resuming work. Got dummy from level 4 to
level 5, bought and ate food on command, priced up the weapon shop, trained at the guild.
Didn't get to level 7 or the Minotaur, but the plan said the bar was a system that could,
and I think we cleared that.

If not, how long would it have taken?
Level 5 took about four grind runs once the loop actually worked. Levels get more
expensive as you climb, so level 7 is probably another 10-15 runs. A few more days, not a
different project.

Would it have been worth the time and money?
The money is nothing. Roughly $5 in model calls for the whole week, and $0.0006 per point
of experience by the end. All the time went into finding bugs that show up in prod.

What breaks first under real use?
Stale memory, easily. Nothing ages or re-checks a fact, so a note that was true turns into
a rut. Second is the map only recording edges in the direction you walked, so every trip
home is unmapped the first time and you pay for it again.

What did we learn about engineering agent loops?
Put the judgment where the judgment actually is and let everything else run mechanically.
Measure it per action and not per turn or the number will flatter you — mine said 100%
model-driven while the code was already doing most of the work for free. And run it live
early, because the offline tests will happily pass while the loop sits there deadlocked.

Can I apply things from this project to other projects?
This bootcamp has been a game changer for me. I primarily build agents onchain on Solana, and it is an
extremely adverserial environment. It is basically a big MMO with real money and PvP in play. I'm building
agents around prediction markets, and this has been invaluable in introducing technical rigor in the agents I build,
and I I've seen a clear level up for my work. Paritcularly observability has been helpful.