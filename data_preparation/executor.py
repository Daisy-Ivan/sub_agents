"""Processing-plan execution for the data preparation sub-agent."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .config import DataPreparationConfig
from .exceptions import ExecutionError
from .schemas import PreparationPlan, SubTask
from .tools import ToolContext, ToolRegistry


@dataclass(slots=True)
class ExecutionSummary:
    """Structured summary of a plan execution run."""

    updated_plan: PreparationPlan
    execution_trace: list[dict[str, Any]] = field(default_factory=list)
    output_paths: list[Path] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    partial_success: bool = False
    success: bool = True

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable summary payload."""

        return {
            "updated_plan": self.updated_plan.model_dump(mode="json"),
            "execution_trace": self.execution_trace,
            "output_paths": [str(path) for path in self.output_paths],
            "warnings": list(self.warnings),
            "partial_success": self.partial_success,
            "success": self.success,
        }


class PlanExecutor:
    """Execute a processing plan using the registered low-level tools."""

    def __init__(
        self,
        config: DataPreparationConfig | None = None,
        registry: ToolRegistry | None = None,
    ) -> None:
        self.config = config or DataPreparationConfig()
        self.registry = registry or ToolRegistry.build_default()

    def execute(self, plan: PreparationPlan) -> ExecutionSummary:
        """Execute a plan in order, updating task statuses and collecting trace entries."""

        try:
            normalized_plan = PreparationPlan.model_validate(plan)
        except Exception as exc:
            raise ExecutionError(f"invalid execution plan: {exc}") from exc

        output_dir = self._resolve_output_dir(normalized_plan)
        context = ToolContext(output_dir=output_dir)
        execution_trace: list[dict[str, Any]] = []
        output_paths: list[Path] = []
        warnings: list[str] = []
        failed_count = 0
        succeeded_count = 0

        for task in normalized_plan.tasks:
            task.status = "running"
            execution_trace.append(
                self._trace_entry(
                    task,
                    event="task_started",
                    details={"tool_name": task.tool_name or task.task_type},
                )
            )

            try:
                tool = self.registry.resolve(task)
                result = tool.run(task, context)
                if not result.success:
                    raise ExecutionError(result.message)
            except Exception as exc:
                task.status = "failed"
                failed_count += 1
                warnings.append(str(exc))
                execution_trace.append(
                    self._trace_entry(
                        task,
                        event="task_failed",
                        details={"error": str(exc)},
                    )
                )
                if not self.config.allow_partial_success:
                    raise ExecutionError(f"task {task.task_id} failed: {exc}") from exc
                continue

            task.status = "done"
            succeeded_count += 1
            output_paths.extend(result.output_paths)
            warnings.extend(result.warnings)
            execution_trace.append(
                self._trace_entry(
                    task,
                    event="task_completed",
                    details={
                        "message": result.message,
                        "output_paths": [str(path) for path in result.output_paths],
                        "warnings": list(result.warnings),
                    },
                )
            )

        return ExecutionSummary(
            updated_plan=normalized_plan,
            execution_trace=execution_trace,
            output_paths=output_paths,
            warnings=self._dedupe(warnings),
            partial_success=failed_count > 0 and succeeded_count > 0,
            success=failed_count == 0,
        )

    def _resolve_output_dir(self, plan: PreparationPlan) -> Path:
        if self.config.output_dir is not None:
            output_dir = self.config.output_dir
        else:
            first_ref = next(
                (Path(ref) for task in plan.tasks for ref in task.input_refs),
                Path.cwd(),
            )
            output_dir = first_ref.parent / "prepared_outputs"
        output_dir.mkdir(parents=True, exist_ok=True)
        return output_dir

    def _trace_entry(
        self,
        task: SubTask,
        *,
        event: str,
        details: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "task_id": task.task_id,
            "task_type": task.task_type,
            "status": task.status,
            "event": event,
            "details": details,
        }

    def _dedupe(self, values: list[str]) -> list[str]:
        deduped: list[str] = []
        seen: set[str] = set()
        for value in values:
            normalized = value.strip()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            deduped.append(normalized)
        return deduped
