"""Route-specific reporting for runtime preparation results."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..schemas import NormalizedInputBundle, ReadinessDecision, ValidationReport


@dataclass(slots=True)
class RouteReport:
    """Route-specific summary of produced artifacts and validation state."""

    route: str
    title: str
    summary: str
    warnings: list[str] = field(default_factory=list)
    artifact_paths: list[Path] = field(default_factory=list)
    structured_output_paths: list[Path] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable route summary."""

        return {
            "route": self.route,
            "title": self.title,
            "summary": self.summary,
            "warnings": list(self.warnings),
            "artifact_paths": [str(path) for path in self.artifact_paths],
            "structured_output_paths": [str(path) for path in self.structured_output_paths],
            "metadata": dict(self.metadata),
        }


class ReportBuilderCapability:
    """Build route-specific summaries without assembling the final result object."""

    def build(
        self,
        *,
        bundle: NormalizedInputBundle,
        readiness_decision: ReadinessDecision,
        route_name: str,
        validation_report: ValidationReport,
        execution_summary: Any | None = None,
        refinement_summary: Any | None = None,
    ) -> RouteReport:
        """Construct a route-oriented summary of artifacts and warnings."""

        if route_name == "direct_output":
            structured_output_paths = self._bundle_structured_paths(bundle)
            artifact_paths = structured_output_paths + self._bundle_report_paths(bundle)
            summary = (
                f"Direct output route preserved {len(structured_output_paths)} structured artifact(s) "
                f"without heavy processing. {validation_report.summary}"
            )
            title = "Direct Output Summary"
        elif route_name == "processing":
            artifact_paths = self._summary_paths(refinement_summary) or self._summary_paths(execution_summary)
            structured_output_paths = [path for path in artifact_paths if path.suffix.lower() == ".csv"]
            summary = (
                f"Processing route produced {len(artifact_paths)} artifact(s), including "
                f"{len(structured_output_paths)} structured output(s). {validation_report.summary}"
            )
            title = "Processing Route Summary"
        elif route_name == "report_only":
            artifact_paths = self._bundle_report_paths(bundle)
            structured_output_paths = []
            summary = (
                f"Report-only route preserved {len(artifact_paths)} view-only artifact(s) and did not "
                f"fabricate structured numerical outputs. {validation_report.summary}"
            )
            title = "Report-Only Summary"
        else:
            artifact_paths = self._bundle_unknown_paths(bundle)
            structured_output_paths = []
            summary = (
                f"Unsupported route kept {len(artifact_paths)} unresolved artifact(s) with warnings "
                f"for downstream handling. {validation_report.summary}"
            )
            title = "Unsupported Route Summary"

        warnings = self._collect_warnings(
            readiness_decision=readiness_decision,
            validation_report=validation_report,
            execution_summary=execution_summary,
            refinement_summary=refinement_summary,
        )

        return RouteReport(
            route=route_name,
            title=title,
            summary=summary,
            warnings=warnings,
            artifact_paths=artifact_paths,
            structured_output_paths=structured_output_paths,
            metadata={
                "bundle_status": readiness_decision.bundle_status,
                "artifact_count": len(artifact_paths),
                "structured_output_count": len(structured_output_paths),
                "validation_passed": validation_report.passed,
            },
        )

    def _summary_paths(self, summary: Any | None) -> list[Path]:
        if summary is None:
            return []
        output_paths = getattr(summary, "output_paths", None)
        if output_paths is None and isinstance(summary, dict):
            output_paths = summary.get("output_paths", [])
        return [
            raw_path if isinstance(raw_path, Path) else Path(str(raw_path))
            for raw_path in (output_paths or [])
        ]

    def _bundle_structured_paths(self, bundle: NormalizedInputBundle) -> list[Path]:
        return [
            result.file_path
            for result in (
                bundle.genotype_files + bundle.environment_files + bundle.metadata_files
            )
            if result.usability != "unsupported"
        ]

    def _bundle_report_paths(self, bundle: NormalizedInputBundle) -> list[Path]:
        return [result.file_path for result in bundle.report_files]

    def _bundle_unknown_paths(self, bundle: NormalizedInputBundle) -> list[Path]:
        return [result.file_path for result in bundle.unknown_files]

    def _collect_warnings(
        self,
        *,
        readiness_decision: ReadinessDecision,
        validation_report: ValidationReport,
        execution_summary: Any | None,
        refinement_summary: Any | None,
    ) -> list[str]:
        warnings: list[str] = list(readiness_decision.warnings)

        for summary in (execution_summary, refinement_summary):
            if summary is None:
                continue
            summary_warnings = getattr(summary, "warnings", None)
            if summary_warnings is None and isinstance(summary, dict):
                summary_warnings = summary.get("warnings", [])
            warnings.extend(summary_warnings or [])

        warnings.extend(
            issue.message
            for issue in validation_report.issues
            if issue.level in {"warning", "error"}
        )
        return self._dedupe(warnings)

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
