"""Typed schema contracts for the data preparation sub-agent.

The implementation prefers ``pydantic`` when it is available. The local
execution environment used for this task does not provide it, so this module
includes a small compatibility fallback that preserves the same public models
and a ``model_dump()`` API for tests and runtime snapshots.
"""

from __future__ import annotations

from dataclasses import dataclass, field as dataclass_field
from pathlib import Path
from typing import Any, Literal

from .exceptions import DataPreparationSchemaError

try:  # pragma: no cover - exercised only when pydantic is installed.
    from pydantic import BaseModel, ConfigDict, Field, field_validator

    PYDANTIC_AVAILABLE = True
except ModuleNotFoundError:  # pragma: no cover - covered by fallback tests.
    BaseModel = object  # type: ignore[assignment]
    ConfigDict = dict  # type: ignore[assignment]
    Field = None  # type: ignore[assignment]
    field_validator = None  # type: ignore[assignment]
    PYDANTIC_AVAILABLE = False


if PYDANTIC_AVAILABLE:  # pragma: no cover - local environment uses fallback.
    class SchemaModel(BaseModel):
        """Shared pydantic configuration for schema models."""

        model_config = ConfigDict(arbitrary_types_allowed=True, extra="forbid")


    class RawInputFile(SchemaModel):
        """User-provided raw input file reference."""

        file_path: Path
        file_name: str | None = None
        user_hint: str | None = None
        metadata: dict[str, Any] = Field(default_factory=dict)


    class PreparationRequest(SchemaModel):
        """Top-level request contract for the sub-agent."""

        input_files: list[RawInputFile]
        task_goal: str
        constraints: dict[str, Any] = Field(default_factory=dict)

        @field_validator("task_goal")
        @classmethod
        def _validate_task_goal(cls, value: str) -> str:
            if not value.strip():
                raise ValueError("task_goal must not be empty")
            return value


    class FileInspectionResult(SchemaModel):
        """Structured inspection result for a single input file."""

        file_path: Path
        modality: Literal["table", "text", "image", "pdf", "archive", "unknown"]
        detected_category: Literal["genotype", "environment", "metadata", "report", "unknown"]
        detected_format: str
        confidence: float = Field(ge=0.0, le=1.0)
        usability: Literal["analysis_ready", "transformable", "view_only", "unsupported"]
        evidence: list[str] = Field(default_factory=list)
        preview_columns: list[str] = Field(default_factory=list)
        warnings: list[str] = Field(default_factory=list)


    class NormalizedInputBundle(SchemaModel):
        """Normalized grouping of inspected input files."""

        genotype_files: list[FileInspectionResult] = Field(default_factory=list)
        environment_files: list[FileInspectionResult] = Field(default_factory=list)
        metadata_files: list[FileInspectionResult] = Field(default_factory=list)
        report_files: list[FileInspectionResult] = Field(default_factory=list)
        unknown_files: list[FileInspectionResult] = Field(default_factory=list)


    class ReadinessDecision(SchemaModel):
        """Bundle-level readiness assessment output."""

        bundle_status: Literal[
            "analysis_ready",
            "partially_ready",
            "transformable",
            "view_only",
            "unsupported",
        ]
        file_statuses: dict[str, str] = Field(default_factory=dict)
        rationale: str
        warnings: list[str] = Field(default_factory=list)

        @field_validator("rationale")
        @classmethod
        def _validate_rationale(cls, value: str) -> str:
            if not value.strip():
                raise ValueError("rationale must not be empty")
            return value


    class SubTask(SchemaModel):
        """A single executable task in the processing route."""

        task_id: str
        task_type: str
        description: str
        input_refs: list[str]
        tool_name: str | None = None
        status: Literal["pending", "running", "done", "failed", "skipped"] = "pending"


    class PreparationPlan(SchemaModel):
        """A process-path execution plan."""

        plan_id: str
        tasks: list[SubTask]
        rationale: str


    class ValidationIssue(SchemaModel):
        """A single validation finding."""

        level: Literal["info", "warning", "error"]
        message: str
        field: str | None = None
        suggestion: str | None = None


    class ValidationReport(SchemaModel):
        """Validation summary for a routed result."""

        passed: bool
        issues: list[ValidationIssue] = Field(default_factory=list)
        summary: str


    class GenomeDataOutput(SchemaModel):
        """Standardized genome output payload."""

        standardized_format: str
        output_paths: list[Path]
        sample_axis_aligned: bool
        variant_axis_aligned: bool
        metadata: dict[str, Any] = Field(default_factory=dict)


    class EnvironmentDataOutput(SchemaModel):
        """Standardized environment output payload."""

        standardized_format: str
        output_paths: list[Path]
        temporal_aligned: bool
        spatial_aligned: bool
        metadata: dict[str, Any] = Field(default_factory=dict)


    class PreparationResult(SchemaModel):
        """Unified final result returned by the sub-agent."""

        genome_output: GenomeDataOutput | None = None
        environment_output: EnvironmentDataOutput | None = None
        inspection_results: list[FileInspectionResult] = Field(default_factory=list)
        normalized_bundle: NormalizedInputBundle | None = None
        readiness_decision: ReadinessDecision | None = None
        validation_report: ValidationReport
        execution_trace: list[dict[str, Any]] = Field(default_factory=list)
        final_status: str

else:
    _MODALITIES = {"table", "text", "image", "pdf", "archive", "unknown"}
    _CATEGORIES = {"genotype", "environment", "metadata", "report", "unknown"}
    _FILE_USABILITIES = {"analysis_ready", "transformable", "view_only", "unsupported"}
    _BUNDLE_STATUSES = {
        "analysis_ready",
        "partially_ready",
        "transformable",
        "view_only",
        "unsupported",
    }
    _TASK_STATUSES = {"pending", "running", "done", "failed", "skipped"}
    _ISSUE_LEVELS = {"info", "warning", "error"}


    def _ensure_string(value: Any, field_name: str) -> str:
        if not isinstance(value, str):
            raise DataPreparationSchemaError(f"{field_name} must be a string")
        value = value.strip()
        if not value:
            raise DataPreparationSchemaError(f"{field_name} must not be empty")
        return value


    def _ensure_optional_string(value: Any, field_name: str) -> str | None:
        if value is None:
            return None
        return _ensure_string(value, field_name)


    def _ensure_bool(value: Any, field_name: str) -> bool:
        if not isinstance(value, bool):
            raise DataPreparationSchemaError(f"{field_name} must be a boolean")
        return value


    def _ensure_float(value: Any, field_name: str, *, minimum: float, maximum: float) -> float:
        if not isinstance(value, (int, float)):
            raise DataPreparationSchemaError(f"{field_name} must be numeric")
        float_value = float(value)
        if float_value < minimum or float_value > maximum:
            raise DataPreparationSchemaError(
                f"{field_name} must be between {minimum} and {maximum}"
            )
        return float_value


    def _ensure_mapping(value: Any, field_name: str) -> dict[str, Any]:
        if value is None:
            return {}
        if not isinstance(value, dict):
            raise DataPreparationSchemaError(f"{field_name} must be a mapping")
        return dict(value)


    def _ensure_string_mapping(value: Any, field_name: str) -> dict[str, str]:
        raw = _ensure_mapping(value, field_name)
        normalized: dict[str, str] = {}
        for key, item in raw.items():
            normalized[str(key)] = _ensure_string(item, f"{field_name}[{key!r}]")
        return normalized


    def _ensure_list(value: Any, field_name: str) -> list[Any]:
        if value is None:
            return []
        if not isinstance(value, list):
            raise DataPreparationSchemaError(f"{field_name} must be a list")
        return list(value)


    def _ensure_literal(value: Any, field_name: str, allowed: set[str]) -> str:
        normalized = _ensure_string(value, field_name)
        if normalized not in allowed:
            allowed_values = ", ".join(sorted(allowed))
            raise DataPreparationSchemaError(
                f"{field_name} must be one of: {allowed_values}"
            )
        return normalized


    def _coerce_path(value: Any, field_name: str) -> Path:
        if isinstance(value, Path):
            return value
        if isinstance(value, str) and value.strip():
            return Path(value)
        raise DataPreparationSchemaError(f"{field_name} must be a filesystem path")


    def _coerce_model(value: Any, model_cls: type["CompatModel"], field_name: str) -> "CompatModel":
        if isinstance(value, model_cls):
            return value
        if isinstance(value, dict):
            return model_cls(**value)
        raise DataPreparationSchemaError(f"{field_name} must be a {model_cls.__name__}")


    def _coerce_model_list(
        value: Any,
        model_cls: type["CompatModel"],
        field_name: str,
    ) -> list["CompatModel"]:
        return [
            _coerce_model(item, model_cls, f"{field_name}[{index}]")
            for index, item in enumerate(_ensure_list(value, field_name))
        ]


    def _coerce_string_list(value: Any, field_name: str) -> list[str]:
        return [
            _ensure_string(item, f"{field_name}[{index}]")
            for index, item in enumerate(_ensure_list(value, field_name))
        ]


    def _coerce_path_list(value: Any, field_name: str) -> list[Path]:
        return [
            _coerce_path(item, f"{field_name}[{index}]")
            for index, item in enumerate(_ensure_list(value, field_name))
        ]


    def _dump_value(value: Any, *, mode: str) -> Any:
        if isinstance(value, CompatModel):
            return value.model_dump(mode=mode)
        if isinstance(value, list):
            return [_dump_value(item, mode=mode) for item in value]
        if isinstance(value, dict):
            return {key: _dump_value(item, mode=mode) for key, item in value.items()}
        if isinstance(value, Path) and mode == "json":
            return str(value)
        return value


    class CompatModel:
        """Small fallback model API compatible with the current tests."""

        def model_dump(self, *, mode: str = "python") -> dict[str, Any]:
            data: dict[str, Any] = {}
            for field_name in self.__dataclass_fields__:  # type: ignore[attr-defined]
                data[field_name] = _dump_value(getattr(self, field_name), mode=mode)
            return data

        @classmethod
        def model_validate(cls, value: Any) -> "CompatModel":
            if isinstance(value, cls):
                return value
            if isinstance(value, dict):
                return cls(**value)
            raise DataPreparationSchemaError(f"value must be a {cls.__name__} or mapping")


    @dataclass(slots=True, kw_only=True)
    class RawInputFile(CompatModel):
        """User-provided raw input file reference."""

        file_path: Path
        file_name: str | None = None
        user_hint: str | None = None
        metadata: dict[str, Any] = dataclass_field(default_factory=dict)

        def __post_init__(self) -> None:
            self.file_path = _coerce_path(self.file_path, "file_path")
            self.file_name = _ensure_optional_string(self.file_name, "file_name")
            self.user_hint = _ensure_optional_string(self.user_hint, "user_hint")
            self.metadata = _ensure_mapping(self.metadata, "metadata")


    @dataclass(slots=True, kw_only=True)
    class PreparationRequest(CompatModel):
        """Top-level request contract for the sub-agent."""

        input_files: list[RawInputFile]
        task_goal: str
        constraints: dict[str, Any] = dataclass_field(default_factory=dict)

        def __post_init__(self) -> None:
            self.input_files = _coerce_model_list(
                self.input_files,
                RawInputFile,
                "input_files",
            )
            self.task_goal = _ensure_string(self.task_goal, "task_goal")
            self.constraints = _ensure_mapping(self.constraints, "constraints")


    @dataclass(slots=True, kw_only=True)
    class FileInspectionResult(CompatModel):
        """Structured inspection result for a single input file."""

        file_path: Path
        modality: Literal["table", "text", "image", "pdf", "archive", "unknown"]
        detected_category: Literal["genotype", "environment", "metadata", "report", "unknown"]
        detected_format: str
        confidence: float
        usability: Literal["analysis_ready", "transformable", "view_only", "unsupported"]
        evidence: list[str] = dataclass_field(default_factory=list)
        preview_columns: list[str] = dataclass_field(default_factory=list)
        warnings: list[str] = dataclass_field(default_factory=list)

        def __post_init__(self) -> None:
            self.file_path = _coerce_path(self.file_path, "file_path")
            self.modality = _ensure_literal(self.modality, "modality", _MODALITIES)
            self.detected_category = _ensure_literal(
                self.detected_category,
                "detected_category",
                _CATEGORIES,
            )
            self.detected_format = _ensure_string(self.detected_format, "detected_format")
            self.confidence = _ensure_float(
                self.confidence,
                "confidence",
                minimum=0.0,
                maximum=1.0,
            )
            self.usability = _ensure_literal(self.usability, "usability", _FILE_USABILITIES)
            self.evidence = _coerce_string_list(self.evidence, "evidence")
            self.preview_columns = _coerce_string_list(self.preview_columns, "preview_columns")
            self.warnings = _coerce_string_list(self.warnings, "warnings")


    @dataclass(slots=True, kw_only=True)
    class NormalizedInputBundle(CompatModel):
        """Normalized grouping of inspected input files."""

        genotype_files: list[FileInspectionResult] = dataclass_field(default_factory=list)
        environment_files: list[FileInspectionResult] = dataclass_field(default_factory=list)
        metadata_files: list[FileInspectionResult] = dataclass_field(default_factory=list)
        report_files: list[FileInspectionResult] = dataclass_field(default_factory=list)
        unknown_files: list[FileInspectionResult] = dataclass_field(default_factory=list)

        def __post_init__(self) -> None:
            self.genotype_files = _coerce_model_list(
                self.genotype_files,
                FileInspectionResult,
                "genotype_files",
            )
            self.environment_files = _coerce_model_list(
                self.environment_files,
                FileInspectionResult,
                "environment_files",
            )
            self.metadata_files = _coerce_model_list(
                self.metadata_files,
                FileInspectionResult,
                "metadata_files",
            )
            self.report_files = _coerce_model_list(
                self.report_files,
                FileInspectionResult,
                "report_files",
            )
            self.unknown_files = _coerce_model_list(
                self.unknown_files,
                FileInspectionResult,
                "unknown_files",
            )


    @dataclass(slots=True, kw_only=True)
    class ReadinessDecision(CompatModel):
        """Bundle-level readiness assessment output."""

        bundle_status: Literal[
            "analysis_ready",
            "partially_ready",
            "transformable",
            "view_only",
            "unsupported",
        ]
        file_statuses: dict[str, str] = dataclass_field(default_factory=dict)
        rationale: str = ""
        warnings: list[str] = dataclass_field(default_factory=list)

        def __post_init__(self) -> None:
            self.bundle_status = _ensure_literal(
                self.bundle_status,
                "bundle_status",
                _BUNDLE_STATUSES,
            )
            self.file_statuses = _ensure_string_mapping(self.file_statuses, "file_statuses")
            self.rationale = _ensure_string(self.rationale, "rationale")
            self.warnings = _coerce_string_list(self.warnings, "warnings")


    @dataclass(slots=True, kw_only=True)
    class SubTask(CompatModel):
        """A single executable task in the processing route."""

        task_id: str
        task_type: str
        description: str
        input_refs: list[str]
        tool_name: str | None = None
        status: Literal["pending", "running", "done", "failed", "skipped"] = "pending"

        def __post_init__(self) -> None:
            self.task_id = _ensure_string(self.task_id, "task_id")
            self.task_type = _ensure_string(self.task_type, "task_type")
            self.description = _ensure_string(self.description, "description")
            self.input_refs = _coerce_string_list(self.input_refs, "input_refs")
            self.tool_name = _ensure_optional_string(self.tool_name, "tool_name")
            self.status = _ensure_literal(self.status, "status", _TASK_STATUSES)


    @dataclass(slots=True, kw_only=True)
    class PreparationPlan(CompatModel):
        """A process-path execution plan."""

        plan_id: str
        tasks: list[SubTask]
        rationale: str

        def __post_init__(self) -> None:
            self.plan_id = _ensure_string(self.plan_id, "plan_id")
            self.tasks = _coerce_model_list(self.tasks, SubTask, "tasks")
            self.rationale = _ensure_string(self.rationale, "rationale")


    @dataclass(slots=True, kw_only=True)
    class ValidationIssue(CompatModel):
        """A single validation finding."""

        level: Literal["info", "warning", "error"]
        message: str
        field: str | None = None
        suggestion: str | None = None

        def __post_init__(self) -> None:
            self.level = _ensure_literal(self.level, "level", _ISSUE_LEVELS)
            self.message = _ensure_string(self.message, "message")
            self.field = _ensure_optional_string(self.field, "field")
            self.suggestion = _ensure_optional_string(self.suggestion, "suggestion")


    @dataclass(slots=True, kw_only=True)
    class ValidationReport(CompatModel):
        """Validation summary for a routed result."""

        passed: bool
        issues: list[ValidationIssue] = dataclass_field(default_factory=list)
        summary: str = ""

        def __post_init__(self) -> None:
            self.passed = _ensure_bool(self.passed, "passed")
            self.issues = _coerce_model_list(self.issues, ValidationIssue, "issues")
            self.summary = _ensure_string(self.summary, "summary")


    @dataclass(slots=True, kw_only=True)
    class GenomeDataOutput(CompatModel):
        """Standardized genome output payload."""

        standardized_format: str
        output_paths: list[Path]
        sample_axis_aligned: bool
        variant_axis_aligned: bool
        metadata: dict[str, Any] = dataclass_field(default_factory=dict)

        def __post_init__(self) -> None:
            self.standardized_format = _ensure_string(
                self.standardized_format,
                "standardized_format",
            )
            self.output_paths = _coerce_path_list(self.output_paths, "output_paths")
            self.sample_axis_aligned = _ensure_bool(
                self.sample_axis_aligned,
                "sample_axis_aligned",
            )
            self.variant_axis_aligned = _ensure_bool(
                self.variant_axis_aligned,
                "variant_axis_aligned",
            )
            self.metadata = _ensure_mapping(self.metadata, "metadata")


    @dataclass(slots=True, kw_only=True)
    class EnvironmentDataOutput(CompatModel):
        """Standardized environment output payload."""

        standardized_format: str
        output_paths: list[Path]
        temporal_aligned: bool
        spatial_aligned: bool
        metadata: dict[str, Any] = dataclass_field(default_factory=dict)

        def __post_init__(self) -> None:
            self.standardized_format = _ensure_string(
                self.standardized_format,
                "standardized_format",
            )
            self.output_paths = _coerce_path_list(self.output_paths, "output_paths")
            self.temporal_aligned = _ensure_bool(self.temporal_aligned, "temporal_aligned")
            self.spatial_aligned = _ensure_bool(self.spatial_aligned, "spatial_aligned")
            self.metadata = _ensure_mapping(self.metadata, "metadata")


    @dataclass(slots=True, kw_only=True)
    class PreparationResult(CompatModel):
        """Unified final result returned by the sub-agent."""

        validation_report: ValidationReport
        final_status: str
        genome_output: GenomeDataOutput | None = None
        environment_output: EnvironmentDataOutput | None = None
        inspection_results: list[FileInspectionResult] = dataclass_field(default_factory=list)
        normalized_bundle: NormalizedInputBundle | None = None
        readiness_decision: ReadinessDecision | None = None
        execution_trace: list[dict[str, Any]] = dataclass_field(default_factory=list)

        def __post_init__(self) -> None:
            self.validation_report = _coerce_model(
                self.validation_report,
                ValidationReport,
                "validation_report",
            )
            self.final_status = _ensure_string(self.final_status, "final_status")
            if self.genome_output is not None:
                self.genome_output = _coerce_model(
                    self.genome_output,
                    GenomeDataOutput,
                    "genome_output",
                )
            if self.environment_output is not None:
                self.environment_output = _coerce_model(
                    self.environment_output,
                    EnvironmentDataOutput,
                    "environment_output",
                )
            self.inspection_results = _coerce_model_list(
                self.inspection_results,
                FileInspectionResult,
                "inspection_results",
            )
            if self.normalized_bundle is not None:
                self.normalized_bundle = _coerce_model(
                    self.normalized_bundle,
                    NormalizedInputBundle,
                    "normalized_bundle",
                )
            if self.readiness_decision is not None:
                self.readiness_decision = _coerce_model(
                    self.readiness_decision,
                    ReadinessDecision,
                    "readiness_decision",
                )
            self.execution_trace = _ensure_list(self.execution_trace, "execution_trace")
            for index, entry in enumerate(self.execution_trace):
                if not isinstance(entry, dict):
                    raise DataPreparationSchemaError(
                        f"execution_trace[{index}] must be a mapping"
                    )
                self.execution_trace[index] = dict(entry)


__all__ = [
    "EnvironmentDataOutput",
    "FileInspectionResult",
    "GenomeDataOutput",
    "NormalizedInputBundle",
    "PYDANTIC_AVAILABLE",
    "PreparationPlan",
    "PreparationRequest",
    "PreparationResult",
    "RawInputFile",
    "ReadinessDecision",
    "SubTask",
    "ValidationIssue",
    "ValidationReport",
]
