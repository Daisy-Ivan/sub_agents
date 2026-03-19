"""Runtime configuration for the data preparation sub-agent."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from .exceptions import DataPreparationConfigurationError

RuntimeMode = Literal["rule_only", "hybrid", "llm_enhanced"]
_RUNTIME_MODES: set[str] = {"rule_only", "hybrid", "llm_enhanced"}


@dataclass(slots=True)
class DataPreparationConfig:
    """Minimal validated runtime configuration for the sub-agent."""

    runtime_mode: RuntimeMode = "rule_only"
    allow_partial_success: bool = True
    enable_trace: bool = True
    max_preview_rows: int = 5
    max_evidence_items: int = 8
    output_dir: Path | None = None
    llm_options: dict[str, Any] = field(default_factory=dict)
    policy_overrides: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.runtime_mode not in _RUNTIME_MODES:
            allowed = ", ".join(sorted(_RUNTIME_MODES))
            raise DataPreparationConfigurationError(
                f"runtime_mode must be one of: {allowed}"
            )
        if not isinstance(self.allow_partial_success, bool):
            raise DataPreparationConfigurationError(
                "allow_partial_success must be a boolean"
            )
        if not isinstance(self.enable_trace, bool):
            raise DataPreparationConfigurationError("enable_trace must be a boolean")
        if not isinstance(self.max_preview_rows, int) or self.max_preview_rows <= 0:
            raise DataPreparationConfigurationError(
                "max_preview_rows must be a positive integer"
            )
        if not isinstance(self.max_evidence_items, int) or self.max_evidence_items <= 0:
            raise DataPreparationConfigurationError(
                "max_evidence_items must be a positive integer"
            )
        if self.output_dir is not None and not isinstance(self.output_dir, Path):
            if isinstance(self.output_dir, str) and self.output_dir.strip():
                self.output_dir = Path(self.output_dir)
            else:
                raise DataPreparationConfigurationError(
                    "output_dir must be a Path, non-empty string, or None"
                )
        if not isinstance(self.llm_options, dict):
            raise DataPreparationConfigurationError("llm_options must be a mapping")
        if not isinstance(self.policy_overrides, dict):
            raise DataPreparationConfigurationError(
                "policy_overrides must be a mapping"
            )

        self.llm_options = dict(self.llm_options)
        self.policy_overrides = dict(self.policy_overrides)

    @property
    def brain_enabled(self) -> bool:
        """Return whether the current mode is allowed to use the brain layer."""

        return self.runtime_mode != "rule_only"
