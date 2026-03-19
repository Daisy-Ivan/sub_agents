"""Planning-layer scaffold."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal
from uuid import uuid4

from .config import DataPreparationConfig
from .exceptions import PlanningError
from .router import RouteName
from .schemas import (
    FileInspectionResult,
    NormalizedInputBundle,
    PreparationPlan,
    ReadinessDecision,
    SubTask,
)

PlannerMode = Literal["rule_only", "hybrid", "llm_enhanced"]


@dataclass(slots=True)
class PlanningContext:
    """Small normalized view of processing-relevant bundle contents."""

    genotype_files: list[FileInspectionResult]
    environment_files: list[FileInspectionResult]
    metadata_files: list[FileInspectionResult]


class RuleBasedPlanner:
    """Deterministic planner for the processing route."""

    def __init__(self, config: DataPreparationConfig | None = None) -> None:
        self.config = config or DataPreparationConfig()

    def build_plan(
        self,
        bundle: NormalizedInputBundle,
        readiness_decision: ReadinessDecision,
        route_name: RouteName,
    ) -> PreparationPlan | None:
        """Build a preparation plan only for the processing route."""

        try:
            normalized_bundle = NormalizedInputBundle.model_validate(bundle)
            normalized_decision = ReadinessDecision.model_validate(readiness_decision)
        except Exception as exc:
            raise PlanningError(f"invalid planning inputs: {exc}") from exc

        if route_name != "processing":
            return None
        if normalized_decision.bundle_status != "transformable":
            return None

        context = PlanningContext(
            genotype_files=[
                file for file in normalized_bundle.genotype_files if file.usability == "transformable"
            ],
            environment_files=[
                file
                for file in normalized_bundle.environment_files
                if file.usability == "transformable"
            ],
            metadata_files=[
                file for file in normalized_bundle.metadata_files if file.usability == "transformable"
            ],
        )
        tasks = self._build_rule_tasks(context)
        if not tasks:
            raise PlanningError(
                "processing route was selected, but no rule-based preparation tasks could be derived"
            )

        rationale = self._build_rationale(context=context, task_count=len(tasks))
        return PreparationPlan(
            plan_id=f"prep-plan-{uuid4().hex[:8]}",
            tasks=tasks,
            rationale=rationale,
        )

    def _build_rule_tasks(self, context: PlanningContext) -> list[SubTask]:
        tasks: list[SubTask] = []

        if context.genotype_files:
            if any(self._is_plink_component(file.file_path) for file in context.genotype_files):
                tasks.append(
                    self._task(
                        "plink_conversion",
                        "Convert PLINK-style genotype components into a consolidated downstream-friendly representation.",
                        context.genotype_files,
                    )
                )
            else:
                tasks.append(
                    self._task(
                        "snp_matrix_standardization",
                        "Standardize transformable genotype matrices or variant tables into a consistent SNP-oriented structure.",
                        context.genotype_files,
                    )
                )
            tasks.append(
                self._task(
                    "sample_id_validation",
                    "Validate and normalize genotype sample identifiers before downstream joins.",
                    context.genotype_files,
                )
            )

        if context.environment_files:
            tasks.append(
                self._task(
                    "weather_table_normalization",
                    "Normalize transformable environment tables into a consistent weather or site matrix.",
                    context.environment_files,
                )
            )
            tasks.append(
                self._task(
                    "time_axis_check",
                    "Check and normalize temporal axes so downstream environment alignment is safe.",
                    context.environment_files,
                )
            )

        merge_candidates = [
            *context.genotype_files,
            *context.environment_files,
            *context.metadata_files,
        ]
        if len(merge_candidates) > 1:
            tasks.append(
                self._task(
                    "source_merge",
                    "Prepare transformable sources for consistent downstream merging and cross-file alignment.",
                    merge_candidates,
                )
            )

        if context.metadata_files:
            tasks.append(
                self._task(
                    "metadata_normalization",
                    "Normalize transformable metadata tables so they can support sample or site joins safely.",
                    context.metadata_files,
                )
            )

        return tasks

    def _build_rationale(self, *, context: PlanningContext, task_count: int) -> str:
        segments: list[str] = []
        if context.genotype_files:
            segments.append(f"{len(context.genotype_files)} transformable genotype file(s)")
        if context.environment_files:
            segments.append(f"{len(context.environment_files)} transformable environment file(s)")
        if context.metadata_files:
            segments.append(f"{len(context.metadata_files)} transformable metadata file(s)")
        summary = ", ".join(segments)
        return (
            "A processing plan was generated because the bundle was routed to the processing path "
            f"with {summary}. The rule-based planner produced {task_count} preparation task(s)."
        )

    def _task(
        self,
        task_type: str,
        description: str,
        files: list[FileInspectionResult],
    ) -> SubTask:
        task_suffix = uuid4().hex[:6]
        return SubTask(
            task_id=f"{task_type}-{task_suffix}",
            task_type=task_type,
            description=description,
            input_refs=[str(file.file_path) for file in files],
            tool_name=task_type,
            status="pending",
        )

    def _is_plink_component(self, path: Path) -> bool:
        return path.suffix.lower() in {".bed", ".bim", ".fam", ".ped", ".map"}
