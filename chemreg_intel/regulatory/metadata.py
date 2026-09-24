from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from enum import StrEnum
from typing import Any


class AuthorityLevel(StrEnum):
    LEGALLY_BINDING = "LEGALLY BINDING"
    OFFICIAL_REGULATORY_DATABASE = "OFFICIAL REGULATORY DATABASE"
    OFFICIAL_INFORMATIONAL_DATASET = "OFFICIAL INFORMATIONAL DATASET"
    INDUSTRY_SUBMITTED_DATA = "INDUSTRY-SUBMITTED DATA"
    SECONDARY_REFERENCE = "SECONDARY REFERENCE"


class UpdateStatus(StrEnum):
    CURRENT = "CURRENT"
    UPDATE_AVAILABLE = "UPDATE AVAILABLE"
    SOURCE_UNAVAILABLE = "SOURCE UNAVAILABLE"
    VERSION_UNKNOWN = "VERSION UNKNOWN"
    MANUAL_UPDATE_REQUIRED = "MANUAL UPDATE REQUIRED"


@dataclass(frozen=True, slots=True)
class SourceMetadata:
    source_name: str
    source_authority: str
    source_url: str
    source_type: str
    retrieval_date: str
    effective_date: str | None
    dataset_version: str
    legal_notice_url: str
    redistribution_allowed: bool | None
    commercial_use_allowed: bool | None
    authoritative_status: AuthorityLevel
    checksum: str
    record_count: int
    automated_retrieval_allowed: bool | None = None
    local_caching_allowed: bool | None = None
    reuse_decision_notes: str = ""
    legal_notice_version: str = ""

    def __post_init__(self) -> None:
        required = (
            self.source_name, self.source_authority, self.source_url, self.source_type,
            self.retrieval_date, self.dataset_version, self.legal_notice_url,
            self.authoritative_status, self.checksum,
        )
        if not all(required):
            raise ValueError("Required regulatory source metadata may not be empty")
        date.fromisoformat(self.retrieval_date)
        if self.effective_date:
            date.fromisoformat(self.effective_date)
        if self.record_count < 0:
            raise ValueError("record_count may not be negative")

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["authoritative_status"] = str(self.authoritative_status)
        return result


@dataclass(frozen=True, slots=True)
class DatasetSnapshot:
    dataset_id: str
    source: SourceMetadata
    retrieval_timestamp: str
    effective_date: str | None
    version: str
    checksum: str
    record_count: int
    raw_filename: str
    validation_report: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        datetime.fromisoformat(self.retrieval_timestamp.replace("Z", "+00:00"))
        if self.checksum != self.source.checksum:
            raise ValueError("Snapshot and source checksums differ")
        if self.record_count != self.source.record_count:
            raise ValueError("Snapshot and source record counts differ")


@dataclass(frozen=True, slots=True)
class UpdateReport:
    status: UpdateStatus
    checked_at: str
    local_version: str
    remote_version: str | None = None
    message: str = ""


@dataclass(slots=True)
class ValidationIssue:
    row: int | None
    field: str
    severity: str
    message: str


@dataclass(slots=True)
class ValidationReport:
    valid: bool
    record_count: int
    issues: list[ValidationIssue] = field(default_factory=list)
    normalized_headers: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "record_count": self.record_count,
            "issues": [asdict(issue) for issue in self.issues],
            "normalized_headers": self.normalized_headers,
        }

