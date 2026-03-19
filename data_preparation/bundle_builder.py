"""Normalized bundle construction from inspection results."""

from __future__ import annotations

from collections.abc import Iterable

from .exceptions import BundleBuildError
from .schemas import FileInspectionResult, NormalizedInputBundle


class BundleBuilder:
    """Group inspection results into a stable normalized bundle."""

    _CATEGORY_TO_FIELD = {
        "genotype": "genotype_files",
        "environment": "environment_files",
        "metadata": "metadata_files",
        "report": "report_files",
        "unknown": "unknown_files",
    }

    def build(
        self,
        inspection_results: list[FileInspectionResult],
    ) -> NormalizedInputBundle:
        """Build a normalized bundle from file-level inspection results."""

        try:
            normalized_results = self._normalize_results(inspection_results)
        except Exception as exc:
            if isinstance(exc, BundleBuildError):
                raise
            raise BundleBuildError(f"failed to normalize inspection results: {exc}") from exc

        grouped: dict[str, list[FileInspectionResult]] = {
            "genotype_files": [],
            "environment_files": [],
            "metadata_files": [],
            "report_files": [],
            "unknown_files": [],
        }

        for result in normalized_results:
            target_field = self._CATEGORY_TO_FIELD.get(
                result.detected_category,
                "unknown_files",
            )
            grouped[target_field].append(result)

        return NormalizedInputBundle(**grouped)

    def _normalize_results(
        self,
        inspection_results: Iterable[FileInspectionResult],
    ) -> list[FileInspectionResult]:
        if inspection_results is None:
            raise BundleBuildError("inspection_results must not be None")

        normalized_results: list[FileInspectionResult] = []
        for index, item in enumerate(inspection_results):
            try:
                normalized_results.append(FileInspectionResult.model_validate(item))
            except Exception as exc:
                raise BundleBuildError(
                    f"inspection_results[{index}] is not a valid FileInspectionResult: {exc}"
                ) from exc
        return normalized_results
