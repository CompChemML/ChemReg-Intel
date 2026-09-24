from __future__ import annotations

from .models import Mixture
from .rules.base import ClassificationStatus, EvidenceRoute, HazardRuleResult

SUPPORTED_ARCHITECTURE = {
    "dilution", "batching", "concentration of highly hazardous mixtures",
    "interpolation within one toxicity category", "substantially similar mixtures", "aerosols",
}


def bridging_not_implemented(mixture: Mixture, principle: str, *, hazard_class: str, legal_basis: str, rule_version: str, applicability_date: str, source_reference: str) -> HazardRuleResult:
    normalized = principle.strip().lower()
    warning = "BRIDGING PRINCIPLE NOT YET IMPLEMENTED"
    if normalized not in SUPPORTED_ARCHITECTURE:
        warning += f": unrecognized principle '{principle}'"
    return HazardRuleResult(
        hazard_class=hazard_class, legal_basis=legal_basis, rule_version=rule_version,
        applicability_date=applicability_date, required_inputs=("expert-reviewed bridging evidence",),
        calculation_method="No automated bridging calculation",
        decision_steps=(f"Mixture requested bridging principle: {principle}", warning),
        result=ClassificationStatus.MANUAL_REVIEW, resulting_category="",
        evidence_route=EvidenceRoute.BRIDGING_PRINCIPLE, assumptions=(),
        warnings=(warning, "MANUAL REVIEW REQUIRED"), manual_review_required=True,
        source_reference=source_reference,
    )

