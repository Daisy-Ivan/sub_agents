"""Phase 11 contract tests for brain, llm client, and prompt loading."""

from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest

REPO_ROOT = Path(__file__).resolve().parents[5]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from agents.core.sub_agents.data_preparation.agent import DataPreparationSubAgent
from agents.core.sub_agents.data_preparation.brain import PreparationBrain
from agents.core.sub_agents.data_preparation.config import DataPreparationConfig
from agents.core.sub_agents.data_preparation.llm_client import (
    DEFAULT_LLM_BASE_URL,
    DEFAULT_LLM_MODEL,
    LLMClient,
)
from agents.core.sub_agents.data_preparation.prompts import (
    list_prompt_templates,
    render_prompt_template,
)
from agents.core.sub_agents.data_preparation.schemas import (
    FileInspectionResult,
    NormalizedInputBundle,
    PreparationPlan,
    PreparationRequest,
    RawInputFile,
    ReadinessDecision,
    SubTask,
)


class _FakeClient:
    def __init__(self, content: str | None = None, error: Exception | None = None) -> None:
        self.content = content or ""
        self.error = error
        self.calls: list[list[dict[str, str]]] = []

    def chat(self, messages: list[dict[str, str]], **_: object) -> object:
        self.calls.append(messages)
        if self.error is not None:
            raise self.error

        class _Response:
            def __init__(self, content: str) -> None:
                self.content = content

        return _Response(self.content)


class _FakeHTTPResponse:
    def __init__(self, payload: dict[str, object]) -> None:
        self._payload = payload

    def read(self) -> bytes:
        return json.dumps(self._payload).encode("utf-8")


class PromptAndClientTests(unittest.TestCase):
    def test_prompt_templates_are_listed_and_renderable(self) -> None:
        templates = list_prompt_templates()
        self.assertIn("tool_generation.md", templates)
        self.assertIn("runtime_tool_planning.md", templates)

        rendered = render_prompt_template(
            "tool_generation",
            task_type="weather_table_normalization",
            tool_name="weather_table_normalization",
            module_name="weather_normalization",
            class_name="WeatherNormalizationTool",
            goal="Normalize weather tables.",
            input_contract="CSV weather table",
            output_contract="normalized csv",
            failure_conditions="missing timestamp column",
            reference_tool="TableNormalizationTool",
        )
        self.assertIn("weather_table_normalization", rendered)
        self.assertIn("WeatherNormalizationTool", rendered)

    def test_llm_client_uses_openai_compatible_chat_completions_shape(self) -> None:
        captured: dict[str, object] = {}

        def fake_transport(http_request: object, timeout: float) -> _FakeHTTPResponse:
            request_obj = http_request
            captured["url"] = request_obj.full_url
            captured["timeout"] = timeout
            captured["payload"] = json.loads(request_obj.data.decode("utf-8"))
            return _FakeHTTPResponse(
                {
                    "model": DEFAULT_LLM_MODEL,
                    "choices": [
                        {
                            "finish_reason": "stop",
                            "message": {"role": "assistant", "content": "debug-ok"},
                        }
                    ],
                    "usage": {"prompt_tokens": 10, "completion_tokens": 2},
                }
            )

        client = LLMClient(transport=fake_transport)
        response = client.chat(
            [
                {"role": "system", "content": "You are a helpful general-purpose agent."},
                {"role": "user", "content": "给我列一个今天的工作计划。"},
            ]
        )

        self.assertEqual(captured["url"], f"{DEFAULT_LLM_BASE_URL}/chat/completions")
        self.assertEqual(captured["payload"]["model"], DEFAULT_LLM_MODEL)
        self.assertEqual(len(captured["payload"]["messages"]), 2)
        self.assertEqual(response.content, "debug-ok")


class BrainContractTests(unittest.TestCase):
    def _build_transformable_bundle(self) -> tuple[NormalizedInputBundle, ReadinessDecision]:
        genotype = FileInspectionResult(
            file_path="samples.bed",
            modality="table",
            detected_category="genotype",
            detected_format="plink_component",
            confidence=0.93,
            usability="transformable",
            evidence=["PLINK component"],
        )
        environment = FileInspectionResult(
            file_path="weather.csv",
            modality="table",
            detected_category="environment",
            detected_format="csv",
            confidence=0.91,
            usability="transformable",
            evidence=["CSV table"],
        )
        bundle = NormalizedInputBundle(
            genotype_files=[genotype],
            environment_files=[environment],
        )
        readiness = ReadinessDecision(
            bundle_status="transformable",
            file_statuses={
                "samples.bed": "transformable",
                "weather.csv": "transformable",
            },
            rationale="Both sources need transformation.",
        )
        return bundle, readiness

    def _build_rule_plan(self) -> PreparationPlan:
        return PreparationPlan(
            plan_id="rule-plan-001",
            tasks=[
                SubTask(
                    task_id="plink-conversion-1",
                    task_type="plink_conversion",
                    description="Convert PLINK inputs.",
                    input_refs=["samples.bed"],
                    tool_name="plink_conversion",
                    status="pending",
                )
            ],
            rationale="Rule-based plan.",
        )

    def test_rule_only_mode_never_calls_llm(self) -> None:
        fake_client = _FakeClient(
            content=json.dumps(
                {
                    "rationale": "unused",
                    "recommended_tasks": [],
                }
            )
        )
        brain = PreparationBrain(
            config=DataPreparationConfig(runtime_mode="rule_only"),
            client=fake_client,
        )
        bundle, readiness = self._build_transformable_bundle()

        suggestion = brain.suggest_processing_tasks(
            bundle=bundle,
            readiness_decision=readiness,
            route_name="processing",
            rule_plan=self._build_rule_plan(),
        )

        self.assertEqual(fake_client.calls, [])
        self.assertFalse(suggestion.attempted_llm)
        self.assertFalse(suggestion.used_llm)
        self.assertEqual(suggestion.tasks, [])

    def test_hybrid_mode_can_call_mocked_brain(self) -> None:
        fake_client = _FakeClient(
            content=json.dumps(
                {
                    "rationale": "Metadata normalization would help joins.",
                    "recommended_tasks": [
                        {
                            "task_type": "metadata_normalization",
                            "tool_name": "metadata_normalization",
                            "description": "Normalize metadata before merging.",
                            "input_refs": ["weather.csv"],
                        }
                    ],
                }
            )
        )
        brain = PreparationBrain(
            config=DataPreparationConfig(runtime_mode="hybrid"),
            client=fake_client,
        )
        bundle, readiness = self._build_transformable_bundle()

        suggestion = brain.suggest_processing_tasks(
            bundle=bundle,
            readiness_decision=readiness,
            route_name="processing",
            rule_plan=self._build_rule_plan(),
        )

        self.assertEqual(len(fake_client.calls), 1)
        self.assertTrue(suggestion.attempted_llm)
        self.assertTrue(suggestion.used_llm)
        self.assertEqual(len(suggestion.tasks), 1)
        self.assertEqual(suggestion.tasks[0].task_type, "metadata_normalization")
        self.assertEqual(suggestion.tasks[0].input_refs, ["weather.csv"])

    def test_llm_failure_falls_back_safely(self) -> None:
        fake_client = _FakeClient(error=RuntimeError("connection refused"))
        brain = PreparationBrain(
            config=DataPreparationConfig(runtime_mode="hybrid"),
            client=fake_client,
        )
        bundle, readiness = self._build_transformable_bundle()

        suggestion = brain.suggest_processing_tasks(
            bundle=bundle,
            readiness_decision=readiness,
            route_name="processing",
            rule_plan=self._build_rule_plan(),
        )

        self.assertEqual(len(fake_client.calls), 1)
        self.assertTrue(suggestion.attempted_llm)
        self.assertFalse(suggestion.used_llm)
        self.assertEqual(suggestion.tasks, [])
        self.assertIn("connection refused", suggestion.fallback_reason or "")

    def test_hybrid_agent_keeps_rule_plan_and_records_brain_suggestion(self) -> None:
        fake_client = _FakeClient(
            content=json.dumps(
                {
                    "rationale": "Add metadata normalization for safer downstream joins.",
                    "recommended_tasks": [
                        {
                            "task_type": "metadata_normalization",
                            "tool_name": "metadata_normalization",
                            "description": "Normalize metadata-like weather annotations.",
                            "input_refs": ["weather.csv"],
                        }
                    ],
                }
            )
        )
        config = DataPreparationConfig(runtime_mode="hybrid")
        brain = PreparationBrain(config=config, client=fake_client)
        agent = DataPreparationSubAgent(config=config, brain=brain)
        bundle, readiness = self._build_transformable_bundle()

        plan = agent.build_processing_plan(
            bundle=bundle,
            readiness_decision=readiness,
            route_name="processing",
        )

        self.assertIsNotNone(plan)
        self.assertGreaterEqual(len(plan.tasks), 2)
        self.assertEqual(plan.tasks[-1].task_type, "metadata_normalization")
        self.assertTrue(
            any(task.task_type == "plink_conversion" for task in plan.tasks),
            "rule-based tasks should still be preserved",
        )

        snapshot = agent.get_memory_snapshot()
        self.assertIn("brain_plan_suggestion", snapshot["metadata"])
        self.assertTrue(snapshot["metadata"]["brain_plan_suggestion"]["attempted_llm"])
        self.assertEqual(len(fake_client.calls), 1)

    def test_hybrid_agent_run_uses_brain_and_completes(self) -> None:
        fake_client = _FakeClient(
            content=json.dumps(
                {
                    "rationale": "Weather table normalization should be kept explicit.",
                    "recommended_tasks": [
                        {
                            "task_type": "weather_table_normalization",
                            "tool_name": "table_normalization",
                            "description": "Normalize the weather table before validation.",
                            "input_refs": ["weather_messy.csv"],
                        }
                    ],
                }
            )
        )
        config = DataPreparationConfig(runtime_mode="hybrid")
        brain = PreparationBrain(config=config, client=fake_client)

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            genotype_path = root / "sample_plink.bim"
            weather_path = root / "weather_messy.csv"
            genotype_path.write_text(
                "1 rs1 0 12345 A G\n"
                "1 rs2 0 67890 C T\n",
                encoding="utf-8",
            )
            weather_path.write_text(
                "date,temp_c,site\n"
                "2024-06-01,28.1,field_a\n"
                "2024-06-02,29.0,field_a\n",
                encoding="utf-8",
            )
            request = PreparationRequest(
                input_files=[
                    RawInputFile(file_path=genotype_path),
                    RawInputFile(file_path=weather_path),
                ],
                task_goal="Normalize transformable genotype and weather inputs.",
            )

            agent = DataPreparationSubAgent(config=config, brain=brain)
            result = agent.run(request)

        snapshot = agent.get_memory_snapshot()
        brain_plan = snapshot["metadata"]["brain_plan_suggestion"]
        self.assertEqual(snapshot["current_state"], "completed")
        self.assertEqual(snapshot["route"], "processing")
        self.assertTrue(brain_plan["attempted_llm"])
        self.assertTrue(brain_plan["used_llm"])
        self.assertGreaterEqual(len(snapshot["preparation_plan"]["tasks"]), 2)
        self.assertIn(result.final_status, {"success", "partial_success", "validation_failed"})
        self.assertEqual(len(fake_client.calls), 1)
