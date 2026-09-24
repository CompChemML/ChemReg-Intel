from __future__ import annotations

from dataclasses import dataclass

from ..bridging import bridging_not_implemented
from ..models import ATEEvidence, ConcentrationKind, Mixture, MixtureComponent
from .base import (
    CalculationTraceRow,
    ClassificationStatus,
    EvidenceRoute,
    HazardRule,
    HazardRuleResult,
)


@dataclass(frozen=True, slots=True)
class _Scenario:
    name: str
    mixture_ate: float | None
    category: str
    unknown_percentage: float
    largest_unknown_component: float
    trace: tuple[CalculationTraceRow, ...]
    warnings: tuple[str, ...]
    steps: tuple[str, ...]


class AcuteToxicityOralRule(HazardRule):
    """CLP Annex I oral acute-toxicity pilot.

    The rule is deliberately limited to route-specific oral evidence. It does
    not perform bridging, convert routes, or substitute SCLs/GCLs/M-factors for
    an acute toxicity estimate.
    """

    hazard_class = "Acute Toxicity — Oral"
    legal_basis = (
        "Regulation (EC) No 1272/2008, Annex I, sections 3.1.3.2, 3.1.3.3, "
        "3.1.3.6.1 and 3.1.3.6.2.3; Tables 1.1, 3.1.1 and 3.1.2"
    )
    rule_version = "clp-annex-i-2026-07-01-oral-pilot-v1"
    applicability_date = "2026-07-01"
    required_inputs = (
        "component concentration or concentration bounds",
        "route-specific oral ATE or evidence that the component is not acutely toxic orally",
        "source provenance for every numerical input",
    )
    calculation_method = "CLP acute-toxicity additivity formula: 100/ATE_mix = sum(C_i/ATE_i)"
    source_reference = "https://eur-lex.europa.eu/eli/reg/2008/1272"

    def __init__(self, *, rule_version: str | None = None, applicability_date: str | None = None) -> None:
        if rule_version is not None:
            self.rule_version = rule_version
        if applicability_date is not None:
            self.applicability_date = applicability_date

    def evaluate(self, mixture: Mixture) -> HazardRuleResult:
        ambiguous = [c.component_name for c in mixture.components if c.identity_ambiguity_flag]
        if ambiguous:
            return self._result(
                status=ClassificationStatus.AMBIGUOUS_COMPONENT,
                route=EvidenceRoute.INSUFFICIENT,
                steps=(f"Ambiguous component identity: {', '.join(ambiguous)}",),
                warnings=("Component identity must be resolved before calculation.",),
                manual=True,
            )

        mixture_oral = self._oral_ates(mixture.mixture_ate_evidence)
        if len(mixture_oral) > 1:
            return self._result(
                status=ClassificationStatus.MANUAL_REVIEW,
                route=EvidenceRoute.MIXTURE_DATA,
                steps=("Multiple oral mixture ATE values were supplied; no value was selected silently.",),
                warnings=("Conflicting mixture-level evidence requires expert selection.",),
                manual=True,
            )
        if mixture_oral:
            return self._from_mixture_ate(mixture_oral[0])

        if mixture.bridging_principle_requested:
            return bridging_not_implemented(
                mixture,
                mixture.bridging_principle_requested,
                hazard_class=self.hazard_class,
                legal_basis=self.legal_basis,
                rule_version=self.rule_version,
                applicability_date=self.applicability_date,
                source_reference=self.source_reference,
            )

        incomplete = [c.component_name for c in mixture.components if c.concentration.bounds() is None]
        if incomplete:
            return self._result(
                status=ClassificationStatus.INSUFFICIENT_DATA,
                route=EvidenceRoute.INSUFFICIENT,
                steps=(f"Missing numerical concentration bounds for: {', '.join(incomplete)}",),
                warnings=("Unknown concentration is not replaced by an assumed value.",),
                manual=True,
            )

        bounds = [(c.concentration.bounds() or (0.0, 0.0)) for c in mixture.components]
        low_total = sum(pair[0] for pair in bounds)
        high_total = sum(pair[1] for pair in bounds)
        if low_total > 100.000001 or high_total < 99.999999:
            return self._result(
                status=ClassificationStatus.INSUFFICIENT_DATA,
                route=EvidenceRoute.INSUFFICIENT,
                steps=(f"Composition bounds do not contain 100% (lower={low_total:g}%, upper={high_total:g}%).",),
                warnings=("Composition integrity check failed.",),
                manual=True,
            )

        has_ranges = any(low != high for low, high in bounds)
        scenarios = [self._calculate_scenario(mixture.components, "lower-bound", 0)]
        if has_ranges:
            scenarios.append(self._calculate_scenario(mixture.components, "upper-bound", 1))

        if any(s.mixture_ate is None for s in scenarios):
            trace = tuple(row for scenario in scenarios for row in scenario.trace)
            warnings = self._unique(item for scenario in scenarios for item in scenario.warnings)
            steps = self._unique(item for scenario in scenarios for item in scenario.steps)
            return self._result(
                status=ClassificationStatus.INSUFFICIENT_DATA,
                route=EvidenceRoute.INSUFFICIENT,
                steps=steps,
                warnings=warnings or ("No usable oral ATE contribution was available.",),
                manual=True,
                trace=trace,
                unknown=max(s.unknown_percentage for s in scenarios),
            )

        ates = sorted(float(s.mixture_ate) for s in scenarios if s.mixture_ate is not None)
        categories = {s.category for s in scenarios}
        unknown = max(s.unknown_percentage for s in scenarios)
        unknown_at_or_above_one = any(s.largest_unknown_component >= 1.0 for s in scenarios)
        warnings = list(self._unique(item for s in scenarios for item in s.warnings))
        steps = self._unique(item for s in scenarios for item in s.steps)
        trace = tuple(row for s in scenarios for row in s.trace)

        if len(categories) > 1:
            status = ClassificationStatus.MANUAL_REVIEW
            manual = True
            category = "Range spans categories: " + ", ".join(sorted(categories))
            warnings.append("Concentration bounds span classification outcomes; no midpoint was used.")
        else:
            category = next(iter(categories))
            status = ClassificationStatus.NOT_TRIGGERED if category == "Not triggered by implemented oral ATE bands" else ClassificationStatus.DERIVED
            manual = False

        if unknown_at_or_above_one:
            status = ClassificationStatus.MANUAL_REVIEW
            manual = True
            warnings.append(
                "At least one component at or above 1% lacks usable oral acute-toxicity information; "
                "the calculated ATE is provisional and a definitive estimate cannot be made."
            )
        if any(c.manual_review_required for c in mixture.components):
            status = ClassificationStatus.MANUAL_REVIEW
            manual = True
            warnings.append("Component evidence is explicitly flagged for manual review.")

        threshold = self._threshold_text(category) if len(categories) == 1 else "Multiple category bands intersected"
        return self._result(
            status=status,
            route=EvidenceRoute.COMPONENT_CALCULATION,
            steps=steps,
            warnings=self._unique(warnings),
            manual=manual,
            category=category,
            trace=trace,
            calculated=ates[0] if len(ates) == 1 else None,
            calculated_range=(ates[0], ates[-1]) if len(ates) > 1 else None,
            threshold=threshold,
            unknown=unknown,
        )

    def _from_mixture_ate(self, evidence: ATEEvidence) -> HazardRuleResult:
        if not self._supported_ate_unit(evidence.unit):
            return self._result(
                status=ClassificationStatus.INSUFFICIENT_DATA,
                route=EvidenceRoute.INSUFFICIENT,
                steps=(f"Mixture oral ATE unit '{evidence.unit}' is not supported.",),
                warnings=("No unit conversion was inferred.",),
                manual=True,
            )
        category = self._category(evidence.value)
        status = ClassificationStatus.NOT_TRIGGERED if category.startswith("Not triggered") else ClassificationStatus.DERIVED
        return self._result(
            status=status,
            route=EvidenceRoute.MIXTURE_DATA,
            steps=("Used route-specific oral data on the mixture itself before any component calculation.",),
            warnings=("Other hazard classes and exposure routes require separate evaluation.",),
            manual=False,
            category=category,
            calculated=evidence.value,
            threshold=self._threshold_text(category),
        )

    def _calculate_scenario(self, components: list[MixtureComponent], name: str, bound_index: int) -> _Scenario:
        contribution_sum = 0.0
        unknown_total = 0.0
        largest_unknown = 0.0
        trace: list[CalculationTraceRow] = []
        warnings: list[str] = []
        steps: list[str] = []

        for component in components:
            bounds = component.concentration.bounds()
            concentration = bounds[bound_index] if bounds else 0.0
            oral = self._oral_ates(component.acute_toxicity_estimates)
            other_routes = [a.route for a in component.acute_toxicity_estimates if a not in oral]
            if other_routes:
                warnings.append(
                    f"{component.component_name}: ignored non-oral ATE evidence ({', '.join(sorted(set(other_routes)))})."
                )
            if component.specific_concentration_limits:
                warnings.append(f"{component.component_name}: SCL evidence preserved but not substituted for an oral ATE.")
            if component.generic_concentration_limits:
                warnings.append(f"{component.component_name}: GCL evidence preserved separately and not substituted for an oral ATE.")
            if component.cut_off_values:
                warnings.append(f"{component.component_name}: supplied cut-off evidence preserved separately from the rule's applicable acute-toxicity cut-off.")
            if component.calculation_thresholds:
                warnings.append(f"{component.component_name}: calculation-threshold evidence preserved separately from GCLs and SCLs.")
            if component.m_factors:
                warnings.append(f"{component.component_name}: M-factor evidence is not used in acute-toxicity calculation.")

            if len(oral) > 1:
                unknown_total += concentration
                largest_unknown = max(largest_unknown, concentration)
                decision = "Multiple oral ATE values; no value selected silently; treated as unknown for this scenario."
                trace.append(self._trace(component, name, concentration, None, None, False, decision))
                continue
            if not oral:
                if component.acute_oral_not_toxic_evidence:
                    decision = "Excluded based on explicit evidence that the component is not acutely toxic by the oral route."
                    trace.append(self._trace(component, name, concentration, None, None, False, decision))
                else:
                    unknown_total += concentration
                    largest_unknown = max(largest_unknown, concentration)
                    decision = "No usable oral ATE; concentration counted as unknown acute-toxicity information."
                    trace.append(self._trace(component, name, concentration, None, None, False, decision))
                continue

            ate = oral[0]
            if not self._supported_ate_unit(ate.unit):
                unknown_total += concentration
                largest_unknown = max(largest_unknown, concentration)
                decision = f"Unsupported oral ATE unit '{ate.unit}'; no conversion inferred; counted as unknown."
                trace.append(self._trace(component, name, concentration, ate, None, False, decision))
                continue
            cutoff = self._cutoff(ate.value)
            if cutoff is None or concentration < cutoff:
                reason = "ATE exceeds implemented oral category bands" if cutoff is None else f"below the {cutoff:g}% cut-off value"
                decision = f"Excluded: {reason}. Cut-off is distinct from GCL, SCL, and classification threshold."
                trace.append(self._trace(component, name, concentration, ate, None, False, decision))
                continue
            contribution = concentration / ate.value
            contribution_sum += contribution
            decision = f"Included as C_i/ATE_i = {concentration:g}/{ate.value:g} = {contribution:.8g}."
            trace.append(self._trace(component, name, concentration, ate, contribution, True, decision))

        if contribution_sum <= 0:
            steps.append(f"{name}: no positive C_i/ATE_i contribution was available.")
            return _Scenario(name, None, "", unknown_total, largest_unknown, tuple(trace), tuple(warnings), tuple(steps))
        if unknown_total >= 100:
            steps.append(f"{name}: unknown acute-toxicity concentration reached 100%; formula cannot be evaluated.")
            return _Scenario(name, None, "", unknown_total, largest_unknown, tuple(trace), tuple(warnings), tuple(steps))

        numerator = 100.0 if unknown_total <= 10.0 else 100.0 - unknown_total
        if unknown_total > 10:
            steps.append(
                f"{name}: unknown component total {unknown_total:g}% exceeds 10%; used corrected numerator 100 - unknown = {numerator:g}."
            )
        else:
            steps.append(f"{name}: unknown component total {unknown_total:g}% does not exceed 10%; used numerator 100.")
        mixture_ate = numerator / contribution_sum
        category = self._category(mixture_ate)
        steps.append(f"{name}: ATE_mix = {numerator:g}/{contribution_sum:.8g} = {mixture_ate:.8g} mg/kg bw; {category}.")
        return _Scenario(name, mixture_ate, category, unknown_total, largest_unknown, tuple(trace), tuple(warnings), tuple(steps))

    @staticmethod
    def _oral_ates(evidence: tuple[ATEEvidence, ...]) -> list[ATEEvidence]:
        return [item for item in evidence if item.route.strip().casefold() == "oral"]

    @staticmethod
    def _supported_ate_unit(unit: str) -> bool:
        return unit.strip().casefold() in {"mg/kg", "mg/kg bw", "mg/kg bodyweight", "mg/kg body weight"}

    @staticmethod
    def _category(value: float) -> str:
        if value <= 5:
            return "Acute Tox. 1 (oral)"
        if value <= 50:
            return "Acute Tox. 2 (oral)"
        if value <= 300:
            return "Acute Tox. 3 (oral)"
        if value <= 2000:
            return "Acute Tox. 4 (oral)"
        return "Not triggered by implemented oral ATE bands"

    @staticmethod
    def _cutoff(ate: float) -> float | None:
        if ate <= 300:
            return 0.1
        if ate <= 2000:
            return 1.0
        return None

    @staticmethod
    def _threshold_text(category: str) -> str:
        return {
            "Acute Tox. 1 (oral)": "0 < oral ATE <= 5 mg/kg bw (Category 1)",
            "Acute Tox. 2 (oral)": "5 < oral ATE <= 50 mg/kg bw (Category 2)",
            "Acute Tox. 3 (oral)": "50 < oral ATE <= 300 mg/kg bw (Category 3)",
            "Acute Tox. 4 (oral)": "300 < oral ATE <= 2000 mg/kg bw (Category 4)",
            "Not triggered by implemented oral ATE bands": "oral ATE > 2000 mg/kg bw",
        }.get(category, "")

    @staticmethod
    def _trace(
        component: MixtureComponent,
        scenario: str,
        concentration: float,
        ate: ATEEvidence | None,
        contribution: float | None,
        included: bool,
        decision: str,
    ) -> CalculationTraceRow:
        concentration_provenance = component.concentration.provenance
        ate_provenance = ate.provenance if ate else None
        return CalculationTraceRow(
            component_name=component.component_name,
            concentration=f"{concentration:g} {component.concentration.unit}",
            oral_ate=ate.value if ate else None,
            ate_unit=ate.unit if ate else "",
            ate_source=ate.source_kind if ate else "",
            contribution=contribution,
            included=included,
            decision=decision,
            scenario=scenario,
            provenance={
                "concentration": {
                    "source": concentration_provenance.source,
                    "authority_level": concentration_provenance.authority_level,
                    "dataset_snapshot": concentration_provenance.dataset_snapshot,
                    "retrieval_date": concentration_provenance.retrieval_date,
                    "reference": concentration_provenance.reference,
                },
                "oral_ate": None if ate_provenance is None else {
                    "source": ate_provenance.source,
                    "authority_level": ate_provenance.authority_level,
                    "dataset_snapshot": ate_provenance.dataset_snapshot,
                    "retrieval_date": ate_provenance.retrieval_date,
                    "reference": ate_provenance.reference,
                    "harmonised": ate.harmonised,
                },
            },
        )

    def _result(
        self,
        *,
        status: ClassificationStatus,
        route: EvidenceRoute,
        steps: tuple[str, ...],
        warnings: tuple[str, ...],
        manual: bool,
        category: str = "",
        trace: tuple[CalculationTraceRow, ...] = (),
        calculated: float | None = None,
        calculated_range: tuple[float, float] | None = None,
        threshold: str = "",
        unknown: float | None = None,
    ) -> HazardRuleResult:
        return HazardRuleResult(
            hazard_class=self.hazard_class,
            legal_basis=self.legal_basis,
            rule_version=self.rule_version,
            applicability_date=self.applicability_date,
            required_inputs=self.required_inputs,
            calculation_method=self.calculation_method,
            decision_steps=steps,
            result=status,
            resulting_category=category,
            evidence_route=route,
            assumptions=(
                "Concentrations are evaluated on the supplied percentage basis; no basis conversion is inferred.",
                "Concentration ranges are evaluated at their bounds; no midpoint is used.",
                "No purity adjustment is made unless already reflected in the supplied concentration.",
                "Only acute toxicity by the oral route is evaluated.",
            ),
            warnings=warnings,
            manual_review_required=manual,
            source_reference=self.source_reference,
            calculation_trace=trace,
            calculated_mixture_ate=calculated,
            calculated_mixture_ate_range=calculated_range,
            classification_threshold_used=threshold,
            unknown_component_percentage=unknown,
        )

    @staticmethod
    def _unique(values) -> tuple[str, ...]:
        return tuple(dict.fromkeys(values))
