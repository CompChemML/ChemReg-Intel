from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Any

from ..models import Mixture


class ClassificationStatus(StrEnum):
    DERIVED = "CLASSIFICATION DERIVED"
    NOT_TRIGGERED = "CLASSIFICATION NOT TRIGGERED UNDER IMPLEMENTED RULE"
    INSUFFICIENT_DATA = "INSUFFICIENT DATA"
    MANUAL_REVIEW = "MANUAL REVIEW REQUIRED"
    RULE_NOT_IMPLEMENTED = "RULE NOT IMPLEMENTED"
    AMBIGUOUS_COMPONENT = "AMBIGUOUS COMPONENT IDENTITY"


class EvidenceRoute(StrEnum):
    MIXTURE_DATA = "DATA ON THE MIXTURE ITSELF"
    BRIDGING_PRINCIPLE = "BRIDGING-PRINCIPLE EVIDENCE"
    COMPONENT_CALCULATION = "COMPONENT-BASED CLASSIFICATION"
    INSUFFICIENT = "INSUFFICIENT EVIDENCE"


@dataclass(frozen=True, slots=True)
class CalculationTraceRow:
    component_name: str
    concentration: str
    oral_ate: float | None
    ate_unit: str
    ate_source: str
    contribution: float | None
    included: bool
    decision: str
    provenance: dict[str, Any]
    scenario: str = "exact"


@dataclass(frozen=True, slots=True)
class HazardRuleResult:
    hazard_class: str
    legal_basis: str
    rule_version: str
    applicability_date: str
    required_inputs: tuple[str, ...]
    calculation_method: str
    decision_steps: tuple[str, ...]
    result: ClassificationStatus
    resulting_category: str
    evidence_route: EvidenceRoute
    assumptions: tuple[str, ...]
    warnings: tuple[str, ...]
    manual_review_required: bool
    source_reference: str
    calculation_trace: tuple[CalculationTraceRow, ...] = ()
    calculated_mixture_ate: float | None = None
    calculated_mixture_ate_range: tuple[float, float] | None = None
    classification_threshold_used: str = ""
    unknown_component_percentage: float | None = None

    def __post_init__(self) -> None:
        forbidden = ("SAFE", "NON-HAZARDOUS", "COMPLIANT", "LEGAL", "APPROVED")
        if any(term in str(self.result) or term in self.resulting_category for term in forbidden):
            raise ValueError("Mixture rule results may not make safety or compliance determinations")

    def to_dict(self) -> dict[str, Any]:
        """Return an export-safe result including the full calculation trace."""
        return asdict(self)


class HazardRule(ABC):
    hazard_class: str
    legal_basis: str
    rule_version: str
    applicability_date: str
    required_inputs: tuple[str, ...]
    calculation_method: str
    source_reference: str

    @abstractmethod
    def evaluate(self, mixture: Mixture) -> HazardRuleResult:
        """Evaluate exactly one hazard class and preserve the decision trace."""
