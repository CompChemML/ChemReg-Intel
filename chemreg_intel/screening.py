from __future__ import annotations

from typing import Any

from .identity import normalize_cas, normalize_ec
from .models import DecisionStatus, IdentityResult, RegulatoryEvidence, SourceRecord


def _identity_keys(identity: IdentityResult) -> set[str]:
    keys = set()
    if identity.matched_cas:
        keys.add(normalize_cas(identity.matched_cas))
    if identity.matched_ec:
        keys.add(normalize_ec(identity.matched_ec))
    return keys


class EvidenceDataset:
    def __init__(self, module: str, source: SourceRecord, records: list[dict[str, Any]]):
        self.module = module
        self.source = source
        self.records = records

    def screen(self, identity: IdentityResult) -> list[RegulatoryEvidence]:
        if identity.manual_review_required or not (identity.matched_cas or identity.matched_ec):
            return [RegulatoryEvidence(
                status=DecisionStatus.MANUAL_REVIEW,
                module=self.module,
                source=self.source,
                manual_review_required=True,
                review_notes="Identity is unresolved or ambiguous; regulatory matching was not completed.",
                dataset_id=self.source.dataset_id,
                authority_level=self.source.authority_level,
                effective_date=self.source.effective_date,
            )]
        keys = _identity_keys(identity)
        matches = [
            record for record in self.records
            if normalize_cas(record.get("cas")) in keys or normalize_ec(record.get("ec")) in keys
        ]
        if not matches:
            return [RegulatoryEvidence(
                status=DecisionStatus.NO_MATCH,
                module=self.module,
                matched_identifier=identity.matched_cas or identity.matched_ec,
                source=self.source,
                review_notes="No matching identifier was found in this specific checked dataset; this is not a compliance determination.",
                dataset_id=self.source.dataset_id,
                authority_level=self.source.authority_level,
                effective_date=self.source.effective_date,
            )]
        return [self._evidence(record) for record in matches]

    def _evidence(self, record: dict[str, Any]) -> RegulatoryEvidence:
        return RegulatoryEvidence(
            status=DecisionStatus.CONFIRMED_MATCH,
            module=self.module,
            matched_identifier=record.get("cas") or record.get("ec", ""),
            entry_number=str(record.get("entry_number", "")),
            summary=record.get("summary", ""),
            conditions_or_thresholds=record.get("conditions_or_thresholds", ""),
            exemptions_or_notes=record.get("exemptions_or_notes", ""),
            classification_fields=record.get("classification_fields", {}),
            source=self.source,
            manual_review_required=bool(record.get("manual_review_required", False)),
            review_notes=record.get("review_notes", ""),
            dataset_id=self.source.dataset_id,
            authority_level=self.source.authority_level,
            effective_date=self.source.effective_date,
        )


class SVHCScreener(EvidenceDataset):
    def __init__(self, source: SourceRecord, records: list[dict[str, Any]]):
        super().__init__("SVHC Screening", source, records)


class RestrictionScreener(EvidenceDataset):
    def __init__(self, source: SourceRecord, records: list[dict[str, Any]]):
        super().__init__("REACH Restrictions", source, records)

    def _evidence(self, record: dict[str, Any]) -> RegulatoryEvidence:
        evidence = super()._evidence(record)
        evidence.status = "POTENTIAL RESTRICTION MATCH"
        evidence.manual_review_required = True
        evidence.review_notes = " ".join(filter(None, [
            evidence.review_notes,
            "A restriction-entry match is not a compliance decision; conditions, scope, thresholds, dates, and exemptions require review.",
        ]))
        return evidence


class CLPScreener(EvidenceDataset):
    def __init__(self, source: SourceRecord, records: list[dict[str, Any]]):
        super().__init__("CLP / GHS", source, records)
