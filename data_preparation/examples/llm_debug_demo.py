"""Debug demo for the local OpenAI-compatible model integration."""

from __future__ import annotations

from pathlib import Path
import sys
import tempfile

REPO_ROOT = Path(__file__).resolve().parents[5]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from agents.core.sub_agents.data_preparation import (
    DataPreparationConfig,
    DataPreparationSubAgent,
    PreparationRequest,
    RawInputFile,
)
from agents.core.sub_agents.data_preparation.llm_client import (
    DEFAULT_LLM_BASE_URL,
    DEFAULT_LLM_MODEL,
    LLMClient,
)

LOCAL_LLM_OPTIONS = {
    "base_url": DEFAULT_LLM_BASE_URL,
    "model": DEFAULT_LLM_MODEL,
    "timeout_seconds": 120,
}


def run_llm_smoke_test() -> None:
    """Verify the local OpenAI-compatible endpoint is reachable."""

    client = LLMClient.from_options(LOCAL_LLM_OPTIONS)
    response = client.chat(
        [
            {
                "role": "system",
                "content": "You are a helpful general-purpose agent.",
            },
            {
                "role": "user",
                "content": "给我列一个今天的工作计划，分成上午、下午、晚上。",
            },
        ]
    )

    print("llm_smoke_model:", response.model)
    print("llm_smoke_finish_reason:", response.finish_reason)
    print("llm_smoke_content:", response.content)


def run_hybrid_end_to_end_demo() -> None:
    """Run the full workflow with hybrid mode enabled."""

    config = DataPreparationConfig(
        runtime_mode="hybrid",
        llm_options=LOCAL_LLM_OPTIONS,
    )

    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        weather_file = root / "sample_weather.csv"
        weather_file.write_text(
            "date,temperature,precipitation,location\n"
            "2024-06-01,28.1,5.2,field_a\n"
            "2024-06-02,29.0,0.0,field_a\n",
            encoding="utf-8",
        )
        genotype_file = root / "sample_plink.bim"
        genotype_file.write_text(
            "1 rs1 0 12345 A G\n"
            "1 rs2 0 67890 C T\n",
            encoding="utf-8",
        )

        request = PreparationRequest(
            input_files=[
                RawInputFile(file_path=weather_file),
                RawInputFile(file_path=genotype_file),
            ],
            task_goal="Inspect raw breeding inputs and propose processing tools.",
        )

        agent = DataPreparationSubAgent(config=config)
        result = agent.run(request)
        memory = agent.get_memory_snapshot()
        route = memory.get("route")
        plan = memory.get("preparation_plan")
        brain_plan = memory.get("metadata", {}).get("brain_plan_suggestion", {})
        validation_report = memory.get("validation_report", {})
        route_report = memory.get("metadata", {}).get("route_report", {})

        print("hybrid_runtime_mode:", config.runtime_mode)
        print("hybrid_llm_base_url:", LOCAL_LLM_OPTIONS["base_url"])
        print("hybrid_llm_model:", LOCAL_LLM_OPTIONS["model"])
        print("hybrid_route:", route)
        print("hybrid_plan_task_types:", [task["task_type"] for task in plan["tasks"]] if plan else [])
        print("brain_attempted_llm:", brain_plan.get("attempted_llm"))
        print("brain_used_llm:", brain_plan.get("used_llm"))
        print("brain_fallback_reason:", brain_plan.get("fallback_reason"))
        print(
            "brain_suggested_task_types:",
            [task.get("task_type") for task in brain_plan.get("tasks", [])],
        )
        print("brain_rationale:", brain_plan.get("rationale"))
        print("hybrid_final_status:", result.final_status)
        print("hybrid_validation_summary:", validation_report.get("summary"))
        print("hybrid_route_report_title:", route_report.get("title"))
        print("hybrid_memory_state:", memory.get("current_state"))


def main() -> None:
    """Run both the connectivity check and the end-to-end hybrid check."""

    print("local_llm_options:", LOCAL_LLM_OPTIONS)
    run_llm_smoke_test()
    run_hybrid_end_to_end_demo()


if __name__ == "__main__":
    main()
