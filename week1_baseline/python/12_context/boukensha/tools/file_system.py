"""Port of week1_baseline/ruby/12_context/lib/boukensha/tools/file_system.rb --
registers the standard set of file-oriented tools against a registry, all
sandboxed to a single root directory.

list_directory and search_files are DISABLED this step (commented out,
matching Ruby exactly) -- leftover from when this app was a coding
harness; the player agent has no use for them yet. Kept in place (not
deleted) so they can be re-registered later if a task needs them -- a
real, deliberate change confirmed via diff against 11_tui's file_system.rb,
not a regression.

Every path argument the agent supplies is resolved relative to that root.
If the resolved path would escape the root (path traversal) the tool
returns an error string rather than raising, so the agent sees it and can
try something sensible instead.
"""
from __future__ import annotations

from pathlib import Path


def register(registry, *, working_dir):
    root = str(Path(working_dir).expanduser().resolve())

    # Resolve a relative (or absolute) agent-supplied path inside root.
    # Returns the absolute path on success, or an error string.
    def resolve(path):
        absolute = str((Path(root) / str(path)).resolve())
        if absolute == root or absolute.startswith(root + "/"):
            return absolute
        return f"error: path '{path}' escapes the working directory"

    def oops(msg):
        return f"error: {msg}"

    def pwd():
        return root

    # list_directory: disabled for now -- leftover from when this app was
    # a coding harness; the current player agent has no use for it. Kept
    # here (commented, matching Ruby) so it can be re-registered later if
    # a task needs it.
    #
    # def list_directory(path="."):
    #     target = resolve(path)
    #     if target.startswith("error:"):
    #         return target
    #     p = Path(target)
    #     if not p.is_dir():
    #         return oops(f"'{path}' is not a directory")
    #     entries = sorted(p.iterdir(), key=lambda e: e.name)
    #     names = [f"{e.name}/" if e.is_dir() else e.name for e in entries]
    #     return "\n".join(names) if names else "(empty)"

    def read_file(path):
        target = resolve(path)
        if target.startswith("error:"):
            return target
        p = Path(target)
        if not p.is_file():
            return oops(f"'{path}' is not a file")
        try:
            return p.read_text()
        except Exception as e:
            # Ruby: `rescue => e` (StandardError, broad) -- a bare OSError
            # catch misses Path.read_text()'s UnicodeDecodeError on a
            # non-UTF-8/binary file, which isn't an OSError subclass.
            return oops(str(e))

    def write_file(path, content):
        target = resolve(path)
        if target.startswith("error:"):
            return target
        p = Path(target)
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content)
            rel = target[len(root) + 1:]
            return f"ok: wrote {len(content.encode('utf-8'))} bytes to {rel}"
        except Exception as e:
            return oops(str(e))

    def delete_file(path):
        target = resolve(path)
        if target.startswith("error:"):
            return target
        p = Path(target)
        if not p.is_file():
            return oops(f"'{path}' is not a file")
        try:
            p.unlink()
            return f"ok: deleted {path}"
        except Exception as e:
            return oops(str(e))

    # search_files: disabled for now -- same reason as list_directory above.
    #
    # def search_files(pattern, path=".", glob="*"):
    #     target = resolve(path)
    #     if target.startswith("error:"):
    #         return target
    #     target_path = Path(target)
    #     search_root = target_path.parent if target_path.is_file() else target_path
    #
    #     try:
    #         regex = re.compile(pattern)
    #     except re.error as e:
    #         return oops(f"invalid pattern: {e}")
    #
    #     files = [target_path] if target_path.is_file() else sorted(search_root.glob(f"**/{glob}"))
    #     matches = []
    #     for f in files:
    #         if not f.is_file():
    #             continue
    #         rel = str(f)[len(root) + 1:]
    #         try:
    #             for lineno, line in enumerate(f.read_text().splitlines(), start=1):
    #                 if regex.search(line):
    #                     matches.append(f"{rel}:{lineno}:{line}")
    #         except Exception as e:
    #             matches.append(f"{rel}: error reading file: {e}")
    #     return "\n".join(matches) if matches else "no matches"

    registry.tool(
        "pwd",
        description="Return the working directory — the root that all file paths are relative to.",
        parameters={},
        block=pwd,
    )
    # registry.tool(
    #     "list_directory",
    #     description="List files and subdirectories at a path relative to the working directory. Defaults to the working directory itself.",
    #     parameters={"path": {"type": "string", "description": "Relative path to list (default '.')"}},
    #     block=list_directory,
    # )
    registry.tool(
        "read_file",
        description="Read and return the full contents of a file. Path is relative to the working directory.",
        parameters={"path": {"type": "string", "description": "Relative path to the file"}},
        block=read_file,
    )
    registry.tool(
        "write_file",
        description="Write content to a file, creating it (and any missing parent directories) if needed, overwriting if it exists. Path is relative to the working directory.",
        parameters={
            "path": {"type": "string", "description": "Relative path to the file"},
            "content": {"type": "string", "description": "Text content to write"},
        },
        block=write_file,
    )
    registry.tool(
        "delete_file",
        description="Delete a file. Directories are not deleted. Path is relative to the working directory.",
        parameters={"path": {"type": "string", "description": "Relative path to the file to delete"}},
        block=delete_file,
    )
    # registry.tool(
    #     "search_files",
    #     description="Search for a text pattern (literal string or regex) across all files in the working directory tree. Returns matching lines in 'path:line_number:content' format.",
    #     parameters={
    #         "pattern": {"type": "string", "description": "The text or regex pattern to search for"},
    #         "path": {"type": "string", "description": "Subdirectory or file to search within (default '.' = entire working directory)"},
    #         "glob": {"type": "string", "description": "File glob to restrict which files are searched, e.g. '*.rb' (default '*')"},
    #     },
    #     block=search_files,
    # )
