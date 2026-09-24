from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date
from enum import StrEnum
from typing import Any

from ..identity import normalize_cas, normalize_ec, normalize_name
from .metadata import AuthorityLevel


class CLPMatchType(StrEnum):
    EXACT_INDEX_NUMBER_MATCH = "EXACT_INDEX_NUMBER_MATCH"
    EXACT_EC_MATCH = "EXACT_EC_MATCH"
    EXACT_CAS_MATCH = "EXACT_CAS_MATCH"
    NAME_MATCH = "NAME_MATCH"
    POSSIBLE_GROUP_ENTRY = "POSSIBLE_GROUP_ENTRY"
    AMBIGUOUS_MATCH = "AMBIGUOUS_MATCH"
    MANUAL_REVIEW_REQUIRED = "MANUAL_REVIEW_REQUIRED"
    NO_MATCH = "NO_MATCH_IN_CHECKED_DATASET"


class CLPResultStatus(StrEnum):
    MATCH = "HARMONISED CLASSIFICATION MATCH"
    PARTIAL = "PARTIAL HARMONISED CLASSIFICATION"
    POSSIBLE_GROUP = "POSSIBLE GROUP ENTRY"
    MANUAL_REVIEW = "MANUAL REVIEW REQUIRED"
    NO_MATCH = "NO MATCH IN CHECKED DATASET"


class LawApplicationStatus(StrEnum):
    PUBLISHED_NOT_YET_APPLICABLE = "PUBLISHED BUT NOT YET APPLICABLE"
    CURRENTLY_APPLICABLE = "CURRENTLY APPLICABLE"
    SUPERSEDED_HISTORICAL = "SUPERSEDED/HISTORICAL"
    VERSION_UNKNOWN = "VERSION UNKNOWN"


@dataclass(frozen=True, slots=True)
class HazardClassification:
    hazard_class_code: str
    hazard_category_code: str
    hazard_statement_code: str


@dataclass(frozen=True, slots=True)
class SpecificConcentrationLimit:
    hazard_class: str
    category: str
    operator: str
    threshold: float
    unit: str
    classification_trigger: str
    upper_operator: str = ""
    upper_threshold: float | None = None
    raw_text: str = ""


@dataclass(frozen=True, slots=True)
class MFactor:
    hazard_context: str
    value: float
    raw_text: str = ""


@dataclass(frozen=True, slots=True)
class AcuteToxicityEstimate:
    route: str
    value: float
    unit: str
    physical_form: str = ""
    raw_text: str = ""


@dataclass(frozen=True, slots=True)
class HarmonisedEntry:
    index_number: str
    chemical_name: str
    ec_number: str = ""
    cas_number: str = ""
    hazards: tuple[HazardClassification, ...] = ()
    pictogram_codes: tuple[str, ...] = ()
    signal_word_code: str = ""
    supplemental_hazard_statements: tuple[str, ...] = ()
    specific_concentration_limits: tuple[SpecificConcentrationLimit, ...] = ()
    m_factors: tuple[MFactor, ...] = ()
    acute_toxicity_estimates: tuple[AcuteToxicityEstimate, ...] = ()
    notes: tuple[str, ...] = ()
    form_or_physical_state_scope: str = ""
    minimum_classification_flag: bool = False
    atp_or_amending_act: str = ""
    publication_date: str | None = None
    application_date: str | None = None
    voluntary_early_application_allowed: bool = False
    legal_reference: str = ""
    informational_reference: str = ""
    authority_level: AuthorityLevel = AuthorityLevel.OFFICIAL_INFORMATIONAL_DATASET
    source_version: str = ""
    retrieval_date: str = ""
    checksum: str = ""
    dataset_id: str = ""
    is_group_entry: bool = False
    group_keys: tuple[str, ...] = ()
    superseded_date: str | None = None

    def __post_init__(self) -> None:
        if not self.index_number or not self.chemical_name:
            raise ValueError("Annex VI index number and chemical name are required")
        if not self.hazards:
            raise ValueError("At least one harmonised hazard classification is required")
        if self.authority_level == AuthorityLevel.LEGALLY_BINDING and not self.legal_reference:
            raise ValueError("Legally binding Annex VI entries require an Official Journal/EUR-Lex reference")
        if self.authority_level == AuthorityLevel.OFFICIAL_INFORMATIONAL_DATASET and not self.informational_reference:
            raise ValueError("Informational Annex VI entries require an informational source reference")
        for value in (self.publication_date, self.application_date, self.superseded_date):
            if value:
                date.fromisoformat(value)

    def application_status(self, as_of_date: str | None) -> LawApplicationStatus:
        if not as_of_date:
            return LawApplicationStatus.VERSION_UNKNOWN
        as_of = date.fromisoformat(as_of_date)
        if self.superseded_date and as_of >= date.fromisoformat(self.superseded_date):
            return LawApplicationStatus.SUPERSEDED_HISTORICAL
        if self.application_date and as_of < date.fromisoformat(self.application_date):
            return LawApplicationStatus.PUBLISHED_NOT_YET_APPLICABLE
        return LawApplicationStatus.CURRENTLY_APPLICABLE

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["authority_level"] = str(self.authority_level)
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "HarmonisedEntry":
        values = dict(data)
        values["authority_level"] = AuthorityLevel(values.get("authority_level", AuthorityLevel.OFFICIAL_INFORMATIONAL_DATASET))
        values["hazards"] = tuple(item if isinstance(item, HazardClassification) else HazardClassification(**item) for item in values.get("hazards") or ())
        values["specific_concentration_limits"] = tuple(item if isinstance(item, SpecificConcentrationLimit) else SpecificConcentrationLimit(**item) for item in values.get("specific_concentration_limits") or ())
        values["m_factors"] = tuple(item if isinstance(item, MFactor) else MFactor(**item) for item in values.get("m_factors") or ())
        values["acute_toxicity_estimates"] = tuple(item if isinstance(item, AcuteToxicityEstimate) else AcuteToxicityEstimate(**item) for item in values.get("acute_toxicity_estimates") or ())
        for field_name in ("pictogram_codes", "supplemental_hazard_statements", "notes", "group_keys"):
            values[field_name] = tuple(values.get(field_name) or ())
        return cls(**values)


@dataclass(slots=True)
class CLPIdentityInput:
    chemical_name: str = ""
    cas_number: str = ""
    ec_number: str = ""
    index_number: str = ""
    form_or_physical_state: str = ""
    ambiguity_flag: bool = False
    manual_review_required: bool = False
    supported_group_memberships: set[str] = field(default_factory=set)
    group_membership_evidence: str = ""


@dataclass(slots=True)
class CLPScreeningContext:
    requested_hazard_classes: set[str] = field(default_factory=set)
    as_of_date: str | None = None


@dataclass(frozen=True, slots=True)
class HarmonisedClassificationResult:
    status: CLPResultStatus
    match_type: CLPMatchType
    input_identity: str
    entry: HarmonisedEntry | None
    covered_hazards: tuple[HazardClassification, ...]
    specific_concentration_limits: tuple[SpecificConcentrationLimit, ...]
    m_factors: tuple[MFactor, ...]
    acute_toxicity_estimates: tuple[AcuteToxicityEstimate, ...]
    notes: tuple[str, ...]
    note_present: bool
    manual_review_required: bool
    application_status: LawApplicationStatus | None
    interpretation_note: str

    def __post_init__(self) -> None:
        forbidden = ("SAFE", "COMPLIANT", "NON-HAZARDOUS", "FULLY CLASSIFIED", "UNCLASSIFIED")
        if any(term in str(self.status) for term in forbidden):
            raise ValueError("Annex VI results may not make completeness or safety determinations")


class CLPAnnexVIEngine:
    disclaimer = "Other hazard classes may require classification separately."

    def __init__(self, entries: list[HarmonisedEntry]):
        self.entries = entries

    @staticmethod
    def _identity_label(identity: CLPIdentityInput) -> str:
        return identity.chemical_name or identity.index_number or identity.cas_number or identity.ec_number

    def screen(self, identity: CLPIdentityInput, context: CLPScreeningContext | None = None) -> list[HarmonisedClassificationResult]:
        context = context or CLPScreeningContext()
        if identity.ambiguity_flag or identity.manual_review_required:
            return [self._empty(identity, CLPResultStatus.MANUAL_REVIEW, CLPMatchType.MANUAL_REVIEW_REQUIRED, "Identity is ambiguous or requires manual review.")]
        candidates: list[tuple[HarmonisedEntry, CLPMatchType]] = []
        for entry in self.entries:
            match_type = self._match_type(identity, entry)
            if match_type:
                candidates.append((entry, match_type))
        if not candidates:
            return [self._empty(identity, CLPResultStatus.NO_MATCH, CLPMatchType.NO_MATCH, "No entry was found in this checked snapshot. This does not mean non-hazardous, safe, or unclassified.")]

        if len(candidates) > 1:
            form = normalize_name(identity.form_or_physical_state)
            form_matches = [(entry, kind) for entry, kind in candidates if form and form in normalize_name(entry.form_or_physical_state_scope)]
            if len(form_matches) == 1:
                candidates = form_matches
            elif len({entry.index_number for entry, _ in candidates}) > 1:
                return [self._result(identity, context, entry, CLPMatchType.AMBIGUOUS_MATCH, force_manual=True) for entry, _ in candidates]
        return [self._result(identity, context, entry, match_type) for entry, match_type in candidates]

    def _match_type(self, identity: CLPIdentityInput, entry: HarmonisedEntry) -> CLPMatchType | None:
        if identity.index_number and identity.index_number.strip() == entry.index_number:
            return CLPMatchType.POSSIBLE_GROUP_ENTRY if entry.is_group_entry and not self._group_supported(identity, entry) else CLPMatchType.EXACT_INDEX_NUMBER_MATCH
        if identity.ec_number and normalize_ec(identity.ec_number) == normalize_ec(entry.ec_number):
            return CLPMatchType.POSSIBLE_GROUP_ENTRY if entry.is_group_entry and not self._group_supported(identity, entry) else CLPMatchType.EXACT_EC_MATCH
        if identity.cas_number and normalize_cas(identity.cas_number) == normalize_cas(entry.cas_number):
            return CLPMatchType.POSSIBLE_GROUP_ENTRY if entry.is_group_entry and not self._group_supported(identity, entry) else CLPMatchType.EXACT_CAS_MATCH
        if identity.chemical_name and normalize_name(identity.chemical_name) == normalize_name(entry.chemical_name):
            return CLPMatchType.POSSIBLE_GROUP_ENTRY if entry.is_group_entry and not self._group_supported(identity, entry) else CLPMatchType.NAME_MATCH
        memberships = {normalize_name(value) for value in identity.supported_group_memberships}
        if entry.is_group_entry and memberships.intersection(normalize_name(value) for value in entry.group_keys):
            return CLPMatchType.POSSIBLE_GROUP_ENTRY
        return None

    @staticmethod
    def _group_supported(identity: CLPIdentityInput, entry: HarmonisedEntry) -> bool:
        memberships = {normalize_name(value) for value in identity.supported_group_memberships}
        return bool(memberships.intersection(normalize_name(value) for value in entry.group_keys) and identity.group_membership_evidence)

    def _result(self, identity: CLPIdentityInput, context: CLPScreeningContext, entry: HarmonisedEntry, match_type: CLPMatchType, force_manual: bool = False) -> HarmonisedClassificationResult:
        covered = {normalize_name(hazard.hazard_class_code) for hazard in entry.hazards}
        requested = {normalize_name(value) for value in context.requested_hazard_classes}
        partial = entry.minimum_classification_flag or bool(requested - covered)
        if match_type == CLPMatchType.POSSIBLE_GROUP_ENTRY:
            status = CLPResultStatus.POSSIBLE_GROUP
        elif match_type == CLPMatchType.AMBIGUOUS_MATCH or force_manual:
            status = CLPResultStatus.MANUAL_REVIEW
        elif partial:
            status = CLPResultStatus.PARTIAL
        else:
            status = CLPResultStatus.MATCH
        application = entry.application_status(context.as_of_date)
        notes = [self.disclaimer]
        if entry.minimum_classification_flag:
            notes.append("A minimum-classification marker is present; consult CLP Annex VI notes and the applicable legal text.")
        if entry.notes:
            notes.append("NOTE_PRESENT: Annex VI notes may materially affect interpretation and require manual review.")
        if application == LawApplicationStatus.PUBLISHED_NOT_YET_APPLICABLE:
            notes.append("The entry is published but not yet applicable for the screening date; voluntary early application must be assessed from the cited act.")
        if entry.is_group_entry:
            notes.append("Group-entry membership must be supported; this engine does not infer membership from name similarity.")
        return HarmonisedClassificationResult(
            status, match_type, self._identity_label(identity), entry, entry.hazards,
            entry.specific_concentration_limits, entry.m_factors, entry.acute_toxicity_estimates,
            entry.notes, bool(entry.notes), True, application, " ".join(notes),
        )

    def _empty(self, identity: CLPIdentityInput, status: CLPResultStatus, match_type: CLPMatchType, note: str) -> HarmonisedClassificationResult:
        return HarmonisedClassificationResult(status, match_type, self._identity_label(identity), None, (), (), (), (), (), False, True, None, note)

