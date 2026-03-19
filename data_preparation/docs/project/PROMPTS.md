# Suggested Codex Prompts

These prompts are designed to help Codex implement the sub-agent incrementally and reliably.

Use them in order instead of asking for the whole system in one step.

---

## Prompt 1 — Read the docs and scaffold the package

Read `../../AGENTS.md` first, then read `README.md`, `SPEC.md`, `TASKS.md`, and `TEST_CONTRACT.md` from this `docs/project/` folder.

Then scaffold the `data_preparation` sub-agent package according to the documented architecture.

Requirements:
- create all directories and placeholder modules
- add `__init__.py` files
- keep imports valid
- do not implement business logic yet
- do not touch unrelated repository areas

At the end:
- summarize created files
- note any unresolved import assumptions

---

## Prompt 2 — Implement schemas, state, memory, exceptions

Read the docs again before coding.

Implement only Phase 2 from `TASKS.md`:
- `schemas.py`
- `state.py`
- `memory.py`
- `exceptions.py`
- minimal `config.py`

Requirements:
- use pydantic
- type annotations everywhere
- include docstrings
- keep models aligned with `SPEC.md`

At the end:
- add or update focused tests for schema creation
- keep code importable

---

## Prompt 3 — Implement inspection

Implement only the inspection layer:
- `inspector.py`
- `capabilities/file_inspection.py`

Requirements:
- support table, text, image, pdf, unknown
- do not rely only on file extensions
- return modality, category, format, confidence, usability, evidence
- keep logic conservative

Test against:
- `sample_inputs/sample_weather.csv`
- `sample_inputs/sample_soil.csv`
- `sample_inputs/sample_genotype.vcf`
- `sample_inputs/sample_weather_chart.png`
- `sample_inputs/sample_report.pdf`
- `sample_inputs/sample_unknown.txt`

At the end:
- add/update inspection tests
- report current limitations clearly

---

## Prompt 4 — Implement bundle builder and readiness assessor

Implement only:
- `bundle_builder.py`
- `readiness_assessor.py`

Requirements:
- group inspection results into a normalized bundle
- determine readiness states:
  - analysis_ready
  - partially_ready
  - transformable
  - view_only
  - unsupported
- include rationale and warnings

At the end:
- add/update tests
- verify mapping against `EXPECTED_CASES.md`

---

## Prompt 5 — Implement router

Implement only:
- `router.py`

Requirements:
- map readiness to:
  - direct_output
  - processing
  - report_only
  - unsupported
- keep routing explicit and testable
- do not overcomplicate policy yet

At the end:
- add/update route tests

---

## Prompt 6 — Implement planner and tools for processing path

Implement only:
- `planner.py`
- `tools/base.py`
- `tools/registry.py`
- minimal low-level tools needed for MVP

Requirements:
- planner is only used for processing path
- implement a rule-based planner first
- keep interfaces ready for hybrid / llm-enhanced evolution
- use structured task definitions

At the end:
- add/update planner tests
- do not add real external bioinformatics dependencies unless mocked or clearly isolated

---

## Prompt 7 — Implement executor and runtime capabilities

Implement only:
- `executor.py`
- `capabilities/data_refine.py`
- `capabilities/data_checker.py`
- `capabilities/report_builder.py`

Requirements:
- support partial success
- update execution trace
- route outputs into validation and reporting
- direct-output path should not force heavy processing

At the end:
- add/update tests
- confirm direct-output and processing paths both work

---

## Prompt 8 — Implement result assembler and main agent

Implement:
- `result_assembler.py`
- `agent.py`

Requirements:
- wire together the full workflow:
  inspect -> bundle -> readiness -> route -> optional process -> validate -> result
- expose clear entry points
- preserve memory snapshots and execution trace

At the end:
- add/update end-to-end tests

---

## Prompt 9 — Add optional brain and llm client

Implement:
- `brain.py`
- `llm_client.py`
- prompt loading under `prompts/`

Requirements:
- support `rule_only`, `hybrid`, `llm_enhanced`
- `rule_only` must not require API access
- LLM failure must fall back safely
- do not scatter API code across modules

At the end:
- add mock-based brain tests

---

## Prompt 10 — Demo and polish

Implement:
- `examples/demo_run.py`

Requirements:
- run locally in `rule_only` mode
- print inspection summary, readiness decision, chosen route, validation summary, and final status
- keep output readable

At the end:
- run focused tests
- summarize what is complete and what remains TODO

---

## General Prompting Rule

Do not ask Codex to build the entire system in one shot.

Prefer:
1. one phase per prompt,
2. tests after each phase,
3. explicit completion checks,
4. updates aligned with `TASKS.md`.

This greatly improves reliability on long implementation tasks.
