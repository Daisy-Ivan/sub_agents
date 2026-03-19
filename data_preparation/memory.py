"""Working memory and trace helpers for the data preparation sub-agent."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .exceptions import DataPreparationStateError
from .schemas import (
    FileInspectionResult,
    NormalizedInputBundle,
    PreparationPlan,
    PreparationRequest,
    ReadinessDecision,
    ValidationReport,
)
from .state import PreparationState, is_valid_transition


def _serialize_value(value: Any) -> Any:
    """Convert nested runtime values into snapshot-safe structures."""

    if isinstance(value, Path):
        return str(value)
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, list):
        return [_serialize_value(item) for item in value]
    if isinstance(value, dict):
        return {key: _serialize_value(item) for key, item in value.items()}
    return value


@dataclass(slots=True)
class PreparationMemory:
    """Mutable runtime memory for the gated workflow."""

    current_state: PreparationState = PreparationState.INITIALIZED
    request: PreparationRequest | None = None
    inspection_results: list[FileInspectionResult] = field(default_factory=list)
    normalized_bundle: NormalizedInputBundle | None = None
    readiness_decision: ReadinessDecision | None = None
    route: str | None = None
    preparation_plan: PreparationPlan | None = None
    validation_report: ValidationReport | None = None
    trace: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    last_error: str | None = None

    def transition_to(
        self,
        new_state: PreparationState,
        *,
        event: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Move the workflow to the next valid state and record the transition."""

        if not is_valid_transition(self.current_state, new_state):
            raise DataPreparationStateError(
                f"invalid transition: {self.current_state.value} -> {new_state.value}"
            )

        previous_state = self.current_state
        self.current_state = new_state
        self.record_trace(
            event or "state_transition",
            details={
                "from": previous_state.value,
                "to": new_state.value,
                **(details or {}),
            },
        )

    def remember_request(self, request: PreparationRequest) -> None:
        """Store the active request in memory."""

        self.request = request
        self.record_trace("request_stored", {"input_count": len(request.input_files)})

    def remember_inspection_results(
        self,
        inspection_results: list[FileInspectionResult],
    ) -> None:
        """Store inspection outputs for later phases."""

        self.inspection_results = list(inspection_results)
        self.record_trace(
            "inspection_results_stored",
            {"count": len(self.inspection_results)},
        )

    def remember_bundle(self, bundle: NormalizedInputBundle) -> None:
        """Store the normalized bundle."""

        self.normalized_bundle = bundle
        self.record_trace("bundle_stored")

    def remember_readiness_decision(self, decision: ReadinessDecision) -> None:
        """Store readiness assessment output."""

        self.readiness_decision = decision
        self.record_trace("readiness_stored", {"bundle_status": decision.bundle_status})

    def remember_route(self, route: str) -> None:
        """Store the selected route."""

        self.route = route
        self.record_trace("route_stored", {"route": route})

    def remember_preparation_plan(self, plan: PreparationPlan | None) -> None:
        """Store the latest processing plan when one is generated."""

        self.preparation_plan = plan
        self.record_trace(
            "preparation_plan_stored",
            {
                "task_count": len(plan.tasks) if plan is not None else 0,
                "plan_generated": plan is not None,
            },
        )

    def remember_validation_report(self, report: ValidationReport) -> None:
        """Store the latest validation report."""

        self.validation_report = report
        self.record_trace("validation_stored", {"passed": report.passed})

    def set_metadata(self, key: str, value: Any) -> None:
        """Persist arbitrary workflow metadata."""

        self.metadata[key] = value

    def record_trace(
        self,
        event: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Append a structured trace entry."""

        self.trace.append(
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "state": self.current_state.value,
                "event": event,
                "details": _serialize_value(details or {}),
            }
        )

    def mark_failed(self, error: Exception | str) -> None:
        """Record a terminal error for later result assembly."""

        self.last_error = str(error)
        if self.current_state is not PreparationState.FAILED:
            if is_valid_transition(self.current_state, PreparationState.FAILED):
                self.current_state = PreparationState.FAILED
            else:
                raise DataPreparationStateError(
                    f"cannot mark failure from state {self.current_state.value}"
                )
        self.record_trace("failure_recorded", {"error": self.last_error})

    def as_dict(self) -> dict[str, Any]:
        """Return a serializable memory snapshot for debugging."""

        return {
            "current_state": self.current_state.value,
            "request": _serialize_value(self.request),
            "inspection_results": _serialize_value(self.inspection_results),
            "normalized_bundle": _serialize_value(self.normalized_bundle),
            "readiness_decision": _serialize_value(self.readiness_decision),
            "route": self.route,
            "preparation_plan": _serialize_value(self.preparation_plan),
            "validation_report": _serialize_value(self.validation_report),
            "trace": _serialize_value(self.trace),
            "metadata": _serialize_value(self.metadata),
            "last_error": self.last_error,
        }
