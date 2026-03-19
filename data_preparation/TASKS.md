# Development Tasks

This document defines the recommended phased implementation order.

---

## Phase 1 — Scaffold

Create the package structure and placeholder modules.

Required:
- add `__init__.py` files
- create all top-level modules
- create `capabilities/`, `tools/`, `adapters/`, `prompts/`, `examples/`, `tests/`
- keep imports valid

Deliverable:
- importable package skeleton

---

## Phase 2 — Schemas, State, Memory, Exceptions

Implement foundational contracts.

Required:
- `schemas.py`
- `state.py`
- `memory.py`
- `exceptions.py`
- minimal config structure in `config.py`

Key outputs:
- all pydantic models
- working memory API
- explicit runtime states
- custom exceptions

Deliverable:
- typed core data structures

---

## Phase 3 — Inspector

Implement inspection logic.

Required:
- `inspector.py`
- `capabilities/file_inspection.py`
- modality-aware logic for:
  - table
  - text
  - image
  - pdf
  - unknown
- structured `FileInspectionResult`

Rules:
- do not rely only on file extensions
- always return evidence and usability

Deliverable:
- file-level inspection pipeline

---

## Phase 4 — Bundle Builder

Implement:
- `bundle_builder.py`

Required behavior:
- convert file-level inspection results into `NormalizedInputBundle`
- preserve inspection results
- keep unknown/report files visible

Deliverable:
- stable internal bundle representation

---

## Phase 5 — Readiness Assessment

Implement:
- `readiness_assessor.py`

Required behavior:
- decide bundle and file readiness
- assign one of:
  - `analysis_ready`
  - `partially_ready`
  - `transformable`
  - `view_only`
  - `unsupported`
- produce rationale and warnings

Deliverable:
- explicit readiness decision layer

---

## Phase 6 — Router

Implement:
- `router.py`

Required behavior:
- choose one route:
  - `direct_output`
  - `processing`
  - `report_only`
  - `unsupported`
- record route choice in trace/state

Deliverable:
- route selection layer

---

## Phase 7 — Planner

Implement:
- `planner.py`

Required behavior:
- only generate a plan when route is `processing`
- implement `RuleBasedPlanner`
- reserve interfaces for hybrid / LLM-assisted planning

Examples of tasks:
- PLINK conversion
- sample ID validation
- SNP matrix standardization
- weather table normalization
- time-axis check
- source merge

Deliverable:
- process-path planning

---

## Phase 8 — Tools and Executor

Implement:
- `tools/base.py`
- `tools/registry.py`
- low-level tools
- `executor.py`

Required behavior:
- execute tasks in order
- update task status
- record trace
- support partial success

Deliverable:
- executable process path

---

## Phase 9 — Runtime Capabilities

Implement:
- `capabilities/data_refine.py`
- `capabilities/data_checker.py`
- `capabilities/report_builder.py`

Required behavior:
- refine transformable inputs conservatively
- validate outputs
- build route-specific summaries

Deliverable:
- refinement, checking, and reporting layers

---

## Phase 10 — Result Assembly

Implement:
- `result_assembler.py`

Required behavior:
- assemble a valid `PreparationResult`
- support direct-output, processing, report-only, and unsupported outputs
- unify warnings and execution trace

Deliverable:
- final unified result builder

---

## Phase 11 — Brain and LLM Integration

Implement:
- `brain.py`
- `llm_client.py`
- prompt loading from `prompts/`

Required behavior:
- optional LLM assistance only
- fallback safe behavior in `rule_only`
- no raw API scattering

Deliverable:
- optional brain layer

---

## Phase 12 — Demo and Tests

Implement:
- `examples/demo_run.py`
- all tests in `tests/`

Minimum tests:
- schema creation
- file inspection
- readiness assessment
- router behavior
- process path
- direct output path
- report-only path
- unsupported path
- partial success
- optional brain mocking

Deliverable:
- runnable demo and test suite

---

## Suggested Execution Pattern for Codex

For each phase:
1. implement only that phase,
2. keep previous phases passing,
3. run focused tests,
4. update docs or TODO markers if something is intentionally deferred.

Do not try to implement everything in one step.
