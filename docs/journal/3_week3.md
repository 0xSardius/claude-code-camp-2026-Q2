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

## Technical Conclusions


## Key Takeaway