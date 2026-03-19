"""Tool registry for the data preparation execution layer."""

from __future__ import annotations

from typing import Any

from ..exceptions import ExecutionError
from ..schemas import SubTask
from .base import BaseTool
from .plink_conversion import PlinkConversionTool
from .report_generation import ReportGenerationTool
from .source_merge import SourceMergeTool
from .table_normalization import TableNormalizationTool


class ToolRegistry:
    """Resolve processing tasks to concrete low-level tools."""

    def __init__(self) -> None:
        self._tools_by_name: dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        """Register a tool under its name and supported task types.

        Steps for adding a new tool:
        1. Copy `tools/tool_template.py` to a new module.
        2. Rename the class and fill in `name` / `supported_task_types`.
        3. Implement `run(task, context) -> ToolResult`.
        4. Import the tool class in this file.
        5. Add `registry.register(YourTool())` in `build_default()`.
        6. Make planner emit matching `task_type` / `tool_name`.
        7. Add focused tests for both the tool and executor path.
        """

        if tool.name:
            self._tools_by_name[tool.name] = tool
        for task_type in tool.supported_task_types:
            self._tools_by_name[task_type] = tool

    def resolve(self, task: SubTask) -> BaseTool:
        """Resolve a subtask to its concrete tool instance."""

        key = task.tool_name or task.task_type
        tool = self._tools_by_name.get(key)
        if tool is None:
            raise ExecutionError(f"no tool is registered for task type {key}")
        return tool

    def describe_tools(self) -> list[dict[str, Any]]:
        """Return stable tool descriptors for prompts and debugging."""

        descriptors: list[dict[str, Any]] = []
        seen_names: set[str] = set()
        for tool in self._tools_by_name.values():
            if not tool.name or tool.name in seen_names:
                continue
            seen_names.add(tool.name)
            descriptors.append(
                {
                    "name": tool.name,
                    "supported_task_types": list(tool.supported_task_types),
                    "summary": tool.prompt_summary(),
                }
            )
        return sorted(descriptors, key=lambda item: item["name"])

    @classmethod
    def build_default(cls) -> "ToolRegistry":
        """Build the default registry for the current rule-based task set.

        When a new tool is added, register it here so the executor can resolve
        it deterministically instead of relying on any model-side discovery.
        """

        registry = cls()
        registry.register(PlinkConversionTool())
        registry.register(TableNormalizationTool())
        registry.register(ReportGenerationTool())
        registry.register(SourceMergeTool())
        return registry
