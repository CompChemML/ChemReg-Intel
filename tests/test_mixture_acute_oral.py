from __future__ import annotations

import json

import pytest

from chemreg_intel.mixture import (
    ATEEvidence,
    AcuteToxicityOralRule,
    ClassificationStatus,
    ConcentrationEvidence,
    ConcentrationKind,
    EvidenceProvenance,
    EvidenceRoute,
    Mixture,
    MixtureComponent,
    ThresholdEvidence,
)
from chemreg_intel.regulatory.clp_annex_vi import MFactor, SpecificConcentrationLimit
from chemreg_intel.regulatory.store import DatasetStore


def provenance(source: str = "Formulator composition", *, authority: str = "USER_SUPPLIED", snapshot: str = "manual:case-1") -> EvidenceProvenance:
    return EvidenceProvenance(
        source=source,
        authority_level=authority,
        dataset_snapshot=snapshot,
        retrieval_date="2026-09-24",
        effective_or_applicability_date="2026-07-01",
        user_supplied=authority == "USER_SUPPLIED",
        reference="validation worksheet",
    )


def exact(value: float) -> ConcentrationEvidence:
    return ConcentrationEvidence(ConcentrationKind.EXACT, "% w/w", provenance(), value=value)


def range_(lower: float, upper: float, *, confidential: bool = False) -> ConcentrationEvidence:
    kind = ConcentrationKind.CONFIDENTIAL_RANGE if confidential else ConcentrationKind.RANGE
    return ConcentrationEvidence(kind, "% w/w", provenance(), lower=lower, upper=upper)


def ate(value: float, route: str = "oral", *, harmonised: bool = False, unit: str = "mg/kg bw") -> ATEEvidence:
    authority = "LEGALLY_BINDING" if harmonised else "USER_SUPPLIED"
    return ATEEvidence(
        route=route,
        value=value,
        unit=unit,
        source_kind="CLP Annex VI ATE" if harmonised else "supplier study",
        provenance=provenance("EUR-Lex Annex VI" if harmonised else "Supplier SDS", authority=authority, snapshot="clp:test-v1" if harmonised else "manual:case-1"),
        harmonised=harmonised,
    )


def component(name: str, concentration: ConcentrationEvidence, *ates: ATEEvidence, non_toxic: bool = False, **kwargs) -> MixtureComponent:
    return MixtureComponent(
        component_name=name,
        concentration=concentration,
        acute_toxicity_estimates=tuple(ates),
        acute_oral_not_toxic_evidence=non_toxic,
        **kwargs,
    )


def mixture(*components: MixtureComponent, **kwargs) -> Mixture:
    return Mixture("mix-1", "Validation mixture", list(components), **kwargs)


def evaluate(*components: MixtureComponent, **kwargs):
    return AcuteToxicityOralRule().evaluate(mixture(*components, **kwargs))


def test_one_component_oral_calculation_and_export_trace():
    result = evaluate(component("Toxicant", exact(100), ate(100)))
    assert result.result == ClassificationStatus.DERIVED
    assert result.resulting_category == "Acute Tox. 3 (oral)"
    assert result.calculated_mixture_ate == pytest.approx(100)
    assert result.evidence_route == EvidenceRoute.COMPONENT_CALCULATION
    exported = result.to_dict()
    assert exported["calculation_trace"][0]["provenance"]["concentration"]["authority_level"] == "USER_SUPPLIED"
    json.dumps(exported, default=str)


def test_multiple_components_use_additivity_formula():
    result = evaluate(
        component("Very toxic", exact(10), ate(5)),
        component("Toxic", exact(20), ate(50)),
        component("Water", exact(70), non_toxic=True),
    )
    assert result.calculated_mixture_ate == pytest.approx(100 / (10 / 5 + 20 / 50))
    assert result.resulting_category == "Acute Tox. 2 (oral)"
    assert sum(row.included for row in result.calculation_trace) == 2


def test_harmonised_oral_ate_provenance_is_preserved():
    result = evaluate(component("Annex VI component", exact(100), ate(50, harmonised=True)))
    evidence = result.calculation_trace[0].provenance["oral_ate"]
    assert evidence["authority_level"] == "LEGALLY_BINDING"
    assert evidence["harmonised"] is True
    assert evidence["dataset_snapshot"] == "clp:test-v1"


def test_range_is_calculated_at_bounds_without_midpoint():
    result = evaluate(
        component("Toxicant", range_(10, 20, confidential=True), ate(100)),
        component("Water", range_(80, 90), non_toxic=True),
    )
    assert result.result == ClassificationStatus.DERIVED
    assert result.resulting_category == "Acute Tox. 4 (oral)"
    assert result.calculated_mixture_ate_range == pytest.approx((500, 1000))
    assert {row.scenario for row in result.calculation_trace} == {"lower-bound", "upper-bound"}
    assert all("15" not in row.concentration for row in result.calculation_trace if row.component_name == "Toxicant")


def test_range_crossing_category_requires_manual_review():
    result = evaluate(
        component("Toxicant", range_(10, 30), ate(10)),
        component("Water", range_(70, 90), non_toxic=True),
    )
    assert result.result == ClassificationStatus.MANUAL_REVIEW
    assert "Acute Tox. 2" in result.resulting_category
    assert "Acute Tox. 3" in result.resulting_category
    assert result.manual_review_required


def test_unknown_component_over_ten_percent_uses_corrected_formula_and_requires_review():
    result = evaluate(
        component("Known toxicant", exact(20), ate(100)),
        component("Unknown", exact(20)),
        component("Water", exact(60), non_toxic=True),
    )
    assert result.calculated_mixture_ate == pytest.approx(400)
    assert result.unknown_component_percentage == pytest.approx(20)
    assert result.result == ClassificationStatus.MANUAL_REVIEW
    assert any("corrected numerator" in step for step in result.decision_steps)


def test_unknown_component_below_one_percent_keeps_regular_formula():
    result = evaluate(
        component("Known toxicant", exact(10), ate(100)),
        component("Trace unknown", exact(0.5)),
        component("Water", exact(89.5), non_toxic=True),
    )
    assert result.calculated_mixture_ate == pytest.approx(1000)
    assert result.result == ClassificationStatus.DERIVED
    assert not result.manual_review_required


def test_missing_concentration_is_insufficient_and_not_assumed():
    unknown = ConcentrationEvidence(ConcentrationKind.UNKNOWN, "% w/w", provenance(), statement="not disclosed")
    result = evaluate(component("Undisclosed", unknown, ate(10)))
    assert result.result == ClassificationStatus.INSUFFICIENT_DATA
    assert result.manual_review_required
    assert "assumed" in result.warnings[0]


def test_non_oral_ate_is_not_converted_or_used():
    result = evaluate(
        component("Route mismatch", exact(10), ate(50, route="dermal"), ate(2, route="inhalation")),
        component("Water", exact(90), non_toxic=True),
    )
    assert result.result == ClassificationStatus.INSUFFICIENT_DATA
    assert any("ignored non-oral" in warning for warning in result.warnings)


def test_mixture_level_oral_data_has_priority_over_components():
    result = evaluate(
        component("Component", exact(100), ate(5)),
        mixture_ate_evidence=(ate(500),),
    )
    assert result.evidence_route == EvidenceRoute.MIXTURE_DATA
    assert result.calculated_mixture_ate == 500
    assert result.resulting_category == "Acute Tox. 4 (oral)"
    assert not result.calculation_trace


def test_bridging_is_architected_but_not_implemented_and_does_not_fall_through():
    result = evaluate(
        component("Component", exact(100), ate(5)),
        bridging_principle_requested="dilution",
    )
    assert result.evidence_route == EvidenceRoute.BRIDGING_PRINCIPLE
    assert result.result == ClassificationStatus.MANUAL_REVIEW
    assert result.warnings[0] == "BRIDGING PRINCIPLE NOT YET IMPLEMENTED"
    assert result.calculated_mixture_ate is None


@pytest.mark.parametrize(
    ("value", "category"),
    [(5, "Acute Tox. 1"), (50, "Acute Tox. 2"), (300, "Acute Tox. 3"), (2000, "Acute Tox. 4")],
)
def test_category_boundaries(value, category):
    result = AcuteToxicityOralRule().evaluate(
        Mixture("m", "boundary", [], mixture_ate_evidence=(ate(value),))
    )
    assert result.resulting_category.startswith(category)


def test_no_trigger_language_never_claims_non_hazardous_or_compliant():
    result = AcuteToxicityOralRule().evaluate(
        Mixture("m", "high ATE", [], mixture_ate_evidence=(ate(2001),))
    )
    assert result.result == ClassificationStatus.NOT_TRIGGERED
    rendered = json.dumps(result.to_dict(), default=str).upper()
    assert "NON-HAZARDOUS" not in rendered
    assert "COMPLIANT" not in rendered
    assert "SAFE" not in rendered


def test_cutoff_is_distinguished_from_scl_gcl_and_m_factor():
    scl = SpecificConcentrationLimit("Skin Corr.", "1A", ">=", 5, "%", "Skin Corr. 1A")
    gcl = ThresholdEvidence("GCL", "Unrelated hazard", 10, "%", provenance())
    supplied_cutoff = ThresholdEvidence("CUT_OFF_VALUE", "Acute Toxicity — Oral", 0.1, "%", provenance())
    calculation_threshold = ThresholdEvidence("CALCULATION_THRESHOLD", "Acute Toxicity — Oral", 1, "%", provenance())
    result = evaluate(
        component(
            "Trace category 1", exact(0.05), ate(5),
            specific_concentration_limits=(scl,), generic_concentration_limits=(gcl,),
            cut_off_values=(supplied_cutoff,), calculation_thresholds=(calculation_threshold,),
            m_factors=(MFactor("Aquatic Acute", 10),),
        ),
        component("Water", exact(99.95), non_toxic=True),
    )
    trace = next(row for row in result.calculation_trace if row.component_name == "Trace category 1")
    assert not trace.included
    assert "Cut-off is distinct from GCL, SCL" in trace.decision
    assert any("SCL evidence preserved" in warning for warning in result.warnings)
    assert any("GCL evidence preserved" in warning for warning in result.warnings)
    assert any("calculation-threshold evidence" in warning for warning in result.warnings)
    assert any("M-factor evidence" in warning for warning in result.warnings)


def test_ambiguous_identity_stops_calculation():
    result = evaluate(component("Ambiguous", exact(100), ate(5), identity_ambiguity_flag=True))
    assert result.result == ClassificationStatus.AMBIGUOUS_COMPONENT
    assert result.manual_review_required


def test_invalid_composition_bounds_are_rejected_by_integrity_check():
    result = evaluate(component("Only disclosed part", range_(20, 40), ate(100)))
    assert result.result == ClassificationStatus.INSUFFICIENT_DATA
    assert "do not contain 100%" in result.decision_steps[0]


def test_historical_rule_version_is_persisted_with_screening_run(tmp_path):
    old_rule = AcuteToxicityOralRule(rule_version="clp-oral-pilot-historical-v1", applicability_date="2025-01-01")
    result = old_rule.evaluate(mixture(component("Toxicant", exact(100), ate(100))))
    store = DatasetStore(tmp_path / "regulatory")
    store.save_screening_run("mixture-run-1", [], {"mixture_id": "mix-1"}, result.to_dict())
    loaded = store.load_screening_run("mixture-run-1")
    assert loaded["results"]["rule_version"] == "clp-oral-pilot-historical-v1"
    assert loaded["results"]["applicability_date"] == "2025-01-01"


def test_provenance_enforces_user_supplied_label():
    with pytest.raises(ValueError, match="USER_SUPPLIED"):
        EvidenceProvenance("Manual", "SECONDARY_REFERENCE", "manual:x", "2026-09-24", user_supplied=True)


def test_concentration_unit_validation():
    with pytest.raises(ValueError, match="Concentration unit"):
        ConcentrationEvidence(ConcentrationKind.EXACT, "mg/L", provenance(), value=5)
