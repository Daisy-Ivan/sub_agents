"""Scaffold smoke tests for Phase 1."""

from __future__ import annotations

import importlib
from pathlib import Path
import sys
import unittest

REPO_ROOT = Path(__file__).resolve().parents[5]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


MODULE_NAMES = [
    "agents.core.sub_agents.data_preparation",
    "agents.core.sub_agents.data_preparation.agent",
    "agents.core.sub_agents.data_preparation.config",
    "agents.core.sub_agents.data_preparation.schemas",
    "agents.core.sub_agents.data_preparation.state",
    "agents.core.sub_agents.data_preparation.memory",
    "agents.core.sub_agents.data_preparation.exceptions",
    "agents.core.sub_agents.data_preparation.inspector",
    "agents.core.sub_agents.data_preparation.bundle_builder",
    "agents.core.sub_agents.data_preparation.readiness_assessor",
    "agents.core.sub_agents.data_preparation.router",
    "agents.core.sub_agents.data_preparation.planner",
    "agents.core.sub_agents.data_preparation.executor",
    "agents.core.sub_agents.data_preparation.result_assembler",
    "agents.core.sub_agents.data_preparation.brain",
    "agents.core.sub_agents.data_preparation.llm_client",
    "agents.core.sub_agents.data_preparation.capabilities.file_inspection",
    "agents.core.sub_agents.data_preparation.capabilities.data_refine",
    "agents.core.sub_agents.data_preparation.capabilities.data_checker",
    "agents.core.sub_agents.data_preparation.capabilities.report_builder",
    "agents.core.sub_agents.data_preparation.tools.base",
    "agents.core.sub_agents.data_preparation.tools.registry",
]


class ScaffoldSmokeTests(unittest.TestCase):
    """Phase 1 acceptance checks for the scaffold package."""

    def test_scaffold_modules_are_importable(self) -> None:
        """Every scaffold module should import without side effects."""

        for module_name in MODULE_NAMES:
            module = importlib.import_module(module_name)
            self.assertIsNotNone(module)

    def test_public_package_exports_expected_symbols(self) -> None:
        """The package root should expose the main public scaffold symbols."""

        package = importlib.import_module("agents.core.sub_agents.data_preparation")
        self.assertTrue(hasattr(package, "DataPreparationSubAgent"))
        self.assertTrue(hasattr(package, "PreparationRequest"))
        self.assertTrue(hasattr(package, "PreparationResult"))
