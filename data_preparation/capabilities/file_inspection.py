"""Rule-based file inspection capability."""

from __future__ import annotations

from dataclasses import dataclass, field
import logging
import mimetypes
from pathlib import Path

from ..config import DataPreparationConfig
from ..exceptions import InspectionError
from ..schemas import FileInspectionResult, RawInputFile

LOGGER = logging.getLogger(__name__)

_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tif", ".tiff", ".webp"}
_ARCHIVE_SUFFIXES = {".zip", ".gz", ".tgz", ".tar", ".bz2", ".xz"}
_GENOTYPE_SUFFIXES = {
    ".vcf",
    ".bcf",
    ".bed",
    ".bim",
    ".fam",
    ".ped",
    ".map",
    ".geno",
    ".hmp",
}
_ENVIRONMENT_KEYWORDS = {
    "weather",
    "soil",
    "temperature",
    "temp",
    "humidity",
    "rain",
    "rainfall",
    "precipitation",
    "climate",
    "site",
    "location",
    "latitude",
    "longitude",
    "elevation",
    "wind",
    "trial",
}
_GENOTYPE_KEYWORDS = {
    "genotype",
    "vcf",
    "variant",
    "marker",
    "snp",
    "chrom",
    "chromosome",
    "ref",
    "alt",
    "allele",
    "plink",
}
_METADATA_KEYWORDS = {
    "metadata",
    "sample_id",
    "sample",
    "accession",
    "pedigree",
    "cultivar",
    "study",
    "experiment",
    "batch",
    "panel",
}
_REPORT_KEYWORDS = {
    "report",
    "summary",
    "analysis",
    "figure",
    "chart",
    "plot",
    "document",
    "screenshot",
    "slide",
}
_PDF_SIGNATURE = b"%PDF"
_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
_JPEG_SIGNATURES = (b"\xff\xd8\xff",)
_GIF_SIGNATURES = (b"GIF87a", b"GIF89a")
_ZIP_SIGNATURE = b"PK\x03\x04"
_GZIP_SIGNATURE = b"\x1f\x8b"
_BINARY_TEXT_SAMPLE_BYTES = 4096
_TEXT_PREVIEW_BYTES = 16384


@dataclass(slots=True)
class TableProbe:
    """Internal signal bundle for table detection."""

    is_table: bool = False
    format_name: str = "unknown"
    preview_columns: list[str] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)


class FileInspectionCapability:
    """Inspect a single file using deterministic local heuristics."""

    def __init__(self, config: DataPreparationConfig | None = None) -> None:
        self.config = config or DataPreparationConfig()

    def inspect(self, raw_input: RawInputFile) -> FileInspectionResult:
        """Inspect a raw input file and return a structured result."""

        path = raw_input.file_path
        evidence: list[str] = []
        warnings: list[str] = []

        if not path.exists():
            return self._build_result(
                file_path=path,
                modality="unknown",
                detected_category="unknown",
                detected_format=self._suffix_label(path),
                usability="unsupported",
                confidence=0.05,
                evidence=["input path does not exist on disk"],
                warnings=["inspection skipped because the file is missing"],
            )

        try:
            preview_bytes = self._read_preview_bytes(path)
        except OSError as exc:
            LOGGER.warning("Failed to read %s during inspection: %s", path, exc)
            return self._build_result(
                file_path=path,
                modality="unknown",
                detected_category="unknown",
                detected_format=self._suffix_label(path),
                usability="unsupported",
                confidence=0.05,
                evidence=["file metadata was found but content could not be read"],
                warnings=[f"inspection read error: {exc}"],
            )
        except Exception as exc:  # pragma: no cover - defensive guard.
            raise InspectionError(f"unexpected inspection failure for {path}: {exc}") from exc

        if not preview_bytes:
            return self._build_result(
                file_path=path,
                modality="unknown",
                detected_category="unknown",
                detected_format=self._suffix_label(path),
                usability="unsupported",
                confidence=0.05,
                evidence=["file is empty"],
                warnings=["empty files cannot be classified reliably"],
            )

        mime_type, _encoding = mimetypes.guess_type(path.name)
        if mime_type:
            evidence.append(f"MIME hint suggests {mime_type}")

        if self._is_pdf(path, preview_bytes, mime_type):
            evidence.append("PDF signature or suffix detected")
            category = self._detect_category(
                raw_input=raw_input,
                modality="pdf",
                detected_format="pdf",
                preview_columns=[],
                text_preview=self._read_text_preview(preview_bytes),
            )
            usability = "view_only"
            warnings.append("PDF inputs are treated as report-style assets unless later evidence proves otherwise")
            return self._finalize_result(
                file_path=path,
                modality="pdf",
                detected_category=category,
                detected_format="pdf",
                usability=usability,
                evidence=evidence + ["non-tabular PDF input requires report-oriented handling"],
                warnings=warnings,
                preview_columns=[],
            )

        if self._is_image(path, preview_bytes, mime_type):
            image_format = self._detect_image_format(path, preview_bytes)
            evidence.append(f"image signature or suffix detected ({image_format})")
            category = self._detect_category(
                raw_input=raw_input,
                modality="image",
                detected_format=image_format,
                preview_columns=[],
                text_preview=None,
            )
            warnings.append("image inputs are treated conservatively and kept view-only")
            return self._finalize_result(
                file_path=path,
                modality="image",
                detected_category=category,
                detected_format=image_format,
                usability="view_only",
                evidence=evidence + ["visual asset detected instead of structured rows"],
                warnings=warnings,
                preview_columns=[],
            )

        if self._is_archive(path, preview_bytes, mime_type):
            archive_format = self._detect_archive_format(path, preview_bytes)
            evidence.append(f"archive signature or suffix detected ({archive_format})")
            category = self._detect_category(
                raw_input=raw_input,
                modality="archive",
                detected_format=archive_format,
                preview_columns=[],
                text_preview=None,
            )
            usability = "transformable" if category != "unknown" else "unsupported"
            if usability == "transformable":
                warnings.append("archive contents need expansion before detailed inspection")
            else:
                warnings.append("archive could not be mapped to a supported semantic category")
            return self._finalize_result(
                file_path=path,
                modality="archive",
                detected_category=category,
                detected_format=archive_format,
                usability=usability,
                evidence=evidence,
                warnings=warnings,
                preview_columns=[],
            )

        text_preview = self._read_text_preview(preview_bytes)
        table_probe = self._probe_table(path, text_preview)
        modality = "table" if table_probe.is_table else "text" if text_preview else "unknown"
        detected_format = table_probe.format_name if table_probe.is_table else self._detect_text_format(path)
        preview_columns = table_probe.preview_columns
        evidence.extend(table_probe.evidence)

        if modality == "text":
            evidence.append("textual content preview was decoded successfully")
        if modality == "unknown":
            warnings.append("file did not look like a supported structured, textual, image, or PDF input")

        category = self._detect_category(
            raw_input=raw_input,
            modality=modality,
            detected_format=detected_format,
            preview_columns=preview_columns,
            text_preview=text_preview,
        )
        usability, usability_evidence, usability_warnings = self._determine_usability(
            path=path,
            modality=modality,
            detected_category=category,
            detected_format=detected_format,
            preview_columns=preview_columns,
        )
        evidence.extend(usability_evidence)
        warnings.extend(usability_warnings)

        return self._finalize_result(
            file_path=path,
            modality=modality,
            detected_category=category,
            detected_format=detected_format,
            usability=usability,
            evidence=evidence,
            warnings=warnings,
            preview_columns=preview_columns,
        )

    def _read_preview_bytes(self, path: Path) -> bytes:
        with path.open("rb") as handle:
            return handle.read(_TEXT_PREVIEW_BYTES)

    def _read_text_preview(self, preview_bytes: bytes) -> str | None:
        if not self._looks_textual(preview_bytes):
            return None

        try:
            text = preview_bytes.decode("utf-8")
        except UnicodeDecodeError:
            try:
                text = preview_bytes.decode("utf-8-sig")
            except UnicodeDecodeError:
                text = preview_bytes.decode("latin-1")

        return text.replace("\r\n", "\n").replace("\r", "\n")

    def _probe_table(self, path: Path, text_preview: str | None) -> TableProbe:
        if not text_preview:
            return TableProbe()

        lines = [line.strip() for line in text_preview.splitlines() if line.strip()]
        if not lines:
            return TableProbe()

        if any(line.startswith("##fileformat=VCF") for line in lines[:5]):
            header_line = next(
                (line for line in lines if line.startswith("#CHROM")),
                "#CHROM\tPOS\tID\tREF\tALT",
            )
            return TableProbe(
                is_table=True,
                format_name="vcf",
                preview_columns=[item.lstrip("#") for item in header_line.split("\t")[:12]],
                evidence=["VCF metadata header detected", "variant table header detected"],
            )

        delimited_probe = self._probe_delimited_table(lines, path)
        if delimited_probe.is_table:
            return delimited_probe

        whitespace_probe = self._probe_whitespace_table(lines, path)
        if whitespace_probe.is_table:
            return whitespace_probe

        return TableProbe()

    def _probe_delimited_table(self, lines: list[str], path: Path) -> TableProbe:
        best_probe = TableProbe()
        best_score = 0
        format_by_delimiter = {
            ",": "csv",
            "\t": "tsv",
            ";": "semicolon_table",
            "|": "pipe_table",
        }

        for delimiter, format_name in format_by_delimiter.items():
            candidate_rows = [line.split(delimiter) for line in lines[:6] if delimiter in line]
            if len(candidate_rows) < 2:
                continue

            widths = {len(row) for row in candidate_rows}
            width = max(widths)
            if len(widths) != 1 or width < 2:
                continue

            header = self._normalize_header(candidate_rows[0])
            preview_columns = header if self._looks_like_header(header) else []
            evidence = [
                f"consistent {format_name} delimiter pattern detected",
                f"{len(candidate_rows)} preview rows share {width} columns",
            ]
            score = len(candidate_rows) * width
            if path.suffix.lower() in {".csv", ".tsv", ".tab"}:
                score += 2
                evidence.append(f"suffix {path.suffix.lower()} matches the parsed table shape")
            if score > best_score:
                best_score = score
                best_probe = TableProbe(
                    is_table=True,
                    format_name=self._refine_table_format(path, delimiter, format_name),
                    preview_columns=preview_columns,
                    evidence=evidence,
                )

        return best_probe

    def _probe_whitespace_table(self, lines: list[str], path: Path) -> TableProbe:
        candidate_rows = [line.split() for line in lines[:6] if len(line.split()) >= 3]
        if len(candidate_rows) < 2:
            return TableProbe()

        widths = {len(row) for row in candidate_rows}
        if len(widths) != 1:
            return TableProbe()

        preview_columns = []
        header = self._normalize_header(candidate_rows[0])
        if self._looks_like_header(header):
            preview_columns = header

        format_name = self._suffix_label(path)
        if format_name == "unknown":
            format_name = "whitespace_table"

        return TableProbe(
            is_table=True,
            format_name=format_name,
            preview_columns=preview_columns,
            evidence=[
                "multiple preview rows share a consistent whitespace-separated shape",
                f"suffix {path.suffix.lower() or '<none>'} does not block structured table detection",
            ],
        )

    def _detect_category(
        self,
        *,
        raw_input: RawInputFile,
        modality: str,
        detected_format: str,
        preview_columns: list[str],
        text_preview: str | None,
    ) -> str:
        suffix = raw_input.file_path.suffix.lower()
        if detected_format == "vcf" or suffix in _GENOTYPE_SUFFIXES:
            return "genotype"

        signal_text = " ".join(
            part
            for part in [
                raw_input.file_path.stem.replace("_", " ").replace("-", " "),
                raw_input.user_hint or "",
                " ".join(preview_columns),
                (text_preview or "")[:1000],
            ]
            if part
        ).lower()

        scores = {
            "genotype": self._keyword_score(signal_text, _GENOTYPE_KEYWORDS),
            "environment": self._keyword_score(signal_text, _ENVIRONMENT_KEYWORDS),
            "metadata": self._keyword_score(signal_text, _METADATA_KEYWORDS),
            "report": self._keyword_score(signal_text, _REPORT_KEYWORDS),
        }

        if modality == "image":
            if scores["environment"] > 0:
                return "environment"
            return "report"

        if modality == "pdf":
            if scores["report"] >= scores["environment"]:
                return "report"
            if scores["environment"] > 0:
                return "environment"
            return "report"

        best_category = max(scores, key=scores.get)
        if scores[best_category] <= 0:
            return "unknown"
        return best_category

    def _determine_usability(
        self,
        *,
        path: Path,
        modality: str,
        detected_category: str,
        detected_format: str,
        preview_columns: list[str],
    ) -> tuple[str, list[str], list[str]]:
        evidence: list[str] = []
        warnings: list[str] = []

        if modality in {"image", "pdf"}:
            evidence.append("non-tabular modalities are preserved for review instead of direct numeric analysis")
            if detected_category == "environment":
                warnings.append("environment semantics come from contextual cues rather than parsed measurements")
            return "view_only", evidence, warnings

        if modality == "archive":
            if detected_category == "unknown":
                return "unsupported", evidence, ["archive contents need manual review before safe use"]
            evidence.append("recognized archive category can be expanded in a later processing phase")
            return "transformable", evidence, warnings

        if modality == "table":
            if detected_format == "vcf":
                evidence.append("VCF structure is directly usable for downstream genotype workflows")
                return "analysis_ready", evidence, warnings

            if detected_category == "environment":
                if self._has_semantic_columns(preview_columns, _ENVIRONMENT_KEYWORDS):
                    evidence.append("environment-oriented columns suggest a directly usable structured table")
                    return "analysis_ready", evidence, warnings
                warnings.append("table structure was detected, but environment semantics remain weak")
                return "transformable", evidence, warnings

            if detected_category == "genotype":
                if path.suffix.lower() in {".bim", ".fam", ".ped", ".map", ".bed"}:
                    warnings.append("genotype table looks like an intermediate format that may need downstream consolidation")
                    return "transformable", evidence, warnings
                evidence.append("genotype-like structured rows were detected")
                return "analysis_ready", evidence, warnings

            if detected_category == "metadata":
                warnings.append("metadata-like tables are structured but may need downstream interpretation")
                return "transformable", evidence, warnings

            if preview_columns:
                warnings.append("table structure was found, but semantic category is still ambiguous")
                return "transformable", evidence, warnings

            return "unsupported", evidence, ["table-like content lacked enough semantic cues for safe use"]

        if modality == "text":
            if detected_category == "report":
                evidence.append("report-like narrative text is kept as view-only context")
                return "view_only", evidence, warnings
            if detected_category in {"genotype", "environment", "metadata"}:
                warnings.append("unstructured text requires normalization before downstream use")
                return "transformable", evidence, warnings
            return "unsupported", evidence, ["plain text did not provide enough structured cues"]

        return "unsupported", evidence, ["unsupported file modality"]

    def _finalize_result(
        self,
        *,
        file_path: Path,
        modality: str,
        detected_category: str,
        detected_format: str,
        usability: str,
        evidence: list[str],
        warnings: list[str],
        preview_columns: list[str],
    ) -> FileInspectionResult:
        deduped_evidence = self._dedupe(evidence)
        if not deduped_evidence:
            deduped_evidence = ["inspection completed with fallback heuristics"]
        deduped_evidence = deduped_evidence[: self.config.max_evidence_items]
        deduped_warnings = self._dedupe(warnings)
        confidence = self._estimate_confidence(
            modality=modality,
            detected_category=detected_category,
            detected_format=detected_format,
            usability=usability,
            preview_columns=preview_columns,
            evidence=deduped_evidence,
            warnings=deduped_warnings,
        )
        return self._build_result(
            file_path=file_path,
            modality=modality,
            detected_category=detected_category,
            detected_format=detected_format,
            usability=usability,
            confidence=confidence,
            evidence=deduped_evidence,
            warnings=deduped_warnings,
            preview_columns=preview_columns[:12],
        )

    def _build_result(
        self,
        *,
        file_path: Path,
        modality: str,
        detected_category: str,
        detected_format: str,
        usability: str,
        confidence: float,
        evidence: list[str],
        warnings: list[str],
        preview_columns: list[str] | None = None,
    ) -> FileInspectionResult:
        return FileInspectionResult(
            file_path=file_path,
            modality=modality,
            detected_category=detected_category,
            detected_format=detected_format,
            confidence=confidence,
            usability=usability,
            evidence=evidence,
            preview_columns=preview_columns or [],
            warnings=warnings,
        )

    def _estimate_confidence(
        self,
        *,
        modality: str,
        detected_category: str,
        detected_format: str,
        usability: str,
        preview_columns: list[str],
        evidence: list[str],
        warnings: list[str],
    ) -> float:
        score = 0.15
        if modality != "unknown":
            score += 0.2
        if detected_category != "unknown":
            score += 0.2
        if detected_format not in {"unknown", "plain_text"}:
            score += 0.15
        if preview_columns:
            score += 0.1
        if usability == "analysis_ready":
            score += 0.1
        elif usability in {"transformable", "view_only"}:
            score += 0.05
        score += min(0.15, len(evidence) * 0.025)
        score -= min(0.2, len(warnings) * 0.04)
        return max(0.05, min(round(score, 3), 0.99))

    def _has_semantic_columns(self, preview_columns: list[str], keywords: set[str]) -> bool:
        header_signal = " ".join(preview_columns).lower()
        return self._keyword_score(header_signal, keywords) >= 2

    def _looks_like_header(self, cells: list[str]) -> bool:
        normalized = [cell.strip() for cell in cells if cell.strip()]
        if len(normalized) < 2:
            return False
        alpha_like = sum(any(char.isalpha() for char in cell) for cell in normalized)
        numeric_like = sum(self._is_numeric_token(cell) for cell in normalized)
        return alpha_like >= max(2, len(normalized) // 2) and numeric_like < len(normalized)

    def _normalize_header(self, cells: list[str]) -> list[str]:
        return [cell.strip().lstrip("#") for cell in cells if cell.strip()]

    def _looks_textual(self, preview_bytes: bytes) -> bool:
        sample = preview_bytes[:_BINARY_TEXT_SAMPLE_BYTES]
        if b"\x00" in sample:
            return False
        printable = 0
        for byte in sample:
            if byte in {9, 10, 13} or 32 <= byte <= 126:
                printable += 1
        return printable / max(len(sample), 1) >= 0.75

    def _detect_text_format(self, path: Path) -> str:
        suffix = path.suffix.lower()
        if suffix:
            return suffix.lstrip(".")
        return "plain_text"

    def _refine_table_format(self, path: Path, delimiter: str, fallback: str) -> str:
        suffix = path.suffix.lower()
        if suffix == ".vcf":
            return "vcf"
        if suffix == ".csv" or delimiter == ",":
            return "csv"
        if suffix in {".tsv", ".tab"} or delimiter == "\t":
            return "tsv"
        return fallback

    def _is_pdf(self, path: Path, preview_bytes: bytes, mime_type: str | None) -> bool:
        return (
            preview_bytes.startswith(_PDF_SIGNATURE)
            or path.suffix.lower() == ".pdf"
            or mime_type == "application/pdf"
        )

    def _is_image(self, path: Path, preview_bytes: bytes, mime_type: str | None) -> bool:
        return (
            path.suffix.lower() in _IMAGE_SUFFIXES
            or any(preview_bytes.startswith(signature) for signature in _JPEG_SIGNATURES)
            or preview_bytes.startswith(_PNG_SIGNATURE)
            or any(preview_bytes.startswith(signature) for signature in _GIF_SIGNATURES)
            or (mime_type or "").startswith("image/")
        )

    def _is_archive(self, path: Path, preview_bytes: bytes, mime_type: str | None) -> bool:
        return (
            path.suffix.lower() in _ARCHIVE_SUFFIXES
            or preview_bytes.startswith(_ZIP_SIGNATURE)
            or preview_bytes.startswith(_GZIP_SIGNATURE)
            or mime_type in {"application/zip", "application/gzip", "application/x-tar"}
        )

    def _detect_image_format(self, path: Path, preview_bytes: bytes) -> str:
        if preview_bytes.startswith(_PNG_SIGNATURE):
            return "png"
        if any(preview_bytes.startswith(signature) for signature in _JPEG_SIGNATURES):
            return "jpeg"
        if any(preview_bytes.startswith(signature) for signature in _GIF_SIGNATURES):
            return "gif"
        return self._suffix_label(path)

    def _detect_archive_format(self, path: Path, preview_bytes: bytes) -> str:
        if preview_bytes.startswith(_ZIP_SIGNATURE):
            return "zip"
        if preview_bytes.startswith(_GZIP_SIGNATURE):
            return "gzip"
        return self._suffix_label(path)

    def _suffix_label(self, path: Path) -> str:
        if not path.suffix:
            return "unknown"
        return path.suffix.lower().lstrip(".")

    def _keyword_score(self, text: str, keywords: set[str]) -> int:
        return sum(keyword in text for keyword in keywords)

    def _is_numeric_token(self, value: str) -> bool:
        candidate = value.strip()
        if not candidate:
            return False
        try:
            float(candidate)
        except ValueError:
            return False
        return True

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
