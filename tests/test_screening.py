from chemreg_intel.demo import demo_inputs, demo_service
from chemreg_intel.models import ChemicalInput, DecisionStatus
from chemreg_intel.service import duplicate_rows


def test_svhc_match_retains_provenance():
    result = demo_service().screen([demo_inputs()[0]])[0]
    assert result.svhc.status == DecisionStatus.CONFIRMED_MATCH
    assert result.svhc.source is not None
    assert result.svhc.source.synthetic is True
    assert result.svhc.source.source_reference


def test_restriction_match_requires_review_when_complex():
    result = demo_service().screen([demo_inputs()[1]])[0]
    assert result.restriction.status == "POTENTIAL RESTRICTION MATCH"
    assert result.restriction.conditions_or_thresholds
    assert result.restriction.manual_review_required


def test_unresolved_identity_stops_regulatory_match():
    result = demo_service().screen([ChemicalInput("Unknownium")])[0]
    assert result.svhc.status == DecisionStatus.MANUAL_REVIEW
    assert result.restriction.status == DecisionStatus.MANUAL_REVIEW


def test_no_match_never_becomes_compliance_claim():
    result = demo_service().screen([demo_inputs()[2]])[0]
    statuses = [result.svhc.status, result.restriction.status, *[item.status for item in result.clp]]
    assert DecisionStatus.NO_MATCH in statuses
    assert all("COMPLIANT" not in status and "NOT REGULATED" not in status for status in statuses)


def test_duplicates_are_retained_and_reported():
    items = [demo_inputs()[0], demo_inputs()[0]]
    items[0].input_row, items[1].input_row = 2, 3
    assert duplicate_rows(items) == {("cas", "71-43-2"): [2, 3]}
    results = demo_service().screen(items)
    assert len(results) == 2
    assert "Duplicate identifier" in results[0].reviewer_notes
