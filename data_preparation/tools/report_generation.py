"""Report-generation tool for lightweight validation artifacts."""

from __future__ import annotations

from ._io_helpers import existing_paths, read_rows
from .base import BaseTool, ToolContext, ToolResult
from ..schemas import SubTask


class ReportGenerationTool(BaseTool):
    """Produce lightweight reports for validation-style processing tasks."""

    name = "report_generation"
    supported_task_types = ("sample_id_validation", "time_axis_check")

    def run(self, task: SubTask, context: ToolContext) -> ToolResult:
        output_paths = []
        warnings = []

        for path in existing_paths(task):
            header, rows = read_rows(path)
            output_path = context.output_dir / f"{path.stem}_{task.task_type}.txt"

            if task.task_type == "sample_id_validation":
                candidate_ids = [row[0].strip() for row in rows if row]
                duplicate_count = len(candidate_ids) - len(set(candidate_ids))
                content = (
                    f"task={task.task_type}\n"
                    f"input={path}\n"
                    f"sample_count={len(candidate_ids)}\n"
                    f"duplicate_count={duplicate_count}\n"
                )
                if duplicate_count:
                    warnings.append(f"duplicate sample identifiers detected in {path.name}")
            else:
                temporal_columns = [
                    column
                    for column in header
                    if any(token in column for token in ("date", "time", "year", "month", "day"))
                ]
                content = (
                    f"task={task.task_type}\n"
                    f"input={path}\n"
                    f"temporal_columns={','.join(temporal_columns)}\n"
                )
                if not temporal_columns:
                    warnings.append(f"no obvious temporal column detected in {path.name}")

            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(content, encoding="utf-8")
            output_paths.append(output_path)

        return ToolResult(
            success=True,
            message=f"Generated {len(output_paths)} lightweight report artifact(s) for {task.task_type}.",
            output_paths=output_paths,
            warnings=warnings,
        )
