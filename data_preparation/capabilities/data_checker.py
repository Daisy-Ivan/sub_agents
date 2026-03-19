"""Validation layer for routed preparation outputs."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from ..exceptions import PreparationValidationError
from ..schemas import (
    FileInspectionResult,
    NormalizedInputBundle,
    ReadinessDecision,
    ValidationIssue,
    ValidationReport,
)
from ..tools._io_helpers import normalize_name, read_rows


@dataclass(slots=True)
class _TableSnapshot:
    path: Path
    kind: str
    header: list[str]
    rows: list[list[str]]
    sample_ids: set[str]


class DataCheckerCapability:
    """Validate route outputs with deterministic structural checks."""

    def validate(
        self,
        *,
        bundle: NormalizedInputBundle,
        readiness_decision: ReadinessDecision,
        route_name: str,
        execution_summary: Any | None = None,
        refinement_summary: Any | None = None,
    ) -> ValidationReport:
        """Validate routed artifacts and return a structured report."""

        try:
            if route_name == "report_only":
                return self._validate_report_only(
                    bundle=bundle,
                    readiness_decision=readiness_decision,
                    execution_summary=execution_summary,
                    refinement_summary=refinement_summary,
                )
            if route_name == "unsupported":
                return self._validate_unsupported(bundle=bundle, readiness_decision=readiness_decision)

            candidate_paths = self._candidate_paths(
                bundle=bundle,
                route_name=route_name,
                execution_summary=execution_summary,
                refinement_summary=refinement_summary,
            )

            issues: list[ValidationIssue] = []
            table_snapshots: list[_TableSnapshot] = []

            if not candidate_paths:
                issues.append(
                    ValidationIssue(
                        level="error",
                        message="no candidate artifacts were available for validation",
                        suggestion="ensure the route produced at least one output artifact",
                    )
                )
                return self._build_report(issues)

            for path in candidate_paths:
                if not path.exists():
                    issues.append(
                        ValidationIssue(
                            level="error",
                            message=f"expected artifact is missing: {path.name}",
                            field=str(path),
                        )
                    )
                    continue

                if path.suffix.lower() == ".vcf":
                    self._validate_vcf(path, issues, table_snapshots)
                    continue

                if path.suffix.lower() not in {".csv", ".tsv", ".txt"}:
                    continue

                try:
                    header, rows = read_rows(path)
                except Exception as exc:
                    issues.append(
                        ValidationIssue(
                            level="error",
                            message=f"could not parse structured artifact {path.name}: {exc}",
                            field=str(path),
                        )
                    )
                    continue

                snapshot = _TableSnapshot(
                    path=path,
                    kind=self._classify_table(path, header),
                    header=header,
                    rows=rows,
                    sample_ids=self._extract_sample_ids(header, rows),
                )
                table_snapshots.append(snapshot)
                self._validate_table_snapshot(snapshot, issues)

            self._check_sample_consistency(table_snapshots, issues)
            self._apply_readiness_warnings(readiness_decision, issues)
            return self._build_report(issues)
        except Exception as exc:  # pragma: no cover - defensive branch
            if isinstance(exc, PreparationValidationError):
                raise
            raise PreparationValidationError(str(exc)) from exc

    def _validate_report_only(
        self,
        *,
        bundle: NormalizedInputBundle,
        readiness_decision: ReadinessDecision,
        execution_summary: Any | None,
        refinement_summary: Any | None,
    ) -> ValidationReport:
        issues: list[ValidationIssue] = []
        structured_paths = [
            path
            for path in self._summary_paths(refinement_summary) or self._summary_paths(execution_summary)
            if path.suffix.lower() == ".csv"
        ]
        if structured_paths:
            issues.append(
                ValidationIssue(
                    level="error",
                    message="report-only route should not emit structured csv outputs",
                    suggestion="preserve view-only artifacts and summaries without fabricating tables",
                )
            )
        elif bundle.report_files:
            issues.append(
                ValidationIssue(
                    level="info",
                    message=f"preserved {len(bundle.report_files)} view-only artifact(s) without conversion",
                )
            )

        self._apply_readiness_warnings(readiness_decision, issues)
        return self._build_report(issues)

    def _validate_unsupported(
        self,
        *,
        bundle: NormalizedInputBundle,
        readiness_decision: ReadinessDecision,
    ) -> ValidationReport:
        issues = [
            ValidationIssue(
                level="error",
                message=f"unsupported route contains {len(bundle.unknown_files)} unsupported artifact(s)",
                suggestion="provide parseable genotype, environment, or metadata files",
            )
        ]
        self._apply_readiness_warnings(readiness_decision, issues)
        return self._build_report(issues)

    def _candidate_paths(
        self,
        *,
        bundle: NormalizedInputBundle,
        route_name: str,
        execution_summary: Any | None,
        refinement_summary: Any | None,
    ) -> list[Path]:
        if route_name == "processing":
            paths = self._summary_paths(refinement_summary) or self._summary_paths(execution_summary)
            return paths

        return [
            result.file_path
            for result in (
                bundle.genotype_files + bundle.environment_files + bundle.metadata_files
            )
            if result.usability != "unsupported"
        ]

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

    def _validate_vcf(
        self,
        path: Path,
        issues: list[ValidationIssue],
        table_snapshots: list[_TableSnapshot],
    ) -> None:
        raw_text = path.read_text(encoding="utf-8")
        header_line = next((line for line in raw_text.splitlines() if line.startswith("#CHROM")), "")
        if not header_line:
            issues.append(
                ValidationIssue(
                    level="error",
                    message=f"VCF header is missing #CHROM in {path.name}",
                    field=str(path),
                )
            )
            return

        columns = [normalize_name(column.lstrip("#")) for column in header_line.split("\t")]
        sample_ids = {column for column in columns[9:] if column}
        table_snapshots.append(
            _TableSnapshot(
                path=path,
                kind="genotype",
                header=columns,
                rows=[],
                sample_ids=sample_ids,
            )
        )

    def _validate_table_snapshot(
        self,
        snapshot: _TableSnapshot,
        issues: list[ValidationIssue],
    ) -> None:
        missing_value_count = self._count_missing_values(snapshot.rows)
        if missing_value_count:
            issues.append(
                ValidationIssue(
                    level="warning",
                    message=f"{snapshot.path.name} contains {missing_value_count} blank value(s)",
                    field=str(snapshot.path),
                )
            )

        if snapshot.kind == "genotype":
            required = {"variant_id", "chromosome"}
            if not required.intersection(snapshot.header):
                issues.append(
                    ValidationIssue(
                        level="error",
                        message=f"{snapshot.path.name} is missing genotype identifiers",
                        suggestion="include columns such as variant_id or chromosome",
                    )
                )

        if snapshot.kind == "environment":
            key_fields = {"date", "sample_id", "location", "latitude", "longitude"}
            if not key_fields.intersection(snapshot.header):
                issues.append(
                    ValidationIssue(
                        level="error",
                        message=f"{snapshot.path.name} is missing environment key fields",
                        suggestion="include date, sample_id, location, or coordinates",
                    )
                )
            if not self._has_temporal_alignment(snapshot.header, snapshot.rows):
                issues.append(
                    ValidationIssue(
                        level="warning",
                        message=f"{snapshot.path.name} has no parseable temporal alignment field",
                        suggestion="include a date or time column with parseable values",
                    )
                )
            if not self._has_spatial_alignment(snapshot.header, snapshot.rows):
                issues.append(
                    ValidationIssue(
                        level="warning",
                        message=f"{snapshot.path.name} has no spatial alignment field",
                        suggestion="include location or latitude/longitude columns",
                    )
                )

    def _classify_table(self, path: Path, header: list[str]) -> str:
        normalized_header = {normalize_name(column) for column in header}
        genotype_tokens = {"variant_id", "chromosome", "allele_1", "allele_2", "genotype"}
        environment_tokens = {
            "date",
            "time",
            "temperature",
            "precipitation",
            "location",
            "latitude",
            "longitude",
        }
        if genotype_tokens.intersection(normalized_header) or "plink" in path.stem.lower():
            return "genotype"
        if environment_tokens.intersection(normalized_header):
            return "environment"
        return "metadata"

    def _extract_sample_ids(self, header: list[str], rows: list[list[str]]) -> set[str]:
        candidate_columns = {"sample_id", "sample", "accession", "line", "genotype_id"}
        for index, column in enumerate(header):
            if normalize_name(column) in candidate_columns:
                return {row[index].strip() for row in rows if len(row) > index and row[index].strip()}
        return set()

    def _check_sample_consistency(
        self,
        snapshots: list[_TableSnapshot],
        issues: list[ValidationIssue],
    ) -> None:
        genotype_samples = set().union(*(snapshot.sample_ids for snapshot in snapshots if snapshot.kind == "genotype"))
        environment_samples = set().union(
            *(snapshot.sample_ids for snapshot in snapshots if snapshot.kind == "environment")
        )
        if not genotype_samples or not environment_samples:
            return

        overlap = genotype_samples & environment_samples
        if not overlap:
            issues.append(
                ValidationIssue(
                    level="error",
                    message="genotype and environment sample identifiers do not overlap",
                    suggestion="align sample identifiers before downstream analysis",
                )
            )
        elif overlap != genotype_samples or overlap != environment_samples:
            issues.append(
                ValidationIssue(
                    level="warning",
                    message="genotype and environment sample identifiers only partially overlap",
                    suggestion="check for dropped or renamed samples",
                )
            )

    def _has_temporal_alignment(self, header: list[str], rows: list[list[str]]) -> bool:
        indices = [
            index
            for index, column in enumerate(header)
            if any(token in normalize_name(column) for token in ("date", "time", "year", "month", "day"))
        ]
        if not indices:
            return False
        for row in rows:
            for index in indices:
                if len(row) > index and self._looks_like_datetime(row[index].strip()):
                    return True
        return False

    def _has_spatial_alignment(self, header: list[str], rows: list[list[str]]) -> bool:
        normalized_header = [normalize_name(column) for column in header]
        if "location" in normalized_header:
            index = normalized_header.index("location")
            return any(len(row) > index and row[index].strip() for row in rows)
        if "latitude" in normalized_header and "longitude" in normalized_header:
            lat_index = normalized_header.index("latitude")
            lon_index = normalized_header.index("longitude")
            return any(
                len(row) > max(lat_index, lon_index) and row[lat_index].strip() and row[lon_index].strip()
                for row in rows
            )
        return False

    def _count_missing_values(self, rows: list[list[str]]) -> int:
        return sum(1 for row in rows for value in row if not value.strip())

    def _looks_like_datetime(self, value: str) -> bool:
        if not value:
            return False
        formats = ("%Y-%m-%d", "%Y/%m/%d", "%Y-%m", "%Y/%m", "%Y%m%d", "%Y-%m-%d %H:%M:%S")
        for fmt in formats:
            try:
                datetime.strptime(value, fmt)
                return True
            except ValueError:
                continue
        return False

    def _apply_readiness_warnings(
        self,
        readiness_decision: ReadinessDecision,
        issues: list[ValidationIssue],
    ) -> None:
        for warning in readiness_decision.warnings:
            issues.append(ValidationIssue(level="warning", message=warning))

    def _build_report(self, issues: list[ValidationIssue]) -> ValidationReport:
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
