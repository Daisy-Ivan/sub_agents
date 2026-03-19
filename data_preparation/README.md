# Data Preparation Sub-Agent

## 1. What This Module Is

`data_preparation` is a sub-agent for turning raw breeding / G2P related inputs into a validated, structured result.

It does not blindly transform every file. The intended behavior is:

1. inspect raw inputs
2. classify them into genotype / environment / metadata / report / unknown
3. decide whether they are already usable
4. route them into the correct path
5. only plan and execute tools when processing is necessary
6. validate the outputs
7. assemble one final `PreparationResult`

This package supports three runtime modes:

- `rule_only`: deterministic rules only
- `hybrid`: rule-based pipeline with optional LLM assistance
- `llm_enhanced`: reserved for deeper model involvement

## 2. Current Status

The internal phases are implemented through `Phase 11`, including local OpenAI-compatible model integration.

The public single-entry runtime is now available:

- `DataPreparationSubAgent.run(request)`

This method wires the full gated chain:

- `inspect_files()`
- `build_bundle()`
- `assess_readiness()`
- `route()`
- `build_processing_plan()`
- `execute_processing_plan()`
- `refine_outputs()`
- `validate_route_outputs()`
- `build_route_report()`
- `assemble_result()`

Some internal demos still keep a manual phase-by-phase path when they need demo-only `plan_mutator` hooks, but normal callers should use `run()`.

## 3. End-to-End Workflow

The workflow is fixed and gated:

```text
Inspect -> Bundle -> Readiness -> Route -> (Plan/Execute if needed) -> Refine -> Validate -> Assemble Result
```

Route mapping is currently:

| Bundle Status | Route |
| --- | --- |
| `analysis_ready` | `direct_output` |
| `partially_ready` | `direct_output` |
| `transformable` | `processing` |
| `view_only` | `report_only` |
| `unsupported` | `unsupported` |

Processing only happens on the `processing` route.

## 4. Directory Structure

The current package layout is:

```text
data_preparation/
  AGENTS.md

  __init__.py
  agent.py
  config.py
  schemas.py
  state.py
  memory.py
  exceptions.py

  inspector.py
  bundle_builder.py
  readiness_assessor.py
  router.py
  planner.py
  executor.py
  result_assembler.py
  brain.py
  llm_client.py

  adapters/
  capabilities/
  docs/
    project/
      README.md
      readmeCN.md
      SPEC.md
      TASKS.md
      TEST_CONTRACT.md
      EXPECTED_CASES.md
      PROMPTS.md
  prompts/
  sample_inputs/
  examples/
  tests/
  tools/
```

Key subdirectories:

- `capabilities/`: runtime business logic helpers such as inspection rules, refinement, validation, and route report assembly
- `docs/project/`: bundled project documentation, specs, task phases, prompt references, and maintenance-facing notes
- `tools/`: low-level executable processing tools plus registry
- `prompts/`: model prompt templates for runtime planning and tool generation
- `examples/`: runnable demos
- `tests/`: phase-level and demo-level tests

## 5. Core File Responsibilities

### Orchestration

- `agent.py`: the main orchestrator; owns phase transitions and memory updates
- `memory.py`: stores request, intermediate artifacts, metadata, and trace
- `state.py`: workflow state machine enum
- `config.py`: runtime mode, output directory, LLM options, and policy overrides
- `schemas.py`: typed contracts for requests, plans, validation, and final results
- `exceptions.py`: package-level error types

### Phase Logic

- `inspector.py`: wraps the file inspection capability
- `bundle_builder.py`: groups inspection results into normalized bundles
- `readiness_assessor.py`: computes `analysis_ready / partially_ready / transformable / view_only / unsupported`
- `router.py`: converts readiness into a route
- `planner.py`: builds deterministic processing tasks for the `processing` route
- `executor.py`: runs registered tools sequentially and records partial success
- `result_assembler.py`: turns all intermediate artifacts into the final `PreparationResult`

### Runtime Capabilities

- `capabilities/file_inspection.py`: rule-based file type / category / usability detection
- `capabilities/data_refine.py`: optional post-processing refinement for structured outputs
- `capabilities/data_checker.py`: route-aware validation
- `capabilities/report_builder.py`: route summary and artifact report assembly

### LLM Integration

- `brain.py`: optional model-assisted planning layer
- `llm_client.py`: OpenAI-compatible HTTP client
- `prompts/runtime_tool_planning.md`: runtime prompt for suggesting registered tool tasks only
- `prompts/tool_generation.md`: development prompt for generating a new tool implementation

### Tools

- `tools/base.py`: `BaseTool` contract
- `tools/registry.py`: tool registration and lookup
- `tools/plink_conversion.py`: PLINK-like genotype normalization
- `tools/table_normalization.py`: CSV/TSV/table normalization tools
- `tools/report_generation.py`: sample/time checks and text reports
- `tools/source_merge.py`: source manifest generation
- `tools/tool_template.py`: template for adding a new tool
- `tools/task_tools.py`: compatibility re-export layer

## 6. How Data Flows Through the Package

The main public call chain today is:

```text
PreparationRequest -> run() -> PreparationResult
```

Internally, `run()` expands to:

```text
PreparationRequest
  -> inspect_files()
  -> build_bundle()
  -> assess_readiness()
  -> route()
  -> build_processing_plan()     # only meaningful for processing
  -> execute_processing_plan()   # only meaningful for processing
  -> refine_outputs()
  -> validate_route_outputs()
  -> build_route_report()
  -> assemble_result()
```

The execution side is deterministic:

```text
planner.py -> SubTask(task_type, tool_name)
executor.py -> tools/registry.py
registry.py -> concrete BaseTool subclass
tool.run(task, context) -> ToolResult
```

This is important for maintenance:

- dropping a file into `tools/` is not enough
- the tool must be registered
- the planner must know when to emit the matching task

## 7. Demos

### 7.1 Simple Demo

Runs a single processing-style example through the public `run()` entry:

```bash
cd /home/dataset-assist-0/swb/swb_bak
python agents/core/sub_agents/data_preparation/examples/demo_run.py
```

### 7.2 Full Scenario Demo

Runs a comprehensive multi-scenario demo and is the best regression smoke demo:

```bash
cd /home/dataset-assist-0/swb/swb_bak
python agents/core/sub_agents/data_preparation/examples/full_scenario_demo.py
```

Supported options:

```bash
python agents/core/sub_agents/data_preparation/examples/full_scenario_demo.py --json
python agents/core/sub_agents/data_preparation/examples/full_scenario_demo.py --scenario processing_transformable_success
python agents/core/sub_agents/data_preparation/examples/full_scenario_demo.py --scenario report_only_assets --scenario unsupported_missing_and_binary
python agents/core/sub_agents/data_preparation/examples/full_scenario_demo.py --output-root /tmp/data_prep_demo
python agents/core/sub_agents/data_preparation/examples/full_scenario_demo.py --list-scenarios
```

Default scenarios covered by `full_scenario_demo.py`:

- `analysis_ready_direct_output`
- `partially_ready_with_report`
- `content_based_detection_unknown_suffix`
- `processing_transformable_success`
- `processing_partial_success`
- `processing_validation_failed`
- `report_only_assets`
- `unsupported_missing_and_binary`

Notes for maintainers:

- the full demo is a regression harness, not just a happy-path script
- a few scenarios intentionally use demo-only `plan_mutator` hooks so that `success`, `partial_success`, and `validation_failed` branches remain stable and easy to test

### 7.3 Optional LLM Demo

The full scenario demo can also include the hybrid planning path:

```bash
python agents/core/sub_agents/data_preparation/examples/full_scenario_demo.py --include-llm
```

There is also a dedicated model debug demo:

```bash
python agents/core/sub_agents/data_preparation/examples/llm_debug_demo.py
```

This debug demo does two things in order:

- calls the local OpenAI-compatible endpoint directly with a smoke-test prompt
- runs `DataPreparationSubAgent.run()` in `hybrid` mode and prints the chosen route, plan, brain usage flags, validation summary, and final status

## 8. Local Model Configuration

The current local model integration assumes an OpenAI-compatible endpoint. The default debug target is:

- `base_url`: `http://127.0.0.1:8000/v1`
- `model`: `Qwen/Qwen3.5-35B-A3B-FP8`

Typical config:

```python
from agents.core.sub_agents.data_preparation import DataPreparationConfig

config = DataPreparationConfig(
    runtime_mode="hybrid",
    llm_options={
        "base_url": "http://127.0.0.1:8000/v1",
        "model": "Qwen/Qwen3.5-35B-A3B-FP8",
        "timeout_seconds": 30,
    },
)
```

Model usage is intentionally scoped:

- rules still produce the base plan
- the brain can suggest additional tasks
- runtime tool execution still goes through planner + registry
- the model does not directly execute arbitrary code from `tools/`

## 9. Programmatic Usage

The recommended programmatic entrypoint is now `run()`:

```python
from agents.core.sub_agents.data_preparation import (
    DataPreparationSubAgent,
    PreparationRequest,
    RawInputFile,
)

request = PreparationRequest(
    input_files=[
        RawInputFile(file_path="path/to/genotypes.vcf"),
        RawInputFile(file_path="path/to/weather.csv"),
    ],
    task_goal="Prepare trial inputs",
)

agent = DataPreparationSubAgent()
result = agent.run(request)
```

If you are debugging a specific phase, the individual phase methods are still available and intentionally remain public.

## 10. Tests

Run the full data preparation test suite:

```bash
cd /home/dataset-assist-0/swb/swb_bak
python -m unittest discover -s agents/core/sub_agents/data_preparation/tests -t . -v
```

Run only the comprehensive demo smoke test:

```bash
python -m unittest agents.core.sub_agents.data_preparation.tests.test_full_scenario_demo -v
```

Useful extra validation:

```bash
python -m compileall agents/core/sub_agents/data_preparation
python agents/core/sub_agents/data_preparation/examples/full_scenario_demo.py
```

### 10.1 Quick Verification

If you only want a fast confidence check that the package still works in this workspace, run these commands in order:

```bash
cd /home/dataset-assist-0/swb/swb_bak
python -m unittest discover -s agents/core/sub_agents/data_preparation/tests -t . -v
python agents/core/sub_agents/data_preparation/examples/demo_run.py
python agents/core/sub_agents/data_preparation/examples/full_scenario_demo.py --json
python agents/core/sub_agents/data_preparation/examples/llm_debug_demo.py
```

What you should expect:

- the unittest suite completes successfully; the latest local verification passed `57` tests
- `demo_run.py` finishes with `memory_state: completed`; the toy input currently ends in `final_status: validation_failed`, which is expected for that sample data
- `full_scenario_demo.py --json` returns a mix of `success`, `partial_success`, `validation_failed`, `report_only`, and `unsupported` scenarios without crashes
- `llm_debug_demo.py` should print the local model name `Qwen/Qwen3.5-35B-A3B-FP8`, show `brain_attempted_llm: True`, `brain_used_llm: True`, and finish the hybrid run with `hybrid_memory_state: completed`

## 11. Maintenance Guide

### 11.1 If You Need to Add a New Detection Rule

Primary files:

- `capabilities/file_inspection.py`
- `inspector.py`
- tests under `tests/test_phase3_inspector.py`

Suggested workflow:

1. add or adjust the heuristic in `file_inspection.py`
2. keep the output in terms of `modality`, `detected_category`, `detected_format`, `usability`
3. add a representative test case
4. verify that downstream readiness / routing still behaves as expected

### 11.2 If You Need to Change Readiness or Routing

Primary files:

- `readiness_assessor.py`
- `router.py`
- tests: `test_phase5_readiness.py`, `test_phase6_router.py`

Use this when the policy changes, for example:

- a file type should become `transformable` instead of `analysis_ready`
- a previously direct-output bundle should now go through processing

### 11.3 If You Need to Add a New Tool

Primary files:

- `tools/tool_template.py`
- `tools/<your_tool>.py`
- `tools/registry.py`
- `planner.py`
- tests

Required steps:

1. copy `tools/tool_template.py`
2. implement a new `BaseTool` subclass
3. register it in `tools/registry.py`
4. make `planner.py` emit a matching `task_type` / `tool_name`
5. add tests for the tool and for end-to-end execution

Do not assume the model will discover the tool automatically. The runtime path is registration-based, not directory-scan-based.

### 11.4 If You Need to Change Validation

Primary files:

- `capabilities/data_checker.py`
- `capabilities/report_builder.py`
- `result_assembler.py`

This is where to update:

- required columns
- temporal/spatial alignment checks
- sample consistency behavior
- summary / warning merging

### 11.5 If You Need to Change Model Behavior

Primary files:

- `brain.py`
- `llm_client.py`
- `prompts/runtime_tool_planning.md`
- `prompts/tool_generation.md`
- tests: `test_phase11_brain_llm.py`

Recommended rule:

- keep rule-based planning as the safe fallback
- only let the model suggest tasks that map to registered tools
- never let runtime execution bypass `registry.py`

### 11.6 If You Need a New Demo or Regression Case

Primary files:

- `examples/full_scenario_demo.py`
- `tests/test_full_scenario_demo.py`

This is the best place to add a new representative scenario because it also doubles as a smoke regression harness.

## 12. Prompt Files

Current prompt files:

- `prompts/runtime_tool_planning.md`: runtime planning prompt for suggesting already-registered tools
- `prompts/tool_generation.md`: development-time prompt for generating new tool code

Use the runtime prompt when the model should help with planning.

Use the tool-generation prompt when the model should help create a new tool module and the associated registry / planner / test changes.

## 13. Known Limitations

- `llm_enhanced` is structurally supported but not as deeply exercised as `rule_only` and `hybrid`
- some tool implementations are still lightweight Python transformations rather than wrappers around domain-native command-line tools
- some demo scenarios intentionally use demo-only `plan_mutator` hooks so that `partial_success` and `validation_failed` branches stay stable for regression testing

## 14. Recommended Next Improvements

- continue migrating demo-only manual orchestration toward `run()` where no `plan_mutator` hook is needed
- add more domain-native genotype/environment tools where needed
- broaden sample input fixtures beyond synthetic test content
- add CI hooks that run `test_full_scenario_demo.py` and the full unittest suite automatically
