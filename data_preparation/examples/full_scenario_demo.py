"""Comprehensive multi-scenario demo for the data preparation sub-agent."""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
import json
from pathlib import Path
import sys
import tempfile
from typing import Any, Callable

REPO_ROOT = Path(__file__).resolve().parents[5]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from agents.core.sub_agents.data_preparation import (  # noqa: E402
    DataPreparationConfig,
    DataPreparationSubAgent,
    PreparationRequest,
    RawInputFile,
)
from agents.core.sub_agents.data_preparation.llm_client import (  # noqa: E402
    DEFAULT_LLM_BASE_URL,
    DEFAULT_LLM_MODEL,
)
from agents.core.sub_agents.data_preparation.schemas import (  # noqa: E402
    PreparationPlan,
    SubTask,
)

LOCAL_LLM_OPTIONS = {
    "base_url": DEFAULT_LLM_BASE_URL,
    "model": DEFAULT_LLM_MODEL,
    "timeout_seconds": 30,
}

RequestBuilder = Callable[[Path], PreparationRequest]
PlanMutator = Callable[[PreparationPlan | None], None]


@dataclass(frozen=True)
class ScenarioSpec:
    """Declarative definition for one demo scenario."""

    name: str
    description: str
    builder: RequestBuilder
    runtime_mode: str = "rule_only"
    llm_options: dict[str, Any] | None = None
    config_overrides: dict[str, Any] = field(default_factory=dict)
    plan_mutator: PlanMutator | None = None


def _write_text(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def _write_bytes(path: Path, content: bytes) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path


def _raw_input(
    path: Path,
    *,
    user_hint: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> RawInputFile:
    return RawInputFile(
        file_path=path,
        user_hint=user_hint,
        metadata=metadata or {},
    )


def _build_analysis_ready_request(root: Path) -> PreparationRequest:
    inputs = root / "inputs"
    genotype_path = _write_text(
        inputs / "genotypes.vcf",
        "##fileformat=VCFv4.2\n"
        "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\tsample_a\n"
        "1\t12345\trs1\tA\tG\t.\tPASS\t.\tGT\t0/1\n",
    )
    environment_path = _write_text(
        inputs / "weather_ready.csv",
        "date,location,temperature,precipitation\n"
        "2024-06-01,field_a,28.1,5.2\n"
        "2024-06-02,field_a,29.0,0.0\n",
    )
    return PreparationRequest(
        input_files=[
            _raw_input(genotype_path),
            _raw_input(environment_path),
        ],
        task_goal="Validate already prepared genotype and environment inputs.",
    )


def _build_partially_ready_request(root: Path) -> PreparationRequest:
    inputs = root / "inputs"
    genotype_path = _write_text(
        inputs / "genotypes.vcf",
        "##fileformat=VCFv4.2\n"
        "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\tsample_a\n"
        "1\t100\trs_alpha\tA\tT\t.\tPASS\t.\tGT\t0/1\n",
    )
    report_path = _write_text(
        inputs / "field_report.pdf",
        "%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\n%%EOF\n",
    )
    return PreparationRequest(
        input_files=[
            _raw_input(genotype_path),
            _raw_input(report_path, user_hint="field summary report"),
        ],
        task_goal="Keep the structured genotype input and preserve the attached report.",
    )


def _build_content_based_detection_request(root: Path) -> PreparationRequest:
    inputs = root / "inputs"
    weather_path = _write_text(
        inputs / "weather_payload.dat",
        "date,location,temperature,precipitation\n"
        "2024-06-01,field_b,31.5,0.2\n"
        "2024-06-02,field_b,30.0,1.1\n",
    )
    return PreparationRequest(
        input_files=[
            _raw_input(
                weather_path,
                user_hint="weather observation table exported from a sensor platform",
            )
        ],
        task_goal="Detect a weather table from content even when the suffix is unknown.",
    )


def _build_processing_success_request(root: Path) -> PreparationRequest:
    inputs = root / "inputs"
    genotype_path = _write_text(
        inputs / "sample_plink.bim",
        "1 rs1 0 12345 A G\n"
        "1 rs2 0 67890 C T\n",
    )
    environment_path = _write_text(
        inputs / "weather_messy.csv",
        "date,temp_c,site\n"
        "2024-06-01,28.1,field_c\n"
        "2024-06-02,29.2,field_c\n",
    )
    return PreparationRequest(
        input_files=[
            _raw_input(genotype_path),
            _raw_input(environment_path),
        ],
        task_goal="Normalize a PLINK-like genotype input and a weather table with non-standard headers.",
    )


def _build_processing_validation_failure_request(root: Path) -> PreparationRequest:
    inputs = root / "inputs"
    genotype_path = _write_text(
        inputs / "sample_plink.bim",
        "1 rs10 0 12345 A G\n"
        "1 rs11 0 67890 C T\n",
    )
    environment_path = _write_text(
        inputs / "soil_measurements.csv",
        "measurement,value\n"
        "ph,6.3\n"
        "organic_matter,1.8\n",
    )
    return PreparationRequest(
        input_files=[
            _raw_input(genotype_path),
            _raw_input(environment_path, user_hint="soil table"),
        ],
        task_goal="Process transformable inputs and surface the missing temporal/spatial alignment problem.",
    )


def _build_report_only_request(root: Path) -> PreparationRequest:
    inputs = root / "inputs"
    pdf_path = _write_text(
        inputs / "weather_summary.pdf",
        "%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\n%%EOF\n",
    )
    png_path = _write_bytes(
        inputs / "weather_chart.png",
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDRdemo",
    )
    return PreparationRequest(
        input_files=[
            _raw_input(pdf_path, user_hint="weather report"),
            _raw_input(png_path, user_hint="weather chart image"),
        ],
        task_goal="Preserve view-only weather assets without pretending they are structured tables.",
    )


def _build_unsupported_request(root: Path) -> PreparationRequest:
    inputs = root / "inputs"
    binary_path = _write_bytes(
        inputs / "mystery.bin",
        b"\x00\x01\x02\x03\x04\x05",
    )
    missing_path = inputs / "missing_input.xyz"
    return PreparationRequest(
        input_files=[
            _raw_input(binary_path),
            _raw_input(missing_path, user_hint="expected genotype export"),
        ],
        task_goal="Show how unsupported and missing inputs are preserved in the unsupported path.",
    )


def _append_unknown_task(plan: PreparationPlan | None) -> None:
    if plan is None:
        return
    plan.tasks.append(
        SubTask(
            task_id="demo_unknown_conversion",
            task_type="unknown_conversion",
            description="Demonstrate partial success when one planned tool is not registered.",
            input_refs=[],
            tool_name="unknown_conversion",
        )
    )


def _remove_non_structural_report_tasks(plan: PreparationPlan | None) -> None:
    if plan is None:
        return
    plan.tasks = [
        task
        for task in plan.tasks
        if task.task_type not in {"sample_id_validation", "time_axis_check"}
    ]


def _make_processing_partial_success_plan(plan: PreparationPlan | None) -> None:
    _remove_non_structural_report_tasks(plan)
    _append_unknown_task(plan)


def get_scenario_specs(*, include_llm: bool = False) -> list[ScenarioSpec]:
    """Return the scenario catalog used by the full demo."""

    scenarios = [
        ScenarioSpec(
            name="analysis_ready_direct_output",
            description="VCF plus clean weather CSV should go straight to direct output.",
            builder=_build_analysis_ready_request,
        ),
        ScenarioSpec(
            name="partially_ready_with_report",
            description="Structured genotype data is preserved while a PDF report stays view-only.",
            builder=_build_partially_ready_request,
        ),
        ScenarioSpec(
            name="content_based_detection_unknown_suffix",
            description="A weather table with a .dat suffix is recognized from content and hint.",
            builder=_build_content_based_detection_request,
        ),
        ScenarioSpec(
            name="processing_transformable_success",
            description="A transformable PLINK-like genotype input is normalized successfully while already-ready context is preserved.",
            builder=_build_processing_success_request,
            plan_mutator=_remove_non_structural_report_tasks,
        ),
        ScenarioSpec(
            name="processing_partial_success",
            description="Processing remains partially successful when one injected demo task is unsupported.",
            builder=_build_processing_success_request,
            plan_mutator=_make_processing_partial_success_plan,
        ),
        ScenarioSpec(
            name="processing_validation_failed",
            description="Processing runs, but validation fails because the environment table lacks key alignment fields.",
            builder=_build_processing_validation_failure_request,
        ),
        ScenarioSpec(
            name="report_only_assets",
            description="PDF and PNG assets are routed to report_only without conversion.",
            builder=_build_report_only_request,
        ),
        ScenarioSpec(
            name="unsupported_missing_and_binary",
            description="A missing file and an opaque binary file demonstrate the unsupported route.",
            builder=_build_unsupported_request,
        ),
    ]
    if include_llm:
        scenarios.append(
            ScenarioSpec(
                name="hybrid_llm_planning",
                description="Optional hybrid mode that asks the local OpenAI-compatible model for planning help.",
                builder=_build_processing_success_request,
                runtime_mode="hybrid",
                llm_options=LOCAL_LLM_OPTIONS,
            )
        )
    return scenarios


def _list_names(paths: list[Path] | None) -> list[str]:
    return [path.name for path in paths or []]


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for item in items:
        if item and item not in seen:
            seen.add(item)
            ordered.append(item)
    return ordered


def _summarize_brain(snapshot: dict[str, Any]) -> dict[str, Any]:
    brain = snapshot.get("metadata", {}).get("brain_plan_suggestion", {})
    return {
        "attempted_llm": brain.get("attempted_llm"),
        "used_llm": brain.get("used_llm"),
        "fallback_reason": brain.get("fallback_reason"),
        "suggested_task_types": [
            task.get("task_type")
            for task in brain.get("tasks", [])
            if isinstance(task, dict) and task.get("task_type")
        ],
    }


def _execute_pipeline(
    agent: DataPreparationSubAgent,
    request: PreparationRequest,
    *,
    plan_mutator: PlanMutator | None = None,
) -> dict[str, Any]:
    inspection_results = agent.inspect_files(request)
    bundle = agent.build_bundle(inspection_results)
    readiness_decision = agent.assess_readiness(bundle)
    route_name = agent.route(bundle, readiness_decision)
    plan = agent.build_processing_plan(bundle, readiness_decision, route_name)
    if plan_mutator is not None:
        plan_mutator(plan)
    execution_summary = agent.execute_processing_plan(plan, route_name)
    refinement_summary = agent.refine_outputs(route_name, execution_summary)
    validation_report = agent.validate_route_outputs(
        bundle,
        readiness_decision,
        route_name,
        execution_summary,
        refinement_summary,
    )
    route_report = agent.build_route_report(
        bundle,
        readiness_decision,
        route_name,
        validation_report,
        execution_summary,
        refinement_summary,
    )
    result = agent.assemble_result(
        bundle=bundle,
        readiness_decision=readiness_decision,
        route_name=route_name,
        validation_report=validation_report,
        inspection_results=inspection_results,
        execution_summary=execution_summary,
        refinement_summary=refinement_summary,
        route_report=route_report,
    )
    return {
        "inspection_results": inspection_results,
        "bundle": bundle,
        "readiness_decision": readiness_decision,
        "route_name": route_name,
        "plan": plan,
        "execution_summary": execution_summary,
        "refinement_summary": refinement_summary,
        "validation_report": validation_report,
        "route_report": route_report,
        "result": result,
        "snapshot": agent.get_memory_snapshot(),
    }


def _summarize_successful_run(
    *,
    spec: ScenarioSpec,
    scenario_root: Path,
    request: PreparationRequest,
    pipeline: dict[str, Any],
) -> dict[str, Any]:
    inspection_results = pipeline["inspection_results"]
    bundle = pipeline["bundle"]
    readiness_decision = pipeline["readiness_decision"]
    route_name = pipeline["route_name"]
    plan = pipeline["plan"]
    execution_summary = pipeline["execution_summary"]
    refinement_summary = pipeline["refinement_summary"]
    validation_report = pipeline["validation_report"]
    route_report = pipeline["route_report"]
    result = pipeline["result"]
    snapshot = pipeline["snapshot"]

    task_statuses = []
    if execution_summary is not None:
        task_statuses = [
            {"task_type": task.task_type, "status": task.status}
            for task in execution_summary.updated_plan.tasks
        ]
    elif plan is not None:
        task_statuses = [
            {"task_type": task.task_type, "status": task.status}
            for task in plan.tasks
        ]

    warnings = _dedupe(
        [
            warning
            for result_item in inspection_results
            for warning in result_item.warnings
        ]
        + list(readiness_decision.warnings)
        + (list(execution_summary.warnings) if execution_summary is not None else [])
        + list(refinement_summary.warnings)
        + list(route_report.warnings)
    )

    return {
        "scenario": spec.name,
        "description": spec.description,
        "runtime_mode": spec.runtime_mode,
        "workspace": str(scenario_root),
        "input_files": [raw_input.file_path.name for raw_input in request.input_files],
        "inspection_results": [
            {
                "file_name": result_item.file_path.name,
                "detected_category": result_item.detected_category,
                "detected_format": result_item.detected_format,
                "usability": result_item.usability,
                "modality": result_item.modality,
                "confidence": result_item.confidence,
                "warnings": list(result_item.warnings),
            }
            for result_item in inspection_results
        ],
        "bundle_counts": {
            "genotype": len(bundle.genotype_files),
            "environment": len(bundle.environment_files),
            "metadata": len(bundle.metadata_files),
            "report": len(bundle.report_files),
            "unknown": len(bundle.unknown_files),
        },
        "bundle_status": readiness_decision.bundle_status,
        "route": route_name,
        "plan_task_types": [task.task_type for task in plan.tasks] if plan is not None else [],
        "plan_task_statuses": task_statuses,
        "execution_output_names": (
            _list_names(execution_summary.output_paths) if execution_summary is not None else []
        ),
        "execution_partial_success": (
            execution_summary.partial_success if execution_summary is not None else False
        ),
        "refinement_performed": refinement_summary.performed,
        "refined_output_names": _list_names(refinement_summary.output_paths),
        "validation_passed": validation_report.passed,
        "validation_summary": validation_report.summary,
        "validation_issues": [
            {
                "level": issue.level,
                "message": issue.message,
                "field": issue.field,
                "suggestion": issue.suggestion,
            }
            for issue in validation_report.issues
        ],
        "route_report_title": route_report.title,
        "route_report_summary": route_report.summary,
        "route_report_artifacts": _list_names(route_report.artifact_paths),
        "final_status": result.final_status,
        "structured_outputs": {
            "genome": (
                _list_names(result.genome_output.output_paths)
                if result.genome_output is not None
                else []
            ),
            "environment": (
                _list_names(result.environment_output.output_paths)
                if result.environment_output is not None
                else []
            ),
        },
        "warnings": warnings,
        "memory_state": snapshot.get("current_state"),
        "trace_steps": len(snapshot.get("trace", [])),
        "brain": _summarize_brain(snapshot),
        "error": None,
        "exception_type": None,
    }


def _run_single_scenario(spec: ScenarioSpec, scenario_root: Path) -> dict[str, Any]:
    scenario_root.mkdir(parents=True, exist_ok=True)

    request: PreparationRequest | None = None
    agent: DataPreparationSubAgent | None = None
    try:
        request = spec.builder(scenario_root)
        output_dir = scenario_root / "prepared_outputs"
        output_dir.mkdir(parents=True, exist_ok=True)
        config_kwargs: dict[str, Any] = {
            "runtime_mode": spec.runtime_mode,
            "output_dir": output_dir,
        }
        if spec.llm_options is not None:
            config_kwargs["llm_options"] = dict(spec.llm_options)
        config_kwargs.update(spec.config_overrides)

        agent = DataPreparationSubAgent(config=DataPreparationConfig(**config_kwargs))
        pipeline = _execute_pipeline(
            agent,
            request,
            plan_mutator=spec.plan_mutator,
        )
        return _summarize_successful_run(
            spec=spec,
            scenario_root=scenario_root,
            request=request,
            pipeline=pipeline,
        )
    except Exception as exc:  # pragma: no cover - defensive fallback for demo stability.
        snapshot = agent.get_memory_snapshot() if agent is not None else {}
        return {
            "scenario": spec.name,
            "description": spec.description,
            "runtime_mode": spec.runtime_mode,
            "workspace": str(scenario_root),
            "input_files": [raw_input.file_path.name for raw_input in request.input_files]
            if request is not None
            else [],
            "inspection_results": [],
            "bundle_counts": {},
            "bundle_status": None,
            "route": None,
            "plan_task_types": [],
            "plan_task_statuses": [],
            "execution_output_names": [],
            "execution_partial_success": False,
            "refinement_performed": False,
            "refined_output_names": [],
            "validation_passed": False,
            "validation_summary": str(exc),
            "validation_issues": [],
            "route_report_title": None,
            "route_report_summary": None,
            "route_report_artifacts": [],
            "final_status": "crashed",
            "structured_outputs": {"genome": [], "environment": []},
            "warnings": [],
            "memory_state": snapshot.get("current_state"),
            "trace_steps": len(snapshot.get("trace", [])),
            "brain": _summarize_brain(snapshot),
            "error": str(exc),
            "exception_type": type(exc).__name__,
        }


def _run_scenarios(root: Path, specs: list[ScenarioSpec]) -> list[dict[str, Any]]:
    return [
        _run_single_scenario(spec, root / f"{index:02d}_{spec.name}")
        for index, spec in enumerate(specs, start=1)
    ]


def run_demo(
    *,
    include_llm: bool = False,
    output_root: Path | None = None,
    scenario_names: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Run the full scenario demo and return structured summaries."""

    specs = get_scenario_specs(include_llm=include_llm)
    if scenario_names:
        selected = set(scenario_names)
        available = {spec.name for spec in specs}
        missing = sorted(selected - available)
        if missing:
            raise ValueError(f"Unknown scenario(s): {', '.join(missing)}")
        specs = [spec for spec in specs if spec.name in selected]

    if output_root is None:
        with tempfile.TemporaryDirectory(prefix="data_prep_full_demo_") as temp_dir:
            return _run_scenarios(Path(temp_dir), specs)

    output_root.mkdir(parents=True, exist_ok=True)
    return _run_scenarios(output_root, specs)


def _format_list(values: list[str]) -> str:
    return ", ".join(values) if values else "(none)"


def _print_human_report(summaries: list[dict[str, Any]]) -> None:
    for index, summary in enumerate(summaries, start=1):
        print(f"[{index}] {summary['scenario']}")
        print(f"  description: {summary['description']}")
        print(f"  runtime_mode: {summary['runtime_mode']}")
        print(f"  workspace: {summary['workspace']}")
        if summary["error"] is not None:
            print(f"  error: {summary['exception_type']}: {summary['error']}")
            print()
            continue

        detected = [
            (
                f"{item['file_name']}<"
                f"{item['detected_category']}/"
                f"{item['detected_format']}/"
                f"{item['usability']}>"
            )
            for item in summary["inspection_results"]
        ]
        print(f"  input_files: {_format_list(summary['input_files'])}")
        print(f"  detected: {_format_list(detected)}")
        print(
            "  bundle_status -> route -> final_status: "
            f"{summary['bundle_status']} -> {summary['route']} -> {summary['final_status']}"
        )
        print(
            "  validation: "
            f"{'passed' if summary['validation_passed'] else 'failed'}"
            f" | {summary['validation_summary']}"
        )
        print(f"  plan_task_types: {_format_list(summary['plan_task_types'])}")
        print(f"  execution_outputs: {_format_list(summary['execution_output_names'])}")
        print(f"  refined_outputs: {_format_list(summary['refined_output_names'])}")
        print(f"  route_artifacts: {_format_list(summary['route_report_artifacts'])}")
        print(
            "  structured_outputs: "
            f"genome={_format_list(summary['structured_outputs']['genome'])}; "
            f"environment={_format_list(summary['structured_outputs']['environment'])}"
        )
        if summary["warnings"]:
            print(f"  warnings: {_format_list(summary['warnings'])}")
        brain = summary["brain"]
        if brain["attempted_llm"] is not None:
            print(
                "  brain: "
                f"attempted_llm={brain['attempted_llm']}, "
                f"used_llm={brain['used_llm']}, "
                f"fallback_reason={brain['fallback_reason']}, "
                f"suggested_task_types={brain['suggested_task_types']}"
            )
        print(f"  memory_state: {summary['memory_state']} | trace_steps: {summary['trace_steps']}")
        print()

    status_counts: dict[str, int] = {}
    for summary in summaries:
        status = summary["final_status"]
        status_counts[status] = status_counts.get(status, 0) + 1
    print("final_status_counts:", status_counts)


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run a comprehensive set of data preparation demo scenarios.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print the structured scenario summaries as JSON.",
    )
    parser.add_argument(
        "--include-llm",
        action="store_true",
        help="Include the optional hybrid planning scenario that targets the local OpenAI-compatible model.",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        help="Persist generated scenario inputs and outputs under this directory instead of a temporary folder.",
    )
    parser.add_argument(
        "--scenario",
        action="append",
        dest="scenario_names",
        help="Run only the named scenario. Can be provided multiple times.",
    )
    parser.add_argument(
        "--list-scenarios",
        action="store_true",
        help="List the available scenario names and exit.",
    )
    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_argument_parser()
    args = parser.parse_args(argv)

    if args.list_scenarios:
        for scenario in get_scenario_specs(include_llm=args.include_llm):
            print(scenario.name)
        return

    summaries = run_demo(
        include_llm=args.include_llm,
        output_root=args.output_root,
        scenario_names=args.scenario_names,
    )
    if args.json:
        print(json.dumps(summaries, ensure_ascii=False, indent=2))
        return
    _print_human_report(summaries)


if __name__ == "__main__":
    main()
