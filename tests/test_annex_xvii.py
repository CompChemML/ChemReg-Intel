from dataclasses import replace
from pathlib import Path

from chemreg_intel.models import IdentityResult
from chemreg_intel.regulatory.adapters.echa_annex_xvii import ECHAAnnexXVIIAdapter
from chemreg_intel.regulatory.adapters.eurlex_annex_xvii import EURLexAnnexXVIIReferenceAdapter
from chemreg_intel.regulatory.annex_xvii import (
    AnnexXVIIEngine,
    AnnexXVIIEntry,
    MANUAL_REVIEW,
    NO_MATCH,
    POTENTIAL_MATCH,
    RestrictionContext,
    RestrictionMatchType,
)
from chemreg_intel.regulatory.metadata import AuthorityLevel
from chemreg_intel.regulatory.store import DatasetStore

FIXTURES = Path(__file__).parent / "fixtures"


def identity(name, cas="", ec="", *, ambiguous=False):
    return IdentityResult(name, cas, ec, name, cas, ec, "test exact", 1.0, ambiguous, ambiguous)


def official_engine(tmp_path):
    store = DatasetStore(tmp_path / "regulatory")
    echa = ECHAAnnexXVIIAdapter()
    raw, records, source, report = echa.import_file(
        FIXTURES / "annex_xvii_echa_curated.csv", retrieval_date="2026-09-24",
        effective_date="2026-07-14", dataset_version="curated-validation-2026-07-14",
    )
    structured_snapshot = store.add_snapshot(
        adapter_id=echa.adapter_id, raw_filename="annex_xvii_echa_curated.csv",
        payload=raw, records=records, source=source, validation_report=report,
    )
    eurlex = EURLexAnnexXVIIReferenceAdapter()
    legal_raw, legal_records, legal_source, legal_report = eurlex.import_file(
        FIXTURES / "annex_xvii_eurlex_references.json", retrieval_date="2026-09-24",
        effective_date="2026-07-14", dataset_version="curated-legal-references-v1",
    )
    legal_snapshot = store.add_snapshot(
        adapter_id=eurlex.adapter_id, raw_filename="annex_xvii_eurlex_references.json",
        payload=legal_raw, records=legal_records, source=legal_source, validation_report=legal_report,
    )
    entries = echa.to_entries(store.load_records(structured_snapshot.dataset_id), structured_snapshot.dataset_id)
    references = eurlex.to_references(store.load_records(legal_snapshot.dataset_id), legal_snapshot.dataset_id)
    return AnnexXVIIEngine(entries, references), store, structured_snapshot, legal_snapshot


def synthetic_group_entry(**overrides):
    values = dict(
        entry_number="TEST-GROUP", entry_title="SYNTHETIC TEST GROUP ENTRY",
        group_or_substance_scope="Synthetic chemical group used only for matching tests",
        eur_lex_reference="fixture-reference://synthetic-group",
        authority_level=AuthorityLevel.SECONDARY_REFERENCE,
        group_keys=("cmr consumer group",), manual_review_required=True,
        dataset_id="synthetic:test-group:v1",
    )
    values.update(overrides)
    return AnnexXVIIEntry(**values)


def test_echa_adapter_imports_entry_centric_schema(tmp_path):
    engine, _, structured, _ = official_engine(tmp_path)
    assert structured.record_count == 3
    nmp = next(entry for entry in engine.entries if entry.entry_number == "71")
    assert nmp.concentration_threshold == 0.3
    assert nmp.threshold_unit == "% w/w"
    assert nmp.exemptions == ""
    assert nmp.derogations
    assert nmp.authority_level == AuthorityLevel.OFFICIAL_INFORMATIONAL_DATASET


def test_source_licenses_and_authority_layers_are_preserved(tmp_path):
    _, _, structured, legal = official_engine(tmp_path)
    assert structured.source.redistribution_allowed is False
    assert structured.source.commercial_use_allowed is None
    assert structured.source.authoritative_status == AuthorityLevel.OFFICIAL_INFORMATIONAL_DATASET
    assert legal.source.redistribution_allowed is True
    assert legal.source.authoritative_status == AuthorityLevel.LEGALLY_BINDING


def test_exact_cas_and_ec_matches(tmp_path):
    engine, *_ = official_engine(tmp_path)
    cas_result = engine.screen(identity("NMP", "872-50-4"))[0]
    ec_result = engine.screen(identity("NMP", ec="212-828-1"))[0]
    assert cas_result.status == POTENTIAL_MATCH
    assert cas_result.match_type == RestrictionMatchType.EXACT_IDENTIFIER_MATCH
    assert ec_result.entry_number == "71"


def test_mixture_threshold_is_context_not_verdict(tmp_path):
    engine, *_ = official_engine(tmp_path)
    result = engine.screen(identity("NMP", "872-50-4"), RestrictionContext(0.4, "% w/w", subject_type="mixture"))[0]
    assert result.threshold == "0.3 % w/w"
    assert "at or above" in result.interpretation_note
    assert result.status == POTENTIAL_MATCH
    assert result.manual_review_required
    assert "NON-COMPLIANT" not in result.status


def test_article_specific_scope_and_exemption_are_preserved(tmp_path):
    engine, *_ = official_engine(tmp_path)
    result = engine.screen(identity("Lead", "7439-92-1"), RestrictionContext(0.1, "% w/w", subject_type="article"))[0]
    assert result.entry_number == "63"
    assert "article" in result.mixture_or_article_scope
    assert "brass" in result.exemptions
    assert result.derogations


def test_use_specific_condition_and_derogation_are_preserved(tmp_path):
    engine, *_ = official_engine(tmp_path)
    result = engine.screen(identity("NMP", "872-50-4"), RestrictionContext(intended_use="wire coating"))[0]
    assert "wire" in result.specific_use_conditions.lower()
    assert "later applicability" in result.derogations.lower()
    assert result.manual_review_required


def test_explicit_group_match_requires_evidence():
    engine = AnnexXVIIEngine([synthetic_group_entry()])
    context = RestrictionContext(group_memberships={"cmr consumer group"}, group_membership_evidence="Reviewer-supplied classification evidence")
    result = engine.screen(identity("Example substance", "71-43-2"), context)[0]
    assert result.match_type == RestrictionMatchType.GROUP_MATCH
    assert "Reviewer-supplied" in result.interpretation_note


def test_ambiguous_group_membership_is_only_possible_match():
    engine = AnnexXVIIEngine([synthetic_group_entry(group_keys=("example aromatic",))])
    result = engine.screen(identity("Example aromatic"))[0]
    assert result.match_type == RestrictionMatchType.POSSIBLE_GROUP_MATCH
    assert result.manual_review_required


def test_scope_match_does_not_infer_group_membership():
    entry = synthetic_group_entry(entry_number="TEST-SCOPE", group_keys=(), scope_tags=("consumer article",))
    result = AnnexXVIIEngine([entry]).screen(identity("Unknown article component"), RestrictionContext(scope_tags={"consumer article"}))[0]
    assert result.match_type == RestrictionMatchType.SCOPE_MATCH


def test_future_effective_date_is_flagged():
    future = synthetic_group_entry(
        entry_number="TEST-FUTURE", substance_name="Acetone", cas_number="67-64-1",
        group_or_substance_scope="Future synthetic test", effective_date="2030-01-01", group_keys=(),
    )
    result = AnnexXVIIEngine([future]).screen(identity("Acetone", "67-64-1"), as_of_date="2026-09-24")[0]
    assert "future-effective" in result.interpretation_note
    assert result.status == POTENTIAL_MATCH


def test_multiple_entries_for_one_substance_are_returned(tmp_path):
    official, *_ = official_engine(tmp_path)
    engine = AnnexXVIIEngine(official.entries + [synthetic_group_entry()], [ref for refs in official.legal_by_entry.values() for ref in refs])
    results = engine.screen(identity("Benzene", "71-43-2"), RestrictionContext(group_memberships={"cmr consumer group"}, group_membership_evidence="Explicit fixture evidence"))
    assert {result.entry_number for result in results} == {"5", "TEST-GROUP"}


def test_ambiguous_identity_stops_restriction_matching(tmp_path):
    engine, *_ = official_engine(tmp_path)
    result = engine.screen(identity("Lead", "7439-92-1", ambiguous=True))[0]
    assert result.status == MANUAL_REVIEW
    assert result.match_type == RestrictionMatchType.MANUAL_REVIEW_REQUIRED


def test_no_match_is_never_unrestricted_or_compliant(tmp_path):
    engine, *_ = official_engine(tmp_path)
    result = engine.screen(identity("Ethanol", "64-17-5"))[0]
    assert result.status == NO_MATCH
    assert result.match_type == RestrictionMatchType.NO_MATCH
    assert all(term not in result.status for term in ("UNRESTRICTED", "COMPLIANT", "SAFE", "LEGAL"))
    assert result.manual_review_required


def test_legal_provenance_stays_separate_from_echa_authority(tmp_path):
    engine, _, structured, legal = official_engine(tmp_path)
    result = engine.screen(identity("NMP", "872-50-4"))[0]
    assert result.authority_level == AuthorityLevel.OFFICIAL_INFORMATIONAL_DATASET
    assert result.legal_authority_level == AuthorityLevel.LEGALLY_BINDING
    assert result.structured_source_dataset_id == structured.dataset_id
    assert result.legal_source_dataset_id == legal.dataset_id
    assert result.legal_sources[0]["celex_number"] == "32018R0588"


def test_historical_annex_versions_remain_reproducible(tmp_path):
    engine, store, structured, _ = official_engine(tmp_path)
    original = store.load_records(structured.dataset_id)
    changed_payload = (FIXTURES / "annex_xvii_echa_curated.csv").read_bytes().replace(b"0.3;% w/w", b"0.4;% w/w", 1)
    changed_path = tmp_path / "annex_changed.csv"
    changed_path.write_bytes(changed_payload)
    adapter = ECHAAnnexXVIIAdapter()
    raw, records, source, report = adapter.import_file(changed_path, retrieval_date="2027-01-01", effective_date="2027-01-01", dataset_version="future-test-v2")
    second = store.add_snapshot(adapter_id=adapter.adapter_id, raw_filename=changed_path.name, payload=raw, records=records, source=source, validation_report=report)
    assert second.dataset_id != structured.dataset_id
    assert store.load_records(structured.dataset_id) == original
    assert store.load_records(second.dataset_id)[0]["concentration_threshold"] == 0.4


def test_matched_entry_never_becomes_non_compliant(tmp_path):
    engine, *_ = official_engine(tmp_path)
    for result in engine.screen(identity("NMP", "872-50-4"), RestrictionContext(9.0, "% w/w")):
        assert result.status == POTENTIAL_MATCH
        assert "NON-COMPLIANT" not in result.status
