from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date
from enum import StrEnum
from typing import Any

from ..identity import normalize_cas, normalize_ec, normalize_name
from ..models import IdentityResult
from .metadata import AuthorityLevel


class RestrictionMatchType(StrEnum):
    EXACT_IDENTIFIER_MATCH = "EXACT_IDENTIFIER_MATCH"
    GROUP_MATCH = "GROUP_MATCH"
    SCOPE_MATCH = "SCOPE_MATCH"
    POSSIBLE_GROUP_MATCH = "POSSIBLE_GROUP_MATCH"
    MANUAL_REVIEW_REQUIRED = "MANUAL_REVIEW_REQUIRED"
    NO_MATCH = "NO_MATCH_IN_CHECKED_DATASET"


POTENTIAL_MATCH = "POTENTIAL RESTRICTION MATCH"
NO_MATCH = "NO MATCH IN CHECKED DATASET"
MANUAL_REVIEW = "MANUAL REVIEW REQUIRED"


@dataclass(frozen=True, slots=True)
class AnnexXVIIAmendment:
    base_entry_version: str
    amending_act: str
    publication_date: str | None = None
    effective_date: str | None = None
    applicability_date: str | None = None
    eur_lex_reference: str = ""


@dataclass(frozen=True, slots=True)
class AnnexXVIIEntry:
    entry_number: str
    entry_title: str
    substance_name: str = ""
    cas_number: str = ""
    ec_number: str = ""
    index_number: str = ""
    group_or_substance_scope: str = ""
    restriction_condition_full_text: str = ""
    structured_scope_summary: str = ""
    mixture_or_article_scope: str = ""
    concentration_threshold: float | None = None
    threshold_unit: str = ""
    specific_use_conditions: str = ""
    exemptions: str = ""
    derogations: str = ""
    transition_dates: str = ""
    effective_date: str | None = None
    appendix_references: str = ""
    legal_basis: str = ""
    amending_regulation: str = ""
    eur_lex_reference: str = ""
    echa_reference: str = ""
    authority_level: AuthorityLevel = AuthorityLevel.OFFICIAL_INFORMATIONAL_DATASET
    manual_review_required: bool = True
    group_keys: tuple[str, ...] = ()
    scope_tags: tuple[str, ...] = ()
    base_entry_version: str = ""
    amending_acts: tuple[AnnexXVIIAmendment, ...] = ()
    dataset_id: str = ""

    def __post_init__(self) -> None:
        if not self.entry_number or not self.entry_title:
            raise ValueError("Annex XVII entry number and title are required")
        if not (self.substance_name or self.group_or_substance_scope):
            raise ValueError("A substance name or group/scope description is required")
        if not self.restriction_condition_full_text and not (self.eur_lex_reference or self.echa_reference):
            raise ValueError("Preserve source wording or provide a traceable source reference")
        if self.effective_date:
            date.fromisoformat(self.effective_date)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["authority_level"] = str(self.authority_level)
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AnnexXVIIEntry":
        values = dict(data)
        values["authority_level"] = AuthorityLevel(values.get("authority_level", AuthorityLevel.OFFICIAL_INFORMATIONAL_DATASET))
        values["group_keys"] = tuple(values.get("group_keys") or ())
        values["scope_tags"] = tuple(values.get("scope_tags") or ())
        values["amending_acts"] = tuple(
            item if isinstance(item, AnnexXVIIAmendment) else AnnexXVIIAmendment(**item)
            for item in values.get("amending_acts") or ()
        )
        threshold = values.get("concentration_threshold")
        values["concentration_threshold"] = float(threshold) if threshold not in (None, "") else None
        return cls(**values)


@dataclass(frozen=True, slots=True)
class LegalDocumentReference:
    entry_number: str
    document_title: str
    celex_number: str
    eur_lex_reference: str
    authority_level: AuthorityLevel
    publication_date: str | None = None
    effective_date: str | None = None
    applicability_date: str | None = None
    amending_act: str = ""
    consolidated_text_date: str | None = None
    legal_text_locator: str = ""
    dataset_id: str = ""

    def __post_init__(self) -> None:
        if self.authority_level not in {AuthorityLevel.LEGALLY_BINDING, AuthorityLevel.OFFICIAL_INFORMATIONAL_DATASET}:
            raise ValueError("EUR-Lex references must retain their legal or official-informational authority")
        if not self.entry_number or not self.celex_number or not self.eur_lex_reference:
            raise ValueError("Entry number, CELEX number, and EUR-Lex reference are required")


@dataclass(slots=True)
class RestrictionContext:
    concentration: float | None = None
    concentration_unit: str = ""
    subject_type: str = ""
    intended_use: str = ""
    user_context: str = ""
    group_memberships: set[str] = field(default_factory=set)
    scope_tags: set[str] = field(default_factory=set)
    group_membership_evidence: str = ""


@dataclass(frozen=True, slots=True)
class RestrictionResult:
    status: str
    input_identity: str
    matched_entry: str
    entry_number: str
    match_type: RestrictionMatchType
    restriction_scope: str
    condition_text: str
    threshold: str
    exemptions: str
    effective_date: str | None
    legal_reference: str
    authority_level: AuthorityLevel | None
    interpretation_note: str
    manual_review_required: bool
    structured_source_dataset_id: str = ""
    legal_source_dataset_id: str = ""
    legal_authority_level: AuthorityLevel | None = None
    legal_sources: tuple[dict[str, Any], ...] = ()
    mixture_or_article_scope: str = ""
    specific_use_conditions: str = ""
    derogations: str = ""
    transition_dates: str = ""
    amending_acts: tuple[dict[str, Any], ...] = ()
    screening_summary_label: str = "SCREENING SUMMARY"
    legal_text_label: str = "LEGAL SOURCE TEXT"

    def __post_init__(self) -> None:
        forbidden = {"RESTRICTED", "ILLEGAL", "NON-COMPLIANT", "UNRESTRICTED", "COMPLIANT"}
        if self.status in forbidden:
            raise ValueError("Restriction results may not make compliance determinations")


class AnnexXVIIEngine:
    def __init__(self, entries: list[AnnexXVIIEntry], legal_references: list[LegalDocumentReference] | None = None):
        self.entries = entries
        self.legal_by_entry: dict[str, list[LegalDocumentReference]] = {}
        for reference in legal_references or []:
            self.legal_by_entry.setdefault(reference.entry_number, []).append(reference)

    @staticmethod
    def _input_identity(identity: IdentityResult) -> str:
        return identity.matched_name or identity.input_name or identity.matched_cas or identity.input_cas or identity.matched_ec or identity.input_ec

    def screen(self, identity: IdentityResult, context: RestrictionContext | None = None, as_of_date: str | None = None) -> list[RestrictionResult]:
        context = context or RestrictionContext()
        if identity.manual_review_required or not (identity.matched_cas or identity.matched_ec or identity.matched_name):
            return [RestrictionResult(
                MANUAL_REVIEW, self._input_identity(identity), "", "",
                RestrictionMatchType.MANUAL_REVIEW_REQUIRED, "", "", "", "", None, "", None,
                "Identity is unresolved or ambiguous; Annex XVII matching was not completed.", True,
            )]
        candidates: list[tuple[AnnexXVIIEntry, RestrictionMatchType, str]] = []
        cas, ec = normalize_cas(identity.matched_cas), normalize_ec(identity.matched_ec)
        normalized_name = normalize_name(identity.matched_name)
        memberships = {normalize_name(value) for value in context.group_memberships}
        scope_tags = {normalize_name(value) for value in context.scope_tags}
        for entry in self.entries:
            if (cas and entry.cas_number and cas == normalize_cas(entry.cas_number)) or (ec and entry.ec_number and ec == normalize_ec(entry.ec_number)):
                candidates.append((entry, RestrictionMatchType.EXACT_IDENTIFIER_MATCH, "Exact normalized CAS or EC identifier match."))
                continue
            entry_groups = {normalize_name(value) for value in entry.group_keys}
            if entry_groups and memberships.intersection(entry_groups):
                candidates.append((entry, RestrictionMatchType.GROUP_MATCH, f"Group membership was explicitly supplied with evidence: {context.group_membership_evidence or 'not documented'}."))
                continue
            entry_scopes = {normalize_name(value) for value in entry.scope_tags}
            if entry_scopes and scope_tags.intersection(entry_scopes):
                candidates.append((entry, RestrictionMatchType.SCOPE_MATCH, "A supplied scope tag intersects the entry scope; applicability still requires legal review."))
                continue
            if entry_groups and normalized_name and any(group in normalized_name or normalized_name in group for group in entry_groups):
                candidates.append((entry, RestrictionMatchType.POSSIBLE_GROUP_MATCH, "Name text suggests possible group membership, but membership was not established."))

        if not candidates:
            return [RestrictionResult(
                NO_MATCH, self._input_identity(identity), "", "", RestrictionMatchType.NO_MATCH,
                "", "", "", "", None, "", None,
                "No matching entry was found in this checked snapshot. This does not mean unrestricted or compliant.", True,
            )]
        return [self._result(identity, context, entry, match_type, note, as_of_date) for entry, match_type, note in candidates]

    def _result(self, identity: IdentityResult, context: RestrictionContext, entry: AnnexXVIIEntry, match_type: RestrictionMatchType, note: str, as_of_date: str | None) -> RestrictionResult:
        references = self.legal_by_entry.get(entry.entry_number, [])
        legal = references[-1] if references else None
        threshold = ""
        if entry.concentration_threshold is not None:
            threshold = f"{entry.concentration_threshold:g} {entry.threshold_unit}".strip()
            if context.concentration is None:
                note += " Concentration was not supplied; the threshold cannot be evaluated."
            elif normalize_name(context.concentration_unit) != normalize_name(entry.threshold_unit):
                note += " Concentration unit differs from the entry threshold unit; no comparison was made."
            else:
                relation = "at or above" if context.concentration >= entry.concentration_threshold else "below"
                note += f" Supplied concentration is {relation} the recorded threshold; this is screening context, not a compliance conclusion."
        if entry.effective_date and as_of_date and date.fromisoformat(entry.effective_date) > date.fromisoformat(as_of_date):
            note += f" Entry is future-effective relative to the screening date {as_of_date}."
        legal_reference = " | ".join(reference.eur_lex_reference for reference in references) or entry.eur_lex_reference or entry.echa_reference
        if not references:
            note += " A separately versioned EUR-Lex legal-reference record was not linked; verify the legal text manually."
        legal_levels = {reference.authority_level for reference in references}
        legal_sources = tuple({
            "document_title": reference.document_title,
            "celex_number": reference.celex_number,
            "reference": reference.eur_lex_reference,
            "authority_level": str(reference.authority_level),
            "effective_date": reference.effective_date,
            "applicability_date": reference.applicability_date,
            "dataset_id": reference.dataset_id,
        } for reference in references)
        return RestrictionResult(
            status=POTENTIAL_MATCH,
            input_identity=self._input_identity(identity), matched_entry=entry.entry_title,
            entry_number=entry.entry_number, match_type=match_type,
            restriction_scope=entry.group_or_substance_scope or entry.structured_scope_summary,
            condition_text=entry.restriction_condition_full_text or f"Legal text not embedded; consult {legal_reference}",
            threshold=threshold, exemptions="; ".join(value for value in (entry.exemptions, entry.derogations) if value),
            effective_date=entry.effective_date, legal_reference=legal_reference,
            authority_level=entry.authority_level, interpretation_note=note,
            manual_review_required=True, structured_source_dataset_id=entry.dataset_id,
            legal_source_dataset_id="|".join(reference.dataset_id for reference in references),
            legal_authority_level=next(iter(legal_levels)) if len(legal_levels) == 1 else None,
            legal_sources=legal_sources,
            mixture_or_article_scope=entry.mixture_or_article_scope,
            specific_use_conditions=entry.specific_use_conditions,
            derogations=entry.derogations,
            transition_dates=entry.transition_dates,
            amending_acts=tuple(asdict(amendment) for amendment in entry.amending_acts),
        )
