// Runs ONE character's autonomous agent loop: connect its MudSession, wire
// up its own MCP tool server (mud_send/mud_save/memory_read/memory_write),
// and drive an SDK query() to completion. orchestrator.ts can run several
// of these concurrently -- each call here is fully self-contained (own
// socket, own tools, own memory dir), which is what makes that safe.
import { query } from "@anthropic-ai/claude-agent-sdk";
import { MudSession } from "../mud/connection.js";
import { createMudTools, MUD_ALLOWED_TOOLS, MUD_SERVER_NAME } from "../mud/tools.js";
import type { CharacterConfig } from "../characters.js";

const HOST = process.env.MUD_HOST ?? "localhost";
const PORT = Number(process.env.MUD_PORT ?? "4000");

export interface CharacterAgentResult {
  character: string;
  numTurns: number;
  totalCostUsd: number;
  finalResult: string;
}

export async function runCharacterAgent(config: CharacterConfig): Promise<CharacterAgentResult> {
  const tag = `[${config.displayName}]`;
  const session = new MudSession(HOST, PORT, config.username, config.password);

  console.log(`${tag} connecting to ${HOST}:${PORT} as ${config.username}...`);
  await session.connect();
  console.log(`${tag} connected + logged in`);

  const mcpServer = createMudTools(session, config.memoryDir);

  let result: CharacterAgentResult = {
    character: config.displayName,
    numTurns: 0,
    totalCostUsd: 0,
    finalResult: "(no result message received)",
  };

  // Both overridable per-run without editing characters.ts -- useful for
  // "same character, new directive" sessions (mirrors how 02's play-mud
  // skill takes fresh ARGUMENTS each invocation).
  const initialPrompt = process.env.MUD_TASK ?? config.initialPrompt;
  const maxTurns = process.env.MUD_MAX_TURNS ? Number(process.env.MUD_MAX_TURNS) : config.maxTurns;

  try {
    const stream = query({
      prompt: initialPrompt,
      options: {
        systemPrompt: config.systemPrompt,
        mcpServers: { [MUD_SERVER_NAME]: mcpServer },
        tools: [], // no built-in tools (Bash, Read, Write, ...) -- MUD/memory tools only
        allowedTools: MUD_ALLOWED_TOOLS,
        maxTurns,
        model: process.env.MUD_AGENT_MODEL,
      },
    });

    for await (const message of stream) {
      if (message.type === "assistant") {
        for (const block of message.message.content) {
          if (block.type === "text" && block.text.trim()) {
            console.log(`${tag} ${block.text.trim()}`);
          } else if (block.type === "tool_use") {
            console.log(`${tag} -> ${block.name}(${JSON.stringify(block.input)})`);
          }
        }
      } else if (message.type === "result") {
        result = {
          character: config.displayName,
          numTurns: message.num_turns,
          totalCostUsd: message.total_cost_usd,
          finalResult: message.subtype === "success" ? message.result : `(${message.subtype}: ${message.errors.join("; ")})`,
        };
        console.log(`${tag} DONE — ${message.num_turns} turns, $${message.total_cost_usd.toFixed(4)}`);
      }
    }
  } finally {
    console.log(`${tag} closing MUD connection...`);
    await session.close();
  }

  return result;
}
