"""Source-merge manifest tool."""

from __future__ import annotations

from ._io_helpers import existing_paths, write_csv
from .base import BaseTool, ToolContext, ToolResult
from ..schemas import SubTask


class SourceMergeTool(BaseTool):
    """Generate a conservative merge manifest for downstream alignment work."""

    name = "source_merge"
    supported_task_types = ("source_merge",)

    def run(self, task: SubTask, context: ToolContext) -> ToolResult:
        paths = existing_paths(task)
        output_path = context.output_dir / f"{task.task_id}_source_manifest.csv"
        rows = [[str(index + 1), path.name, str(path)] for index, path in enumerate(paths)]
        write_csv(output_path, ["source_index", "file_name", "file_path"], rows)
        return ToolResult(
            success=True,
            message="Created a merge manifest for downstream alignment.",
            output_paths=[output_path],
            metadata={"input_count": len(paths)},
        )
