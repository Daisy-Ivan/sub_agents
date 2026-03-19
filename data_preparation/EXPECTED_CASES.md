# Expected Cases

This document defines concrete expected behaviors for representative sample inputs.

These cases are stronger than abstract requirements and should guide both implementation and tests.

---

## Case 1 — Weather Table Already Ready

### Input
- `sample_inputs/sample_weather.csv`

### Expected behavior
- modality: `table`
- category: `environment`
- likely format: `weather_table`
- usability: `analysis_ready` or conservative `transformable`
- readiness: should be close to `analysis_ready`
- preferred route: `direct_output` unless validation indicates missing required structure

### Notes
The system should avoid unnecessary transformation if the table is already well structured.

---

## Case 2 — Soil Table

### Input
- `sample_inputs/sample_soil.csv`

### Expected behavior
- modality: `table`
- category: `environment`
- likely format: `soil_table`
- usability: `analysis_ready` or `transformable`
- route:
  - direct output if already normalized
  - processing if field normalization is needed

---

## Case 3 — Genotype VCF

### Input
- `sample_inputs/sample_genotype.vcf`

### Expected behavior
- category: `genotype`
- likely format: `vcf`
- usability: not `unknown`
- readiness:
  - `analysis_ready` if schema expectations are already met
  - otherwise `transformable`

### Notes
The agent must not misclassify a valid VCF as generic text.

---

## Case 4 — Weather Chart Image

### Input
- `sample_inputs/sample_weather_chart.png`

### Expected behavior
- modality: `image`
- semantic category: likely `environment` or `report`
- usability: usually `view_only`
- readiness: `view_only`
- preferred route: `report_only`

### Notes
The system should not fabricate structured weather rows from a screenshot unless a dedicated extraction capability exists and is explicitly enabled.

---

## Case 5 — PDF Report

### Input
- `sample_inputs/sample_report.pdf`

### Expected behavior
- modality: `pdf`
- category: `report` or `environment`
- usability:
  - usually `view_only`
  - possibly `transformable` only if structured tables can be reliably extracted
- preferred route:
  - `report_only` by default
  - `processing` only with explicit supported extraction path

---

## Case 6 — Unknown Text File

### Input
- `sample_inputs/sample_unknown.txt`

### Expected behavior
- category: `unknown` unless evidence supports another class
- readiness: `unsupported` or low-confidence `view_only`
- preferred route: `unsupported` or `report_only`
- must not crash

---

## Case 7 — Mixed Bundle with Ready + View-Only Inputs

### Input
- `sample_weather.csv`
- `sample_genotype.vcf`
- `sample_weather_chart.png`

### Expected behavior
- build mixed bundle
- readiness:
  - structured files may be `analysis_ready`
  - chart image remains `view_only`
- route policy:
  - direct output for usable structured data
  - preserve image in report section
- final result should represent partial, mixed semantics

---

## Case 8 — Mixed Bundle Requiring Processing

### Input
- a transformable genotype/environment bundle
- plus one unknown file

### Expected behavior
- readiness: `transformable`
- preferred route: `processing`
- planner should generate a non-empty plan
- unsupported file should not collapse the full run
- final result may be partially successful

---

## Case 9 — No Supported Structured Inputs

### Input
- only `sample_weather_chart.png`
- only `sample_report.pdf`
- only `sample_unknown.txt`

### Expected behavior
- no fake structured genome/environment outputs
- report-only or unsupported route
- valid result object returned
- warnings preserved

---

## Case 10 — Rule-Only Mode

### Input
- representative files from sample_inputs

### Expected behavior
- no LLM calls
- full inspection-readiness-routing still works
- demo and tests must pass locally

---

## Case 11 — Hybrid Mode

### Input
- ambiguous image/PDF/table cases

### Expected behavior
- optional brain assistance may be invoked
- if brain fails, the system falls back safely
- route and result remain valid
