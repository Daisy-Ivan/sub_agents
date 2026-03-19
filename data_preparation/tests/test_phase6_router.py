"""Phase 6 tests for explicit routing decisions."""

from __future__ import annotations

from pathlib import Path
import sys
import unittest

REPO_ROOT = Path(__file__).resolve().parents[5]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from agents.core.sub_agents.data_preparation import DataPreparationSubAgent
from agents.core.sub_agents.data_preparation.config import DataPreparationConfig
from agents.core.sub_agents.data_preparation.router import PreparationRouter
from agents.core.sub_agents.data_preparation.schemas import (
    FileInspectionResult,
    NormalizedInputBundle,
    ReadinessDecision,
)


class RouterContractTests(unittest.TestCase):
    """Representative router behavior from the test contract."""

    def test_analysis_ready_maps_to_direct_output(self) -> None:
        router = PreparationRouter()
        route = router.choose_route(
            self._bundle(),
            self._decision("analysis_ready"),
        )
        self.assertEqual(route, "direct_output")

    def test_partially_ready_defaults_to_direct_output(self) -> None:
        router = PreparationRouter()
        route = router.choose_route(
            self._bundle(),
            self._decision("partially_ready"),
        )
        self.assertEqual(route, "direct_output")

    def test_partially_ready_can_be_policy_overridden_to_processing(self) -> None:
        router = PreparationRouter(
            config=DataPreparationConfig(policy_overrides={"partially_ready_route": "processing"})
        )
        route = router.choose_route(
            self._bundle(),
            self._decision("partially_ready"),
        )
        self.assertEqual(route, "processing")

    def test_transformable_maps_to_processing(self) -> None:
        router = PreparationRouter()
        route = router.choose_route(
            self._bundle(),
            self._decision("transformable"),
        )
        self.assertEqual(route, "processing")

    def test_view_only_maps_to_report_only(self) -> None:
        router = PreparationRouter()
        route = router.choose_route(
            self._bundle(),
            self._decision("view_only"),
        )
        self.assertEqual(route, "report_only")

    def test_unsupported_maps_to_unsupported(self) -> None:
        router = PreparationRouter()
        route = router.choose_route(
            self._bundle(),
            self._decision("unsupported"),
        )
        self.assertEqual(route, "unsupported")

    def test_agent_route_updates_memory_and_state(self) -> None:
        agent = DataPreparationSubAgent()
        bundle = self._bundle()
        decision = self._decision("analysis_ready")

        route = agent.route(bundle, decision)
        snapshot = agent.get_memory_snapshot()

        self.assertEqual(route, "direct_output")
        self.assertEqual(snapshot["current_state"], "routed")
        self.assertEqual(snapshot["route"], "direct_output")
        self.assertEqual(snapshot["trace"][-1]["details"]["to"], "routed")

    def _bundle(self) -> NormalizedInputBundle:
        return NormalizedInputBundle(
            genotype_files=[self._inspection("sample_genotype.vcf", "genotype")],
            environment_files=[self._inspection("sample_weather.csv", "environment")],
        )

    def _decision(self, status: str) -> ReadinessDecision:
        return ReadinessDecision(
            bundle_status=status,
            file_statuses={
                "sample_genotype.vcf": "analysis_ready",
                "sample_weather.csv": "analysis_ready",
            },
            rationale=f"Bundle was classified as {status}.",
        )

    def _inspection(self, file_name: str, category: str) -> FileInspectionResult:
        return FileInspectionResult(
            file_path=Path(file_name),
            modality="table",
            detected_category=category,
            detected_format=Path(file_name).suffix.lstrip(".") or "unknown",
            confidence=0.95,
            usability="analysis_ready",
            evidence=[f"{category} inspection evidence"],
            preview_columns=["sample_col"],
        )
