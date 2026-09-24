from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .metadata import AuthorityLevel


AUTHORITY_ORDER = {
    AuthorityLevel.LEGALLY_BINDING: 0,
    AuthorityLevel.OFFICIAL_REGULATORY_DATABASE: 1,
    AuthorityLevel.OFFICIAL_INFORMATIONAL_DATASET: 2,
    AuthorityLevel.INDUSTRY_SUBMITTED_DATA: 3,
    AuthorityLevel.SECONDARY_REFERENCE: 4,
}


@dataclass(frozen=True, slots=True)
class EvidenceClaim:
    source_name: str
    authority_level: AuthorityLevel
    effective_date: str | None
    field: str
    value: Any
    dataset_id: str


@dataclass(frozen=True, slots=True)
class ConflictReport:
    field: str
    claims: tuple[EvidenceClaim, ...]
    difference: str
    manual_review_required: bool


def compare_claims(claims: list[EvidenceClaim]) -> ConflictReport | None:
    if not claims:
        return None
    fields = {claim.field for claim in claims}
    if len(fields) != 1:
        raise ValueError("Claims must concern the same field")
    distinct = {repr(claim.value) for claim in claims}
    if len(distinct) <= 1:
        return None
    ordered = tuple(sorted(claims, key=lambda claim: (AUTHORITY_ORDER[claim.authority_level], claim.effective_date or "")))
    difference = " | ".join(
        f"{claim.source_name} [{claim.authority_level}; effective {claim.effective_date or 'unknown'}]: {claim.value}"
        for claim in ordered
    )
    return ConflictReport(next(iter(fields)), ordered, difference, True)

