"""Phase 4 tests for normalized bundle construction."""

from __future__ import annotations

from pathlib import Path
import sys
import unittest

REPO_ROOT = Path(__file__).resolve().parents[5]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from agents.core.sub_agents.data_preparation import DataPreparationSubAgent
from agents.core.sub_agents.data_preparation.bundle_builder import BundleBuilder
from agents.core.sub_agents.data_preparation.schemas import FileInspectionResult


class BundleBuilderContractTests(unittest.TestCase):
    """Representative bundle-builder behavior from the test contract."""

    def test_builder_groups_mixed_results_by_category(self) -> None:
        builder = BundleBuilder()
        inspection_results = [
            self._inspection("sample_genotype.vcf", "genotype"),
            self._inspection("sample_weather.csv", "environment"),
            self._inspection("sample_metadata.csv", "metadata"),
            self._inspection("sample_report.pdf", "report", modality="pdf", usability="view_only"),
            self._inspection("sample_unknown.txt", "unknown", modality="text", usability="unsupported"),
        ]

        bundle = builder.build(inspection_results)

        self.assertEqual(len(bundle.genotype_files), 1)
        self.assertEqual(len(bundle.environment_files), 1)
        self.assertEqual(len(bundle.metadata_files), 1)
        self.assertEqual(len(bundle.report_files), 1)
        self.assertEqual(len(bundle.unknown_files), 1)
        self.assertEqual(bundle.report_files[0].file_path.name, "sample_report.pdf")
        self.assertEqual(bundle.unknown_files[0].file_path.name, "sample_unknown.txt")

    def test_agent_build_bundle_updates_memory_and_state(self) -> None:
        inspection_results = [
            self._inspection("sample_genotype.vcf", "genotype"),
            self._inspection("sample_weather.csv", "environment"),
            self._inspection("sample_report.pdf", "report", modality="pdf", usability="view_only"),
        ]
        agent = DataPreparationSubAgent()

        bundle = agent.build_bundle(inspection_results)
        snapshot = agent.get_memory_snapshot()

        self.assertEqual(snapshot["current_state"], "bundled")
        self.assertEqual(len(snapshot["normalized_bundle"]["genotype_files"]), 1)
        self.assertEqual(len(snapshot["normalized_bundle"]["environment_files"]), 1)
        self.assertEqual(len(snapshot["normalized_bundle"]["report_files"]), 1)
        self.assertEqual(snapshot["trace"][-1]["details"]["to"], "bundled")
        self.assertEqual(bundle.environment_files[0].file_path.name, "sample_weather.csv")

    def _inspection(
        self,
        file_name: str,
        category: str,
        *,
        modality: str = "table",
        usability: str = "analysis_ready",
    ) -> FileInspectionResult:
        detected_format = Path(file_name).suffix.lstrip(".") or "unknown"
        return FileInspectionResult(
            file_path=Path(file_name),
            modality=modality,
            detected_category=category,
            detected_format=detected_format,
            confidence=0.95,
            usability=usability,
            evidence=[f"{category} inspection evidence"],
            preview_columns=["sample_col"],
        )
