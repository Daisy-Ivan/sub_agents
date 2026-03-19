"""Inspection coordination for raw input files."""

from __future__ import annotations

from typing import Iterable

from .capabilities.file_inspection import FileInspectionCapability
from .config import DataPreparationConfig
from .schemas import FileInspectionResult, RawInputFile


class InputInspector:
    """Coordinate file-level inspection using the rule-based capability."""

    def __init__(self, config: DataPreparationConfig | None = None) -> None:
        self.config = config or DataPreparationConfig()
        self._capability = FileInspectionCapability(config=self.config)

    def inspect(self, raw_input: RawInputFile) -> FileInspectionResult:
        """Inspect a single input file."""

        return self._capability.inspect(raw_input)

    def inspect_many(self, raw_inputs: Iterable[RawInputFile]) -> list[FileInspectionResult]:
        """Inspect a sequence of input files in order."""

        return [self.inspect(raw_input) for raw_input in raw_inputs]
