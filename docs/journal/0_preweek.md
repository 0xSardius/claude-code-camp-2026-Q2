# Preweek Technical Documentation

## Technical Goal
The technical goal of Preweek Explore is to determine how well do Agent Architectures fit our business use-case. 

## Technical Uncertainty
- We don't know what model will be best able to accomplish our goal/loop for the cheapest cost.
- I don't know what the right agentic pattern is to best accomplish our use case.
- We don't know if claude will be able to successfully navigate and complete the MUD loop.
- I'm uncertain that we will be able to get consistent and compounding results across loops.
- I'm uncertain whether the agent can be autonomous, or if it will need us in the loop.
- I'm uncertain whether the agent will be able to consistently connect to the MUD over time, or whether disconnects or other connection issues may hamper progress, or prevent us from saving.

## Technical Hypothesis
- I will be able to design an agent with claude code that will be able to successfully navigate tbaMUD, developer a pattern for leveling up, and role play a character successfully, to accomplish whatever arbitrary goal (within the confines of the game) that the user sets. This will be able to be accomplished by combining the reasonning capability of the Sonnet 5 model, custom skills, personality files, and a self-learning MD file to optimize lessons learned over time.

- I will have to design at least (1) custom skill in order to accomplish our goal, due to the specific nature of the game.

## Technical Observations
- Haiku encountered persistent issues, it created temp files to create a socket connection where it should be persisting a common interface for the MUD.
- Haiku went out of scope and burned time and tokens searching our own codebase on what to do, instead of keeping the goal within the confines of the loop.
- Haiku issues precipitated a switch to Sonnet 5. Sonnet executed quickly and understood task quickly and located the bakery in <3 minutes. It read us the list, and anticipated the next activity, initiating a purchase. I got it to successfully buy bread.
- Built a skill, play-mud, to help ease the process and get up and running faster. Play-mud creates a stateful telnet session and stays connected while moving, fighting, and chatting. This skill became a core part of the loop.
- First test with the skill was successful, and some connection drops caused Sonnet to modify the mud.py code to improve it's own session. I agreed with the upgrades and chose to keep them, as it improved dropped sessions and created a more stable environment for the agent to act in.
- Persistent memory was the next big upgrade for our process. I created a data/player.md and data/world.md files, and let the agent continue updating each with lessons learned to improve the compounding gains of our loops. Player.md records our goal, level, skills, gold, location, and a dated progress log for handling goals I give to claude. World.md shows discovered points of interest on the map and routes between locations, to tighten up our loops.
- After getting memory files, I worked on giving Sonnet a nice loop to reach out main goal: Reach level 7 and defeat the Minotaur. I asked it to go to the newbie zone and grind levels, recording lessons learned along the way.
- The leveling loop got tighter and more efficient over time. Sonnet retained memory of the pathway in the newbie zone, also discovered most efficient monsters to farm, and ways to reset the loop fast and make monsters respawn. All of these were recorded for future sessions.
- The best and most interesting gains came from when I started getting Sonnet to roleplay it's loop as a thief and having a thief personality. It became efficient at executing the loop, and using unique thief skills to accomplish the goals.
- My own technical knowledge of RPGs and game mechanics helped us improve the loop, working with Sonnet to iterate on the most efficient leveling route, practice route, looting and equipment analysis route, plus saving after gaining levels. This created a tight system within our memory files and agentic loop.

## Technical Conclusions
- Sonnet 5 was the correct engine for the loop, Haiku was not.
- Sonnet engaged in helpful logic leaps that allowed us to efficiently accomplish our goal, and intuit the next steps
- A custom skill was necessary to accomplish our goal, confirming our hypothesis. Independent tool calls created problems with our connection, and Sonnet optimized for these within the skill to create a stable play session.
- The plain agent approach is the wrong approach for this project, and skills + persistent memory proved to be the right architecture for this stage.
- The biggest finding was that persistent memory via markdown files allowed the loop to be autonomous and compounding, allowing us to efficiently reach level 4 with no errors.
- Loops measurably tightened over sessions, as better lessons were learned and recorded, with fast routes, optimizations, and skill combos playing into the successful loops.
- Score became a source of truth in-game that the memory files reconciled against to avoid drift.
- The agent can self-optimize its own tooling. Sonnet modified mud.py to preserve its process and auto-reconnect/retry, an improvement I chose to keep. 
- Autonomy is achieveable, however, it emerged through iteration and human-in-the-loop was key here. I helped articulate to Sonnet the loop as: grind newbie zone, loot, level-up, save, return to guild to practice, shop for better gear, repeat, while recording lessons learned and efficient routes, and the system began to really scale through that intelligent iteration together.
- Personality improved performance, not just flavor. Framing the character as a thief (sneaking, backstabbing difficult enemies, favoring daggers), made the agent pick up more efficient, archetype-specific tactics. This was a lesson I learned previously building ElizaOS agents where the personality file is key, and it paid dividends in this context.
- Human-in-the-loop knowledge compounds with the agent's memory, logical leaps, and technical abilities. The tightest gains came from the back and forth: What I knew about the game fed the agent files, which tightened it's loop, which taught me more, and so forth.

## Key Takeaway
- A cheap, but capable model (Sonnet 5) + a single well designed stateful skill + persistent files for compounding memory is sufficient to turn an agent into an autonomous, self-improving MUD player, with connection instability being the main constraint, itself solveable within the aforementioned loop.