// Custom SDK tools exposing the MUD connection + this character's memory
// files to its agent loop. Each character agent gets its own instance of
// this server, closed over its own MudSession and memoryDir, so concurrent
// characters never share a socket or a memory file.
import { z } from "zod";
import { tool, createSdkMcpServer, type McpSdkServerConfigWithInstance } from "@anthropic-ai/claude-agent-sdk";
import { MudSession } from "./connection.js";
import { readMemoryFile, writeMemoryFile, type MemoryFile } from "../memory.js";

export const MUD_SERVER_NAME = "mud";
export const MUD_TOOL_NAMES = ["mud_send", "mud_save", "memory_read", "memory_write"] as const;
export const MUD_ALLOWED_TOOLS = MUD_TOOL_NAMES.map((t) => `mcp__${MUD_SERVER_NAME}__${t}`);

export function createMudTools(session: MudSession, memoryDir: string): McpSdkServerConfigWithInstance {
  const mudSend = tool(
    "mud_send",
    "Send one raw command to the MUD -- exactly what a human would type, e.g. 'look', 'north', 'kill rat', 'consider rat', 'get all corpse'. Returns everything the MUD sent back.",
    {
      command: z.string().describe("the raw MUD command"),
      mode: z
        .enum(["prompt", "quiet"])
        .optional()
        .describe(
          "'prompt' (default) reads until the '> ' prompt reappears. 'quiet' reads until output goes idle for quietMs -- prefer this during combat or when a command triggers a burst of async lines.",
        ),
      timeoutMs: z.number().optional().describe("max time to wait for a response, in ms (default 10000)"),
      quietMs: z.number().optional().describe("idle time required to consider output finished in 'quiet' mode, in ms (default 600)"),
    },
    async (args) => {
      const output = await session.send(args.command, {
        mode: args.mode,
        timeoutMs: args.timeoutMs,
        quietMs: args.quietMs,
      });
      return { content: [{ type: "text" as const, text: output || "(no output)" }] };
    },
  );

  const mudSave = tool(
    "mud_save",
    "Save the character's progress server-side (the 'save' command). Always call this after leveling up, and before ending a session.",
    {},
    async () => {
      const output = await session.send("save", { mode: "quiet", quietMs: 800 });
      return { content: [{ type: "text" as const, text: output || "(no output)" }] };
    },
  );

  const memoryRead = tool(
    "memory_read",
    "Read this character's persistent memory: 'player' (goal, level, skills, gold, location, progress log) or 'world' (map, routes, points of interest). Call this first, before connecting, to recall where you left off.",
    { file: z.enum(["player", "world"]) },
    async (args) => {
      const content = await readMemoryFile(memoryDir, args.file as MemoryFile);
      return { content: [{ type: "text" as const, text: content }] };
    },
  );

  const memoryWrite = tool(
    "memory_write",
    "Overwrite this character's persistent memory file ('player' or 'world') with new markdown content. Call this before ending a session to record goal progress, level, location, map knowledge, and lessons learned -- the next session only knows what's written here.",
    { file: z.enum(["player", "world"]), content: z.string() },
    async (args) => {
      await writeMemoryFile(memoryDir, args.file as MemoryFile, args.content);
      return { content: [{ type: "text" as const, text: `wrote ${args.file}.md` }] };
    },
  );

  return createSdkMcpServer({
    name: MUD_SERVER_NAME,
    version: "0.1.0",
    tools: [mudSend, mudSave, memoryRead, memoryWrite],
  });
}
