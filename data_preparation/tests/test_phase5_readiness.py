"""Phase 5 tests for readiness assessment."""

from __future__ import annotations

from pathlib import Path
import sys
import unittest

REPO_ROOT = Path(__file__).resolve().parents[5]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from agents.core.sub_agents.data_preparation import DataPreparationSubAgent
from agents.core.sub_agents.data_preparation.readiness_assessor import ReadinessAssessor
from agents.core.sub_agents.data_preparation.schemas import FileInspectionResult, NormalizedInputBundle


class ReadinessAssessmentContractTests(unittest.TestCase):
    """Representative readiness behavior from the test contract."""

    def test_analysis_ready_bundle_is_marked_analysis_ready(self) -> None:
        assessor = ReadinessAssessor()
        bundle = NormalizedInputBundle(
            genotype_files=[self._inspection("sample_genotype.vcf", "genotype", usability="analysis_ready")],
            environment_files=[self._inspection("sample_weather.csv", "environment", usability="analysis_ready")],
        )

        decision = assessor.assess(bundle)

        self.assertEqual(decision.bundle_status, "analysis_ready")
        self.assertEqual(decision.file_statuses["sample_genotype.vcf"], "analysis_ready")
        self.assertEqual(decision.file_statuses["sample_weather.csv"], "analysis_ready")

    def test_transformable_bundle_is_marked_transformable(self) -> None:
        assessor = ReadinessAssessor()
        bundle = NormalizedInputBundle(
            genotype_files=[self._inspection("sample_plink.bim", "genotype", usability="transformable")],
            environment_files=[self._inspection("sample_weather.csv", "environment", usability="analysis_ready")],
        )

        decision = assessor.assess(bundle)

        self.assertEqual(decision.bundle_status, "transformable")
        self.assertIn("preparation", decision.rationale)
        self.assertTrue(decision.warnings)

    def test_view_only_bundle_is_marked_view_only(self) -> None:
        assessor = ReadinessAssessor()
        bundle = NormalizedInputBundle(
            environment_files=[
                self._inspection(
                    "sample_weather_chart.png",
                    "environment",
                    modality="image",
                    detected_format="png",
                    usability="view_only",
                )
            ],
            report_files=[
                self._inspection(
                    "sample_report.pdf",
                    "report",
                    modality="pdf",
                    detected_format="pdf",
                    usability="view_only",
                )
            ],
        )

        decision = assessor.assess(bundle)

        self.assertEqual(decision.bundle_status, "view_only")
        self.assertEqual(decision.file_statuses["sample_report.pdf"], "view_only")

    def test_unsupported_bundle_is_marked_unsupported(self) -> None:
        assessor = ReadinessAssessor()
        bundle = NormalizedInputBundle(
            unknown_files=[
                self._inspection(
                    "sample_unknown.txt",
                    "unknown",
                    modality="text",
                    detected_format="txt",
                    usability="unsupported",
                )
            ]
        )

        decision = assessor.assess(bundle)

        self.assertEqual(decision.bundle_status, "unsupported")
        self.assertTrue(decision.warnings)

    def test_partially_ready_bundle_is_marked_partially_ready(self) -> None:
        assessor = ReadinessAssessor()
        bundle = NormalizedInputBundle(
            genotype_files=[self._inspection("sample_genotype.vcf", "genotype", usability="analysis_ready")],
            report_files=[
                self._inspection(
                    "sample_report.pdf",
                    "report",
                    modality="pdf",
                    detected_format="pdf",
                    usability="view_only",
                )
            ],
        )

        decision = assessor.assess(bundle)

        self.assertEqual(decision.bundle_status, "partially_ready")
        self.assertIn("view-only", decision.rationale)

    def test_agent_assess_readiness_updates_memory_and_state(self) -> None:
        agent = DataPreparationSubAgent()
        bundle = NormalizedInputBundle(
            genotype_files=[self._inspection("sample_genotype.vcf", "genotype", usability="analysis_ready")],
            environment_files=[self._inspection("sample_weather.csv", "environment", usability="analysis_ready")],
        )

        decision = agent.assess_readiness(bundle)
        snapshot = agent.get_memory_snapshot()

        self.assertEqual(decision.bundle_status, "analysis_ready")
        self.assertEqual(snapshot["current_state"], "readiness_assessed")
        self.assertEqual(snapshot["readiness_decision"]["bundle_status"], "analysis_ready")
        self.assertEqual(snapshot["trace"][-1]["details"]["to"], "readiness_assessed")

    def _inspection(
        self,
        file_name: str,
        category: str,
        *,
        modality: str = "table",
        detected_format: str | None = None,
        usability: str = "analysis_ready",
    ) -> FileInspectionResult:
        return FileInspectionResult(
            file_path=Path(file_name),
            modality=modality,
            detected_category=category,
            detected_format=detected_format or (Path(file_name).suffix.lstrip(".") or "unknown"),
            confidence=0.95,
            usability=usability,
            evidence=[f"{category} inspection evidence"],
            preview_columns=["sample_col"],
        )
