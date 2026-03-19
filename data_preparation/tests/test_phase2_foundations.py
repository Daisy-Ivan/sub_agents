"""Phase 2 contract tests for schemas, config, state, and memory."""

from __future__ import annotations

from pathlib import Path
import sys
import unittest

REPO_ROOT = Path(__file__).resolve().parents[5]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from agents.core.sub_agents.data_preparation.config import DataPreparationConfig
from agents.core.sub_agents.data_preparation.exceptions import (
    DataPreparationConfigurationError,
    DataPreparationStateError,
)
from agents.core.sub_agents.data_preparation.memory import PreparationMemory
from agents.core.sub_agents.data_preparation.schemas import (
    FileInspectionResult,
    NormalizedInputBundle,
    PreparationRequest,
    PreparationResult,
    RawInputFile,
    ReadinessDecision,
    ValidationReport,
)
from agents.core.sub_agents.data_preparation.state import PreparationState


class SchemaContractTests(unittest.TestCase):
    """Minimum foundational schema checks from the test contract."""

    def test_valid_preparation_request_can_be_created(self) -> None:
        request = PreparationRequest(
            input_files=[RawInputFile(file_path=Path("sample_weather.csv"))],
            task_goal="Prepare genotype and weather inputs for analysis",
        )

        self.assertEqual(len(request.input_files), 1)
        self.assertEqual(request.input_files[0].file_path, Path("sample_weather.csv"))
        self.assertEqual(request.task_goal, "Prepare genotype and weather inputs for analysis")

    def test_invalid_preparation_request_is_rejected(self) -> None:
        with self.assertRaises(Exception):
            PreparationRequest(input_files="not-a-list", task_goal=123)

    def test_core_phase2_models_can_be_created(self) -> None:
        inspection = FileInspectionResult(
            file_path=Path("sample_genotype.vcf"),
            modality="table",
            detected_category="genotype",
            detected_format="vcf",
            confidence=0.95,
            usability="analysis_ready",
            evidence=["vcf header detected"],
        )
        bundle = NormalizedInputBundle(genotype_files=[inspection])
        readiness = ReadinessDecision(
            bundle_status="analysis_ready",
            file_statuses={"sample_genotype.vcf": "analysis_ready"},
            rationale="The genotype file is already structured for downstream use.",
        )
        validation = ValidationReport(
            passed=True,
            summary="Validation passed with no blocking issues.",
        )
        result = PreparationResult(
            inspection_results=[inspection],
            normalized_bundle=bundle,
            readiness_decision=readiness,
            validation_report=validation,
            final_status="ready",
        )

        self.assertEqual(bundle.genotype_files[0].detected_format, "vcf")
        self.assertEqual(readiness.bundle_status, "analysis_ready")
        self.assertTrue(result.validation_report.passed)


class ConfigAndMemoryTests(unittest.TestCase):
    """Phase 2 tests for config validation and working memory behavior."""

    def test_config_validates_runtime_mode(self) -> None:
        config = DataPreparationConfig(runtime_mode="rule_only")
        self.assertFalse(config.brain_enabled)

        with self.assertRaises(DataPreparationConfigurationError):
            DataPreparationConfig(runtime_mode="invalid-mode")  # type: ignore[arg-type]

    def test_memory_tracks_state_and_trace(self) -> None:
        request = PreparationRequest(
            input_files=[RawInputFile(file_path="sample_weather.csv")],
            task_goal="Prepare inputs",
        )
        inspection = FileInspectionResult(
            file_path="sample_weather.csv",
            modality="table",
            detected_category="environment",
            detected_format="csv",
            confidence=0.9,
            usability="transformable",
            evidence=["csv-like header detected"],
        )

        memory = PreparationMemory()
        memory.remember_request(request)
        memory.transition_to(PreparationState.INSPECTING)
        memory.transition_to(PreparationState.INSPECTED)
        memory.remember_inspection_results([inspection])

        snapshot = memory.as_dict()
        self.assertEqual(snapshot["current_state"], "inspected")
        self.assertEqual(snapshot["request"]["task_goal"], "Prepare inputs")
        self.assertEqual(len(snapshot["trace"]), 4)
        self.assertEqual(snapshot["inspection_results"][0]["detected_category"], "environment")

    def test_memory_rejects_invalid_state_transition(self) -> None:
        memory = PreparationMemory()
        with self.assertRaises(DataPreparationStateError):
            memory.transition_to(PreparationState.BUNDLED)
