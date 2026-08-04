"""Port of week0_explore/mud_manager/lib/mud_manager/session.rb -- a
long-lived telnet connection to a CircleMUD server. Vendored inside this
step's package rather than as a separate installable Python package (see
docs/plans/python_port/10_standard_tool_library's placement-decision
section) -- mud_manager the Ruby gem is an external dependency Tools::Mud
requires; there's no equivalent Python package to depend on, and standing
one up was judged out of proportion to what this one step needs.

A background thread continuously drains the socket into an internal
buffer, stripping telnet IAC negotiation bytes. Tools::Mud sends a command
and then calls read_until_quiet (or read_until for a known prompt) to
collect both the command's response and any async chatter that arrived in
the meantime.
"""
from __future__ import annotations

import re
import socket
import threading
import time


class SessionError(Exception):
    pass


class ConnectionError(SessionError):  # noqa: A001 -- matches Ruby's Session::ConnectionError name
    pass


class LoginError(SessionError):
    pass


class SessionTimeout(SessionError):
    # Ruby names this `Timeout` (nested under Session) -- Python's stdlib
    # already has a built-in-adjacent TimeoutError; naming this
    # SessionTimeout avoids shadowing confusion, not a behavior change.
    pass


class Session:
    DEFAULT_HOST = "localhost"
    DEFAULT_PORT = 4000
    DEFAULT_TIMEOUT = 10.0

    # Telnet protocol bytes we recognise. We don't negotiate -- we just
    # consume and discard IAC sequences so they don't pollute the buffer.
    IAC, DONT, DO, WONT, WILL, SB, SE = 0xFF, 0xFE, 0xFD, 0xFC, 0xFB, 0xFA, 0xF0

    # CircleMUD terminates every command response with a prompt ending in
    # "> " -- waiting for that sentinel is faster and more deterministic
    # than a silence window.
    PROMPT_SENTINEL = "> "

    def __init__(self, *, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT, timeout: float = DEFAULT_TIMEOUT):
        self.host = host
        self.port = port
        self._timeout = timeout
        self._socket: socket.socket | None = None
        self._reader: threading.Thread | None = None
        self._buffer = ""
        self._lock = threading.Lock()
        self._cv = threading.Condition(self._lock)
        self._closed = False
        self._last_recv_at: float | None = None

    def open(self) -> "Session":
        if self._socket is not None:
            raise SessionError("already open")
        try:
            self._socket = socket.create_connection((self.host, self.port))
        except OSError as e:
            raise ConnectionError(f"connect {self.host}:{self.port} failed: {e}")
        self._closed = False
        self._start_reader()
        return self

    def is_open(self) -> bool:
        return self._socket is not None and not self._closed

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        try:
            if self._socket:
                self._socket.close()
        except OSError:
            pass  # already closed / broken -- fine
        if self._reader:
            self._reader.join(1)
        self._socket = None
        self._reader = None

    # Send a command. Accepts a str, a mud_primitives.Command (anything
    # with a .raw attribute), or None (blank line -- Ruby's :return/:enter
    # symbol sentinel has no Python equivalent; callers pass None or ""
    # directly instead). A trailing newline is appended.
    def send_command(self, command) -> str:
        if not self.is_open():
            raise SessionError("session not open")
        if hasattr(command, "raw"):
            line = command.raw
        elif command is None:
            line = ""
        else:
            line = str(command)
        self._socket.sendall((line + "\r\n").encode("utf-8"))
        return line

    send = send_command

    # Drain whatever is currently buffered and return it. Non-blocking.
    def drain(self) -> str:
        with self._lock:
            out, self._buffer = self._buffer, ""
            return out

    # Block until quiet_seconds have elapsed with no new bytes arriving, or
    # timeout total seconds pass. Returns whatever accumulated. The
    # workhorse for "send a command, get the full response."
    def read_until_quiet(self, quiet_seconds: float = 1.0, timeout: float | None = None) -> str:
        if not self.is_open():
            raise SessionError("session not open")
        deadline = time.monotonic() + (timeout if timeout is not None else self._timeout)
        with self._lock:
            while True:
                remaining_total = deadline - time.monotonic()
                if remaining_total <= 0:
                    break
                if self._last_recv_at is not None and (time.monotonic() - self._last_recv_at) >= quiet_seconds and self._buffer:
                    break
                if self._last_recv_at is not None and self._buffer:
                    wait_for = quiet_seconds - (time.monotonic() - self._last_recv_at)
                else:
                    wait_for = remaining_total
                wait_for = min(wait_for, remaining_total)
                if wait_for <= 0:
                    break
                self._cv.wait(wait_for)
            out, self._buffer = self._buffer, ""
            return out

    # Block until the buffer contains the given pattern (str or compiled
    # regex), then return everything up to and including the match. Raises
    # SessionTimeout if `timeout` seconds pass without a match.
    def read_until(self, pattern, timeout: float | None = None) -> str:
        if not self.is_open():
            raise SessionError("session not open")
        regex = pattern if isinstance(pattern, re.Pattern) else re.compile(re.escape(pattern))
        deadline = time.monotonic() + (timeout if timeout is not None else self._timeout)
        with self._lock:
            while True:
                m = regex.search(self._buffer)
                if m:
                    cut = m.end()
                    out, self._buffer = self._buffer[:cut], self._buffer[cut:]
                    return out
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    # Report the timeout we actually waited, not the argument --
                    # every caller that relies on the default passed None here,
                    # so this read "after Nones" in the one log that mattered.
                    #
                    # And say what the server DID send. A timeout waiting for
                    # "Password" means the server said something else, and that
                    # something else is the whole diagnosis: "Did I get that
                    # right (Y/N)?" means it thinks the character is new, which
                    # is a server-side problem no retry will fix. Without the
                    # tail, that cost a debugging session to work out.
                    effective = timeout if timeout is not None else self._timeout
                    tail = self._buffer[-200:].strip()
                    saw = f"server sent: {tail!r}" if tail else "server sent nothing"
                    raise SessionTimeout(
                        f"read_until {pattern!r} after {effective}s; {saw}"
                    )
                if self._closed:
                    raise ConnectionError("socket closed while waiting")
                self._cv.wait(remaining)

    # "> " is not unique to CircleMUD's trailing status prompt -- found
    # live (2026-07-26): the `equipment` command's bracketed slot labels
    # (e.g. "<used as light> ") can end in the exact same two-character
    # sequence, well before the real prompt arrives. A bare first-match
    # read_until stopped there, silently truncating every line the server
    # sent afterward (the rest of the equipment listing never reached the
    # caller). Fixed by requiring a short quiet window after the sentinel
    # is seen: if more bytes keep arriving right after a "> " match, it
    # wasn't the real end of the response yet, so keep waiting instead of
    # trusting the first occurrence. Mirrors read_until_quiet's own
    # quiet-window loop shape, just gated on the sentinel being present
    # too rather than requiring quiet unconditionally. Falls back to
    # draining the buffer if the prompt is never seen within the timeout
    # (e.g. during combat when extra async lines may slip in).
    def read_until_prompt(self, timeout: float | None = None, quiet_seconds: float = 0.3) -> str:
        if not self.is_open():
            raise SessionError("session not open")
        deadline = time.monotonic() + (timeout if timeout is not None else self._timeout)
        with self._lock:
            while True:
                remaining_total = deadline - time.monotonic()
                if remaining_total <= 0:
                    break
                has_sentinel = self.PROMPT_SENTINEL in self._buffer
                if has_sentinel and self._last_recv_at is not None and (time.monotonic() - self._last_recv_at) >= quiet_seconds:
                    break
                if has_sentinel and self._last_recv_at is not None:
                    wait_for = quiet_seconds - (time.monotonic() - self._last_recv_at)
                else:
                    wait_for = remaining_total
                wait_for = min(wait_for, remaining_total)
                if wait_for <= 0:
                    break
                self._cv.wait(wait_for)
            out, self._buffer = self._buffer, ""
            return out

    # Walk the CircleMUD login dance for an EXISTING account. No
    # new-character-creation flow -- Ruby's mud_manager doesn't implement
    # one either (confirmed by reading session.rb directly during this
    # project's live character-creation session, which had to be scripted
    # by hand outside the gem for exactly this reason).
    def login(self, username: str, password: str) -> str | None:
        # Ruby's login is an if/elsif with no else, and Ruby methods
        # implicitly return their last expression's value -- the
        # Reconnecting branch (just a comment) returns nil, the Welcome
        # branch returns read_until_quiet's result (the post-login
        # welcome/MOTD text, which Tools::Mud#mud_connect surfaces to the
        # agent), and Wrong password raises. Mirrored explicitly here with
        # real return statements rather than relying on Python's own
        # implicit-None-on-fallthrough (which would only reproduce the
        # Reconnecting case, not the Welcome one).
        self.read_until(re.compile(r"By what name do you wish to be known.*\?", re.IGNORECASE))
        self.send_command(username)
        self.read_until(re.compile(r"Password", re.IGNORECASE))
        self.send_command(password)
        output = self.read_until(re.compile(r"Welcome|Reconnecting|Wrong password", re.IGNORECASE))
        if re.search("Reconnecting", output, re.IGNORECASE):
            return None  # already in-world, skip menu
        elif re.search("Welcome", output, re.IGNORECASE):
            self.send_command(None)  # enter for main menu
            self.send_command("1")  # enter the game
            return self.read_until_quiet()
        elif re.search("Wrong password", output, re.IGNORECASE):
            raise LoginError("wrong password")
        return None

    # ----- internals -----

    def _start_reader(self) -> None:
        def run():
            try:
                while True:
                    chunk = self._socket.recv(4096)
                    if not chunk:
                        break
                    text = self._strip_iac(chunk)
                    if text:
                        with self._lock:
                            self._buffer += text
                            self._last_recv_at = time.monotonic()
                            self._cv.notify_all()
            except OSError:
                pass  # remote closed / socket torn down -- fall through
            finally:
                with self._lock:
                    self._closed = True
                    self._cv.notify_all()

        self._reader = threading.Thread(target=run, daemon=True)
        self._reader.start()

    # Telnet protocol IAC stripper. The MUD may interleave:
    #   IAC (WILL|WONT|DO|DONT) <option>            -- 3 bytes
    #   IAC SB <option> ... IAC SE                   -- variable
    #   IAC IAC                                      -- literal 0xFF byte
    # We discard all of them. CircleMUD's negotiation is mostly echo
    # toggling around the password prompt, which we don't honor.
    def _strip_iac(self, raw: bytes) -> str:
        out = bytearray()
        i = 0
        n = len(raw)
        while i < n:
            b = raw[i]
            if b == self.IAC:
                nxt = raw[i + 1] if i + 1 < n else None
                if nxt is None:
                    break
                elif nxt == self.IAC:
                    out.append(0xFF)
                    i += 2
                elif nxt in (self.WILL, self.WONT, self.DO, self.DONT):
                    i += 3
                elif nxt == self.SB:
                    j = i + 2
                    while j < n and not (raw[j] == self.IAC and j + 1 < n and raw[j + 1] == self.SE):
                        j += 1
                    i = j + 2
                else:
                    i += 2
            else:
                out.append(b)
                i += 1
        # Ruby decodes the stripped bytes with force_encoding(UTF_8),
        # which never raises (it doesn't validate). Python's "latin-1"
        # codec is the equivalent never-raises choice here -- the MUD's
        # raw output can contain stray non-UTF-8 bytes (ANSI color codes,
        # etc.) that a strict utf-8 decode would reject.
        return out.decode("latin-1", errors="replace")
