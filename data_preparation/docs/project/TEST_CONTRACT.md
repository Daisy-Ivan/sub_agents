# Test Contract

This file defines the minimum required test and validation behavior for the Data Readiness and Preparation Sub-Agent.

The implementation is not considered complete until these tests pass or are explicitly marked with a justified TODO.

---

## 1. Schema Tests

### Required
- create a valid `PreparationRequest`
- reject invalid request structures
- create valid `FileInspectionResult`
- create valid `NormalizedInputBundle`
- create valid `ReadinessDecision`
- create valid `PreparationResult`

---

## 2. Inspection Tests

The agent must support representative input types.

### Table-like environment input
Input:
- `sample_weather.csv`

Expected:
- modality = `table`
- category = `environment`
- usability = `analysis_ready` or `transformable`

### Soil table input
Input:
- `sample_soil.csv`

Expected:
- modality = `table`
- category = `environment`

### Genotype VCF input
Input:
- `sample_genotype.vcf`

Expected:
- category = `genotype`
- usability must not be `unknown`

### Image-based weather chart
Input:
- `sample_weather_chart.png`

Expected:
- modality = `image`
- category likely `environment` or `report`
- usability = `view_only` or `transformable` with explicit caution

### Report PDF
Input:
- `sample_report.pdf`

Expected:
- modality = `pdf`
- category = `report` or `environment`
- usability must not pretend to be structured analysis-ready data unless evidence supports it

### Unknown text
Input:
- `sample_unknown.txt`

Expected:
- category = `unknown` or weak metadata/report classification
- must not crash

---

## 3. Bundle Builder Tests

Given mixed inspection results, the bundle builder must:
- place genotype files under `genotype_files`
- place environment files under `environment_files`
- preserve unknown files
- preserve report files

---

## 4. Readiness Assessment Tests

### Analysis-ready bundle
A bundle containing a standard weather table and a valid VCF should be eligible for:
- `analysis_ready`
- or `partially_ready` if only minor caveats remain

### Transformable bundle
A bundle containing transformable inputs such as PLINK placeholder or messy table should yield:
- `transformable`

### View-only bundle
A bundle dominated by chart screenshots or report-only PDFs should yield:
- `view_only`

### Unsupported bundle
Unsupported inputs should yield:
- `unsupported`

---

## 5. Router Tests

The router must map readiness into a route:

- `analysis_ready` -> `direct_output`
- `partially_ready` -> usually `direct_output` with stronger validation or policy-driven decision
- `transformable` -> `processing`
- `view_only` -> `report_only`
- `unsupported` -> `unsupported`

This mapping must be explicit and testable.

---

## 6. Planner Tests

Planner should only be invoked for the processing path.

Required:
- no processing plan for direct-output-only case
- non-empty plan for transformable case
- readable rationale
- valid `SubTask` status initialization

---

## 7. Executor Tests

### Processing path
Given a transformable bundle and a valid plan:
- executor must run tasks in order
- update subtask states
- record execution trace
- preserve failures as trace entries

### Partial success
If one task fails but others succeed:
- result must not necessarily hard-fail
- warnings/errors must be recorded
- final result may be partial but valid

---

## 8. Direct Output Path Tests

If input is already analysis-ready:
- no heavy processing plan should be required
- minimal validation should still run
- result should contain structured output directly

This is mandatory because the sub-agent must not always process data.

---

## 9. Report-Only Path Tests

For view-only inputs:
- no fabricated structured numerical outputs
- inspection summary must be preserved
- final result should indicate report-only semantics

---

## 10. Unsupported Path Tests

For unsupported inputs:
- no crash
- warnings/errors included
- valid `PreparationResult` still returned when possible

---

## 11. Validation Tests

`capabilities/data_checker.py` must test:
- required fields
- missing values
- sample consistency
- temporal alignment
- spatial alignment
- output of `ValidationReport`

---

## 12. Brain / LLM Tests

These can be mock-based.

Required:
- `rule_only` mode does not call the LLM
- `hybrid` mode can call a mocked brain
- LLM failure falls back to rule-based result
- no route should become impossible without the LLM

---

## 13. Demo Contract

`examples/demo_run.py` must:
1. build a request,
2. run the sub-agent,
3. print or serialize:
   - inspection results,
   - readiness decision,
   - route,
   - validation summary,
   - final status

The demo must run locally without requiring a live LLM API in `rule_only` mode.

---

## 14. Completion Rule

The module is complete for v1 only when:
- inspection works,
- readiness gate works,
- router works,
- direct output path works,
- processing path works,
- report-only path works,
- unsupported path works,
- tests cover representative cases,
- the demo runs end-to-end.
