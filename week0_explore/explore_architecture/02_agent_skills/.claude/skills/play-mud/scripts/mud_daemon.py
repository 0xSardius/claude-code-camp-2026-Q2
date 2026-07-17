#!/usr/bin/env python3
"""Background daemon holding one persistent telnet connection to the MUD.

Claude Code invokes short-lived subprocesses (one per tool call), which
cannot hold a TCP socket open across calls. This daemon runs in the
background, keeps the connection + login session alive, and exposes it
to those short-lived calls over a Unix domain socket. `mud.py` is the
client that talks to it -- start this indirectly via `mud.py start`.

Protocol: client connects to the Unix socket, writes one line of JSON,
reads back one line of JSON, then disconnects.

Requests:  {"op": "ping"}
           {"op": "send", "text": "look", "timeout": 10, "quiet": 0.6}
           {"op": "drain", "timeout": 1.0}
           {"op": "stop"}
Responses: {"ok": true, "output": "..."}  or  {"ok": false, "error": "..."}
"""
import argparse
import hashlib
import json
import os
import re
import signal
import socket
import sys
import tempfile
import threading
import time

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUN_DIR = os.path.join(SKILL_DIR, "run")
PID_PATH = os.path.join(RUN_DIR, "mud.pid")
LOG_PATH = os.path.join(RUN_DIR, "mud.log")
STATUS_PATH = os.path.join(RUN_DIR, "mud.status")

# AF_UNIX socket paths are capped at ~108 bytes on Linux, and this skill can
# live many directories deep -- so the socket itself goes in /tmp under a
# name derived from the skill's install path (stable across restarts, and
# collision-free if the skill is checked out in more than one place).
_SOCK_KEY = hashlib.sha1(SKILL_DIR.encode()).hexdigest()[:12]
SOCK_PATH = os.path.join(tempfile.gettempdir(), f"play-mud-{_SOCK_KEY}.sock")

IAC, DONT, DO, WONT, WILL, SB, SE = 255, 254, 253, 252, 251, 250, 240
PROMPT_SENTINEL = "> "


def log(msg):
    with open(LOG_PATH, "a") as f:
        f.write(f"[{time.strftime('%H:%M:%S')}] {msg}\n")


class MudConnection:
    """Mirrors week0_explore/mud_manager's Session: a reader thread drains
    the socket into a text buffer (stripping telnet IAC negotiation), and
    callers block on read_until / read_until_quiet / read_until_prompt.
    """

    def __init__(self, host, port, timeout=10.0):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.sock = None
        self.buf = ""
        self.cond = threading.Condition()
        self.last_recv = None
        self.closed = True

    def open(self):
        self.sock = socket.create_connection((self.host, self.port), timeout=10)
        self.closed = False
        threading.Thread(target=self._reader, daemon=True).start()

    def _reader(self):
        try:
            while True:
                chunk = self.sock.recv(4096)
                if not chunk:
                    break
                text = self._strip_iac(chunk).decode("utf-8", "replace")
                if text:
                    with self.cond:
                        self.buf += text
                        self.last_recv = time.monotonic()
                        self.cond.notify_all()
        except OSError:
            pass
        finally:
            with self.cond:
                self.closed = True
                self.cond.notify_all()

    @staticmethod
    def _strip_iac(data):
        out = bytearray()
        i, n = 0, len(data)
        while i < n:
            b = data[i]
            if b == IAC:
                nxt = data[i + 1] if i + 1 < n else None
                if nxt is None:
                    break
                if nxt == IAC:
                    out.append(0xFF)
                    i += 2
                elif nxt in (WILL, WONT, DO, DONT):
                    i += 3
                elif nxt == SB:
                    j = i + 2
                    while j + 1 < n and not (data[j] == IAC and data[j + 1] == SE):
                        j += 1
                    i = j + 2
                else:
                    i += 2
            else:
                out.append(b)
                i += 1
        return bytes(out)

    def send(self, line):
        if self.closed:
            raise ConnectionError("mud session is closed")
        self.sock.sendall(line.encode("utf-8", "replace") + b"\r\n")

    def read_until(self, pattern, timeout=10.0):
        regex = pattern if hasattr(pattern, "search") else re.compile(re.escape(pattern))
        deadline = time.monotonic() + timeout
        with self.cond:
            while True:
                m = regex.search(self.buf)
                if m:
                    cut = m.end()
                    out, self.buf = self.buf[:cut], self.buf[cut:]
                    return out
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError(f"read_until {pattern!r} timed out")
                if self.closed:
                    raise ConnectionError("socket closed while waiting")
                self.cond.wait(remaining)

    def read_until_quiet(self, quiet=0.6, timeout=10.0):
        deadline = time.monotonic() + timeout
        with self.cond:
            while True:
                now = time.monotonic()
                if now >= deadline:
                    break
                if self.last_recv and (now - self.last_recv) >= quiet and self.buf:
                    break
                wait_for = (quiet - (now - self.last_recv)) if (self.last_recv and self.buf) else (deadline - now)
                wait_for = min(wait_for, deadline - now)
                if wait_for <= 0:
                    break
                self.cond.wait(wait_for)
            out, self.buf = self.buf, ""
            return out

    def read_until_prompt(self, timeout=10.0):
        try:
            return self.read_until(PROMPT_SENTINEL, timeout=timeout)
        except TimeoutError:
            with self.cond:
                out, self.buf = self.buf, ""
                return out

    def login(self, username, password):
        self.read_until(re.compile(r"By what name.*\?", re.I), timeout=15)
        self.send(username)
        self.read_until(re.compile(r"password", re.I), timeout=15)
        self.send(password)
        output = self.read_until(re.compile(r"Welcome|Reconnecting|Wrong password", re.I), timeout=15)
        if re.search("Wrong password", output, re.I):
            raise ConnectionError("wrong password")
        if re.search("Welcome", output, re.I):
            self.send("")   # enter for main menu
            self.send("1")  # enter the game
            self.read_until_quiet(quiet=1.0, timeout=15)
        # "Reconnecting" -> already in-world, nothing else to do.


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default=os.environ.get("MUD_HOST", "localhost"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("MUD_PORT", "4000")))
    parser.add_argument("--username", default=os.environ.get("MUD_USERNAME", "dummy"))
    parser.add_argument("--password", default=os.environ.get("MUD_PASSWORD", "helloworld"))
    args = parser.parse_args()

    os.makedirs(RUN_DIR, exist_ok=True)
    if os.path.exists(SOCK_PATH):
        os.remove(SOCK_PATH)
    with open(STATUS_PATH, "w") as f:
        f.write("starting")

    conn = MudConnection(args.host, args.port)
    try:
        conn.open()
        log(f"connected to {args.host}:{args.port}")
        conn.login(args.username, args.password)
        log(f"logged in as {args.username}")
    except Exception as e:
        log(f"startup failed: {e}")
        with open(STATUS_PATH, "w") as f:
            f.write(f"error: {e}")
        sys.exit(1)

    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server.bind(SOCK_PATH)
    server.listen(8)
    server.settimeout(0.5)

    with open(PID_PATH, "w") as f:
        f.write(str(os.getpid()))
    with open(STATUS_PATH, "w") as f:
        f.write("ready")

    running = {"flag": True}

    def handle(client):
        try:
            data = client.makefile("r").readline()
            if not data:
                return
            req = json.loads(data)
            op = req.get("op")
            if op == "ping":
                resp = {"ok": True, "status": "alive"}
            elif op == "send":
                # Claim whatever's already buffered (unfetched async output from
                # before this call) BEFORE sending, so the read below only waits
                # on fresh bytes triggered by this command -- otherwise stale
                # leftover content can satisfy read_until_quiet/read_until_prompt
                # immediately and this command's real response shows up a call
                # late. Anything reclaimed here is prepended, not dropped.
                with conn.cond:
                    leftover, conn.buf = conn.buf, ""
                conn.send(req.get("text", ""))
                quiet = req.get("quiet")
                timeout = req.get("timeout", 10.0)
                out = conn.read_until_quiet(quiet=quiet, timeout=timeout) if quiet else conn.read_until_prompt(timeout=timeout)
                resp = {"ok": True, "output": leftover + out}
            elif op == "drain":
                out = conn.read_until_quiet(quiet=0.3, timeout=req.get("timeout", 1.0))
                resp = {"ok": True, "output": out}
            elif op == "stop":
                try:
                    conn.send("quit")
                    conn.read_until_quiet(quiet=0.5, timeout=3.0)
                except Exception:
                    pass
                resp = {"ok": True, "status": "stopping"}
                running["flag"] = False
            else:
                resp = {"ok": False, "error": f"unknown op {op!r}"}
            client.sendall((json.dumps(resp) + "\n").encode())
        except Exception as e:
            log(f"request error: {e}")
            try:
                client.sendall((json.dumps({"ok": False, "error": str(e)}) + "\n").encode())
            except Exception:
                pass
        finally:
            client.close()

    def shutdown(*_):
        running["flag"] = False

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)

    try:
        while running["flag"]:
            try:
                client, _ = server.accept()
            except socket.timeout:
                if conn.closed:
                    log("mud connection dropped; shutting down")
                    break
                continue
            handle(client)
    finally:
        log("shutting down")
        try:
            conn.sock.close()
        except Exception:
            pass
        server.close()
        for p in (SOCK_PATH, PID_PATH, STATUS_PATH):
            if os.path.exists(p):
                os.remove(p)


if __name__ == "__main__":
    main()
