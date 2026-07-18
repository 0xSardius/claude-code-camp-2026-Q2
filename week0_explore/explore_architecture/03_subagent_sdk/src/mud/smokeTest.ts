// Milestone 2 smoke test: prove the ported connection layer works against
// the live MUD before wiring up any SDK agent on top of it. Not part of
// the eventual agent loop -- just a one-off verification script.
import { MudSession } from "./connection.js";

const host = process.env.MUD_HOST ?? "localhost";
const port = Number(process.env.MUD_PORT ?? "4000");
const username = process.env.MUD_USERNAME ?? "balthasar";
const password = process.env.MUD_PASSWORD ?? "magicman";

async function main() {
  const session = new MudSession(host, port, username, password);
  console.log(`connecting to ${host}:${port} as ${username}...`);
  await session.connect();
  console.log("connected + logged in");

  const look = await session.send("look", { mode: "quiet", quietMs: 800 });
  console.log("--- look ---");
  console.log(look);

  const score = await session.send("score", { mode: "quiet", quietMs: 800 });
  console.log("--- score ---");
  console.log(score);

  await session.close();
  console.log("closed cleanly");
}

main().catch((err) => {
  console.error("smoke test failed:", err);
  process.exit(1);
});
