# DataPreparationSubAgent Specification

## 1. Scope

This specification defines the implementation contract for the **Data Readiness and Preparation Sub-Agent**.

The module must be:
- self-contained,
- end-to-end,
- typed,
- testable,
- able to run without LLM dependency in `rule_only` mode,
- extensible to LLM-assisted operation in `hybrid` and `llm_enhanced` modes.

---

## 2. Objective

The agent must transform a set of **raw, unlabeled input files** into a structured preparation result by:

1. inspecting files,
2. building a normalized bundle,
3. assessing readiness,
4. routing to the correct path,
5. optionally planning and executing transformations,
6. validating outputs,
7. returning a unified result.

The agent must **not** assume all files require transformation.

---

## 3. Required High-Level Flow

The fixed lifecycle of `run()` must be:

```text
Inspect
→ Bundle
→ Readiness Assessment
→ Route
   ├─ Direct Output Path
   ├─ Processing Path
   ├─ Report-Only Path
   └─ Unsupported Path
→ Validation
→ Result Assembly
```

Processing is conditional, not mandatory.

---

## 4. Required Runtime Modes

The configuration must support:

### `rule_only`
- no external LLM call
- pure local logic
- deterministic fallback

### `hybrid`
- rules remain primary
- LLM may assist ambiguous inspection, readiness judgment, planning, and reporting

### `llm_enhanced`
- LLM participates more actively
- fallback to rules remains mandatory

---

## 5. Required Schemas

All schemas must be defined in `schemas.py`.

## 5.1 Input Schemas

```python
class RawInputFile(BaseModel):
    file_path: Path
    file_name: str | None = None
    user_hint: str | None = None
    metadata: dict = Field(default_factory=dict)
```

```python
class PreparationRequest(BaseModel):
    input_files: list[RawInputFile]
    task_goal: str
    constraints: dict = Field(default_factory=dict)
```

## 5.2 Inspection Schemas

```python
class FileInspectionResult(BaseModel):
    file_path: Path
    modality: Literal["table", "text", "image", "pdf", "archive", "unknown"]
    detected_category: Literal["genotype", "environment", "metadata", "report", "unknown"]
    detected_format: str
    confidence: float
    usability: Literal["analysis_ready", "transformable", "view_only", "unsupported"]
    evidence: list[str] = Field(default_factory=list)
    preview_columns: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
```

## 5.3 Bundle Schema

```python
class NormalizedInputBundle(BaseModel):
    genotype_files: list[FileInspectionResult] = Field(default_factory=list)
    environment_files: list[FileInspectionResult] = Field(default_factory=list)
    metadata_files: list[FileInspectionResult] = Field(default_factory=list)
    report_files: list[FileInspectionResult] = Field(default_factory=list)
    unknown_files: list[FileInspectionResult] = Field(default_factory=list)
```

## 5.4 Readiness Schemas

```python
class ReadinessDecision(BaseModel):
    bundle_status: Literal["analysis_ready", "partially_ready", "transformable", "view_only", "unsupported"]
    file_statuses: dict[str, str] = Field(default_factory=dict)
    rationale: str
    warnings: list[str] = Field(default_factory=list)
```

## 5.5 Planning Schemas

```python
class SubTask(BaseModel):
    task_id: str
    task_type: str
    description: str
    input_refs: list[str]
    tool_name: str | None = None
    status: Literal["pending", "running", "done", "failed", "skipped"] = "pending"
```

```python
class PreparationPlan(BaseModel):
    plan_id: str
    tasks: list[SubTask]
    rationale: str
```

## 5.6 Validation Schemas

```python
class ValidationIssue(BaseModel):
    level: Literal["info", "warning", "error"]
    message: str
    field: str | None = None
    suggestion: str | None = None
```

```python
class ValidationReport(BaseModel):
    passed: bool
    issues: list[ValidationIssue] = Field(default_factory=list)
    summary: str
```

## 5.7 Output Schemas

```python
class GenomeDataOutput(BaseModel):
    standardized_format: str
    output_paths: list[Path]
    sample_axis_aligned: bool
    variant_axis_aligned: bool
    metadata: dict = Field(default_factory=dict)
```

```python
class EnvironmentDataOutput(BaseModel):
    standardized_format: str
    output_paths: list[Path]
    temporal_aligned: bool
    spatial_aligned: bool
    metadata: dict = Field(default_factory=dict)
```

```python
class PreparationResult(BaseModel):
    genome_output: GenomeDataOutput | None = None
    environment_output: EnvironmentDataOutput | None = None
    inspection_results: list[FileInspectionResult] = Field(default_factory=list)
    normalized_bundle: NormalizedInputBundle | None = None
    readiness_decision: ReadinessDecision | None = None
    validation_report: ValidationReport
    execution_trace: list[dict] = Field(default_factory=list)
    final_status: str
```

---

## 6. Required Core Modules

## 6.1 `agent.py`
Main entry point.

Must expose at least:
- `inspect_files(request) -> list[FileInspectionResult]`
- `build_bundle(inspection_results) -> NormalizedInputBundle`
- `assess_readiness(bundle) -> ReadinessDecision`
- `route(bundle, readiness_decision) -> str`
- `run(request) -> PreparationResult`
- `get_memory_snapshot() -> dict`

Responsibilities:
- orchestrate the fixed workflow,
- manage state transitions,
- invoke optional LLM brain only through `brain.py`,
- produce unified outputs.

## 6.2 `inspector.py`
Coordinates file inspection.

Responsibilities:
- inspect raw files,
- determine modality,
- determine semantic category,
- determine usability,
- record evidence and warnings.

Must support image, PDF, table, text, and unknown inputs.

## 6.3 `bundle_builder.py`
Converts file-level inspection results into a normalized bundle.

Responsibilities:
- group by semantic class,
- preserve inspection results,
- provide a stable internal structure for readiness assessment and planning.

## 6.4 `readiness_assessor.py`
Determines whether processing is required.

Responsibilities:
- determine file-level readiness,
- determine bundle-level readiness,
- distinguish between:
  - `analysis_ready`
  - `partially_ready`
  - `transformable`
  - `view_only`
  - `unsupported`

## 6.5 `router.py`
Routes the bundle according to readiness.

Must support:
- `direct_output`
- `processing`
- `report_only`
- `unsupported`

Routing must be explicit and recorded in execution trace.

## 6.6 `planner.py`
Used only for the processing path.

Responsibilities:
- create tasks for transformable inputs,
- support `rule_only`, `hybrid`, and `llm_enhanced` logic,
- never be required for direct-output-only cases.

## 6.7 `executor.py`
Executes the plan.

Responsibilities:
- invoke tools,
- update subtask status,
- record trace,
- invoke refinement and checking,
- support partial success.

## 6.8 `result_assembler.py`
Builds the final result object.

Responsibilities:
- normalize outputs across all route paths,
- include reports, warnings, and trace,
- return a valid `PreparationResult`.

## 6.9 `memory.py`
Working memory, not chat memory.

Responsibilities:
- input summary,
- inspection results,
- bundle,
- readiness decision,
- route selection,
- plan,
- task execution status,
- warnings/errors,
- validation report,
- final status.

## 6.10 `brain.py`
Unified reasoning gateway for LLM assistance.

Responsibilities:
- assist ambiguous inspection,
- assist readiness explanation,
- assist plan generation,
- assist report explanation.

`brain.py` must be optional and must not be the only execution path.

## 6.11 `llm_client.py`
LLM API wrapper only.

Responsibilities:
- model selection,
- message dispatch,
- retry and timeout policy,
- response parsing.

Business logic must not live here.

---

## 7. Required Runtime Capability Modules

These live under `capabilities/`.

## 7.1 `file_inspection.py`
Runtime file understanding capability.

Must support:
- table inspection,
- text inspection,
- image inspection,
- PDF inspection,
- usability assignment,
- evidence collection.

## 7.2 `data_refine.py`
Data normalization capability.

Must support:
- safe column standardization,
- field normalization,
- minimal structure conversion,
- conservative defaults.

## 7.3 `data_checker.py`
Validation capability.

Must support:
- required fields,
- missing values,
- sample consistency,
- temporal alignment,
- spatial alignment,
- output validation report.

## 7.4 `report_builder.py`
Builds route-specific reports and summaries.

---

## 8. Required Tooling Modules

These live under `tools/`.

Minimum required files:
- `base.py`
- `registry.py`
- `io_tools.py`
- `genotype_tools.py`
- `environment_tools.py`
- `image_tools.py`
- `pdf_tools.py`

All tools must:
- use explicit inputs and outputs,
- be independently testable,
- avoid hidden side effects,
- return structured results.

---

## 9. Adapters

These live under `adapters/`.

## 9.1 `modality_adapter.py`
Determines how modality-specific behavior is handled.

## 9.2 `scenario_adapter.py`
Supports scenario-dependent behavior such as:
- breeding/G2P preparation,
- genotype-only workflows,
- environment-only workflows,
- demo mode.

## 9.3 `policy_adapter.py`
Supports policy-dependent behavior such as:
- strict
- balanced
- exploratory

This adapter must define how unknown, view-only, and partial success cases are handled.

---

## 10. Route Semantics

## 10.1 Direct Output Path
Use when bundle is already analysis-ready.

Behavior:
- do not generate a processing plan,
- perform minimal validation,
- return structured output directly.

## 10.2 Processing Path
Use when bundle is transformable.

Behavior:
- build plan,
- execute tools,
- refine,
- validate,
- return processed outputs.

## 10.3 Report-Only Path
Use when bundle is relevant but not suitable for structured transformation.

Examples:
- chart screenshots,
- report PDFs.

Behavior:
- produce inspection/report outputs,
- do not fabricate structured numerical outputs.

## 10.4 Unsupported Path
Use when files are unsupported or unclassifiable.

Behavior:
- record warnings/errors,
- allow partial success where possible.

---

## 11. LLM Integration Rules

The architecture must reserve extension points for an API-driven LLM brain.

LLM use is optional in v1, but the architecture must support:

- ambiguous image/PDF inspection assistance,
- readiness explanation,
- planning support,
- route rationale support.

The system must support three modes:
- `rule_only`
- `hybrid`
- `llm_enhanced`

When LLM calls fail, the system must degrade safely to rule-based behavior.

---

## 12. Engineering Constraints

Required:
- Python 3.10+
- `pathlib`
- type annotations everywhere
- `pydantic`
- `logging`
- `pytest`
- local demo script
- partial success support
- no hard dependency on network access in `rule_only`

Avoid:
- giant monolithic functions,
- hidden global state,
- extension-only classification,
- mandatory processing of already-ready data,
- direct LLM API calls scattered across modules.

---

## 13. Acceptance Criteria

v1 is complete when:

1. raw files can be passed in without pre-labeling,
2. files are inspected and classified,
3. bundle is built correctly,
4. readiness is assessed explicitly,
5. router selects a valid path,
6. already-ready inputs bypass unnecessary processing,
7. transformable inputs can be processed,
8. view-only and unsupported inputs are handled safely,
9. result is assembled into a valid `PreparationResult`,
10. tests and demo run successfully.
