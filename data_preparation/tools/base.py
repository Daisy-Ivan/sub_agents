"""Base tool contracts for the data preparation execution layer."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..schemas import SubTask


@dataclass(slots=True)
class ToolContext:
    """Shared execution context passed to low-level tools."""

    output_dir: Path
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ToolResult:
    """Structured result returned by a low-level execution tool."""

    success: bool
    message: str
    output_paths: list[Path] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


class BaseTool(ABC):
    """Abstract base class for future execution tools."""

    name: str = ""
    supported_task_types: tuple[str, ...] = ()

    def supports(self, task_type: str) -> bool:
        """Return whether this tool can execute the given task type."""

        return task_type in self.supported_task_types

    def prompt_summary(self) -> str:
        """Return a short human-readable description for tool-selection prompts."""

        docstring = (self.__doc__ or "").strip()
        if not docstring:
            return "Registered execution tool."
        return docstring.splitlines()[0].strip()

    @abstractmethod
    def run(self, task: SubTask, context: ToolContext) -> ToolResult:
        """Execute a task and return a structured result."""
