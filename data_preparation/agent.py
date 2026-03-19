"""Main orchestration scaffold for the data preparation sub-agent."""

from __future__ import annotations

from typing import Any

from .brain import PlanSuggestionResult, PreparationBrain
from .bundle_builder import BundleBuilder
from .capabilities.data_checker import DataCheckerCapability
from .capabilities.data_refine import DataRefineCapability, RefinementSummary
from .capabilities.report_builder import ReportBuilderCapability, RouteReport
from .config import DataPreparationConfig
from .exceptions import (
    BundleBuildError,
    ExecutionError,
    InspectionError,
    PlanningError,
    PreparationValidationError,
    ReadinessAssessmentError,
    RoutingError,
)
from .executor import ExecutionSummary, PlanExecutor
from .inspector import InputInspector
from .memory import PreparationMemory
from .planner import RuleBasedPlanner
from .readiness_assessor import ReadinessAssessor
from .result_assembler import ResultAssembler
from .router import PreparationRouter, RouteName
from .schemas import (
    FileInspectionResult,
    NormalizedInputBundle,
    PreparationPlan,
    PreparationRequest,
    PreparationResult,
    ReadinessDecision,
    ValidationReport,
)
from .state import PreparationState


class DataPreparationSubAgent:
    """Foundational orchestration scaffold for the gated workflow."""

    def __init__(
        self,
        config: DataPreparationConfig | None = None,
        brain: PreparationBrain | None = None,
    ) -> None:
        self.config = config or DataPreparationConfig()
        self._brain = brain or PreparationBrain(config=self.config)
        self._bundle_builder = BundleBuilder()
        self._checker = DataCheckerCapability()
        self._executor = PlanExecutor(config=self.config)
        self._inspector = InputInspector(config=self.config)
        self._planner = RuleBasedPlanner(config=self.config)
        self._readiness_assessor = ReadinessAssessor()
        self._refiner = DataRefineCapability()
        self._result_assembler = ResultAssembler()
        self._report_builder = ReportBuilderCapability()
        self._router = PreparationRouter(config=self.config)
        self._memory = PreparationMemory()

    def inspect_files(self, request: PreparationRequest) -> list[FileInspectionResult]:
        """Inspect all raw input files and store the results in memory."""

        self._memory = PreparationMemory()
        self._memory.remember_request(request)
        self._memory.transition_to(
            PreparationState.INSPECTING,
            event="inspection_started",
            details={"input_count": len(request.input_files)},
        )
        try:
            inspection_results = self._inspector.inspect_many(request.input_files)
        except Exception as exc:
            error = exc if isinstance(exc, InspectionError) else InspectionError(str(exc))
            self._memory.mark_failed(error)
            raise error from exc

        self._memory.remember_inspection_results(inspection_results)
        self._memory.transition_to(
            PreparationState.INSPECTED,
            event="inspection_completed",
            details={"result_count": len(inspection_results)},
        )
        return inspection_results

    def build_bundle(
        self,
        inspection_results: list[FileInspectionResult],
    ) -> NormalizedInputBundle:
        """Build a normalized bundle and store it in memory."""

        self._prepare_for_bundling(inspection_results)
        if self._memory.current_state == PreparationState.INSPECTED:
            self._memory.transition_to(
                PreparationState.BUNDLING,
                event="bundle_build_started",
                details={"inspection_count": len(inspection_results)},
            )

        try:
            bundle = self._bundle_builder.build(inspection_results)
        except Exception as exc:
            error = exc if isinstance(exc, BundleBuildError) else BundleBuildError(str(exc))
            self._memory.mark_failed(error)
            raise error from exc

        self._memory.remember_bundle(bundle)
        if self._memory.current_state == PreparationState.BUNDLING:
            self._memory.transition_to(
                PreparationState.BUNDLED,
                event="bundle_build_completed",
                details={
                    "genotype_count": len(bundle.genotype_files),
                    "environment_count": len(bundle.environment_files),
                    "metadata_count": len(bundle.metadata_files),
                    "report_count": len(bundle.report_files),
                    "unknown_count": len(bundle.unknown_files),
                },
            )
        else:
            self._memory.record_trace(
                "bundle_rebuilt",
                details={
                    "genotype_count": len(bundle.genotype_files),
                    "environment_count": len(bundle.environment_files),
                    "metadata_count": len(bundle.metadata_files),
                    "report_count": len(bundle.report_files),
                    "unknown_count": len(bundle.unknown_files),
                },
            )
        return bundle

    def assess_readiness(
        self,
        bundle: NormalizedInputBundle,
    ) -> ReadinessDecision:
        """Assess bundle readiness and store the result in memory."""

        self._prepare_for_readiness(bundle)
        if self._memory.current_state == PreparationState.BUNDLED:
            self._memory.transition_to(
                PreparationState.ASSESSING_READINESS,
                event="readiness_assessment_started",
                details={"file_count": self._count_bundle_files(bundle)},
            )

        try:
            decision = self._readiness_assessor.assess(bundle)
        except Exception as exc:
            error = (
                exc
                if isinstance(exc, ReadinessAssessmentError)
                else ReadinessAssessmentError(str(exc))
            )
            self._memory.mark_failed(error)
            raise error from exc

        self._memory.remember_readiness_decision(decision)
        if self._memory.current_state == PreparationState.ASSESSING_READINESS:
            self._memory.transition_to(
                PreparationState.READINESS_ASSESSED,
                event="readiness_assessment_completed",
                details={"bundle_status": decision.bundle_status},
            )
        else:
            self._memory.record_trace(
                "readiness_reassessed",
                details={"bundle_status": decision.bundle_status},
            )
        return decision

    def route(
        self,
        bundle: NormalizedInputBundle,
        readiness_decision: ReadinessDecision,
    ) -> RouteName:
        """Choose a route and store it in memory."""

        self._prepare_for_routing(bundle, readiness_decision)
        if self._memory.current_state == PreparationState.READINESS_ASSESSED:
            self._memory.transition_to(
                PreparationState.ROUTING,
                event="routing_started",
                details={"bundle_status": readiness_decision.bundle_status},
            )

        try:
            route_name = self._router.choose_route(bundle, readiness_decision)
        except Exception as exc:
            error = exc if isinstance(exc, RoutingError) else RoutingError(str(exc))
            self._memory.mark_failed(error)
            raise error from exc

        self._memory.remember_route(route_name)
        if self._memory.current_state == PreparationState.ROUTING:
            self._memory.transition_to(
                PreparationState.ROUTED,
                event="routing_completed",
                details={"route": route_name},
            )
        else:
            self._memory.record_trace("route_reselected", details={"route": route_name})
        return route_name

    def run(self, request: PreparationRequest) -> PreparationResult:
        """Run the full gated workflow through final result assembly."""

        inspection_results = self.inspect_files(request)
        bundle = self.build_bundle(inspection_results)
        readiness_decision = self.assess_readiness(bundle)
        route_name = self.route(bundle, readiness_decision)
        plan = self.build_processing_plan(bundle, readiness_decision, route_name)
        execution_summary = self.execute_processing_plan(plan, route_name)
        refinement_summary = self.refine_outputs(route_name, execution_summary)
        validation_report = self.validate_route_outputs(
            bundle=bundle,
            readiness_decision=readiness_decision,
            route_name=route_name,
            execution_summary=execution_summary,
            refinement_summary=refinement_summary,
        )
        route_report = self.build_route_report(
            bundle=bundle,
            readiness_decision=readiness_decision,
            route_name=route_name,
            validation_report=validation_report,
            execution_summary=execution_summary,
            refinement_summary=refinement_summary,
        )
        return self.assemble_result(
            bundle=bundle,
            readiness_decision=readiness_decision,
            route_name=route_name,
            validation_report=validation_report,
            inspection_results=inspection_results,
            execution_summary=execution_summary,
            refinement_summary=refinement_summary,
            route_report=route_report,
        )

    def build_processing_plan(
        self,
        bundle: NormalizedInputBundle,
        readiness_decision: ReadinessDecision,
        route_name: RouteName,
    ) -> PreparationPlan | None:
        """Build a processing plan only when the selected route requires one."""

        self._prepare_for_planning(bundle, readiness_decision, route_name)
        try:
            plan = self._planner.build_plan(bundle, readiness_decision, route_name)
        except Exception as exc:
            error = exc if isinstance(exc, PlanningError) else PlanningError(str(exc))
            self._memory.mark_failed(error)
            raise error from exc

        if plan is not None and self._brain.available():
            suggestion = self.propose_brain_plan(
                bundle=bundle,
                readiness_decision=readiness_decision,
                route_name=route_name,
                rule_plan=plan,
            )
            self._memory.set_metadata("brain_plan_suggestion", suggestion.as_dict())
            if suggestion.tasks:
                plan = self._merge_plan_with_suggestion(plan, suggestion)
                self._memory.record_trace(
                    "brain_plan_applied",
                    {
                        "suggested_task_count": len(suggestion.tasks),
                        "warning_count": len(suggestion.warnings),
                    },
                )
            else:
                self._memory.record_trace(
                    "brain_plan_not_applied",
                    {
                        "attempted_llm": suggestion.attempted_llm,
                        "used_llm": suggestion.used_llm,
                        "fallback_reason": suggestion.fallback_reason,
                        "warning_count": len(suggestion.warnings),
                    },
                )

        self._memory.remember_preparation_plan(plan)
        self._memory.record_trace(
            "planning_completed",
            {
                "route": route_name,
                "task_count": len(plan.tasks) if plan is not None else 0,
            },
        )
        return plan

    def get_memory_snapshot(self) -> dict[str, Any]:
        """Return the current placeholder memory snapshot."""

        return self._memory.as_dict()

    def refine_outputs(
        self,
        route_name: RouteName,
        execution_summary: ExecutionSummary | dict[str, Any] | None = None,
    ) -> RefinementSummary:
        """Apply conservative refinement to processing outputs and store the summary."""

        execution_payload = execution_summary
        if execution_payload is None:
            execution_payload = self._memory.metadata.get("execution_summary")

        summary = self._refiner.refine(route_name, execution_payload)
        self._memory.set_metadata("refinement_summary", summary.as_dict())
        self._memory.record_trace(
            "refinement_completed",
            {
                "route": route_name,
                "performed": summary.performed,
                "output_count": len(summary.output_paths),
            },
        )
        return summary

    def validate_route_outputs(
        self,
        bundle: NormalizedInputBundle,
        readiness_decision: ReadinessDecision,
        route_name: RouteName,
        execution_summary: ExecutionSummary | dict[str, Any] | None = None,
        refinement_summary: RefinementSummary | dict[str, Any] | None = None,
    ) -> ValidationReport:
        """Validate routed artifacts and persist the validation report in memory."""

        if self._memory.current_state == PreparationState.ROUTED:
            self._memory.transition_to(
                PreparationState.VALIDATING,
                event="validation_started",
                details={"route": route_name},
            )
        elif self._memory.current_state == PreparationState.PROCESSING:
            self._memory.transition_to(
                PreparationState.VALIDATING,
                event="validation_started",
                details={"route": route_name, "reason": "processing completed externally"},
            )
        elif self._memory.current_state != PreparationState.VALIDATING:
            raise PreparationValidationError(
                f"cannot validate outputs from workflow state {self._memory.current_state.value}"
            )

        try:
            report = self._checker.validate(
                bundle=bundle,
                readiness_decision=readiness_decision,
                route_name=route_name,
                execution_summary=execution_summary,
                refinement_summary=refinement_summary,
            )
        except Exception as exc:
            error = (
                exc
                if isinstance(exc, PreparationValidationError)
                else PreparationValidationError(str(exc))
            )
            self._memory.mark_failed(error)
            raise error from exc

        self._memory.remember_validation_report(report)
        self._memory.record_trace(
            "validation_completed",
            {"route": route_name, "passed": report.passed, "issue_count": len(report.issues)},
        )
        return report

    def build_tool_generation_prompt(self, **fields: Any) -> str:
        """Expose the development-time tool generation prompt for debugging."""

        return self._brain.build_tool_generation_prompt(**fields)

    def propose_brain_plan(
        self,
        *,
        bundle: NormalizedInputBundle,
        readiness_decision: ReadinessDecision,
        route_name: RouteName,
        rule_plan: PreparationPlan | None = None,
    ) -> PlanSuggestionResult:
        """Expose optional brain planning so hybrid runs can be debugged safely."""

        return self._brain.suggest_processing_tasks(
            bundle=bundle,
            readiness_decision=readiness_decision,
            route_name=route_name,
            rule_plan=rule_plan,
        )

    def build_route_report(
        self,
        bundle: NormalizedInputBundle,
        readiness_decision: ReadinessDecision,
        route_name: RouteName,
        validation_report: ValidationReport,
        execution_summary: ExecutionSummary | dict[str, Any] | None = None,
        refinement_summary: RefinementSummary | dict[str, Any] | None = None,
    ) -> RouteReport:
        """Build a route-specific runtime report and store it in memory metadata."""

        report = self._report_builder.build(
            bundle=bundle,
            readiness_decision=readiness_decision,
            route_name=route_name,
            validation_report=validation_report,
            execution_summary=execution_summary,
            refinement_summary=refinement_summary,
        )
        self._memory.set_metadata("route_report", report.as_dict())
        self._memory.record_trace(
            "route_report_built",
            {
                "route": route_name,
                "artifact_count": len(report.artifact_paths),
                "structured_output_count": len(report.structured_output_paths),
            },
        )
        return report

    def _merge_plan_with_suggestion(
        self,
        plan: PreparationPlan,
        suggestion: PlanSuggestionResult,
    ) -> PreparationPlan:
        tasks = [*plan.tasks, *suggestion.tasks]
        rationale = plan.rationale
        if suggestion.rationale:
            rationale = (
                f"{plan.rationale} Optional brain suggestion: {suggestion.rationale}"
            )
        return PreparationPlan(
            plan_id=plan.plan_id,
            tasks=tasks,
            rationale=rationale,
        )

    def assemble_result(
        self,
        bundle: NormalizedInputBundle | None = None,
        readiness_decision: ReadinessDecision | None = None,
        route_name: RouteName | None = None,
        validation_report: ValidationReport | None = None,
        inspection_results: list[FileInspectionResult] | None = None,
        execution_summary: ExecutionSummary | dict[str, Any] | None = None,
        refinement_summary: RefinementSummary | dict[str, Any] | None = None,
        route_report: RouteReport | dict[str, Any] | None = None,
    ) -> PreparationResult:
        """Assemble the final unified result and mark the workflow terminal."""

        bundle = bundle or self._memory.normalized_bundle
        readiness_decision = readiness_decision or self._memory.readiness_decision
        route_name = route_name or self._memory.route
        validation_report = validation_report or self._memory.validation_report
        inspection_results = inspection_results or self._memory.inspection_results
        execution_summary = execution_summary or self._memory.metadata.get("execution_summary")
        refinement_summary = refinement_summary or self._memory.metadata.get("refinement_summary")
        route_report = route_report or self._memory.metadata.get("route_report")

        if bundle is None:
            raise PreparationValidationError("a normalized bundle is required before result assembly")
        if readiness_decision is None:
            raise PreparationValidationError("a readiness decision is required before result assembly")
        if route_name is None:
            raise PreparationValidationError("a selected route is required before result assembly")
        if validation_report is None:
            raise PreparationValidationError("a validation report is required before result assembly")

        result = self._result_assembler.assemble(
            inspection_results=inspection_results,
            normalized_bundle=bundle,
            readiness_decision=readiness_decision,
            validation_report=validation_report,
            route_name=route_name,
            execution_trace=self._memory.trace,
            execution_summary=execution_summary,
            refinement_summary=refinement_summary,
            route_report=route_report,
            last_error=self._memory.last_error,
        )

        self._memory.inspection_results = list(inspection_results)
        self._memory.normalized_bundle = bundle
        self._memory.readiness_decision = readiness_decision
        self._memory.route = route_name
        self._memory.validation_report = result.validation_report

        details = {
            "route": route_name,
            "final_status": result.final_status,
            "validation_passed": result.validation_report.passed,
            "genome_output_count": len(result.genome_output.output_paths)
            if result.genome_output is not None
            else 0,
            "environment_output_count": len(result.environment_output.output_paths)
            if result.environment_output is not None
            else 0,
        }

        if result.final_status == "failed":
            if self._memory.current_state != PreparationState.FAILED:
                self._memory.mark_failed(
                    self._memory.last_error or "result assembly marked the workflow as failed"
                )
        elif self._memory.current_state in {PreparationState.ROUTED, PreparationState.VALIDATING}:
            self._memory.transition_to(
                PreparationState.COMPLETED,
                event="result_assembled",
                details=details,
            )
        elif self._memory.current_state == PreparationState.COMPLETED:
            self._memory.record_trace("result_reassembled", details)
        elif self._memory.current_state == PreparationState.FAILED:
            self._memory.record_trace("result_assembled_from_failed_state", details)
        else:
            raise PreparationValidationError(
                f"cannot assemble result from workflow state {self._memory.current_state.value}"
            )

        result.execution_trace = list(self._memory.trace)
        self._memory.set_metadata("preparation_result", result.model_dump(mode="json"))
        return result

    def execute_processing_plan(
        self,
        plan: PreparationPlan | None,
        route_name: RouteName,
    ) -> ExecutionSummary | None:
        """Execute a processing plan when the selected route requires processing."""

        if plan is None:
            self._memory.record_trace(
                "execution_skipped",
                {"route": route_name, "reason": "no preparation plan was generated"},
            )
            return None

        self._prepare_for_execution(route_name)
        if self._memory.current_state == PreparationState.ROUTED:
            self._memory.transition_to(
                PreparationState.PROCESSING,
                event="execution_started",
                details={"route": route_name, "task_count": len(plan.tasks)},
            )

        try:
            summary = self._executor.execute(plan)
        except Exception as exc:
            error = exc if isinstance(exc, ExecutionError) else ExecutionError(str(exc))
            self._memory.mark_failed(error)
            raise error from exc

        self._memory.remember_preparation_plan(summary.updated_plan)
        self._memory.set_metadata("execution_summary", summary.as_dict())
        for entry in summary.execution_trace:
            self._memory.record_trace(entry["event"], entry["details"])

        if self._memory.current_state == PreparationState.PROCESSING:
            self._memory.transition_to(
                PreparationState.VALIDATING,
                event="execution_completed",
                details={
                    "partial_success": summary.partial_success,
                    "success": summary.success,
                    "output_count": len(summary.output_paths),
                },
            )
        return summary

    def _prepare_for_bundling(
        self,
        inspection_results: list[FileInspectionResult],
    ) -> None:
        """Ensure memory contains inspection outputs before bundle building starts."""

        state = self._memory.current_state
        if state == PreparationState.INITIALIZED:
            self._memory.transition_to(
                PreparationState.INSPECTING,
                event="inspection_results_injected",
                details={"inspection_count": len(inspection_results)},
            )
            self._memory.remember_inspection_results(inspection_results)
            self._memory.transition_to(
                PreparationState.INSPECTED,
                event="inspection_injection_completed",
                details={"inspection_count": len(inspection_results)},
            )
            return

        if state == PreparationState.INSPECTING:
            self._memory.remember_inspection_results(inspection_results)
            self._memory.transition_to(
                PreparationState.INSPECTED,
                event="inspection_completed",
                details={"inspection_count": len(inspection_results)},
            )
            return

        if state in {PreparationState.INSPECTED, PreparationState.BUNDLING}:
            self._memory.remember_inspection_results(inspection_results)
            return

        if state == PreparationState.BUNDLED:
            self._memory.remember_inspection_results(inspection_results)
            return

        raise BundleBuildError(
            f"cannot build bundle from workflow state {self._memory.current_state.value}"
        )

    def _prepare_for_readiness(self, bundle: NormalizedInputBundle) -> None:
        """Ensure memory contains a bundle before readiness assessment starts."""

        state = self._memory.current_state
        file_count = self._count_bundle_files(bundle)

        if state == PreparationState.INITIALIZED:
            self._memory.transition_to(
                PreparationState.INSPECTING,
                event="bundle_injected",
                details={"file_count": file_count},
            )
            self._memory.transition_to(
                PreparationState.INSPECTED,
                event="bundle_injection_skipped_inspection",
                details={"reason": "bundle was provided directly"},
            )
            self._memory.transition_to(
                PreparationState.BUNDLING,
                event="bundle_injection_started",
                details={"file_count": file_count},
            )
            self._memory.remember_bundle(bundle)
            self._memory.transition_to(
                PreparationState.BUNDLED,
                event="bundle_injection_completed",
                details={"file_count": file_count},
            )
            return

        if state == PreparationState.INSPECTED:
            self._memory.transition_to(
                PreparationState.BUNDLING,
                event="bundle_injection_started",
                details={"file_count": file_count},
            )
            self._memory.remember_bundle(bundle)
            self._memory.transition_to(
                PreparationState.BUNDLED,
                event="bundle_injection_completed",
                details={"file_count": file_count},
            )
            return

        if state == PreparationState.BUNDLING:
            self._memory.remember_bundle(bundle)
            self._memory.transition_to(
                PreparationState.BUNDLED,
                event="bundle_build_completed",
                details={"file_count": file_count},
            )
            return

        if state in {PreparationState.BUNDLED, PreparationState.ASSESSING_READINESS}:
            self._memory.remember_bundle(bundle)
            return

        raise ReadinessAssessmentError(
            f"cannot assess readiness from workflow state {self._memory.current_state.value}"
        )

    def _count_bundle_files(self, bundle: NormalizedInputBundle) -> int:
        """Return the total number of files represented in a normalized bundle."""

        return (
            len(bundle.genotype_files)
            + len(bundle.environment_files)
            + len(bundle.metadata_files)
            + len(bundle.report_files)
            + len(bundle.unknown_files)
        )

    def _prepare_for_routing(
        self,
        bundle: NormalizedInputBundle,
        readiness_decision: ReadinessDecision,
    ) -> None:
        """Ensure memory contains readiness outputs before routing starts."""

        state = self._memory.current_state
        if state == PreparationState.INITIALIZED:
            self._prepare_for_readiness(bundle)
            self._memory.transition_to(
                PreparationState.ASSESSING_READINESS,
                event="readiness_injected_for_routing",
                details={"bundle_status": readiness_decision.bundle_status},
            )
            self._memory.remember_readiness_decision(readiness_decision)
            self._memory.transition_to(
                PreparationState.READINESS_ASSESSED,
                event="readiness_injection_completed",
                details={"bundle_status": readiness_decision.bundle_status},
            )
            return

        if state == PreparationState.BUNDLED:
            self._memory.transition_to(
                PreparationState.ASSESSING_READINESS,
                event="readiness_injected_for_routing",
                details={"bundle_status": readiness_decision.bundle_status},
            )
            self._memory.remember_bundle(bundle)
            self._memory.remember_readiness_decision(readiness_decision)
            self._memory.transition_to(
                PreparationState.READINESS_ASSESSED,
                event="readiness_injection_completed",
                details={"bundle_status": readiness_decision.bundle_status},
            )
            return

        if state == PreparationState.ASSESSING_READINESS:
            self._memory.remember_bundle(bundle)
            self._memory.remember_readiness_decision(readiness_decision)
            self._memory.transition_to(
                PreparationState.READINESS_ASSESSED,
                event="readiness_assessment_completed",
                details={"bundle_status": readiness_decision.bundle_status},
            )
            return

        if state in {PreparationState.READINESS_ASSESSED, PreparationState.ROUTING}:
            self._memory.remember_bundle(bundle)
            self._memory.remember_readiness_decision(readiness_decision)
            return

        raise RoutingError(
            f"cannot route from workflow state {self._memory.current_state.value}"
        )

    def _prepare_for_planning(
        self,
        bundle: NormalizedInputBundle,
        readiness_decision: ReadinessDecision,
        route_name: RouteName,
    ) -> None:
        """Ensure routing outputs are present before planning starts."""

        state = self._memory.current_state
        if state == PreparationState.INITIALIZED:
            self._prepare_for_routing(bundle, readiness_decision)
            self._memory.transition_to(
                PreparationState.ROUTING,
                event="route_injected_for_planning",
                details={"route": route_name},
            )
            self._memory.remember_route(route_name)
            self._memory.transition_to(
                PreparationState.ROUTED,
                event="route_injection_completed",
                details={"route": route_name},
            )
            return

        if state == PreparationState.READINESS_ASSESSED:
            self._memory.transition_to(
                PreparationState.ROUTING,
                event="route_injected_for_planning",
                details={"route": route_name},
            )
            self._memory.remember_bundle(bundle)
            self._memory.remember_readiness_decision(readiness_decision)
            self._memory.remember_route(route_name)
            self._memory.transition_to(
                PreparationState.ROUTED,
                event="route_injection_completed",
                details={"route": route_name},
            )
            return

        if state == PreparationState.ROUTING:
            self._memory.remember_bundle(bundle)
            self._memory.remember_readiness_decision(readiness_decision)
            self._memory.remember_route(route_name)
            self._memory.transition_to(
                PreparationState.ROUTED,
                event="routing_completed",
                details={"route": route_name},
            )
            return

        if state == PreparationState.ROUTED:
            self._memory.remember_bundle(bundle)
            self._memory.remember_readiness_decision(readiness_decision)
            self._memory.remember_route(route_name)
            return

        raise PlanningError(
            f"cannot build a processing plan from workflow state {self._memory.current_state.value}"
        )

    def _prepare_for_execution(self, route_name: RouteName) -> None:
        """Ensure processing-route state is present before execution starts."""

        if route_name != "processing":
            raise ExecutionError("execution is only valid for the processing route")

        state = self._memory.current_state
        if state == PreparationState.ROUTED:
            if self._memory.route not in {None, "processing"}:
                raise ExecutionError(
                    f"memory route is {self._memory.route}, which does not match processing execution"
                )
            if self._memory.route is None:
                self._memory.remember_route("processing")
            return

        if state == PreparationState.PROCESSING:
            return

        raise ExecutionError(
            f"cannot execute a processing plan from workflow state {self._memory.current_state.value}"
        )
