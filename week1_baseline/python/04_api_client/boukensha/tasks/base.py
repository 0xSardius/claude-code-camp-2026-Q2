"""Port of week1_baseline/ruby/04_api_client/lib/boukensha/tasks/base.rb --
byte-identical to 03_prompt_builder's version except a settings.is_a?(Hash)
guard in fetch and a "settings.yml" -> "settings.yaml" wording fix (see
docs/plans/python_port/04_api_client). Keep this a literal mirror of the
Ruby Tasks::Base class; re-read the Ruby source before changing behavior
here.

Ruby's "abstract, classmethod-only, never instantiated" pattern is mirrored
here with @classmethod on every public method and a TASK_NAME class
attribute subclasses must set (checked by task_name(), which raises if
unset -- same as Ruby's .task_name raising NotImplementedError).
"""
from __future__ import annotations

from pathlib import Path
from typing import Any


class Base:
    TASK_NAME: str | None = None

    @classmethod
    def task_name(cls) -> str:
        if cls.TASK_NAME is None:
            raise NotImplementedError(f"{cls.__name__} must define TASK_NAME")
        return cls.TASK_NAME

    @classmethod
    def provider(cls, settings: dict) -> str:
        # Ruby: fetch(...) || raise -- raises on nil OR false, not just nil.
        # `value is None or value is False` matches that; a bare `not value`
        # would be too broad (would also reject "" and 0, which Ruby's ||
        # does NOT treat as missing).
        value = cls._fetch(settings, "provider")
        if value is None or value is False:
            raise ValueError(f"tasks.{cls.task_name()}.provider is required in settings.yaml")
        return value

    @classmethod
    def model(cls, settings: dict) -> str:
        value = cls._fetch(settings, "model")
        if value is None or value is False:
            raise ValueError(f"tasks.{cls.task_name()}.model is required in settings.yaml")
        return value

    @classmethod
    def prompt_override(cls, settings: dict, prompt: str = "system") -> bool:
        node = cls._fetch(settings, "prompt_override")
        if not isinstance(node, dict):
            return False
        return node.get(str(prompt)) is True

    @classmethod
    def prompt(
        cls,
        settings: dict,
        name: str = "system",
        *,
        user_prompts_dir: str | None = None,
        default_prompts_dir: str | None = None,
    ) -> str | None:
        if cls.prompt_override(settings, name):
            text = cls._read_user_prompt(name, user_prompts_dir=user_prompts_dir)
            if text:
                return text
        return cls._read_default_prompt(name, default_prompts_dir=default_prompts_dir)

    @classmethod
    def system_prompt(
        cls,
        settings: dict,
        *,
        user_prompts_dir: str | None = None,
        default_prompts_dir: str | None = None,
    ) -> str | None:
        return cls.prompt(
            settings, "system", user_prompts_dir=user_prompts_dir, default_prompts_dir=default_prompts_dir
        )

    # ---------- private -----------------------------------------------------

    @classmethod
    def _fetch(cls, settings: dict, key: Any) -> Any:
        # Ruby (04_api_client): `return nil unless settings.is_a?(Hash)` --
        # guards against settings being None (e.g. config.tasks("nonexistent")
        # resolves to None), so provider()/model() raise their own clear
        # "required in settings.yaml" error instead of a confusing
        # AttributeError from calling .get on None. Supersedes this
        # method's previous behavior (03_prompt_builder and earlier), which
        # deliberately mirrored Ruby's old NoMethodError-on-nil crash --
        # that's no longer true of the Ruby source as of this step.
        if not isinstance(settings, dict):
            return None
        return settings.get(str(key))

    @classmethod
    def _read_user_prompt(cls, prompt_name: str, *, user_prompts_dir: str | None = None) -> str | None:
        if not user_prompts_dir:
            return None
        return cls._read_file(Path(user_prompts_dir) / cls.task_name() / f"{prompt_name}.md")

    @classmethod
    def _read_default_prompt(cls, prompt_name: str, *, default_prompts_dir: str | None = None) -> str | None:
        if not default_prompts_dir:
            return None
        return cls._read_file(Path(default_prompts_dir) / f"{prompt_name}.md")

    @staticmethod
    def _read_file(path: Path) -> str | None:
        return path.read_text().strip() if path.exists() else None
