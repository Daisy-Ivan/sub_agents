"""End-to-end single-entry demo for the data preparation sub-agent."""

from __future__ import annotations

from pathlib import Path
import sys
import tempfile

REPO_ROOT = Path(__file__).resolve().parents[5]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from agents.core.sub_agents.data_preparation import (
    DataPreparationSubAgent,
    PreparationRequest,
    RawInputFile,
)


def main() -> None:
    """Run the full workflow through the public ``run()`` entry point."""

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
            task_goal="Inspect raw breeding inputs",
        )

        agent = DataPreparationSubAgent()
        preparation_result = agent.run(request)
        snapshot = agent.get_memory_snapshot()
        inspection_results = snapshot["inspection_results"]
        bundle = snapshot["normalized_bundle"]
        readiness_decision = snapshot["readiness_decision"]
        route = snapshot["route"]
        plan = snapshot["preparation_plan"]
        execution_summary = snapshot["metadata"].get("execution_summary")
        refinement_summary = snapshot["metadata"].get("refinement_summary")
        route_report = snapshot["metadata"].get("route_report")
        validation_report = snapshot["validation_report"]

        print("inspection_count:", len(inspection_results))
        for result in inspection_results:
            print(
                f"{Path(result['file_path']).name}: "
                f"modality={result['modality']}, "
                f"category={result['detected_category']}, "
                f"format={result['detected_format']}, "
                f"usability={result['usability']}, "
                f"confidence={result['confidence']}"
            )
        print(
            "bundle_counts:",
            {
                "genotype": len(bundle["genotype_files"]),
                "environment": len(bundle["environment_files"]),
                "metadata": len(bundle["metadata_files"]),
                "report": len(bundle["report_files"]),
                "unknown": len(bundle["unknown_files"]),
            },
        )
        print("bundle_status:", readiness_decision["bundle_status"])
        print("readiness_rationale:", readiness_decision["rationale"])
        print("route:", route)
        print("plan_generated:", plan is not None)
        if plan is not None:
            print("plan_task_types:", [task["task_type"] for task in plan["tasks"]])
        print("execution_summary_present:", execution_summary is not None)
        if execution_summary is not None:
            print("execution_partial_success:", execution_summary["partial_success"])
            print(
                "execution_outputs:",
                [Path(path).name for path in execution_summary["output_paths"]],
            )
        print("refinement_performed:", refinement_summary["performed"])
        print("refined_outputs:", [Path(path).name for path in refinement_summary["output_paths"]])
        print("validation_passed:", validation_report["passed"])
        print("validation_summary:", validation_report["summary"])
        print("route_report_title:", route_report["title"])
        print("route_report_summary:", route_report["summary"])
        print("route_report_artifacts:", [Path(path).name for path in route_report["artifact_paths"]])
        print("final_status:", preparation_result.final_status)
        print(
            "genome_outputs:",
            [str(path.name) for path in preparation_result.genome_output.output_paths]
            if preparation_result.genome_output is not None
            else [],
        )
        print(
            "environment_outputs:",
            [str(path.name) for path in preparation_result.environment_output.output_paths]
            if preparation_result.environment_output is not None
            else [],
        )
        print("memory_state:", agent.get_memory_snapshot()["current_state"])


if __name__ == "__main__":
    main()
