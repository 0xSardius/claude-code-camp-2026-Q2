"""Port of week1_baseline/ruby/10_standard_tool_library/lib/boukensha/tools/shell.rb --
includes the shell-metacharacter allow-list fix (see
docs/plans/python_port/10_standard_tool_library), not just a translation
of the original vulnerable version: the allowed_commands allow-list only
checked a command's first whitespace token, but the command runs through
a real shell either way, so "git status; rm -rf ~" would pass an
allow-list containing only "git". Fixed in the Ruby source first (verified
live), ported with the identical fix here.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

_METACHARS = re.compile(r"[;&|><`$\n]|\$\(")


def register(registry, *, working_dir, timeout=30, allowed_commands=None):
    root = str(Path(working_dir).expanduser().resolve())

    def oops(msg):
        return f"error: {msg}"

    def run_command(command):
        # Guard: check the first token against the allow-list when one is
        # set. command runs via a shell (subprocess.run(..., shell=True),
        # same as Ruby's Open3.capture2e(command, chdir: root) with a
        # single string argument), so checking only the first token isn't
        # enough on its own -- reject shell metacharacters too so the
        # allow-list can't be chained past.
        if allowed_commands:
            if _METACHARS.search(str(command)):
                return oops(
                    "command contains shell metacharacters (; & | > < ` $ or a newline), "
                    "which is not allowed when an allowed-commands list is set"
                )
            stripped = str(command).strip()
            executable = stripped.split()[0] if stripped else ""
            if executable not in [str(c) for c in allowed_commands]:
                return oops(f"'{executable}' is not in the allowed-commands list ({', '.join(str(c) for c in allowed_commands)})")

        try:
            # subprocess.run(..., timeout=...) DOES kill the child process
            # on timeout (unlike Ruby's Timeout.timeout wrapping
            # Open3.capture2e, which only interrupts the calling thread and
            # leaves the child running -- a real, separately-noted gap in
            # the Ruby source). Not reconciled backward into Ruby; this
            # makes the Python port more correct on this specific point,
            # not a fidelity gap.
            result = subprocess.run(
                command,
                shell=True,
                cwd=root,
                timeout=timeout,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
            )
        except subprocess.TimeoutExpired:
            return oops(f"command timed out after {timeout}s: {command}")
        except OSError as e:
            return oops(f"command not found: {e}")
        except Exception as e:
            # Ruby has a final `rescue => e` (StandardError, broad) after
            # its ENOENT/Timeout::Error branches -- anything else
            # subprocess.run(shell=True) can raise (e.g. a ValueError from
            # an embedded NUL byte in the command string) should get this
            # tool's own "error: ..." formatting too, not escape uncaught.
            return oops(str(e))

        exit_note = "" if result.returncode == 0 else f"\n[exit {result.returncode}]"
        output = result.stdout.decode("utf-8", errors="replace").strip()
        return f"(no output){exit_note}" if not output else f"{output}{exit_note}"

    allow_note = f" Allowed executables: {', '.join(str(c) for c in allowed_commands)}." if allowed_commands else ""
    registry.tool(
        "run_command",
        description=(
            f"Run a shell command inside the working directory and return its combined stdout+stderr output. "
            f"Commands run with a {timeout}-second timeout.{allow_note}"
        ),
        parameters={"command": {"type": "string", "description": "The shell command to execute (e.g. 'ruby script.rb', 'ls -la', 'git status')"}},
        block=run_command,
    )
