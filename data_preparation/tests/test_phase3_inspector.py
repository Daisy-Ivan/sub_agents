"""Phase 3 tests for rule-based file inspection."""

from __future__ import annotations

from pathlib import Path
import sys
import tempfile
import unittest

REPO_ROOT = Path(__file__).resolve().parents[5]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from agents.core.sub_agents.data_preparation import DataPreparationSubAgent
from agents.core.sub_agents.data_preparation.inspector import InputInspector
from agents.core.sub_agents.data_preparation.schemas import PreparationRequest, RawInputFile


class InspectionContractTests(unittest.TestCase):
    """Representative inspection tests from the test contract."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.inspector = InputInspector()

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_weather_csv_detected_as_environment_table(self) -> None:
        file_path = self._write_text(
            "sample_weather.csv",
            "date,temperature,precipitation,location\n"
            "2024-06-01,28.1,5.2,field_a\n"
            "2024-06-02,29.0,0.0,field_a\n",
        )

        result = self.inspector.inspect(RawInputFile(file_path=file_path))

        self.assertEqual(result.modality, "table")
        self.assertEqual(result.detected_category, "environment")
        self.assertIn(result.usability, {"analysis_ready", "transformable"})
        self.assertIn("temperature", [column.lower() for column in result.preview_columns])
        self.assertTrue(result.evidence)

    def test_soil_csv_detected_as_environment_table(self) -> None:
        file_path = self._write_text(
            "sample_soil.csv",
            "site_id,soil_ph,organic_matter,depth_cm\n"
            "A01,6.2,3.1,20\n"
            "A02,6.5,3.4,20\n",
        )

        result = self.inspector.inspect(RawInputFile(file_path=file_path))

        self.assertEqual(result.modality, "table")
        self.assertEqual(result.detected_category, "environment")
        self.assertTrue(result.evidence)

    def test_vcf_detected_as_genotype_table(self) -> None:
        file_path = self._write_text(
            "sample_genotype.vcf",
            "##fileformat=VCFv4.2\n"
            "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\n"
            "1\t12345\trs1\tA\tG\t.\tPASS\t.\n",
        )

        result = self.inspector.inspect(RawInputFile(file_path=file_path))

        self.assertEqual(result.modality, "table")
        self.assertEqual(result.detected_category, "genotype")
        self.assertEqual(result.detected_format, "vcf")
        self.assertNotEqual(result.usability, "unsupported")
        self.assertIn("CHROM", result.preview_columns[0].upper())

    def test_weather_chart_png_detected_as_view_only_image(self) -> None:
        file_path = self._write_bytes(
            "sample_weather_chart.png",
            b"\x89PNG\r\n\x1a\n" + b"fakepngpayload",
        )

        result = self.inspector.inspect(RawInputFile(file_path=file_path))

        self.assertEqual(result.modality, "image")
        self.assertIn(result.detected_category, {"environment", "report"})
        self.assertIn(result.usability, {"view_only", "transformable"})
        self.assertTrue(result.warnings)

    def test_report_pdf_detected_as_report_view_only(self) -> None:
        file_path = self._write_bytes(
            "sample_report.pdf",
            b"%PDF-1.4\nBreeding report summary\n",
        )

        result = self.inspector.inspect(RawInputFile(file_path=file_path))

        self.assertEqual(result.modality, "pdf")
        self.assertIn(result.detected_category, {"report", "environment"})
        self.assertNotEqual(result.usability, "analysis_ready")
        self.assertTrue(result.evidence)

    def test_unknown_text_does_not_crash(self) -> None:
        file_path = self._write_text(
            "sample_unknown.txt",
            "Remember to review the attached notes before the next meeting.\n",
        )

        result = self.inspector.inspect(RawInputFile(file_path=file_path))

        self.assertEqual(result.modality, "text")
        self.assertIn(result.detected_category, {"unknown", "report", "metadata"})
        self.assertIn(result.usability, {"unsupported", "view_only", "transformable"})

    def test_content_based_detection_does_not_require_known_suffix(self) -> None:
        file_path = self._write_text(
            "weather_payload.dat",
            "date,temp_c,rainfall_mm,site\n"
            "2024-06-01,28.1,5.2,field_a\n"
            "2024-06-02,27.6,1.1,field_a\n",
        )

        result = self.inspector.inspect(
            RawInputFile(file_path=file_path, user_hint="daily weather observations")
        )

        self.assertEqual(result.modality, "table")
        self.assertEqual(result.detected_category, "environment")
        self.assertIn(result.usability, {"analysis_ready", "transformable"})

    def test_agent_inspect_files_updates_memory(self) -> None:
        weather_file = self._write_text(
            "sample_weather.csv",
            "date,temperature,precipitation,location\n"
            "2024-06-01,28.1,5.2,field_a\n",
        )
        genotype_file = self._write_text(
            "sample_genotype.vcf",
            "##fileformat=VCFv4.2\n"
            "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\n"
            "1\t12345\trs1\tA\tG\t.\tPASS\t.\n",
        )
        request = PreparationRequest(
            input_files=[
                RawInputFile(file_path=weather_file),
                RawInputFile(file_path=genotype_file),
            ],
            task_goal="Inspect raw breeding inputs",
        )

        agent = DataPreparationSubAgent()
        results = agent.inspect_files(request)
        snapshot = agent.get_memory_snapshot()

        self.assertEqual(len(results), 2)
        self.assertEqual(snapshot["current_state"], "inspected")
        self.assertEqual(snapshot["trace"][-1]["details"]["to"], "inspected")
        self.assertEqual(snapshot["inspection_results"][0]["modality"], "table")

    def _write_text(self, relative_path: str, content: str) -> Path:
        path = self.root / relative_path
        path.write_text(content, encoding="utf-8")
        return path

    def _write_bytes(self, relative_path: str, content: bytes) -> Path:
        path = self.root / relative_path
        path.write_bytes(content)
        return path
