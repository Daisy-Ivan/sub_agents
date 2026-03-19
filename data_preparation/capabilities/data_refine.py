"""Conservative runtime refinement for processing outputs."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..tools._io_helpers import normalize_name, read_rows, write_csv


_HEADER_SYNONYMS = {
    "sample": "sample_id",
    "sampleid": "sample_id",
    "sample_identifier": "sample_id",
    "accession": "sample_id",
    "accession_id": "sample_id",
    "line": "sample_id",
    "line_id": "sample_id",
    "genotype_id": "sample_id",
    "variant": "variant_id",
    "snp": "variant_id",
    "snp_id": "variant_id",
    "temp": "temperature",
    "temp_c": "temperature",
    "temperature_c": "temperature",
    "air_temperature": "temperature",
    "rainfall": "precipitation",
    "rainfall_mm": "precipitation",
    "rain_mm": "precipitation",
    "precipitation_mm": "precipitation",
    "site": "location",
    "field": "location",
    "field_id": "location",
    "plot": "location",
    "station": "location",
    "lat": "latitude",
    "lon": "longitude",
    "lng": "longitude",
}


@dataclass(slots=True)
class RefinementSummary:
    """Structured summary of conservative output refinement."""

    route: str
    performed: bool
    output_paths: list[Path] = field(default_factory=list)
    created_paths: list[Path] = field(default_factory=list)
    actions: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable summary payload."""

        return {
            "route": self.route,
            "performed": self.performed,
            "output_paths": [str(path) for path in self.output_paths],
            "created_paths": [str(path) for path in self.created_paths],
            "actions": list(self.actions),
            "warnings": list(self.warnings),
            "metadata": dict(self.metadata),
        }


class DataRefineCapability:
    """Refine processing outputs conservatively without fabricating new data."""

    def refine(
        self,
        route_name: str,
        execution_summary: Any | None = None,
    ) -> RefinementSummary:
        """Normalize headers and cell whitespace for processing outputs."""

        candidate_paths = self._extract_output_paths(execution_summary)
        if route_name != "processing" or not candidate_paths:
            return RefinementSummary(
                route=route_name,
                performed=False,
                output_paths=candidate_paths,
            )

        final_paths: list[Path] = []
        created_paths: list[Path] = []
        actions: list[str] = []
        warnings: list[str] = []

        for path in candidate_paths:
            if path.suffix.lower() != ".csv":
                final_paths.append(path)
                continue

            try:
                header, rows = read_rows(path)
            except Exception as exc:  # pragma: no cover - defensive path
                warnings.append(f"skipped refinement for {path.name}: {exc}")
                final_paths.append(path)
                continue

            normalized_header = self._normalize_header(header)
            normalized_rows = self._normalize_rows(rows, len(normalized_header))
            header_changed = normalized_header != header
            rows_changed = normalized_rows != rows

            if not header_changed and not rows_changed:
                final_paths.append(path)
                continue

            output_path = path.with_name(f"{path.stem}_refined.csv")
            write_csv(output_path, normalized_header, normalized_rows)
            final_paths.append(output_path)
            created_paths.append(output_path)

            if header_changed:
                actions.append(f"standardized columns in {path.name}")
            if rows_changed:
                actions.append(f"trimmed cell values in {path.name}")

        return RefinementSummary(
            route=route_name,
            performed=bool(created_paths),
            output_paths=final_paths,
            created_paths=created_paths,
            actions=actions,
            warnings=self._dedupe(warnings),
            metadata={"input_output_count": len(candidate_paths)},
        )

    def _extract_output_paths(self, execution_summary: Any | None) -> list[Path]:
        if execution_summary is None:
            return []

        output_paths = getattr(execution_summary, "output_paths", None)
        if output_paths is None and isinstance(execution_summary, dict):
            output_paths = execution_summary.get("output_paths", [])

        resolved_paths: list[Path] = []
        for raw_path in output_paths or []:
            resolved_paths.append(raw_path if isinstance(raw_path, Path) else Path(str(raw_path)))
        return resolved_paths

    def _normalize_header(self, header: list[str]) -> list[str]:
        normalized = [
            _HEADER_SYNONYMS.get(normalize_name(column), normalize_name(column))
            for column in header
        ]
        return self._dedupe_columns(normalized)

    def _normalize_rows(self, rows: list[list[str]], width: int) -> list[list[str]]:
        normalized_rows: list[list[str]] = []
        for row in rows:
            trimmed_row = [cell.strip() for cell in row[:width]]
            if len(trimmed_row) < width:
                trimmed_row.extend([""] * (width - len(trimmed_row)))
            normalized_rows.append(trimmed_row)
        return normalized_rows

    def _dedupe_columns(self, columns: list[str]) -> list[str]:
        deduped: list[str] = []
        seen: dict[str, int] = {}
        for column in columns:
            count = seen.get(column, 0) + 1
            seen[column] = count
            deduped.append(column if count == 1 else f"{column}_{count}")
        return deduped

    def _dedupe(self, values: list[str]) -> list[str]:
        deduped: list[str] = []
        seen: set[str] = set()
        for value in values:
            normalized = value.strip()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            deduped.append(normalized)
        return deduped
