// Entry point. Runs every character in the registry as an independent,
// concurrent agent loop -- this is the capability 02_agent_skills can't
// offer (one interactive chat = one character at a time). Add more entries
// to `characters` in characters.ts to pilot more characters in one run.
import { characters } from "./characters.js";
import { runCharacterAgent } from "./agents/characterAgent.js";

async function main() {
  console.log(`Launching ${characters.length} character agent(s) concurrently: ${characters.map((c) => c.displayName).join(", ")}`);

  const results = await Promise.allSettled(characters.map((c) => runCharacterAgent(c)));

  console.log("\n=== Summary ===");
  results.forEach((r, i) => {
    const name = characters[i].displayName;
    if (r.status === "fulfilled") {
      console.log(`${name}: ${r.value.numTurns} turns, $${r.value.totalCostUsd.toFixed(4)} — ${r.value.finalResult}`);
    } else {
      console.log(`${name}: FAILED — ${r.reason}`);
    }
  });
}

main().catch((err) => {
  console.error("orchestrator failed:", err);
  process.exit(1);
});
