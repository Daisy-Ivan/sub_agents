"""Shared I/O helpers for low-level execution tools."""

from __future__ import annotations

import csv
from pathlib import Path

from ..exceptions import ExecutionError
from ..schemas import SubTask


def normalize_name(value: str) -> str:
    """Normalize a header token into a stable snake_case-like name."""

    normalized = value.strip().lower().replace("-", "_").replace(" ", "_")
    while "__" in normalized:
        normalized = normalized.replace("__", "_")
    return normalized.strip("_") or "column"


def existing_paths(task: SubTask) -> list[Path]:
    """Return validated existing input paths for a task."""

    paths = [Path(path) for path in task.input_refs]
    missing = [str(path) for path in paths if not path.exists()]
    if missing:
        raise ExecutionError(f"missing task inputs: {', '.join(missing)}")
    return paths


def detect_delimiter(header_line: str) -> str | None:
    """Infer the delimiter from the first line of a text table."""

    if "\t" in header_line:
        return "\t"
    if "," in header_line:
        return ","
    if ";" in header_line:
        return ";"
    if "|" in header_line:
        return "|"
    return None


def read_rows(path: Path) -> tuple[list[str], list[list[str]]]:
    """Read a simple delimited or whitespace table into header and rows."""

    raw_text = path.read_text(encoding="utf-8").replace("\r\n", "\n").replace("\r", "\n")
    lines = [line for line in raw_text.splitlines() if line.strip()]
    if not lines:
        raise ExecutionError(f"input file is empty: {path}")

    delimiter = detect_delimiter(lines[0])
    if delimiter is not None:
        rows = list(csv.reader(lines, delimiter=delimiter))
    else:
        rows = [line.split() for line in lines]

    if not rows or not rows[0]:
        raise ExecutionError(f"could not parse structured rows from: {path}")

    header = [normalize_name(cell.lstrip("#")) for cell in rows[0]]
    body = rows[1:] if len(rows) > 1 else []
    return header, body


def write_csv(path: Path, header: list[str], rows: list[list[str]]) -> None:
    """Write a CSV file, creating parent directories when needed."""

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        writer.writerows(rows)
