"""Port of week1_baseline/ruby/12_context/lib/boukensha/config.rb --
Tasks::Base/Tasks::Player are gone in Ruby this step; Config absorbs their
responsibilities directly (system_prompt, model, provider_type,
agent_max_*). See docs/plans/python_port/12_context.

No PROMPTS_DIR constant -- 12_context's Ruby step ships no prompts/
directory at all (confirmed), so there's no step-bundled default prompt
to fall back to anymore. system_prompt resolves entirely from the user's
.boukensha config dir (task-override path or flat path), or None if
neither exists.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv


class Config:
    # The .boukensha config directory is resolved in this order:
    #   1. BOUKENSHA_DIR environment variable
    #   2. ~/.boukensha  (default)
    #
    # 11_tui had a third tier (.boukensha/ in the current working
    # directory) -- Ruby's 12_context config.rb#resolve_dir dropped it
    # entirely (a real behavior change, not comment churn; confirmed via
    # diff against 11_tui's config.rb). This port initially kept the old
    # 3-tier logic by mistake (the port plan incorrectly claimed
    # resolve_dir was unchanged) -- found by code review (CONFIRMED) and
    # fixed to match Ruby's 2-tier version exactly.
    DEFAULT_DIR = str(Path.home() / ".boukensha")

    def __init__(self) -> None:
        self.dir = self._resolve_dir()
        self._load_env()
        self.settings = self._load_settings()
        self.system_prompt = self._load_system_prompt()

    # ---------- provider ----------------------------------------------------

    @property
    def provider_type(self) -> str:
        v = self.dig("tasks", "player", "provider")
        return v if v is not None else "anthropic"

    @property
    def model(self) -> str:
        v = self.dig("tasks", "player", "model")
        return v if v is not None else "claude-haiku-4-5"

    # ---------- system prompt ------------------------------------------------

    def system_override(self) -> bool:
        # Dead code in Ruby too -- _load_system_prompt checks a different,
        # hardcoded key path directly rather than calling this. Ported
        # faithfully, not "fixed" -- not this port's call to resolve an
        # open question the source itself hasn't resolved.
        return self.dig("system", "override") is True

    # ---------- MUD connection ------------------------------------------------

    @property
    def mud_host(self) -> str:
        v = self.dig("mud", "host")
        return v if v is not None else "localhost"

    @property
    def mud_port(self) -> int:
        v = self.dig("mud", "port")
        return v if v is not None else 4000

    @property
    def mud_username(self) -> str | None:
        return self.dig("mud", "username")

    @property
    def mud_password(self) -> str | None:
        return self.dig("mud", "password")

    # ---------- agent limits ---------------------------------------------------
    # Static per-turn circuit breakers, read where the agent is constructed.
    # A value of 0 or None means "disabled" (no ceiling) -- useful for debugging.

    def agent_max_iterations(self) -> int:
        v = self.dig("agent", "max_iterations")
        return 25 if v is None else int(v)

    def agent_max_output_tokens(self) -> int:
        # Raised 1024 -> 4096 (week2). `max_tokens` is a ceiling on thinking
        # PLUS response text, and adaptive thinking is now requested on models
        # that support it -- so the old ceiling became materially tighter at
        # the same moment truncation stopped being silently reclassified as a
        # completed turn. Costs nothing to raise: you are billed for tokens
        # actually produced, not for the cap.
        v = self.dig("agent", "max_output_tokens")
        return 4096 if v is None else int(v)

    def agent_max_turn_tokens(self) -> int:
        v = self.dig("agent", "max_turn_tokens")
        return 60_000 if v is None else int(v)

    def agent_prompt_caching(self) -> bool:
        # Kill-switch for Anthropic prompt caching. Defaults ON: it is the
        # single largest lever for this workload (input outweighs output
        # 74:1) and it relieves the turn-budget ceiling that cut off 82% of
        # week1 turns. Set `agent.prompt_caching: false` to disable.
        v = self.dig("agent", "prompt_caching")
        return True if v is None else bool(v)

    def agent_compaction_threshold(self) -> float:
        v = self.dig("agent", "compaction_threshold")
        return 0.85 if v is None else float(v)

    # ---------- low-level helpers -----------------------------------------

    def dig(self, *keys: Any) -> Any:
        node: Any = self.settings
        for key in keys:
            if isinstance(node, dict):
                node = node.get(str(key))
            else:
                return None
        return node

    def __repr__(self) -> str:
        return f"#<Boukensha::Config dir={self.dir} provider={self.provider_type} model={self.model}>"

    __str__ = __repr__

    # ---------- private -----------------------------------------------------

    def _resolve_dir(self) -> str:
        raw = os.environ.get("BOUKENSHA_DIR")
        if raw is None:
            raw = self.DEFAULT_DIR
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

    # Resolves the system prompt. When the player task opts into a prompt
    # override (tasks.player.prompt_override.system: true), the task-scoped
    # file prompts/player/system.md wins; otherwise (and as a fallback) the
    # flat prompts/system.md is used. Returns None when neither exists.
    def _load_system_prompt(self) -> str | None:
        if self.dig("tasks", "player", "prompt_override", "system") is True:
            task_file = Path(self.dir) / "prompts" / "player" / "system.md"
            if task_file.exists():
                return task_file.read_text().strip()

        system_file = Path(self.dir) / "prompts" / "system.md"
        return system_file.read_text().strip() if system_file.exists() else None
