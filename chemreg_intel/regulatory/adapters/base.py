from __future__ import annotations

import hashlib
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..metadata import SourceMetadata, UpdateReport, ValidationReport


class SourceAdapter(ABC):
    """Contract for a regulatory source without assuming network access."""

    adapter_id: str
    supported_extensions: tuple[str, ...]

    @staticmethod
    def checksum_bytes(payload: bytes) -> str:
        return hashlib.sha256(payload).hexdigest()

    @abstractmethod
    def parse(self, payload: bytes, filename: str) -> list[dict[str, Any]]:
        """Parse and normalize a source snapshot without mutating storage."""

    @abstractmethod
    def validate(self, records: list[dict[str, Any]]) -> ValidationReport:
        """Validate normalized records and return row-level diagnostics."""

    @abstractmethod
    def metadata(
        self,
        payload: bytes,
        records: list[dict[str, Any]],
        *,
        retrieval_date: str,
        effective_date: str | None,
        dataset_version: str | None,
    ) -> SourceMetadata:
        """Build complete provenance and licensing metadata."""

    @abstractmethod
    def check_for_update(self, local: SourceMetadata) -> UpdateReport:
        """Check update status without changing or replacing a snapshot."""

    def import_file(
        self,
        path: str | Path,
        *,
        retrieval_date: str,
        effective_date: str | None = None,
        dataset_version: str | None = None,
    ) -> tuple[bytes, list[dict[str, Any]], SourceMetadata, ValidationReport]:
        path = Path(path)
        if path.suffix.lower() not in self.supported_extensions:
            raise ValueError(f"Unsupported source format {path.suffix}; expected {self.supported_extensions}")
        payload = path.read_bytes()
        records = self.parse(payload, path.name)
        report = self.validate(records)
        if not report.valid:
            messages = "; ".join(issue.message for issue in report.issues if issue.severity == "ERROR")
            raise ValueError(f"Dataset validation failed: {messages}")
        source = self.metadata(
            payload, records, retrieval_date=retrieval_date,
            effective_date=effective_date, dataset_version=dataset_version,
        )
        return payload, records, source, report

    @staticmethod
    def checked_now() -> str:
        return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

