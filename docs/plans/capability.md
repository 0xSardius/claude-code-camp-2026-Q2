# Notes on Capability

## Initial Findings / Questions

- Is brute forcing pathing using deterministic code "capable?"
- Algorithmic: Keep taking the first unexplored doorway you see, and whenever you hit a dead end, retrace your steps and try the next one. No regard if its label is lava pit walk it.
- Agentic: Walk each step and reason where you are going based on possible exits descriptions, asking people around you. Consider the scope of search, if you are walking into a dangerous location. The cost of your travel.
- Reasoning is important to accomplishing this loop
- Don't really know if your initial plans until measured
- Focus on the task and keep varying and wrangle your systems and subsystems. Leave the goal for later. This tracks with my extensive experience programming onchain agents, it is often a iterative process of discovery that takes you places you didn't originally think you would go


### Baseline loop
- Reasons on every step
- high cost per action
- weak or inconsistent memory
- repeats mistakes
- makes short-sighted choices
- no reliable planning
- easily loops or gets stuck
- poor verifiction of progress

### Capable loop (On Paper)
- Reasoning at every step
- High token cost
- high latency
- no distinction between judgment and routine work
- design tax is hidden until the loop is implemented and measured

## Agentic Engineering Loop
- INstead of brute force guessing, we create a map in memory and reference it to keep token costs down
- Ensuring we are not over-relying and brute forcing actions
- brute forcing here means not just displaying all actions for every opportunity, and then running through and trying them one by one until something works. We want to preserve intelligent loops that both efficiently accomplish our goal, and keep token costs reasonable
- Ensuring memory is utilized every time and there aren't gaps.
- Intelligently extrapolating which locations go to which places, remembering optimal routes
- Skill usage, resource management, inventory management, combat, leveling, character progression, sleeping, eating, drinking, movement, all are different systems we need incorporated into the loop
- building discreet plan.md's for our different loops and systems can be a way to architect the system, suggested by A. Brown. For instance, combat file, movement, etc. AB will typically start things off along with some of his own ideas and direction in the file, an

## Testing
- We need extensive testing for all of our systems within our agentic loop
