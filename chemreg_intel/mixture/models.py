from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import StrEnum

from ..regulatory.clp_annex_vi import AcuteToxicityEstimate, HazardClassification, MFactor, SpecificConcentrationLimit


class ConcentrationKind(StrEnum):
    EXACT = "EXACT"
    RANGE = "RANGE"
    UNKNOWN = "UNKNOWN"
    BELOW_THRESHOLD = "BELOW_THRESHOLD_STATEMENT"
    CONFIDENTIAL_RANGE = "CONFIDENTIAL_CONCENTRATION_RANGE"


@dataclass(frozen=True, slots=True)
class EvidenceProvenance:
    source: str
    authority_level: str
    dataset_snapshot: str
    retrieval_date: str
    effective_or_applicability_date: str | None = None
    user_supplied: bool = False
    reference: str = ""

    def __post_init__(self) -> None:
        if not self.source or not self.authority_level or not self.dataset_snapshot or not self.retrieval_date:
            raise ValueError("Every numerical input requires complete source provenance")
        date.fromisoformat(self.retrieval_date)
        if self.effective_or_applicability_date:
            date.fromisoformat(self.effective_or_applicability_date)
        if self.user_supplied and self.authority_level != "USER_SUPPLIED":
            raise ValueError("Manually entered evidence must use USER_SUPPLIED authority")


@dataclass(frozen=True, slots=True)
class ConcentrationEvidence:
    kind: ConcentrationKind
    unit: str
    provenance: EvidenceProvenance
    value: float | None = None
    lower: float | None = None
    upper: float | None = None
    statement: str = ""

    def __post_init__(self) -> None:
        if self.unit not in {"% w/w", "% v/v", "%"}:
            raise ValueError("Concentration unit must be %, % w/w, or % v/v")
        if self.kind == ConcentrationKind.EXACT and self.value is None:
            raise ValueError("Exact concentration requires value")
        if self.kind in {ConcentrationKind.RANGE, ConcentrationKind.CONFIDENTIAL_RANGE}:
            if self.lower is None or self.upper is None or self.lower > self.upper:
                raise ValueError("Concentration range requires ordered lower and upper bounds")
        if self.kind == ConcentrationKind.BELOW_THRESHOLD and self.upper is None:
            raise ValueError("Below-threshold evidence requires the stated upper threshold")
        for number in (self.value, self.lower, self.upper):
            if number is not None and not 0 <= number <= 100:
                raise ValueError("Concentration values must be between 0 and 100")

    def bounds(self) -> tuple[float, float] | None:
        if self.kind == ConcentrationKind.EXACT:
            return float(self.value), float(self.value)
        if self.kind in {ConcentrationKind.RANGE, ConcentrationKind.CONFIDENTIAL_RANGE}:
            return float(self.lower), float(self.upper)
        if self.kind == ConcentrationKind.BELOW_THRESHOLD:
            return 0.0, float(self.upper)
        return None


@dataclass(frozen=True, slots=True)
class ATEEvidence:
    route: str
    value: float
    unit: str
    source_kind: str
    provenance: EvidenceProvenance
    physical_form: str = ""
    harmonised: bool = False

    def __post_init__(self) -> None:
        if self.value <= 0:
            raise ValueError("ATE must be positive")
        if not self.route or not self.unit or not self.source_kind:
            raise ValueError("ATE route, unit, and source kind are required")


@dataclass(frozen=True, slots=True)
class ThresholdEvidence:
    threshold_type: str
    hazard_class: str
    value: float
    unit: str
    provenance: EvidenceProvenance
    operator: str = ">="
    note: str = ""


@dataclass(slots=True)
class MixtureComponent:
    component_name: str
    concentration: ConcentrationEvidence
    cas: str = ""
    ec: str = ""
    index_number: str = ""
    component_role: str = ""
    purity_if_known: float | None = None
    impurity_flag: bool = False
    classification_source: str = ""
    harmonised_classification: tuple[HazardClassification, ...] = ()
    other_classification: tuple[HazardClassification, ...] = ()
    specific_concentration_limits: tuple[SpecificConcentrationLimit, ...] = ()
    generic_concentration_limits: tuple[ThresholdEvidence, ...] = ()
    cut_off_values: tuple[ThresholdEvidence, ...] = ()
    calculation_thresholds: tuple[ThresholdEvidence, ...] = ()
    m_factors: tuple[MFactor, ...] = ()
    acute_toxicity_estimates: tuple[ATEEvidence, ...] = ()
    notes: tuple[str, ...] = ()
    source_provenance: tuple[EvidenceProvenance, ...] = ()
    acute_oral_not_toxic_evidence: bool = False
    identity_ambiguity_flag: bool = False
    manual_review_required: bool = False

    @property
    def concentration_value(self) -> float | None:
        return self.concentration.value

    @property
    def concentration_unit(self) -> str:
        return self.concentration.unit

    @property
    def concentration_range(self) -> tuple[float, float] | None:
        return self.concentration.bounds() if self.concentration.kind != ConcentrationKind.EXACT else None


@dataclass(slots=True)
class Mixture:
    mixture_id: str
    product_name: str
    components: list[MixtureComponent]
    mixture_ate_evidence: tuple[ATEEvidence, ...] = ()
    mixture_test_data_reference: str = ""
    bridging_principle_requested: str = ""
    notes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.mixture_id or not self.product_name:
            raise ValueError("Mixture ID and product name are required")
        if not self.components and not self.mixture_ate_evidence:
            raise ValueError("Mixture requires components or mixture-level ATE evidence")
        names = [component.component_name.casefold() for component in self.components]
        if len(names) != len(set(names)):
            raise ValueError("Duplicate component names require explicit disambiguation")
