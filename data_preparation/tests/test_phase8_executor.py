"""Phase 8 tests for tool execution and process-path handling."""

from __future__ import annotations

from pathlib import Path
import sys
import tempfile
import unittest

REPO_ROOT = Path(__file__).resolve().parents[5]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from agents.core.sub_agents.data_preparation import DataPreparationSubAgent
from agents.core.sub_agents.data_preparation.config import DataPreparationConfig
from agents.core.sub_agents.data_preparation.executor import PlanExecutor
from agents.core.sub_agents.data_preparation.schemas import (
    FileInspectionResult,
    NormalizedInputBundle,
    PreparationPlan,
    ReadinessDecision,
    SubTask,
)


class ExecutorContractTests(unittest.TestCase):
    """Representative executor behavior from the test contract."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_processing_plan_executes_tasks_in_order(self) -> None:
        genotype_file = self._write_text(
            "sample_plink.bim",
            "1 rs1 0 12345 A G\n"
            "1 rs2 0 67890 C T\n",
        )
        weather_file = self._write_text(
            "sample_weather_messy.csv",
            "date,temp_c,rainfall_mm\n"
            "2024-06-01,28.1,5.2\n"
            "2024-06-02,27.8,0.0\n",
        )
        bundle = NormalizedInputBundle(
            genotype_files=[self._inspection(genotype_file, "genotype", usability="transformable")],
            environment_files=[self._inspection(weather_file, "environment", usability="transformable")],
        )
        decision = ReadinessDecision(
            bundle_status="transformable",
            file_statuses={
                str(genotype_file): "transformable",
                str(weather_file): "transformable",
            },
            rationale="The bundle contains transformable genotype and environment inputs.",
        )

        agent = DataPreparationSubAgent(
            config=DataPreparationConfig(output_dir=self.root / "prepared_outputs")
        )
        route = agent.route(bundle, decision)
        plan = agent.build_processing_plan(bundle, decision, route)
        summary = agent.execute_processing_plan(plan, route)

        self.assertIsNotNone(summary)
        assert summary is not None
        self.assertTrue(summary.execution_trace)
        self.assertTrue(all(task.status == "done" for task in summary.updated_plan.tasks))
        self.assertEqual(
            [entry["task_type"] for entry in summary.execution_trace if entry["event"] == "task_started"],
            [task.task_type for task in summary.updated_plan.tasks],
        )
        self.assertTrue(all(path.exists() for path in summary.output_paths))

        snapshot = agent.get_memory_snapshot()
        self.assertEqual(snapshot["current_state"], "validating")
        self.assertEqual(snapshot["preparation_plan"]["tasks"][0]["status"], "done")

    def test_partial_success_records_failed_task_without_hard_failure(self) -> None:
        genotype_file = self._write_text(
            "sample_plink.bim",
            "1 rs1 0 12345 A G\n",
        )
        output_dir = self.root / "prepared_outputs"
        executor = PlanExecutor(config=DataPreparationConfig(output_dir=output_dir))
        plan = PreparationPlan(
            plan_id="partial-plan",
            rationale="One known task and one unknown task to test partial success.",
            tasks=[
                SubTask(
                    task_id="plink-convert-1",
                    task_type="plink_conversion",
                    description="Convert PLINK component.",
                    input_refs=[str(genotype_file)],
                    tool_name="plink_conversion",
                ),
                SubTask(
                    task_id="unknown-1",
                    task_type="unknown_conversion",
                    description="Unknown task should fail gracefully.",
                    input_refs=[str(genotype_file)],
                    tool_name="unknown_conversion",
                ),
            ],
        )

        summary = executor.execute(plan)

        self.assertTrue(summary.partial_success)
        self.assertFalse(summary.success)
        self.assertEqual(summary.updated_plan.tasks[0].status, "done")
        self.assertEqual(summary.updated_plan.tasks[1].status, "failed")
        self.assertTrue(any(entry["event"] == "task_failed" for entry in summary.execution_trace))
        self.assertTrue(summary.warnings)

    def _write_text(self, relative_path: str, content: str) -> Path:
        path = self.root / relative_path
        path.write_text(content, encoding="utf-8")
        return path

    def _inspection(
        self,
        file_path: Path,
        category: str,
        *,
        usability: str,
    ) -> FileInspectionResult:
        return FileInspectionResult(
            file_path=file_path,
            modality="table",
            detected_category=category,
            detected_format=file_path.suffix.lstrip(".") or "unknown",
            confidence=0.95,
            usability=usability,
            evidence=[f"{category} inspection evidence"],
            preview_columns=["sample_col"],
        )
