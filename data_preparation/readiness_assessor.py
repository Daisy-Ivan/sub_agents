"""Readiness assessment for normalized input bundles."""

from __future__ import annotations

from collections import Counter

from .exceptions import ReadinessAssessmentError
from .schemas import FileInspectionResult, NormalizedInputBundle, ReadinessDecision


class ReadinessAssessor:
    """Assess whether a normalized bundle is ready, partial, transformable, or unsupported."""

    def assess(self, bundle: NormalizedInputBundle) -> ReadinessDecision:
        """Assess bundle readiness from grouped inspection results."""

        try:
            normalized_bundle = NormalizedInputBundle.model_validate(bundle)
        except Exception as exc:
            raise ReadinessAssessmentError(f"invalid normalized bundle: {exc}") from exc

        files = self._flatten_bundle(normalized_bundle)
        if not files:
            return ReadinessDecision(
                bundle_status="unsupported",
                file_statuses={},
                rationale="The normalized bundle is empty, so there is nothing safe to route downstream.",
                warnings=["bundle does not contain any inspected files"],
            )

        file_statuses = {str(file.file_path): file.usability for file in files}
        usability_counts = Counter(file.usability for file in files)
        warnings = self._collect_warnings(files)

        bundle_status = self._determine_bundle_status(usability_counts)
        rationale = self._build_rationale(bundle_status=bundle_status, counts=usability_counts)

        if usability_counts["unsupported"] > 0:
            warnings.append(
                "One or more files remain unsupported and should not be treated as analysis-ready inputs."
            )
        if usability_counts["view_only"] > 0 and bundle_status in {"partially_ready", "view_only"}:
            warnings.append(
                "View-only assets are preserved for context but should not be treated as structured numeric data."
            )
        if usability_counts["transformable"] > 0:
            warnings.append(
                "At least one input still requires preparation before downstream analysis."
            )

        return ReadinessDecision(
            bundle_status=bundle_status,
            file_statuses=file_statuses,
            rationale=rationale,
            warnings=self._dedupe(warnings),
        )

    def _flatten_bundle(self, bundle: NormalizedInputBundle) -> list[FileInspectionResult]:
        return [
            *bundle.genotype_files,
            *bundle.environment_files,
            *bundle.metadata_files,
            *bundle.report_files,
            *bundle.unknown_files,
        ]

    def _determine_bundle_status(self, counts: Counter[str]) -> str:
        if counts["transformable"] > 0:
            return "transformable"
        if counts["analysis_ready"] > 0:
            if counts["view_only"] > 0 or counts["unsupported"] > 0:
                return "partially_ready"
            return "analysis_ready"
        if counts["view_only"] > 0:
            return "view_only"
        return "unsupported"

    def _build_rationale(self, *, bundle_status: str, counts: Counter[str]) -> str:
        segments = []
        for status in ("analysis_ready", "transformable", "view_only", "unsupported"):
            count = counts[status]
            if count:
                segments.append(f"{count} {status.replace('_', '-')}")
        composition = ", ".join(segments)

        if bundle_status == "analysis_ready":
            return (
                "All inspected files are already structured for downstream use; "
                f"bundle composition: {composition}."
            )
        if bundle_status == "partially_ready":
            return (
                "The bundle contains directly usable structured inputs, but some companion files are "
                f"view-only or unsupported; bundle composition: {composition}."
            )
        if bundle_status == "transformable":
            return (
                "At least one relevant input still needs preparation before safe downstream use; "
                f"bundle composition: {composition}."
            )
        if bundle_status == "view_only":
            return (
                "The bundle is dominated by report-style or visual assets that can be reviewed but not "
                f"treated as structured analysis-ready inputs; bundle composition: {composition}."
            )
        return (
            "The bundle does not contain enough supported structured inputs for downstream routing; "
            f"bundle composition: {composition}."
        )

    def _collect_warnings(self, files: list[FileInspectionResult]) -> list[str]:
        warnings: list[str] = []
        for file in files:
            warnings.extend(file.warnings)
        return warnings

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
