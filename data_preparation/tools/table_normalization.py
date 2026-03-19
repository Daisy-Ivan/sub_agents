"""Generic table normalization tool."""

from __future__ import annotations

from ._io_helpers import existing_paths, read_rows, write_csv
from .base import BaseTool, ToolContext, ToolResult
from ..schemas import SubTask


class TableNormalizationTool(BaseTool):
    """Normalize delimited or whitespace tables into simple CSV outputs."""

    name = "table_normalization"
    supported_task_types = (
        "snp_matrix_standardization",
        "weather_table_normalization",
        "metadata_normalization",
    )

    def run(self, task: SubTask, context: ToolContext) -> ToolResult:
        output_paths = []
        for path in existing_paths(task):
            header, rows = read_rows(path)
            width = len(header)
            normalized_rows = [row[:width] + [""] * max(0, width - len(row)) for row in rows]
            output_path = context.output_dir / f"{path.stem}_{task.task_type}.csv"
            write_csv(output_path, header, normalized_rows)
            output_paths.append(output_path)

        return ToolResult(
            success=True,
            message=f"Normalized {len(output_paths)} table input(s) for task {task.task_type}.",
            output_paths=output_paths,
        )
