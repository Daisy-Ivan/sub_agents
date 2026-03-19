"""PLINK conversion tool."""

from __future__ import annotations

from ._io_helpers import existing_paths, write_csv
from .base import BaseTool, ToolContext, ToolResult
from ..exceptions import ExecutionError
from ..schemas import SubTask


class PlinkConversionTool(BaseTool):
    """Convert PLINK-like component files into a simple standardized table."""

    name = "plink_conversion"
    supported_task_types = ("plink_conversion",)

    def run(self, task: SubTask, context: ToolContext) -> ToolResult:
        output_paths = []
        for path in existing_paths(task):
            suffix = path.suffix.lower()
            if suffix == ".bim":
                header = [
                    "chromosome",
                    "variant_id",
                    "genetic_distance",
                    "position",
                    "allele_1",
                    "allele_2",
                ]
                rows = [
                    line.split()[:6]
                    for line in path.read_text(encoding="utf-8").splitlines()
                    if line.strip()
                ]
            else:
                rows = [
                    [str(index + 1), line.strip()]
                    for index, line in enumerate(path.read_text(encoding="utf-8").splitlines())
                    if line.strip()
                ]
                header = ["record_index", "raw_record"]

            if not rows:
                raise ExecutionError(f"PLINK conversion found no records in {path}")

            output_path = context.output_dir / f"{path.stem}_plink_converted.csv"
            write_csv(output_path, header, rows)
            output_paths.append(output_path)

        return ToolResult(
            success=True,
            message=f"Converted {len(output_paths)} PLINK-like input(s) into standardized tables.",
            output_paths=output_paths,
        )
