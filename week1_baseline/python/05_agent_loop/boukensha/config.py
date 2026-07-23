"""Port of week1_baseline/ruby/04_api_client/lib/boukensha/config.rb --
byte-identical to 03_prompt_builder's Ruby source except a PROMPTS_DIR
off-by-one bug (fixed on the Ruby side, no Python change needed -- see
docs/plans/python_port/04_api_client). Keep this a literal mirror of the
Ruby Config class; re-read the Ruby source before changing behavior here.

PROMPTS_DIR (added in 03_prompt_builder, absent since 01_struct_skeleton --
see docs/plans/python_port/01_struct_skeleton) resolves via 1 .parent.parent
hop, correct since it was first added: Python's config.py has no lib/
wrapper directory the way Ruby's lib/boukensha/config.rb does, so it needs
one fewer hop than Ruby's (fixed) 2 `../`.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv


class Config:
    # The .boukensha config directory is resolved in this order:
    #   1. BOUKENSHA_DIR environment variable (set before loading .env)
    #   2. ~/.boukensha  (default)
    DEFAULT_DIR = str(Path.home() / ".boukensha")

    # Default prompts shipped alongside this package. Ruby's equivalent is
    # 2 `../` hops from lib/boukensha/config.rb to the step root (lib/boukensha
    # -> lib -> step root); Python's config.py has no `lib/` wrapper directory
    # (boukensha/config.py sits directly under the step root), so 1
    # `.parent.parent` hop lands in the same place -- different hop count by
    # construction, not a mismatch.
    PROMPTS_DIR = str(Path(__file__).resolve().parent.parent / "prompts")

    def __init__(self) -> None:
        self.dir = self._resolve_dir()
        self._load_env()
        self.settings = self._load_settings()

    # ---------- tasks -----------------------------------------------------

    def tasks(self, name: str | None = None) -> Any:
        """With no argument: the full tasks dict from settings.yaml.
        With a name: that task's settings dict, e.g. tasks("player").
        """
        dug = self.dig("tasks")
        all_tasks = {} if dug is None else dug
        if name is None:
            return all_tasks
        return all_tasks.get(str(name))

    @property
    def user_prompts_dir(self) -> str:
        """The user's prompts directory for task prompt overrides."""
        return str(Path(self.dir) / "prompts")

    # ---------- MUD connection ---------------------------------------------

    # Ruby's `dig(...) || default` only falls back when dig returns nil --
    # 0, "", etc. are truthy in Ruby and would be kept as-is. Python's `or`
    # falls back on ANY falsy value, so `x or default` is NOT equivalent --
    # use an explicit `is None` check to match Ruby's actual semantics
    # (confirmed bug, found by code review 2026-07-21: an explicit
    # `mud.port: 0` or `mud.host: ""` in settings.yaml was being silently
    # overridden with the default instead of honored).

    @property
    def mud_host(self) -> str:
        dug = self.dig("mud", "host")
        return "localhost" if dug is None else dug

    @property
    def mud_port(self) -> int:
        dug = self.dig("mud", "port")
        return 4000 if dug is None else dug

    @property
    def mud_username(self) -> str | None:
        return self.dig("mud", "username")

    @property
    def mud_password(self) -> str | None:
        return self.dig("mud", "password")

    # ---------- low-level helpers -------------------------------------------

    def dig(self, *keys: Any) -> Any:
        """Fetch a nested key path from settings, e.g. dig("mud", "host")."""
        node: Any = self.settings
        for key in keys:
            if isinstance(node, dict):
                node = node.get(str(key))
            else:
                return None
        return node

    def __repr__(self) -> str:
        return f"#<Boukensha::Config dir={self.dir} tasks={','.join(self.tasks().keys())}>"

    __str__ = __repr__

    # ---------- private -----------------------------------------------------

    def _resolve_dir(self) -> str:
        # Ruby's ENV.fetch("BOUKENSHA_DIR", nil) only falls back to
        # DEFAULT_DIR when the var is entirely UNSET -- an explicitly
        # empty BOUKENSHA_DIR="" is honored as-is (Ruby's "" is truthy).
        # os.environ.get(...) or default has the same falsy-collapse bug
        # as mud_host/mud_port above -- use `is None`-style presence check
        # instead (os.environ.get with no default returns None iff unset).
        env_value = os.environ.get("BOUKENSHA_DIR")
        raw = self.DEFAULT_DIR if env_value is None else env_value
        # Ruby's Pathname#expand_path normalizes without following symlinks;
        # Path.resolve() also follows symlinks. Harmless difference for the
        # realistic inputs here (absolute paths or "~/.boukensha"), noted for
        # fidelity's sake rather than silently diverging.
        return str(Path(raw).expanduser().resolve())

    def _load_env(self) -> None:
        env_file = Path(self.dir) / ".env"
        if env_file.exists():
            load_dotenv(str(env_file))

    def _load_settings(self) -> dict:
        settings_file = Path(self.dir) / "settings.yaml"
        if settings_file.exists():
            return yaml.safe_load(settings_file.read_text()) or {}
        return {}
