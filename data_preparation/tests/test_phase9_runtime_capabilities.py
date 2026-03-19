"""Tests for Phase 9 runtime refinement, checking, and reporting."""

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
)
from agents.core.sub_agents.data_preparation.capabilities.data_checker import (
    DataCheckerCapability,
)
from agents.core.sub_agents.data_preparation.capabilities.data_refine import (
    DataRefineCapability,
    RefinementSummary,
)
from agents.core.sub_agents.data_preparation.capabilities.report_builder import (
    ReportBuilderCapability,
)


class Phase9RuntimeCapabilitiesTests(unittest.TestCase):
    def setUp(self) -> None:
        self.refiner = DataRefineCapability()
        self.checker = DataCheckerCapability()
        self.report_builder = ReportBuilderCapability()

    def test_processing_route_refines_environment_headers(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output_path = root / "weather_table_normalization.csv"
            output_path.write_text(
                "date,temp_c,rainfall_mm,site\n2024-06-01,28.1,5.2,field_a\n",
                encoding="utf-8",
            )

            summary = self.refiner.refine(
                "processing",
                {"output_paths": [str(output_path)]},
            )

            self.assertTrue(summary.performed)
            refined_path = summary.output_paths[0]
            self.assertTrue(refined_path.name.endswith("_refined.csv"))
            header = refined_path.read_text(encoding="utf-8").splitlines()[0]
            self.assertEqual(header, "date,temperature,precipitation,location")

    def test_data_checker_reports_missing_values_and_alignment_issues(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            environment_path = root / "environment.csv"
            environment_path.write_text(
                "sample_id,temperature\nsample_a,\nsample_b,23.1\n",
                encoding="utf-8",
            )
            bundle = NormalizedInputBundle()
            readiness = ReadinessDecision(
                bundle_status="transformable",
                rationale="environment table needs refinement",
            )

            report = self.checker.validate(
                bundle=bundle,
                readiness_decision=readiness,
                route_name="processing",
                refinement_summary={"output_paths": [str(environment_path)]},
            )

            self.assertTrue(report.passed)
            messages = [issue.message for issue in report.issues]
            self.assertTrue(any("blank value" in message for message in messages))
            self.assertTrue(any("temporal alignment" in message for message in messages))
            self.assertTrue(any("spatial alignment" in message for message in messages))

    def test_data_checker_detects_sample_consistency_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            genotype_path = root / "genotype.csv"
            environment_path = root / "environment.csv"
            genotype_path.write_text(
                "sample_id,variant_id,chromosome\nA,rs1,1\nB,rs2,1\n",
                encoding="utf-8",
            )
            environment_path.write_text(
                "sample_id,date,location\nX,2024-06-01,field_a\nY,2024-06-02,field_a\n",
                encoding="utf-8",
            )

            report = self.checker.validate(
                bundle=NormalizedInputBundle(),
                readiness_decision=ReadinessDecision(
                    bundle_status="transformable",
                    rationale="processing outputs ready for checking",
                ),
                route_name="processing",
                refinement_summary={
                    "output_paths": [str(genotype_path), str(environment_path)],
                },
            )

            self.assertFalse(report.passed)
            self.assertTrue(
                any(
                    "do not overlap" in issue.message
                    for issue in report.issues
                    if issue.level == "error"
                )
            )

    def test_direct_output_validation_passes_for_ready_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            weather_path = root / "weather.csv"
            vcf_path = root / "genotypes.vcf"
            weather_path.write_text(
                "date,temperature,precipitation,location\n2024-06-01,28.1,5.2,field_a\n",
                encoding="utf-8",
            )
            vcf_path.write_text(
                "##fileformat=VCFv4.2\n"
                "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\tsample_a\n",
                encoding="utf-8",
            )
            bundle = NormalizedInputBundle(
                genotype_files=[
                    FileInspectionResult(
                        file_path=vcf_path,
                        modality="text",
                        detected_category="genotype",
                        detected_format="vcf",
                        confidence=0.95,
                        usability="analysis_ready",
                    )
                ],
                environment_files=[
                    FileInspectionResult(
                        file_path=weather_path,
                        modality="table",
                        detected_category="environment",
                        detected_format="csv",
                        confidence=0.98,
                        usability="analysis_ready",
                    )
                ],
            )

            report = self.checker.validate(
                bundle=bundle,
                readiness_decision=ReadinessDecision(
                    bundle_status="analysis_ready",
                    rationale="inputs are directly usable",
                ),
                route_name="direct_output",
            )

            self.assertTrue(report.passed)
            self.assertEqual(report.summary, "Validation passed with no issues.")

    def test_report_only_route_report_preserves_view_only_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            pdf_path = root / "field_notes.pdf"
            png_path = root / "trait_plot.png"
            pdf_path.write_text("placeholder pdf", encoding="utf-8")
            png_path.write_text("placeholder png", encoding="utf-8")

            bundle = NormalizedInputBundle(
                report_files=[
                    FileInspectionResult(
                        file_path=pdf_path,
                        modality="pdf",
                        detected_category="report",
                        detected_format="pdf",
                        confidence=0.9,
                        usability="view_only",
                    ),
                    FileInspectionResult(
                        file_path=png_path,
                        modality="image",
                        detected_category="report",
                        detected_format="png",
                        confidence=0.88,
                        usability="view_only",
                    ),
                ]
            )
            readiness = ReadinessDecision(
                bundle_status="view_only",
                rationale="view-only artifacts were provided",
            )
            validation_report = self.checker.validate(
                bundle=bundle,
                readiness_decision=readiness,
                route_name="report_only",
            )

            route_report = self.report_builder.build(
                bundle=bundle,
                readiness_decision=readiness,
                route_name="report_only",
                validation_report=validation_report,
            )

            self.assertTrue(validation_report.passed)
            self.assertEqual(route_report.structured_output_paths, [])
            self.assertIn("did not fabricate structured numerical outputs", route_report.summary)

    def test_unsupported_route_validation_returns_valid_report(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            unknown_path = root / "mystery.bin"
            unknown_path.write_bytes(b"abc123")
            bundle = NormalizedInputBundle(
                unknown_files=[
                    FileInspectionResult(
                        file_path=unknown_path,
                        modality="unknown",
                        detected_category="unknown",
                        detected_format="bin",
                        confidence=0.1,
                        usability="unsupported",
                    )
                ]
            )

            report = self.checker.validate(
                bundle=bundle,
                readiness_decision=ReadinessDecision(
                    bundle_status="unsupported",
                    rationale="unsupported input encountered",
                    warnings=["unsupported binary input"],
                ),
                route_name="unsupported",
            )

            self.assertFalse(report.passed)
            self.assertTrue(any(issue.level == "error" for issue in report.issues))

    def test_agent_phase9_methods_store_validation_and_report_in_memory(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            weather_file = root / "sample_weather.csv"
            genotype_file = root / "sample_plink.bim"
            weather_file.write_text(
                "date,temp_c,rainfall_mm,site\n2024-06-01,28.1,5.2,field_a\n",
                encoding="utf-8",
            )
            genotype_file.write_text(
                "1 rs1 0 12345 A G\n1 rs2 0 67890 C T\n",
                encoding="utf-8",
            )

            request = PreparationRequest(
                input_files=[
                    RawInputFile(file_path=weather_file),
                    RawInputFile(file_path=genotype_file),
                ],
                task_goal="Prepare breeding data",
            )

            agent = DataPreparationSubAgent()
            inspection_results = agent.inspect_files(request)
            bundle = agent.build_bundle(inspection_results)
            readiness = agent.assess_readiness(bundle)
            route = agent.route(bundle, readiness)
            plan = agent.build_processing_plan(bundle, readiness, route)
            execution_summary = agent.execute_processing_plan(plan, route)
            refinement_summary = agent.refine_outputs(route, execution_summary)
            validation_report = agent.validate_route_outputs(
                bundle,
                readiness,
                route,
                execution_summary,
                refinement_summary,
            )
            route_report = agent.build_route_report(
                bundle,
                readiness,
                route,
                validation_report,
                execution_summary,
                refinement_summary,
            )

            snapshot = agent.get_memory_snapshot()
            self.assertEqual(snapshot["current_state"], "validating")
            self.assertIsNotNone(snapshot["validation_report"])
            self.assertIn("refinement_summary", snapshot["metadata"])
            self.assertIn("route_report", snapshot["metadata"])
            self.assertEqual(snapshot["metadata"]["route_report"]["route"], route)
            self.assertEqual(route_report.route, route)


if __name__ == "__main__":
    unittest.main()
