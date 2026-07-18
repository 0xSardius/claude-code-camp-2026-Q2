// Per-character persistent memory, same player.md/world.md pattern as
// 02_agent_skills, but namespaced under data/<character>/ so concurrent
// character agents never share or collide on state.
import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";

export type MemoryFile = "player" | "world";

function filePath(memoryDir: string, file: MemoryFile): string {
  return path.join(memoryDir, `${file}.md`);
}

export async function readMemoryFile(memoryDir: string, file: MemoryFile): Promise<string> {
  try {
    return await readFile(filePath(memoryDir, file), "utf-8");
  } catch (e) {
    if ((e as NodeJS.ErrnoException).code === "ENOENT") {
      return `(no ${file}.md yet -- this is a fresh start, nothing recorded)`;
    }
    throw e;
  }
}

export async function writeMemoryFile(memoryDir: string, file: MemoryFile, content: string): Promise<void> {
  await mkdir(memoryDir, { recursive: true });
  await writeFile(filePath(memoryDir, file), content, "utf-8");
}
