# DataPreparationSubAgent Instructions

## Scope

Work only inside this directory and its descendants unless a change outside this directory is strictly necessary for imports or package initialization.

Target directory:

`agents/core/sub_agents/data_preparation/`

Do not refactor unrelated parts of the repository.

---

## Goal

Implement a self-contained **Data Readiness and Preparation Sub-Agent**.

This module must:
- inspect raw files,
- build a normalized bundle,
- assess readiness,
- route into the correct path,
- optionally process transformable inputs,
- validate outputs,
- assemble a unified result.

Do not assume all inputs require processing.

---

## Required Architecture

The sub-agent must follow this gated workflow:

`inspect -> bundle -> readiness assessment -> route -> (optional process) -> validate -> result`

Supported route paths:
- `direct_output`
- `processing`
- `report_only`
- `unsupported`

This structure is mandatory.

---

## Runtime Design Rules

- Use fixed workflow + modular internal components.
- Use typed schemas for all major inputs and outputs.
- Use runtime capability modules under `capabilities/`.
- Do not call runtime modules “skills” in Python code.
- Reserve `.agents/skills/.../SKILL.md` for Codex development-time skills only.
- Support `rule_only`, `hybrid`, and `llm_enhanced` modes.
- `rule_only` must work without external API access.

---

## LLM Rules

- Do not hard-require LLM access for the MVP.
- If implementing LLM-assisted behavior, route it through:
  - `brain.py`
  - `llm_client.py`
  - `prompts/`
- Never scatter raw API calls across `inspector.py`, `planner.py`, or `executor.py`.
- LLM failures must fall back safely to rule-based behavior.

---

## Inspection Rules

- Do not rely only on file extensions.
- Use multiple signals:
  - parseability,
  - headers,
  - content preview,
  - modality cues,
  - semantic cues,
  - PDF/image hints when available.
- Every inspected file must receive:
  - modality
  - semantic category
  - format
  - confidence
  - usability
  - evidence

---

## Readiness Rules

The system must explicitly determine whether files or bundles are:

- `analysis_ready`
- `partially_ready`
- `transformable`
- `view_only`
- `unsupported`

This decision must affect routing.

Do not always create a plan.
Do not always process data.
Already-ready inputs should go through the direct output path.

---

## Routing Rules

The router must decide among:
- direct output path,
- processing path,
- report-only path,
- unsupported path.

This route must be explicit and recorded in trace/state.

---

## Engineering Requirements

- Python 3.10+
- type annotations everywhere
- `pathlib`
- `pydantic`
- `logging`
- `pytest`
- clear docstrings
- robust error handling
- testable modules
- allow partial success

Avoid:
- giant files,
- unclear state transitions,
- hidden side effects,
- hardcoding everything in `agent.py`.

---

## Development Order

Follow `docs/project/TASKS.md` in order.

At the end of each phase:
1. keep imports working,
2. keep code runnable,
3. add or update tests,
4. update docs or status if needed.

Do not skip directly to polishing before the workflow is implemented.

---

## Completion Standard

The implementation is not done until:
- the main workflow is implemented,
- the gating logic works,
- direct-output and processing paths are both supported,
- route-specific outputs are represented,
- tests cover representative cases,
- the demo script runs end-to-end locally.
