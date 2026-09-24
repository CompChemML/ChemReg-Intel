import json
from dataclasses import replace
from pathlib import Path

from chemreg_intel.regulatory.adapters.echa_clp_annex_vi import ECHACLPAnnexVIAdapter
from chemreg_intel.regulatory.adapters.eurlex_clp_annex_vi import EURLexCLPAnnexVIAdapter
from chemreg_intel.regulatory.clp_annex_vi import (
    CLPAnnexVIEngine,
    CLPIdentityInput,
    CLPMatchType,
    CLPResultStatus,
    CLPScreeningContext,
    HarmonisedEntry,
    HazardClassification,
    LawApplicationStatus,
)
from chemreg_intel.regulatory.metadata import AuthorityLevel
from chemreg_intel.regulatory.store import DatasetStore

FIXTURE = Path(__file__).parent / "fixtures" / "clp_annex_vi_eurlex_curated.json"


def legal_engine(tmp_path):
    adapter = EURLexCLPAnnexVIAdapter()
    raw, records, source, report = adapter.import_file(
        FIXTURE, retrieval_date="2026-09-24", effective_date="2026-09-24",
        dataset_version="curated-clp-validation-v1",
    )
    store = DatasetStore(tmp_path / "regulatory")
    snapshot = store.add_snapshot(
        adapter_id=adapter.adapter_id, raw_filename=FIXTURE.name,
        payload=raw, records=records, source=source, validation_report=report,
    )
    entries = adapter.to_entries(store.load_records(snapshot.dataset_id), snapshot.dataset_id, snapshot.source)
    return CLPAnnexVIEngine(entries), store, snapshot


def find_entry(engine, index_number):
    return next(entry for entry in engine.entries if entry.index_number == index_number)


def test_legal_manifest_import_and_provenance(tmp_path):
    engine, _, snapshot = legal_engine(tmp_path)
    assert snapshot.record_count == 4
    assert snapshot.source.authoritative_status == AuthorityLevel.LEGALLY_BINDING
    assert snapshot.source.redistribution_allowed is True
    for entry in engine.entries:
        assert entry.dataset_id == snapshot.dataset_id
        assert entry.source_version == "curated-clp-validation-v1"
        assert entry.checksum == snapshot.checksum
        assert entry.authority_level == AuthorityLevel.LEGALLY_BINDING


def test_exact_index_ec_and_cas_matching(tmp_path):
    engine, *_ = legal_engine(tmp_path)
    by_index = engine.screen(CLPIdentityInput(index_number="605-001-00-5"))[0]
    by_ec = engine.screen(CLPIdentityInput(ec_number="203-453-4"))[0]
    by_cas = engine.screen(CLPIdentityInput(cas_number="54-11-5"))[0]
    assert by_index.match_type == CLPMatchType.EXACT_INDEX_NUMBER_MATCH
    assert by_ec.match_type == CLPMatchType.EXACT_EC_MATCH
    assert by_cas.match_type == CLPMatchType.EXACT_CAS_MATCH
    assert by_cas.entry.index_number == "614-001-00-4"


def test_exact_name_match_does_not_use_fuzzy_matching(tmp_path):
    engine, *_ = legal_engine(tmp_path)
    exact = engine.screen(CLPIdentityInput(chemical_name="ozone"))[0]
    typo = engine.screen(CLPIdentityInput(chemical_name="ozon"))[0]
    assert exact.match_type == CLPMatchType.NAME_MATCH
    assert typo.match_type == CLPMatchType.NO_MATCH


def test_multi_hazard_entry_remains_structured(tmp_path):
    engine, *_ = legal_engine(tmp_path)
    ozone = find_entry(engine, "008-004-00-4")
    assert len(ozone.hazards) == 8
    assert {item.hazard_class_code for item in ozone.hazards} >= {"Ox. Gas", "Carc.", "Muta.", "STOT SE", "STOT RE"}
    assert all(hasattr(item, "hazard_statement_code") for item in ozone.hazards)


def test_scl_is_preserved_structurally_without_mixture_calculation(tmp_path):
    engine, *_ = legal_engine(tmp_path)
    formaldehyde = find_entry(engine, "605-001-00-5")
    scl = next(item for item in formaldehyde.specific_concentration_limits if item.classification_trigger == "H317")
    assert scl.hazard_class == "Skin Sens."
    assert scl.operator == ">="
    assert scl.threshold == 0.2
    assert scl.unit == "%"


def test_m_factors_are_independent_from_scls_and_ates(tmp_path):
    engine, *_ = legal_engine(tmp_path)
    acrolein = find_entry(engine, "605-008-00-3")
    assert [(item.hazard_context, item.value) for item in acrolein.m_factors] == [
        ("Aquatic Acute 1", 100.0), ("Aquatic Chronic 1", 1.0),
    ]
    assert acrolein.specific_concentration_limits[0].threshold == 0.1
    assert acrolein.acute_toxicity_estimates == ()


def test_ates_are_preserved_by_route(tmp_path):
    engine, *_ = legal_engine(tmp_path)
    nicotine = find_entry(engine, "614-001-00-4")
    assert {(item.route, item.value, item.unit) for item in nicotine.acute_toxicity_estimates} == {
        ("inhalation", 0.19, "mg/L"), ("dermal", 70.0, "mg/kg bw"), ("oral", 5.0, "mg/kg bw"),
    }
    assert nicotine.m_factors == ()


def test_notes_and_minimum_classification_force_partial_review(tmp_path):
    engine, *_ = legal_engine(tmp_path)
    result = engine.screen(CLPIdentityInput(index_number="605-001-00-5"))[0]
    assert result.status == CLPResultStatus.PARTIAL
    assert result.notes == ("B", "D")
    assert result.note_present
    assert "NOTE_PRESENT" in result.interpretation_note
    assert "minimum-classification" in result.interpretation_note
    assert result.manual_review_required


def test_uncovered_requested_hazard_class_uses_partial_wording(tmp_path):
    engine, *_ = legal_engine(tmp_path)
    result = engine.screen(
        CLPIdentityInput(cas_number="54-11-5"),
        CLPScreeningContext(requested_hazard_classes={"Acute Tox.", "Carc."}),
    )[0]
    assert result.status == CLPResultStatus.PARTIAL
    assert "Other hazard classes may require classification separately." in result.interpretation_note
    assert "FULLY CLASSIFIED" not in result.status


def test_future_application_and_voluntary_early_application(tmp_path):
    engine, *_ = legal_engine(tmp_path)
    result = engine.screen(
        CLPIdentityInput(index_number="008-004-00-4"),
        CLPScreeningContext(as_of_date="2026-09-24"),
    )[0]
    assert result.application_status == LawApplicationStatus.PUBLISHED_NOT_YET_APPLICABLE
    assert result.entry.voluntary_early_application_allowed is True
    assert "voluntary early application" in result.interpretation_note


def test_group_entry_is_not_assigned_without_membership_evidence():
    group = HarmonisedEntry(
        index_number="TEST-000-00-0", chemical_name="SYNTHETIC TEST: metal compounds",
        hazards=(HazardClassification("Carc.", "1B", "H350"),),
        authority_level=AuthorityLevel.SECONDARY_REFERENCE,
        is_group_entry=True, group_keys=("synthetic metal compounds",), dataset_id="synthetic:group:v1",
    )
    result = CLPAnnexVIEngine([group]).screen(CLPIdentityInput(index_number="TEST-000-00-0"))[0]
    assert result.status == CLPResultStatus.POSSIBLE_GROUP
    assert result.match_type == CLPMatchType.POSSIBLE_GROUP_ENTRY
    assert result.manual_review_required


def test_duplicate_identifier_with_different_forms_is_ambiguous_without_form(tmp_path):
    engine, *_ = legal_engine(tmp_path)
    ozone = find_entry(engine, "008-004-00-4")
    alternate = replace(ozone, index_number="008-004-00-5", form_or_physical_state_scope="solution", dataset_id="synthetic:alternate")
    results = CLPAnnexVIEngine([ozone, alternate]).screen(CLPIdentityInput(cas_number="10028-15-6"))
    assert len(results) == 2
    assert all(result.match_type == CLPMatchType.AMBIGUOUS_MATCH for result in results)
    resolved = CLPAnnexVIEngine([ozone, alternate]).screen(CLPIdentityInput(cas_number="10028-15-6", form_or_physical_state="gas"))
    assert len(resolved) == 1 and resolved[0].entry.index_number == "008-004-00-4"


def test_no_match_never_means_non_hazardous_safe_or_unclassified(tmp_path):
    engine, *_ = legal_engine(tmp_path)
    result = engine.screen(CLPIdentityInput(cas_number="64-17-5"))[0]
    assert result.status == CLPResultStatus.NO_MATCH
    assert result.match_type == CLPMatchType.NO_MATCH
    for forbidden in ("NON-HAZARDOUS", "SAFE", "UNCLASSIFIED"):
        assert forbidden not in result.status
    assert "does not mean non-hazardous" in result.interpretation_note


def test_harmonised_match_always_warns_about_other_hazards(tmp_path):
    engine, *_ = legal_engine(tmp_path)
    result = engine.screen(CLPIdentityInput(cas_number="107-02-8"))[0]
    assert result.status == CLPResultStatus.MATCH
    assert CLPAnnexVIEngine.disclaimer in result.interpretation_note


def test_echa_convenience_adapter_stays_informational(tmp_path):
    csv_path = tmp_path / "echa_schema_fixture.csv"
    csv_path.write_text(
        "Index No,Chemical Name,EC No,CAS No,Hazard Class Code,Hazard Category Code,Hazard Statement Code,Pictogram Code,Signal Word Code\n"
        "999-001-00-1,TEST SUBSTANCE,200-753-7,71-43-2,Carc.,1B,H350,GHS08,Dgr\n"
        "999-001-00-1,TEST SUBSTANCE,200-753-7,71-43-2,Muta.,1B,H340,GHS08,Dgr\n",
        encoding="utf-8",
    )
    adapter = ECHACLPAnnexVIAdapter()
    raw, records, source, report = adapter.import_file(csv_path, retrieval_date="2026-09-24", dataset_version="schema-fixture", effective_date=None)
    assert report.valid and len(records[0]["hazards"]) == 2
    assert source.authoritative_status == AuthorityLevel.OFFICIAL_INFORMATIONAL_DATASET
    assert source.redistribution_allowed is False
    assert source.commercial_use_allowed is False


def test_authority_layers_are_not_merged(tmp_path):
    engine, *_ = legal_engine(tmp_path)
    legal = find_entry(engine, "605-001-00-5")
    informational = replace(
        legal, authority_level=AuthorityLevel.OFFICIAL_INFORMATIONAL_DATASET,
        informational_reference="https://echa.europa.eu/information-on-chemicals/annex-vi-to-clp",
        dataset_id="echa:separate-snapshot", source_version="echa-convenience",
    )
    results = CLPAnnexVIEngine([legal, informational]).screen(CLPIdentityInput(index_number="605-001-00-5"))
    assert len(results) == 2
    assert {result.entry.authority_level for result in results} == {
        AuthorityLevel.LEGALLY_BINDING, AuthorityLevel.OFFICIAL_INFORMATIONAL_DATASET,
    }
    assert {result.entry.dataset_id for result in results} == {legal.dataset_id, "echa:separate-snapshot"}


def test_historical_legal_snapshots_are_reproducible(tmp_path):
    _, store, first = legal_engine(tmp_path)
    first_records = store.load_records(first.dataset_id)
    document = json.loads(FIXTURE.read_text(encoding="utf-8"))
    document["records"][0]["atp_or_amending_act"] = "Historical test revision"
    changed = tmp_path / "clp_revision.json"
    changed.write_text(json.dumps(document), encoding="utf-8")
    adapter = EURLexCLPAnnexVIAdapter()
    raw, records, source, report = adapter.import_file(changed, retrieval_date="2027-02-01", effective_date="2027-02-01", dataset_version="curated-clp-validation-v2")
    second = store.add_snapshot(adapter_id=adapter.adapter_id, raw_filename=changed.name, payload=raw, records=records, source=source, validation_report=report)
    assert second.dataset_id != first.dataset_id
    assert store.load_records(first.dataset_id) == first_records
    assert store.load_records(second.dataset_id)[0]["atp_or_amending_act"] == "Historical test revision"

