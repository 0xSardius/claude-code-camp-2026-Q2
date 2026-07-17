#!/usr/bin/env python3
"""CLI for playing the MUD -- talks to the background mud_daemon.py over a
Unix domain socket. Each invocation is a fresh, short-lived process; the
daemon is what keeps the actual telnet session (and login state) alive
between them.

Usage:
  mud.py start  [--host H] [--port P] [--username U] [--password W]
  mud.py send   "<command>" [--timeout SECS] [--quiet SECS]
  mud.py drain  [--timeout SECS]
  mud.py stop
  mud.py status
"""
import argparse
import hashlib
import json
import os
import signal
import socket
import subprocess
import sys
import tempfile
import time

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SKILL_DIR = os.path.dirname(SCRIPT_DIR)
RUN_DIR = os.path.join(SKILL_DIR, "run")
PID_PATH = os.path.join(RUN_DIR, "mud.pid")
LOG_PATH = os.path.join(RUN_DIR, "mud.log")
STATUS_PATH = os.path.join(RUN_DIR, "mud.status")
DAEMON_PATH = os.path.join(SCRIPT_DIR, "mud_daemon.py")

# Must match mud_daemon.py's derivation exactly -- see the comment there.
_SOCK_KEY = hashlib.sha1(SKILL_DIR.encode()).hexdigest()[:12]
SOCK_PATH = os.path.join(tempfile.gettempdir(), f"play-mud-{_SOCK_KEY}.sock")


def request(op, timeout=15.0, **fields):
    if not os.path.exists(SOCK_PATH):
        raise ConnectionError("daemon not running -- run `mud.py start` first")
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.settimeout(timeout + 2)
    s.connect(SOCK_PATH)
    payload = {"op": op, **fields}
    s.sendall((json.dumps(payload) + "\n").encode())
    data = s.makefile("r").readline()
    s.close()
    if not data:
        raise ConnectionError("daemon closed the connection without a response")
    return json.loads(data)


def env_defaults():
    return (
        os.environ.get("MUD_HOST", "localhost"),
        int(os.environ.get("MUD_PORT", "4000")),
        os.environ.get("MUD_USERNAME", "dummy"),
        os.environ.get("MUD_PASSWORD", "helloworld"),
    )


def ensure_daemon(host, port, username, password, announce=True):
    """(Re)start the daemon if it isn't already responding to pings.

    This MUD's connections have been observed to drop unpredictably after
    anywhere from ~10 seconds to a few minutes -- not something this skill
    can fix server-side -- so `send`/`drain` fall back to this instead of
    just erroring out. The character resumes wherever it was server-side
    ("has reconnected"), since tbaMUD keeps a dropped link's character
    around for a while before extracting it.
    """
    if os.path.exists(SOCK_PATH):
        try:
            if request("ping", timeout=3).get("ok"):
                return False
        except Exception:
            pass  # stale socket, fall through and (re)start

    os.makedirs(RUN_DIR, exist_ok=True)
    for p in (SOCK_PATH, PID_PATH, STATUS_PATH):
        if os.path.exists(p):
            os.remove(p)
    with open(LOG_PATH, "a") as f:
        f.write(f"--- (re)starting daemon at {time.time()} ---\n")

    daemon_args = [
        sys.executable, DAEMON_PATH,
        "--host", host, "--port", str(port),
        "--username", username, "--password", password,
    ]
    subprocess.Popen(
        daemon_args,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        start_new_session=True,
    )

    deadline = time.time() + 30
    while time.time() < deadline:
        if os.path.exists(STATUS_PATH):
            status = open(STATUS_PATH).read().strip()
            if status == "ready":
                if announce:
                    print(f"connected and logged in as {username}")
                return True
            if status.startswith("error"):
                raise ConnectionError(status)
        time.sleep(0.3)
    raise TimeoutError("timed out waiting for daemon to become ready; check run/mud.log")


def cmd_start(args):
    try:
        if not ensure_daemon(args.host, args.port, args.username, args.password):
            print("already running")
    except (ConnectionError, TimeoutError) as e:
        print(str(e), file=sys.stderr)
        sys.exit(1)


def _kill_stale_daemon():
    """Best-effort SIGTERM + cleanup so a restart doesn't race the old
    daemon's own (slower) self-shutdown after it notices its MUD connection
    died."""
    if os.path.exists(PID_PATH):
        try:
            os.kill(int(open(PID_PATH).read().strip()), signal.SIGTERM)
        except (OSError, ValueError):
            pass
    for p in (SOCK_PATH, PID_PATH, STATUS_PATH):
        if os.path.exists(p):
            try:
                os.remove(p)
            except OSError:
                pass


def _send_with_reconnect(op, **fields):
    try:
        resp = request(op, **fields)
    except ConnectionError:
        print("(connection had dropped -- reconnecting...)", file=sys.stderr)
        ensure_daemon(*env_defaults(), announce=False)
        return request(op, **fields)

    # The daemon can also reply over its still-open Unix socket with an
    # explicit "the mud link died" error, rather than the client-side
    # request() ever raising -- same underlying flakiness, different shape.
    if not resp.get("ok") and "closed" in str(resp.get("error", "")).lower():
        print("(mud session had died -- restarting daemon and retrying...)", file=sys.stderr)
        _kill_stale_daemon()
        ensure_daemon(*env_defaults(), announce=False)
        return request(op, **fields)

    return resp


def cmd_send(args):
    resp = _send_with_reconnect("send", text=args.text, timeout=args.timeout, quiet=args.quiet)
    if not resp.get("ok"):
        print(f"error: {resp.get('error')}", file=sys.stderr)
        sys.exit(1)
    print(resp["output"])


def cmd_drain(args):
    resp = _send_with_reconnect("drain", timeout=args.timeout)
    if not resp.get("ok"):
        print(f"error: {resp.get('error')}", file=sys.stderr)
        sys.exit(1)
    print(resp["output"])


def cmd_stop(args):
    try:
        resp = request("stop", timeout=5)
        print(resp.get("status", "stopped"))
    except Exception as e:
        print(f"stop failed ({e}); daemon may already be down")


def cmd_status(args):
    try:
        resp = request("ping", timeout=3)
        print("running" if resp.get("ok") else "not responding")
    except Exception:
        print("not running")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p_start = sub.add_parser("start", help="connect and log in (spawns background daemon)")
    p_start.add_argument("--host", default=os.environ.get("MUD_HOST", "localhost"))
    p_start.add_argument("--port", type=int, default=int(os.environ.get("MUD_PORT", "4000")))
    p_start.add_argument("--username", default=os.environ.get("MUD_USERNAME", "dummy"))
    p_start.add_argument("--password", default=os.environ.get("MUD_PASSWORD", "helloworld"))
    p_start.set_defaults(func=cmd_start)

    p_send = sub.add_parser("send", help="send one command, return its output")
    p_send.add_argument("text", help="the raw MUD command, e.g. 'look' or 'north'")
    p_send.add_argument("--timeout", type=float, default=10.0)
    p_send.add_argument("--quiet", type=float, default=None,
                         help="read until N idle seconds instead of the '> ' prompt (use during combat/spam)")
    p_send.set_defaults(func=cmd_send)

    p_drain = sub.add_parser("drain", help="fetch any buffered async output (combat rounds, tells, etc.)")
    p_drain.add_argument("--timeout", type=float, default=1.0)
    p_drain.set_defaults(func=cmd_drain)

    p_stop = sub.add_parser("stop", help="quit the MUD and shut down the daemon")
    p_stop.set_defaults(func=cmd_stop)

    p_status = sub.add_parser("status", help="check whether the daemon is running")
    p_status.set_defaults(func=cmd_status)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
