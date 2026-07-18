// Ported from 02_agent_skills's mud_daemon.py (MudConnection). Same
// telnet/IAC-stripping and login-dance behavior, deliberately re-implemented
// here rather than imported, so 03 has zero runtime dependency on 02.
//
// One structural simplification vs. the Python version: that daemon needed
// a background reader thread + condition variable because it had to survive
// across separate short-lived CLI invocations (each `Bash` tool call is a
// fresh subprocess). Here the orchestrator process itself stays alive for
// the whole run, so a single-threaded event-loop-based wait is enough --
// no thread, no lock, no Unix-socket IPC to a daemon.
import net from "node:net";

const IAC = 255;
const DONT = 254;
const DO = 253;
const WONT = 252;
const WILL = 251;
const SB = 250;
const SE = 240;

const PROMPT_SENTINEL = "> ";

export class MudConnectionError extends Error {}
export class MudLoginError extends MudConnectionError {}
export class MudTimeoutError extends MudConnectionError {}

function escapeRegExp(s: string): string {
  return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function stripIac(data: Buffer): string {
  const out: number[] = [];
  let i = 0;
  const n = data.length;
  while (i < n) {
    const b = data[i];
    if (b === IAC) {
      const nxt = i + 1 < n ? data[i + 1] : null;
      if (nxt === null) break;
      if (nxt === IAC) {
        out.push(0xff);
        i += 2;
      } else if (nxt === WILL || nxt === WONT || nxt === DO || nxt === DONT) {
        i += 3;
      } else if (nxt === SB) {
        let j = i + 2;
        while (j + 1 < n && !(data[j] === IAC && data[j + 1] === SE)) j++;
        i = j + 2;
      } else {
        i += 2;
      }
    } else {
      out.push(b);
      i++;
    }
  }
  return Buffer.from(out).toString("utf-8");
}

/** Low-level telnet connection: IAC-stripped byte stream, pattern/quiet/prompt reads. */
export class MudConnection {
  private socket: net.Socket | null = null;
  private buf = "";
  private closed = true;
  private lastRecv: number | null = null;
  private waiters: Array<() => void> = [];

  constructor(private host: string, private port: number) {}

  get isOpen(): boolean {
    return this.socket !== null && !this.closed;
  }

  open(): Promise<void> {
    if (this.socket) throw new MudConnectionError("already open");
    return new Promise<void>((resolve, reject) => {
      const sock = net.createConnection({ host: this.host, port: this.port });
      sock.once("connect", () => {
        this.socket = sock;
        this.closed = false;
        resolve();
      });
      sock.once("error", (err) => reject(new MudConnectionError(`connect ${this.host}:${this.port} failed: ${err.message}`)));
      sock.on("data", (chunk) => this.onData(chunk));
      sock.on("close", () => {
        this.closed = true;
        this.notifyWaiters();
      });
    });
  }

  close(): void {
    this.closed = true;
    this.socket?.destroy();
    this.socket = null;
    this.notifyWaiters();
  }

  private onData(chunk: Buffer): void {
    const text = stripIac(chunk);
    if (text.length) {
      this.buf += text;
      this.lastRecv = Date.now();
      this.notifyWaiters();
    }
  }

  private notifyWaiters(): void {
    const pending = this.waiters;
    this.waiters = [];
    pending.forEach((cb) => cb());
  }

  private waitForChange(timeoutMs: number): Promise<void> {
    return new Promise((resolve) => {
      let settled = false;
      const cb = () => {
        if (settled) return;
        settled = true;
        clearTimeout(timer);
        resolve();
      };
      const timer = setTimeout(cb, Math.max(timeoutMs, 0));
      this.waiters.push(cb);
    });
  }

  send(line: string): void {
    if (!this.isOpen) throw new MudConnectionError("mud session is closed");
    this.socket!.write(line + "\r\n");
  }

  /** Claim and clear whatever's buffered right now, without waiting. */
  claimBuffer(): string {
    const out = this.buf;
    this.buf = "";
    return out;
  }

  async readUntil(pattern: string | RegExp, timeoutMs = 10_000): Promise<string> {
    const regex = typeof pattern === "string" ? new RegExp(escapeRegExp(pattern)) : pattern;
    const deadline = Date.now() + timeoutMs;
    for (;;) {
      const m = regex.exec(this.buf);
      if (m) {
        const cut = m.index + m[0].length;
        const out = this.buf.slice(0, cut);
        this.buf = this.buf.slice(cut);
        return out;
      }
      const remaining = deadline - Date.now();
      if (remaining <= 0) throw new MudTimeoutError(`readUntil ${pattern} timed out`);
      if (this.closed) throw new MudConnectionError("socket closed while waiting");
      await this.waitForChange(remaining);
    }
  }

  async readUntilQuiet(quietMs = 600, timeoutMs = 10_000): Promise<string> {
    const deadline = Date.now() + timeoutMs;
    for (;;) {
      const now = Date.now();
      if (now >= deadline) break;
      if (this.lastRecv !== null && now - this.lastRecv >= quietMs && this.buf.length) break;
      const waitFor = this.lastRecv !== null && this.buf.length ? quietMs - (now - this.lastRecv) : deadline - now;
      const clamped = Math.min(waitFor, deadline - now);
      if (clamped <= 0) break;
      await this.waitForChange(clamped);
    }
    return this.claimBuffer();
  }

  async readUntilPrompt(timeoutMs = 10_000): Promise<string> {
    try {
      return await this.readUntil(PROMPT_SENTINEL, timeoutMs);
    } catch (e) {
      if (e instanceof MudTimeoutError) return this.claimBuffer();
      throw e;
    }
  }

  /** Walk the CircleMUD login dance for an EXISTING character. */
  async login(username: string, password: string): Promise<void> {
    await this.readUntil(/By what name.*\?/i, 15_000);
    this.send(username);
    await this.readUntil(/password/i, 15_000);
    this.send(password);
    const out = await this.readUntil(/Welcome|Reconnecting|Wrong password/i, 15_000);
    if (/Wrong password/i.test(out)) throw new MudLoginError("wrong password");
    if (/Welcome/i.test(out)) {
      this.send(""); // enter for main menu
      this.send("1"); // enter the game
      await this.readUntilQuiet(1_000, 15_000);
    }
    // "Reconnecting" -> already in-world, nothing else to do.
  }
}

export interface SendOptions {
  mode?: "prompt" | "quiet";
  timeoutMs?: number;
  quietMs?: number;
}

/**
 * Owns credentials + a MudConnection, and transparently reconnects/re-logs-in
 * once on a dropped connection -- this MUD has been observed to drop the
 * socket unpredictably (see 02's player.md notes), so this is not optional.
 * Also claims any stale buffered output before sending, mirroring the fix
 * that solved 02's "response shows up a call late" race.
 */
export class MudSession {
  private conn: MudConnection;

  constructor(private host: string, private port: number, private username: string, private password: string) {
    this.conn = new MudConnection(host, port);
  }

  async connect(): Promise<void> {
    await this.conn.open();
    await this.conn.login(this.username, this.password);
  }

  private async reconnect(): Promise<void> {
    this.conn.close();
    this.conn = new MudConnection(this.host, this.port);
    await this.connect();
  }

  async send(command: string, opts: SendOptions = {}): Promise<string> {
    try {
      return await this.sendOnce(command, opts);
    } catch (e) {
      if (e instanceof MudConnectionError) {
        await this.reconnect();
        return await this.sendOnce(command, opts);
      }
      throw e;
    }
  }

  private async sendOnce(command: string, opts: SendOptions): Promise<string> {
    const leftover = this.conn.claimBuffer();
    this.conn.send(command);
    const timeoutMs = opts.timeoutMs ?? 10_000;
    const out =
      opts.mode === "quiet"
        ? await this.conn.readUntilQuiet(opts.quietMs ?? 600, timeoutMs)
        : await this.conn.readUntilPrompt(timeoutMs);
    return leftover + out;
  }

  async close(): Promise<void> {
    try {
      this.conn.send("quit");
      await this.conn.readUntilQuiet(500, 3_000);
    } catch {
      // best effort -- socket may already be gone
    }
    this.conn.close();
  }
}
