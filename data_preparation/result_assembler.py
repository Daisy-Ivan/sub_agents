"""Final result assembly for the data preparation sub-agent."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .schemas import (
    EnvironmentDataOutput,
    FileInspectionResult,
    GenomeDataOutput,
    NormalizedInputBundle,
    PreparationResult,
    ReadinessDecision,
    ValidationIssue,
    ValidationReport,
)
from .tools._io_helpers import normalize_name, read_rows

_ROUTE_FROM_STATUS = {
    "analysis_ready": "direct_output",
    "partially_ready": "direct_output",
    "transformable": "processing",
    "view_only": "report_only",
    "unsupported": "unsupported",
}
_GENOTYPE_HEADER_TOKENS = {
    "variant_id",
    "chromosome",
    "allele_1",
    "allele_2",
    "genotype",
}
_ENVIRONMENT_HEADER_TOKENS = {
    "date",
    "time",
    "temperature",
    "precipitation",
    "location",
    "latitude",
    "longitude",
}
_GENOTYPE_PATH_TOKENS = ("plink", "genotype", "snp", "variant")
_ENVIRONMENT_PATH_TOKENS = ("weather", "environment", "climate", "temperature", "precipitation")


class ResultAssembler:
    """Assemble a unified final result from routed workflow outputs."""

    def assemble(
        self,
        *,
        inspection_results: list[FileInspectionResult] | None = None,
        normalized_bundle: NormalizedInputBundle | None = None,
        readiness_decision: ReadinessDecision | None = None,
        validation_report: ValidationReport,
        route_name: str | None = None,
        execution_trace: list[dict[str, Any]] | None = None,
        execution_summary: Any | None = None,
        refinement_summary: Any | None = None,
        route_report: Any | None = None,
        last_error: str | None = None,
    ) -> PreparationResult:
        """Build a validated ``PreparationResult`` for any supported route."""

        normalized_readiness = self._coerce_readiness(readiness_decision)
        route = self._resolve_route_name(route_name, normalized_readiness)
        merged_validation = self._merge_validation_report(
            validation_report=ValidationReport.model_validate(validation_report),
            readiness_decision=normalized_readiness,
            execution_summary=execution_summary,
            refinement_summary=refinement_summary,
            route_report=route_report,
            last_error=last_error,
        )
        bundle = self._coerce_bundle(normalized_bundle)
        normalized_inspection_results = self._coerce_inspection_results(inspection_results)

        genome_output = self._build_genome_output(
            route_name=route,
            bundle=bundle,
            validation_report=merged_validation,
            execution_summary=execution_summary,
            refinement_summary=refinement_summary,
            route_report=route_report,
        )
        environment_output = self._build_environment_output(
            route_name=route,
            bundle=bundle,
            validation_report=merged_validation,
            execution_summary=execution_summary,
            refinement_summary=refinement_summary,
            route_report=route_report,
        )

        return PreparationResult(
            genome_output=genome_output,
            environment_output=environment_output,
            inspection_results=normalized_inspection_results,
            normalized_bundle=bundle,
            readiness_decision=normalized_readiness,
            validation_report=merged_validation,
            execution_trace=list(execution_trace or []),
            final_status=self._final_status(
                route_name=route,
                validation_report=merged_validation,
                execution_summary=execution_summary,
                last_error=last_error,
            ),
        )

    def _resolve_route_name(
        self,
        route_name: str | None,
        readiness_decision: ReadinessDecision | None,
    ) -> str:
        if route_name is not None:
            return route_name
        if readiness_decision is None:
            raise ValueError("route_name or readiness_decision is required for result assembly")
        return _ROUTE_FROM_STATUS[readiness_decision.bundle_status]

    def _coerce_bundle(
        self,
        bundle: NormalizedInputBundle | None,
    ) -> NormalizedInputBundle | None:
        if bundle is None:
            return None
        return NormalizedInputBundle.model_validate(bundle)

    def _coerce_readiness(
        self,
        readiness_decision: ReadinessDecision | None,
    ) -> ReadinessDecision | None:
        if readiness_decision is None:
            return None
        return ReadinessDecision.model_validate(readiness_decision)

    def _coerce_inspection_results(
        self,
        inspection_results: list[FileInspectionResult] | None,
    ) -> list[FileInspectionResult]:
        return [
            FileInspectionResult.model_validate(result)
            for result in (inspection_results or [])
        ]

    def _merge_validation_report(
        self,
        *,
        validation_report: ValidationReport,
        readiness_decision: ReadinessDecision | None,
        execution_summary: Any | None,
        refinement_summary: Any | None,
        route_report: Any | None,
        last_error: str | None,
    ) -> ValidationReport:
        issues = list(validation_report.issues)
        seen_messages = {issue.message.strip() for issue in issues if issue.message.strip()}

        for warning in self._collect_warning_messages(
            readiness_decision=readiness_decision,
            execution_summary=execution_summary,
            refinement_summary=refinement_summary,
            route_report=route_report,
        ):
            if warning in seen_messages:
                continue
            seen_messages.add(warning)
            issues.append(ValidationIssue(level="warning", message=warning))

        if last_error:
            normalized_error = last_error.strip()
            if normalized_error and normalized_error not in seen_messages:
                issues.append(ValidationIssue(level="error", message=normalized_error))

        if len(issues) == len(validation_report.issues):
            return validation_report
        return self._build_validation_report(issues)

    def _collect_warning_messages(
        self,
        *,
        readiness_decision: ReadinessDecision | None,
        execution_summary: Any | None,
        refinement_summary: Any | None,
        route_report: Any | None,
    ) -> list[str]:
        warnings: list[str] = []
        if readiness_decision is not None:
            warnings.extend(readiness_decision.warnings)

        for summary in (execution_summary, refinement_summary, route_report):
            warnings.extend(self._summary_warnings(summary))

        if self._summary_flag(execution_summary, "partial_success", False):
            warnings.append("processing route completed with partial success")

        return self._dedupe_strings(warnings)

    def _summary_warnings(self, summary: Any | None) -> list[str]:
        if summary is None:
            return []
        if isinstance(summary, dict):
            raw_warnings = summary.get("warnings", [])
        else:
            raw_warnings = getattr(summary, "warnings", [])
        return self._dedupe_strings([str(item) for item in raw_warnings or []])

    def _summary_paths(self, summary: Any | None) -> list[Path]:
        if summary is None:
            return []
        if isinstance(summary, dict):
            raw_paths = summary.get("output_paths", [])
        else:
            raw_paths = getattr(summary, "output_paths", [])
        return [
            raw_path if isinstance(raw_path, Path) else Path(str(raw_path))
            for raw_path in (raw_paths or [])
        ]

    def _summary_value(self, summary: Any | None, key: str) -> Any:
        if summary is None:
            return None
        if isinstance(summary, dict):
            return summary.get(key)
        return getattr(summary, key, None)

    def _summary_flag(self, summary: Any | None, key: str, default: bool) -> bool:
        value = self._summary_value(summary, key)
        return default if value is None else bool(value)

    def _build_genome_output(
        self,
        *,
        route_name: str,
        bundle: NormalizedInputBundle | None,
        validation_report: ValidationReport,
        execution_summary: Any | None,
        refinement_summary: Any | None,
        route_report: Any | None,
    ) -> GenomeDataOutput | None:
        if route_name == "direct_output" and bundle is not None:
            source_files = [item for item in bundle.genotype_files if item.usability != "unsupported"]
            if not source_files:
                return None
            return GenomeDataOutput(
                standardized_format=self._format_from_inspections(source_files),
                output_paths=[item.file_path for item in source_files],
                sample_axis_aligned=self._sample_axis_aligned(validation_report),
                variant_axis_aligned=self._variant_axis_aligned(validation_report),
                metadata=self._build_output_metadata(
                    route_name=route_name,
                    output_paths=[item.file_path for item in source_files],
                    route_report=route_report,
                ),
            )

        if route_name == "processing":
            output_paths = self._processing_output_paths(
                kind="genotype",
                execution_summary=execution_summary,
                refinement_summary=refinement_summary,
            )
            if not output_paths:
                return None
            return GenomeDataOutput(
                standardized_format=self._format_from_paths(output_paths),
                output_paths=output_paths,
                sample_axis_aligned=self._sample_axis_aligned(validation_report),
                variant_axis_aligned=self._variant_axis_aligned(validation_report),
                metadata=self._build_output_metadata(
                    route_name=route_name,
                    output_paths=output_paths,
                    route_report=route_report,
                ),
            )

        return None

    def _build_environment_output(
        self,
        *,
        route_name: str,
        bundle: NormalizedInputBundle | None,
        validation_report: ValidationReport,
        execution_summary: Any | None,
        refinement_summary: Any | None,
        route_report: Any | None,
    ) -> EnvironmentDataOutput | None:
        if route_name == "direct_output" and bundle is not None:
            source_files = [item for item in bundle.environment_files if item.usability != "unsupported"]
            if not source_files:
                return None
            return EnvironmentDataOutput(
                standardized_format=self._format_from_inspections(source_files),
                output_paths=[item.file_path for item in source_files],
                temporal_aligned=self._temporal_aligned(validation_report),
                spatial_aligned=self._spatial_aligned(validation_report),
                metadata=self._build_output_metadata(
                    route_name=route_name,
                    output_paths=[item.file_path for item in source_files],
                    route_report=route_report,
                ),
            )

        if route_name == "processing":
            output_paths = self._processing_output_paths(
                kind="environment",
                execution_summary=execution_summary,
                refinement_summary=refinement_summary,
            )
            if not output_paths:
                return None
            return EnvironmentDataOutput(
                standardized_format=self._format_from_paths(output_paths),
                output_paths=output_paths,
                temporal_aligned=self._temporal_aligned(validation_report),
                spatial_aligned=self._spatial_aligned(validation_report),
                metadata=self._build_output_metadata(
                    route_name=route_name,
                    output_paths=output_paths,
                    route_report=route_report,
                ),
            )

        return None

    def _processing_output_paths(
        self,
        *,
        kind: str,
        execution_summary: Any | None,
        refinement_summary: Any | None,
    ) -> list[Path]:
        candidate_paths = self._summary_paths(refinement_summary) or self._summary_paths(execution_summary)
        return [
            path
            for path in candidate_paths
            if self._is_structured_output(path) and self._classify_processing_path(path) == kind
        ]

    def _is_structured_output(self, path: Path) -> bool:
        return path.suffix.lower() in {".csv", ".tsv", ".vcf"}

    def _classify_processing_path(self, path: Path) -> str:
        normalized_stem = normalize_name(path.stem)
        if any(token in normalized_stem for token in _GENOTYPE_PATH_TOKENS):
            return "genotype"
        if any(token in normalized_stem for token in _ENVIRONMENT_PATH_TOKENS):
            return "environment"

        if path.suffix.lower() == ".vcf":
            return "genotype"
        if path.suffix.lower() not in {".csv", ".tsv", ".txt"} or not path.exists():
            return "other"

        try:
            header, _ = read_rows(path)
        except Exception:
            return "other"

        normalized_header = {normalize_name(column) for column in header}
        if normalized_header.intersection(_GENOTYPE_HEADER_TOKENS):
            return "genotype"
        if normalized_header.intersection(_ENVIRONMENT_HEADER_TOKENS):
            return "environment"
        return "other"

    def _format_from_inspections(self, inspections: list[FileInspectionResult]) -> str:
        formats = [result.detected_format for result in inspections if result.detected_format]
        return self._dedupe_strings(formats)[0] if len(self._dedupe_strings(formats)) == 1 else (
            "mixed" if formats else "unknown"
        )

    def _format_from_paths(self, paths: list[Path]) -> str:
        formats = self._dedupe_strings([self._format_from_path(path) for path in paths])
        if not formats:
            return "unknown"
        if len(formats) == 1:
            return formats[0]
        return "mixed"

    def _format_from_path(self, path: Path) -> str:
        suffix = path.suffix.lower().lstrip(".")
        return suffix or "unknown"

    def _build_output_metadata(
        self,
        *,
        route_name: str,
        output_paths: list[Path],
        route_report: Any | None,
    ) -> dict[str, Any]:
        metadata: dict[str, Any] = {
            "route": route_name,
            "output_count": len(output_paths),
        }
        route_summary = self._summary_value(route_report, "summary")
        if route_summary:
            metadata["route_summary"] = str(route_summary)
        route_warnings = self._summary_warnings(route_report)
        if route_warnings:
            metadata["route_warnings"] = route_warnings
        return metadata

    def _sample_axis_aligned(self, validation_report: ValidationReport) -> bool:
        return not self._has_issue_message(
            validation_report,
            ("sample identifiers do not overlap", "sample identifiers only partially overlap"),
        )

    def _variant_axis_aligned(self, validation_report: ValidationReport) -> bool:
        return not self._has_issue_message(
            validation_report,
            ("missing genotype identifiers", "vcf header is missing #chrom"),
        )

    def _temporal_aligned(self, validation_report: ValidationReport) -> bool:
        return not self._has_issue_message(validation_report, ("temporal alignment",))

    def _spatial_aligned(self, validation_report: ValidationReport) -> bool:
        return not self._has_issue_message(validation_report, ("spatial alignment",))

    def _has_issue_message(
        self,
        validation_report: ValidationReport,
        needles: tuple[str, ...],
    ) -> bool:
        messages = [
            issue.message.lower()
            for issue in validation_report.issues
            if issue.level in {"warning", "error"}
        ]
        return any(needle in message for needle in needles for message in messages)

    def _build_validation_report(self, issues: list[ValidationIssue]) -> ValidationReport:
        error_count = sum(1 for issue in issues if issue.level == "error")
        warning_count = sum(1 for issue in issues if issue.level == "warning")
        if error_count == 0 and warning_count == 0:
            summary = "Validation passed with no issues."
        elif error_count == 0:
            summary = f"Validation passed with {warning_count} warning(s)."
        else:
            summary = f"Validation failed with {error_count} error(s) and {warning_count} warning(s)."
        return ValidationReport(
            passed=error_count == 0,
            issues=issues,
            summary=summary,
        )

    def _final_status(
        self,
        *,
        route_name: str,
        validation_report: ValidationReport,
        execution_summary: Any | None,
        last_error: str | None,
    ) -> str:
        if last_error:
            return "failed"
        if route_name == "unsupported":
            return "unsupported"
        if route_name == "report_only":
            return "report_only" if validation_report.passed else "validation_failed"
        if self._summary_flag(execution_summary, "partial_success", False):
            return "partial_success"
        if validation_report.passed:
            return "success"
        return "validation_failed"

    def _dedupe_strings(self, values: list[str]) -> list[str]:
        deduped: list[str] = []
        seen: set[str] = set()
        for value in values:
            normalized = value.strip()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            deduped.append(normalized)
        return deduped
