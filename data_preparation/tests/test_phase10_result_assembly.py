"""Tests for Phase 10 unified result assembly."""

from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from agents.core.sub_agents.data_preparation import (
    DataPreparationSubAgent,
    FileInspectionResult,
    NormalizedInputBundle,
    PreparationRequest,
    RawInputFile,
    ReadinessDecision,
    ValidationIssue,
    ValidationReport,
)
from agents.core.sub_agents.data_preparation.result_assembler import ResultAssembler


class Phase10ResultAssemblyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.assembler = ResultAssembler()

    def test_direct_output_result_contains_structured_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            vcf_path = root / "genotypes.vcf"
            weather_path = root / "weather.csv"
            vcf_path.write_text(
                "##fileformat=VCFv4.2\n"
                "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\tsample_a\n",
                encoding="utf-8",
            )
            weather_path.write_text(
                "date,temperature,precipitation,location\n2024-06-01,28.1,5.2,field_a\n",
                encoding="utf-8",
            )

            genotype_result = FileInspectionResult(
                file_path=vcf_path,
                modality="text",
                detected_category="genotype",
                detected_format="vcf",
                confidence=0.98,
                usability="analysis_ready",
            )
            environment_result = FileInspectionResult(
                file_path=weather_path,
                modality="table",
                detected_category="environment",
                detected_format="csv",
                confidence=0.99,
                usability="analysis_ready",
            )
            bundle = NormalizedInputBundle(
                genotype_files=[genotype_result],
                environment_files=[environment_result],
            )
            readiness = ReadinessDecision(
                bundle_status="analysis_ready",
                rationale="inputs are already analysis ready",
            )
            validation = ValidationReport(
                passed=True,
                summary="Validation passed with no issues.",
            )

            result = self.assembler.assemble(
                inspection_results=[genotype_result, environment_result],
                normalized_bundle=bundle,
                readiness_decision=readiness,
                validation_report=validation,
                route_name="direct_output",
                execution_trace=[{"event": "validation_completed", "details": {"route": "direct_output"}}],
            )

            self.assertEqual(result.final_status, "success")
            self.assertEqual(result.genome_output.output_paths, [vcf_path])
            self.assertEqual(result.genome_output.standardized_format, "vcf")
            self.assertTrue(result.genome_output.sample_axis_aligned)
            self.assertEqual(result.environment_output.output_paths, [weather_path])
            self.assertEqual(result.environment_output.standardized_format, "csv")
            self.assertTrue(result.environment_output.temporal_aligned)

    def test_processing_result_prefers_refined_outputs_and_merges_warnings(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            raw_genotype_path = root / "trial_plink_converted.csv"
            raw_environment_path = root / "weather_table_normalization.csv"
            refined_genotype_path = root / "trial_plink_converted_refined.csv"
            refined_environment_path = root / "weather_table_normalization_refined.csv"
            for path, content in (
                (
                    raw_genotype_path,
                    "sample_id,variant_id,chromosome\nsample_a,rs1,1\n",
                ),
                (
                    raw_environment_path,
                    "date,temp_c,site\n2024-06-01,28.1,field_a\n",
                ),
                (
                    refined_genotype_path,
                    "sample_id,variant_id,chromosome\nsample_a,rs1,1\n",
                ),
                (
                    refined_environment_path,
                    "date,temperature,location\n2024-06-01,28.1,field_a\n",
                ),
            ):
                path.write_text(content, encoding="utf-8")

            result = self.assembler.assemble(
                inspection_results=[],
                normalized_bundle=NormalizedInputBundle(),
                readiness_decision=ReadinessDecision(
                    bundle_status="transformable",
                    rationale="inputs need conservative processing",
                    warnings=["bundle requires conservative normalization"],
                ),
                validation_report=ValidationReport(
                    passed=True,
                    summary="Validation passed with no issues.",
                ),
                route_name="processing",
                execution_summary={
                    "output_paths": [str(raw_genotype_path), str(raw_environment_path)],
                    "warnings": ["execution emitted one non-blocking warning"],
                    "partial_success": False,
                },
                refinement_summary={
                    "output_paths": [str(refined_genotype_path), str(refined_environment_path)],
                    "warnings": ["refinement standardized environment headers"],
                },
                route_report={
                    "summary": "Processing route produced refined structured outputs.",
                    "warnings": ["route summary warning"],
                },
            )

            self.assertEqual(result.final_status, "success")
            self.assertEqual(result.genome_output.output_paths, [refined_genotype_path])
            self.assertEqual(result.environment_output.output_paths, [refined_environment_path])
            issue_messages = [issue.message for issue in result.validation_report.issues]
            self.assertIn("bundle requires conservative normalization", issue_messages)
            self.assertIn("execution emitted one non-blocking warning", issue_messages)
            self.assertIn("refinement standardized environment headers", issue_messages)
            self.assertIn("route summary warning", issue_messages)

    def test_report_only_result_preserves_summary_without_structured_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            report_path = root / "field_notes.pdf"
            report_path.write_text("placeholder report", encoding="utf-8")

            inspection = FileInspectionResult(
                file_path=report_path,
                modality="pdf",
                detected_category="report",
                detected_format="pdf",
                confidence=0.9,
                usability="view_only",
            )
            result = self.assembler.assemble(
                inspection_results=[inspection],
                normalized_bundle=NormalizedInputBundle(report_files=[inspection]),
                readiness_decision=ReadinessDecision(
                    bundle_status="view_only",
                    rationale="view-only artifacts were provided",
                ),
                validation_report=ValidationReport(
                    passed=True,
                    issues=[
                        ValidationIssue(
                            level="info",
                            message="preserved 1 view-only artifact(s) without conversion",
                        )
                    ],
                    summary="Validation passed with no issues.",
                ),
                route_name="report_only",
            )

            self.assertEqual(result.final_status, "report_only")
            self.assertIsNone(result.genome_output)
            self.assertIsNone(result.environment_output)
            self.assertEqual(len(result.inspection_results), 1)
            self.assertEqual(result.inspection_results[0].file_path, report_path)

    def test_unsupported_result_is_valid_and_carries_warnings(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            unknown_path = root / "mystery.bin"
            unknown_path.write_bytes(b"abc123")

            inspection = FileInspectionResult(
                file_path=unknown_path,
                modality="unknown",
                detected_category="unknown",
                detected_format="bin",
                confidence=0.1,
                usability="unsupported",
            )
            result = self.assembler.assemble(
                inspection_results=[inspection],
                normalized_bundle=NormalizedInputBundle(unknown_files=[inspection]),
                readiness_decision=ReadinessDecision(
                    bundle_status="unsupported",
                    rationale="unsupported binary input was provided",
                    warnings=["unsupported binary input"],
                ),
                validation_report=ValidationReport(
                    passed=False,
                    issues=[
                        ValidationIssue(
                            level="error",
                            message="unsupported route contains 1 unsupported artifact(s)",
                        )
                    ],
                    summary="Validation failed with 1 error(s) and 0 warning(s).",
                ),
                route_name="unsupported",
            )

            self.assertEqual(result.final_status, "unsupported")
            self.assertIsNone(result.genome_output)
            self.assertIsNone(result.environment_output)
            issue_messages = [issue.message for issue in result.validation_report.issues]
            self.assertIn("unsupported binary input", issue_messages)

    def test_agent_assemble_result_marks_workflow_completed(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            weather_path = root / "weather.csv"
            genotype_path = root / "genotypes.vcf"
            weather_path.write_text(
                "date,temperature,precipitation,location\n2024-06-01,28.1,5.2,field_a\n",
                encoding="utf-8",
            )
            genotype_path.write_text(
                "##fileformat=VCFv4.2\n"
                "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\tsample_a\n",
                encoding="utf-8",
            )

            request = PreparationRequest(
                input_files=[
                    RawInputFile(file_path=weather_path),
                    RawInputFile(file_path=genotype_path),
                ],
                task_goal="Prepare data for downstream analysis",
            )

            agent = DataPreparationSubAgent()
            inspection_results = agent.inspect_files(request)
            bundle = agent.build_bundle(inspection_results)
            readiness = agent.assess_readiness(bundle)
            route = agent.route(bundle, readiness)
            validation_report = agent.validate_route_outputs(bundle, readiness, route)
            route_report = agent.build_route_report(
                bundle,
                readiness,
                route,
                validation_report,
            )
            result = agent.assemble_result(
                bundle=bundle,
                readiness_decision=readiness,
                route_name=route,
                validation_report=validation_report,
                inspection_results=inspection_results,
                route_report=route_report,
            )

            snapshot = agent.get_memory_snapshot()
            self.assertEqual(snapshot["current_state"], "completed")
            self.assertEqual(result.final_status, "success")
            self.assertIn("preparation_result", snapshot["metadata"])
            self.assertEqual(
                snapshot["metadata"]["preparation_result"]["final_status"],
                "success",
            )
            self.assertEqual(result.execution_trace[-1]["event"], "result_assembled")

    def test_agent_run_executes_end_to_end_via_single_entrypoint(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            weather_path = root / "weather.csv"
            genotype_path = root / "genotypes.vcf"
            weather_path.write_text(
                "date,temperature,precipitation,location\n2024-06-01,28.1,5.2,field_a\n",
                encoding="utf-8",
            )
            genotype_path.write_text(
                "##fileformat=VCFv4.2\n"
                "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\tsample_a\n"
                "1\t12345\trs1\tA\tG\t.\tPASS\t.\tGT\t0/1\n",
                encoding="utf-8",
            )

            request = PreparationRequest(
                input_files=[
                    RawInputFile(file_path=weather_path),
                    RawInputFile(file_path=genotype_path),
                ],
                task_goal="Validate already-prepared breeding inputs",
            )

            agent = DataPreparationSubAgent()
            result = agent.run(request)

            snapshot = agent.get_memory_snapshot()
            self.assertEqual(snapshot["current_state"], "completed")
            self.assertEqual(snapshot["route"], "direct_output")
            self.assertEqual(result.final_status, "success")
            self.assertTrue(result.validation_report.passed)
            self.assertIn("route_report", snapshot["metadata"])
            self.assertIn("preparation_result", snapshot["metadata"])


if __name__ == "__main__":
    unittest.main()
