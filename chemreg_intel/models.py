from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date
from enum import StrEnum
from typing import Any


class DecisionStatus(StrEnum):
    CONFIRMED_MATCH = "CONFIRMED MATCH"
    NO_MATCH = "NO MATCH IN CHECKED SOURCE"
    AMBIGUOUS = "AMBIGUOUS"
    MANUAL_REVIEW = "MANUAL REVIEW REQUIRED"
    NOT_ASSESSED = "NOT ASSESSED"


class MatchMethod(StrEnum):
    CAS_EXACT = "CAS exact"
    EC_EXACT = "EC exact"
    NAME_EXACT = "name exact"
    SYNONYM_EXACT = "synonym exact"
    NAME_SUGGESTION = "fuzzy name suggestion"
    NONE = "none"


@dataclass(slots=True)
class SourceRecord:
    source_name: str
    source_reference: str
    source_version: str
    retrieval_date: str
    regulatory_list: str
    synthetic: bool = False
    source_authority: str = ""
    source_type: str = ""
    effective_date: str | None = None
    dataset_id: str = ""
    authority_level: str = ""
    legal_notice_url: str = ""
    redistribution_allowed: bool | None = None
    commercial_use_allowed: bool | None = None
    checksum: str = ""
    record_count: int | None = None

    def __post_init__(self) -> None:
        if not all(
            [self.source_name, self.source_reference, self.source_version,
             self.retrieval_date, self.regulatory_list]
        ):
            raise ValueError("Source provenance fields may not be empty")
        date.fromisoformat(self.retrieval_date)
        if self.effective_date:
            date.fromisoformat(self.effective_date)


@dataclass(slots=True)
class SubstanceRecord:
    name: str
    cas: str = ""
    ec: str = ""
    synonyms: tuple[str, ...] = ()


@dataclass(slots=True)
class ChemicalInput:
    input_name: str = ""
    input_cas: str = ""
    input_ec: str = ""
    concentration: float | None = None
    supplier_product: str = ""
    input_row: int | None = None


@dataclass(slots=True)
class IdentityResult:
    input_name: str
    input_cas: str
    input_ec: str
    matched_name: str = ""
    matched_cas: str = ""
    matched_ec: str = ""
    match_method: str = MatchMethod.NONE
    match_confidence: float = 0.0
    ambiguity_flag: bool = False
    manual_review_required: bool = True
    suggestions: list[str] = field(default_factory=list)
    input_row: int | None = None


@dataclass(slots=True)
class RegulatoryEvidence:
    status: str
    module: str
    matched_identifier: str = ""
    entry_number: str = ""
    summary: str = ""
    conditions_or_thresholds: str = ""
    exemptions_or_notes: str = ""
    classification_fields: dict[str, Any] = field(default_factory=dict)
    source: SourceRecord | None = None
    manual_review_required: bool = False
    review_notes: str = ""
    dataset_id: str = ""
    authority_level: str = ""
    effective_date: str | None = None

    def to_dict(self) -> dict[str, Any]:
        output = asdict(self)
        source = output.pop("source") or {}
        output.update({f"source_{key}": value for key, value in source.items()})
        return output


@dataclass(slots=True)
class ScreeningResult:
    chemical: ChemicalInput
    identity: IdentityResult
    svhc: RegulatoryEvidence
    restriction: RegulatoryEvidence
    clp: list[RegulatoryEvidence]
    reviewer_notes: str = ""
