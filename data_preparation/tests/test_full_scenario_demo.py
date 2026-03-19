"""Smoke tests for the comprehensive scenario demo."""

from __future__ import annotations

import unittest

from agents.core.sub_agents.data_preparation.examples.full_scenario_demo import run_demo


class FullScenarioDemoTest(unittest.TestCase):
    def test_run_demo_covers_expected_routes_and_statuses(self) -> None:
        summaries = run_demo(include_llm=False)

        self.assertGreaterEqual(len(summaries), 8)

        crashed = [summary["scenario"] for summary in summaries if summary["error"] is not None]
        self.assertEqual(crashed, [])

        by_name = {summary["scenario"]: summary for summary in summaries}
        self.assertIn("analysis_ready_direct_output", by_name)
        self.assertIn("content_based_detection_unknown_suffix", by_name)
        self.assertIn("processing_transformable_success", by_name)
        self.assertIn("processing_partial_success", by_name)
        self.assertIn("processing_validation_failed", by_name)
        self.assertIn("report_only_assets", by_name)
        self.assertIn("unsupported_missing_and_binary", by_name)

        final_statuses = {summary["final_status"] for summary in summaries}
        self.assertIn("success", final_statuses)
        self.assertIn("partial_success", final_statuses)
        self.assertIn("validation_failed", final_statuses)
        self.assertIn("report_only", final_statuses)
        self.assertIn("unsupported", final_statuses)

        self.assertEqual(by_name["analysis_ready_direct_output"]["route"], "direct_output")
        self.assertEqual(
            by_name["content_based_detection_unknown_suffix"]["route"],
            "direct_output",
        )
        self.assertEqual(
            by_name["processing_transformable_success"]["final_status"],
            "success",
        )
        self.assertEqual(
            by_name["processing_partial_success"]["final_status"],
            "partial_success",
        )
        self.assertEqual(
            by_name["processing_validation_failed"]["final_status"],
            "validation_failed",
        )
        self.assertEqual(by_name["report_only_assets"]["final_status"], "report_only")
        self.assertEqual(
            by_name["unsupported_missing_and_binary"]["final_status"],
            "unsupported",
        )


if __name__ == "__main__":
    unittest.main()
