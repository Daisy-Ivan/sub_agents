"""Phase 7 tests for process-path planning."""

from __future__ import annotations

from pathlib import Path
import sys
import unittest

REPO_ROOT = Path(__file__).resolve().parents[5]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from agents.core.sub_agents.data_preparation import DataPreparationSubAgent
from agents.core.sub_agents.data_preparation.planner import RuleBasedPlanner
from agents.core.sub_agents.data_preparation.schemas import (
    FileInspectionResult,
    NormalizedInputBundle,
    ReadinessDecision,
)


class PlannerContractTests(unittest.TestCase):
    """Representative planning behavior from the test contract."""

    def test_no_plan_for_direct_output_route(self) -> None:
        planner = RuleBasedPlanner()
        bundle = NormalizedInputBundle(
            genotype_files=[self._inspection("sample_genotype.vcf", "genotype", usability="analysis_ready")],
            environment_files=[self._inspection("sample_weather.csv", "environment", usability="analysis_ready")],
        )
        decision = self._decision("analysis_ready")

        plan = planner.build_plan(bundle, decision, "direct_output")

        self.assertIsNone(plan)

    def test_non_empty_plan_for_transformable_processing_case(self) -> None:
        planner = RuleBasedPlanner()
        bundle = NormalizedInputBundle(
            genotype_files=[self._inspection("sample_plink.bim", "genotype", usability="transformable")],
            environment_files=[self._inspection("sample_weather_messy.csv", "environment", usability="transformable")],
        )
        decision = self._decision("transformable", file_statuses={
            "sample_plink.bim": "transformable",
            "sample_weather_messy.csv": "transformable",
        })

        plan = planner.build_plan(bundle, decision, "processing")

        self.assertIsNotNone(plan)
        assert plan is not None
        self.assertTrue(plan.tasks)
        self.assertIn("processing path", plan.rationale)
        self.assertTrue(all(task.status == "pending" for task in plan.tasks))
        self.assertIn("plink_conversion", [task.task_type for task in plan.tasks])
        self.assertIn("weather_table_normalization", [task.task_type for task in plan.tasks])

    def test_agent_build_processing_plan_updates_memory(self) -> None:
        agent = DataPreparationSubAgent()
        bundle = NormalizedInputBundle(
            genotype_files=[self._inspection("sample_plink.bim", "genotype", usability="transformable")],
        )
        decision = self._decision(
            "transformable",
            file_statuses={"sample_plink.bim": "transformable"},
        )

        plan = agent.build_processing_plan(bundle, decision, "processing")
        snapshot = agent.get_memory_snapshot()

        self.assertIsNotNone(plan)
        assert plan is not None
        self.assertEqual(snapshot["current_state"], "routed")
        self.assertEqual(snapshot["route"], "processing")
        self.assertEqual(snapshot["preparation_plan"]["plan_id"], plan.plan_id)
        self.assertEqual(snapshot["trace"][-1]["details"]["task_count"], len(plan.tasks))

    def _decision(
        self,
        status: str,
        *,
        file_statuses: dict[str, str] | None = None,
    ) -> ReadinessDecision:
        return ReadinessDecision(
            bundle_status=status,
            file_statuses=file_statuses or {
                "sample_genotype.vcf": "analysis_ready",
                "sample_weather.csv": "analysis_ready",
            },
            rationale=f"Bundle was classified as {status}.",
        )

    def _inspection(
        self,
        file_name: str,
        category: str,
        *,
        usability: str,
    ) -> FileInspectionResult:
        return FileInspectionResult(
            file_path=Path(file_name),
            modality="table",
            detected_category=category,
            detected_format=Path(file_name).suffix.lstrip(".") or "unknown",
            confidence=0.95,
            usability=usability,
            evidence=[f"{category} inspection evidence"],
            preview_columns=["sample_col"],
        )
