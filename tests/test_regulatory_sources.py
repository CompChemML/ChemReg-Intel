import hashlib
import sqlite3

import pytest

from chemreg_intel.models import IdentityResult
from chemreg_intel.regulatory.adapters.echa_candidate_list import ECHACandidateListAdapter
from chemreg_intel.regulatory.conflicts import EvidenceClaim, compare_claims
from chemreg_intel.regulatory.metadata import AuthorityLevel, UpdateStatus
from chemreg_intel.regulatory.store import DatasetStore
from chemreg_intel.regulatory.registry import AdapterRegistry
from chemreg_intel.regulatory.updates import evaluate_update
from chemreg_intel.screening import SVHCScreener


CSV_ONE = b"Substance name,EC No.,CAS No.,Date of inclusion,Reason for inclusion,Decision\nTest substance alpha,200-753-7,71-43-2,04-Feb-2026,Test reason,TEST-1\n"
CSV_TWO = b"Substance name,EC No.,CAS No.,Date of inclusion,Reason for inclusion,Decision\nTest substance beta,203-625-9,108-88-3,25-Jun-2025,Second test reason,TEST-2\n"


def import_snapshot(tmp_path, payload=CSV_ONE, version="fixture-v1"):
    source_file = tmp_path / f"{version}.csv"
    source_file.write_bytes(payload)
    adapter = ECHACandidateListAdapter()
    imported = adapter.import_file(
        source_file, retrieval_date="2026-09-24",
        effective_date="2026-02-04", dataset_version=version,
    )
    raw, records, source, report = imported
    store = DatasetStore(tmp_path / "store")
    snapshot = store.add_snapshot(
        adapter_id=adapter.adapter_id, raw_filename=source_file.name,
        payload=raw, records=records, source=source, validation_report=report,
    )
    return adapter, store, snapshot, records, source, report


def test_candidate_list_import_normalizes_schema(tmp_path):
    _, _, snapshot, records, _, report = import_snapshot(tmp_path)
    assert report.valid
    assert snapshot.record_count == 1
    assert records[0] == {
        "substance_name": "Test substance alpha", "ec_number": "200-753-7",
        "cas_number": "71-43-2", "date_of_inclusion": "2026-02-04",
        "raw_ec_number": "200-753-7", "raw_cas_number": "71-43-2",
        "reason_for_inclusion": "Test reason", "candidate_list_status": "included",
        "decision_reference": "TEST-1", "source_row": 2,
    }


def test_candidate_import_detects_semicolon_delimiter_and_leading_title():
    payload = b"Candidate List export;;;;;\nSubstance name;EC Number;CAS Number;Date of inclusion;Reason for inclusion;Decision\nTest substance;200-753-7;71-43-2;04/02/2026;Test;D-1\n"
    adapter = ECHACandidateListAdapter()
    records = adapter.parse(payload, "candidate.csv")
    assert records[0]["source_row"] == 3
    assert records[0]["cas_number"] == "71-43-2"


def test_adapter_registry_is_pluggable_and_rejects_duplicate_ids():
    registry = AdapterRegistry()
    registry.register(ECHACandidateListAdapter())
    assert registry.adapter_ids() == ("echa-candidate-list",)
    assert isinstance(registry.get("echa-candidate-list"), ECHACandidateListAdapter)
    with pytest.raises(ValueError, match="already registered"):
        registry.register(ECHACandidateListAdapter())


def test_checksum_and_license_metadata(tmp_path):
    _, _, snapshot, _, source, _ = import_snapshot(tmp_path)
    assert source.checksum == hashlib.sha256(CSV_ONE).hexdigest()
    assert snapshot.checksum == source.checksum
    assert source.redistribution_allowed is False
    assert source.commercial_use_allowed is None
    assert source.automated_retrieval_allowed is False
    assert source.local_caching_allowed is True
    assert source.legal_notice_url == "https://echa.europa.eu/legal-notice"


def test_two_versions_are_preserved_and_reproducible(tmp_path):
    _, store, first, _, _, _ = import_snapshot(tmp_path, CSV_ONE, "fixture-v1")
    source_file = tmp_path / "fixture-v2.csv"
    source_file.write_bytes(CSV_TWO)
    adapter = ECHACandidateListAdapter()
    raw, records, source, report = adapter.import_file(
        source_file, retrieval_date="2026-09-24", effective_date="2025-06-25", dataset_version="fixture-v2"
    )
    second = store.add_snapshot(
        adapter_id=adapter.adapter_id, raw_filename=source_file.name,
        payload=raw, records=records, source=source, validation_report=report,
    )
    assert first.dataset_id != second.dataset_id
    assert store.load_records(first.dataset_id)[0]["substance_name"] == "Test substance alpha"
    assert store.load_records(second.dataset_id)[0]["substance_name"] == "Test substance beta"
    store.save_screening_run("run-1", [first.dataset_id], [{"cas": "71-43-2"}], [{"status": "CONFIRMED MATCH"}])
    assert store.load_screening_run("run-1")["dataset_ids"] == [first.dataset_id]


def test_identical_import_is_idempotent_not_replaced(tmp_path):
    adapter, store, first, records, source, report = import_snapshot(tmp_path)
    second = store.add_snapshot(
        adapter_id=adapter.adapter_id, raw_filename="renamed.csv",
        payload=CSV_ONE, records=records, source=source, validation_report=report,
    )
    assert second.dataset_id == first.dataset_id
    assert len(store.list_snapshots()) == 1


def test_snapshot_tables_reject_mutation(tmp_path):
    _, store, snapshot, _, _, _ = import_snapshot(tmp_path)
    with sqlite3.connect(store.database_path) as connection, pytest.raises(sqlite3.IntegrityError):
        connection.execute("UPDATE datasets SET version = 'changed' WHERE dataset_id = ?", (snapshot.dataset_id,))


def test_provenance_reaches_screening_result(tmp_path):
    adapter, store, snapshot, records, _, _ = import_snapshot(tmp_path)
    source_record = adapter.to_source_record(snapshot.source, snapshot.dataset_id)
    screener = SVHCScreener(source_record, adapter.to_screening_records(records))
    identity = IdentityResult("input", "71-43-2", "", "Test substance alpha", "71-43-2", "200-753-7", "CAS exact", 1.0, False, False)
    result = screener.screen(identity)[0]
    assert result.dataset_id == snapshot.dataset_id
    assert result.authority_level == "OFFICIAL REGULATORY DATABASE"
    assert result.source.checksum == snapshot.checksum
    assert "does not determine all legal obligations" in result.exemptions_or_notes
    assert result.manual_review_required
    assert "not a compliance conclusion" in result.review_notes


def test_candidate_source_requires_manual_update(tmp_path):
    adapter, _, _, _, source, _ = import_snapshot(tmp_path)
    report = adapter.check_for_update(source)
    assert report.status == UpdateStatus.MANUAL_UPDATE_REQUIRED


@pytest.mark.parametrize(
    "kwargs, expected",
    [
        ({"remote_version": "v1"}, UpdateStatus.CURRENT),
        ({"remote_version": "v2"}, UpdateStatus.UPDATE_AVAILABLE),
        ({"remote_version": None}, UpdateStatus.VERSION_UNKNOWN),
        ({"remote_version": None, "source_available": False}, UpdateStatus.SOURCE_UNAVAILABLE),
    ],
)
def test_generic_update_detection(kwargs, expected):
    assert evaluate_update("v1", **kwargs).status == expected


def test_conflicting_sources_are_displayed_not_silently_resolved():
    claims = [
        EvidenceClaim("EUR-Lex text", AuthorityLevel.LEGALLY_BINDING, "2026-01-01", "hazard", "A", "legal:1"),
        EvidenceClaim("Industry dossier", AuthorityLevel.INDUSTRY_SUBMITTED_DATA, "2025-01-01", "hazard", "B", "industry:1"),
    ]
    report = compare_claims(claims)
    assert report is not None
    assert report.manual_review_required
    assert report.claims[0].authority_level == AuthorityLevel.LEGALLY_BINDING
    assert "EUR-Lex text" in report.difference and "Industry dossier" in report.difference


def test_same_claim_has_no_conflict():
    claims = [
        EvidenceClaim("A", AuthorityLevel.OFFICIAL_REGULATORY_DATABASE, None, "status", "listed", "a:1"),
        EvidenceClaim("B", AuthorityLevel.SECONDARY_REFERENCE, None, "status", "listed", "b:1"),
    ]
    assert compare_claims(claims) is None


def test_no_match_language_remains_safe(tmp_path):
    adapter, _, snapshot, records, _, _ = import_snapshot(tmp_path)
    screener = SVHCScreener(adapter.to_source_record(snapshot.source, snapshot.dataset_id), adapter.to_screening_records(records))
    identity = IdentityResult("input", "64-17-5", "", "Ethanol", "64-17-5", "200-578-6", "CAS exact", 1.0, False, False)
    result = screener.screen(identity)[0]
    assert result.status == "NO MATCH IN CHECKED SOURCE"
    assert all(term not in result.status for term in ("NOT REGULATED", "SAFE", "LEGAL", "COMPLIANT"))
