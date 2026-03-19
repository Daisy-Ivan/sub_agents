"""Prompt-loading helpers for optional LLM use."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Mapping

from ..exceptions import PromptTemplateError

PROMPTS_DIR = Path(__file__).resolve().parent
_DOUBLE_BRACE_PATTERN = re.compile(r"\{\{\s*([A-Za-z0-9_]+)\s*\}\}")
_ANGLE_BRACKET_PATTERN = re.compile(r"<([A-Za-z0-9_]+)>")


def list_prompt_templates() -> list[str]:
    """Return available runtime prompt templates."""

    return sorted(
        path.name
        for path in PROMPTS_DIR.glob("*.md")
        if path.is_file() and path.name != "README.md"
    )


def resolve_prompt_path(name: str) -> Path:
    """Resolve a template name to an on-disk prompt path."""

    normalized = name.strip()
    if not normalized:
        raise PromptTemplateError("prompt name must be a non-empty string")
    if not normalized.endswith(".md"):
        normalized = f"{normalized}.md"

    path = PROMPTS_DIR / normalized
    if not path.is_file():
        raise PromptTemplateError(f"prompt template not found: {normalized}")
    return path


def load_prompt_template(name: str) -> str:
    """Load a raw prompt template by filename or stem."""

    return resolve_prompt_path(name).read_text(encoding="utf-8")


def render_prompt_template(
    name: str,
    variables: Mapping[str, Any] | None = None,
    **kwargs: Any,
) -> str:
    """Render a prompt template using simple placeholder replacement."""

    values: dict[str, Any] = {}
    if variables:
        values.update(dict(variables))
    values.update(kwargs)

    template = load_prompt_template(name)
    missing: set[str] = set()

    def replace(match: re.Match[str]) -> str:
        key = match.group(1)
        if key not in values:
            missing.add(key)
            return match.group(0)

        value = values[key]
        if isinstance(value, (list, tuple, set)):
            return "\n".join(str(item) for item in value)
        if isinstance(value, dict):
            return json.dumps(value, ensure_ascii=True, indent=2, sort_keys=True)
        return str(value)

    rendered = _DOUBLE_BRACE_PATTERN.sub(replace, template)
    rendered = _ANGLE_BRACKET_PATTERN.sub(replace, rendered)

    if missing:
        missing_names = ", ".join(sorted(missing))
        raise PromptTemplateError(
            f"missing prompt variables for {name}: {missing_names}"
        )
    return rendered


__all__ = [
    "PROMPTS_DIR",
    "list_prompt_templates",
    "load_prompt_template",
    "render_prompt_template",
    "resolve_prompt_path",
]
