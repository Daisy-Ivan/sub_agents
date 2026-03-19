"""Template for adding a new execution tool.

How to use this template:
1. Copy this file and rename it, for example `my_new_tool.py`.
2. Rename `TemplateTool` to a concrete class name.
3. Fill in `name` and `supported_task_types`.
4. Implement the task logic inside `run(...)`.
5. Register the tool in `tools/registry.py`.
6. Make planner output matching `task_type` / `tool_name`.
7. Add focused tests for the tool and executor path.

This file is intentionally not registered by default.
"""

from __future__ import annotations

from pathlib import Path

from ..exceptions import ExecutionError
from ..schemas import SubTask
from .base import BaseTool, ToolContext, ToolResult


class TemplateTool(BaseTool):
    """Copyable scaffold for new low-level processing tools."""

    name = "template_tool"
    supported_task_types = ("template_task",)

    def run(self, task: SubTask, context: ToolContext) -> ToolResult:
        """Execute a new task type and return a structured result.

        Recommended implementation pattern:
        - validate `task.input_refs`
        - read source files
        - write outputs into `context.output_dir`
        - return `ToolResult(success=True, ...)`
        """

        input_paths = [Path(path) for path in task.input_refs]
        if not input_paths:
            raise ExecutionError("template tool requires at least one input path")

        missing_paths = [str(path) for path in input_paths if not path.exists()]
        if missing_paths:
            raise ExecutionError(f"missing task inputs: {', '.join(missing_paths)}")

        output_path = context.output_dir / f"{task.task_id}_template_output.txt"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            "\n".join(
                [
                    f"task_id={task.task_id}",
                    f"task_type={task.task_type}",
                    f"input_count={len(input_paths)}",
                    "Replace this file with real tool logic.",
                ]
            ),
            encoding="utf-8",
        )

        return ToolResult(
            success=True,
            message="Template tool executed. Replace this implementation with real task logic.",
            output_paths=[output_path],
            metadata={
                "template": True,
                "next_steps": [
                    "rename the tool class",
                    "implement real transformation logic",
                    "register the tool in ToolRegistry.build_default",
                    "emit matching task_type/tool_name from planner",
                ],
            },
        )
