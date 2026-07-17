1. An agent file with referenced files eg. AGENT.md, @~/docs/*.MD

Observations with Haiku:
- Coding harness will read local files, not pertaining to the loop.
- Sonnet 5 didn't engage in this behavior
- THe agent in the exmaple ended up creating temp file to create a socket connection and execute commands, we should be persistign a common interface for the mud eg. mug_manager

Observations with Sonnet 5: 
- Executed quickly and understood pathway, bought a Danish successfully
- Seemed to grok goal quickly, didn't explore files in the codebase, and took around 2-3 minutes to find the bakery, then grokked the next goal of listing the products and whether I wanted to buy.
- I was able to save successfully too after the purchase


## 2. Agent skills driven by main agent ~./.skills

- A very common way to drive specific functionality is via Agent Skills which is an open format for agents adopted 
- agent executed quickly and accurately with the skill to find the bakery.

### Observations
- The skill helped us get up and running, but we could still improve the overall flow by adding at least a scratchpad, and recording notes of the most efficient and common routes, useful npcs, etc.
- further skills we could expand would be a level-up skill (grind the newbie zone), eat-and-drink, explore, etc.
- Could be interesting to give it unique and varied goals: I want you to make a total blackguard thief, who when he can, does things to lower his alignment and morality at all times.
- I'm understanding how to make the loop autonomous, and this comes from us understanding what the flow of the game is. Grind newbie zone, on level up, return to guild to practice, then peruse market to by best equipment, and repeat
- using Sonnet 5 throughpout, has definitely been a good engine for the process, makes proper logical leaps when needed, has been cheaper than fable, which would be overkill for this type of a task
- it made a logical leap to trigger respaqwns in the newbie loop by going back to the field and coming back. I had it track it's time to optimize between loops as well
- We kept having disconnect errors, so it also self-optimized the mud.py script to preserve it's process.
- we have a good back and forth, where what I'm learning about the game compounds with its loop, and I'm deepening my own knowledge by asking it to play like my archetype (Sneak where you canb, using daggers, I'm a thief)
- upon level-up, it recorded in the player and world files lessons learned (high xp mobs, locations of good monsters, to speed up the loop)
- I also have it save after each level (applying my own rpg knowledge here, I play a lot of tabletop rpgs (Warhammer 40k dark heresy) and video game rpgs (You name them, I've played them, currently in a 135h rogue trader run))
- applying lessons I learned building with ElizaOS to give dummy the proper personality - thief with a heart of gold, basically based on the character from the book The Blacktongue Thief
- end of this session has been good, leveled up backstab twice, identified zombie as the highest newbie NPC to hunt, skill combo to open up the fight with