from chemreg_intel.sds import review_sds, review_sds_consistency


def test_missing_sections_are_flagged():
    findings = review_sds({"1": "Product", "2": "Hazards"})
    sections = {item["section"] for item in findings}
    assert "3" in sections and "15" in sections
    assert all(item["severity"] == "MANUAL REVIEW REQUIRED" for item in findings)


def test_sds_consistency_reports_missing_evidence_without_invalidity_claim():
    sections = {section: "present" for section in ("1", "2", "3", "8", "9", "11", "12")}
    sections["15"] = "No SVHC substances"
    findings = review_sds_consistency(sections, [{
        "section": "15", "evidence_type": "Candidate List match",
        "value": "NMP Candidate List inclusion", "contradictory_claim": "No SVHC substances",
        "source_reference": "https://echa.europa.eu/candidate-list-table",
    }])
    assert len(findings) == 1
    assert findings[0]["severity"] == "MANUAL REVIEW REQUIRED"
    assert "conflicts" in findings[0]["finding"]
    assert "does not determine" in findings[0]["interpretation"]
    assert "invalid" in findings[0]["interpretation"]


def test_sds_consistency_reports_missing_identity_and_hazard_text():
    sections = {section: "present" for section in ("1", "2", "3", "8", "9", "11", "12", "15")}
    findings = review_sds_consistency(sections, [
        {"section": "3", "evidence_type": "composition identity", "value": "872-50-4", "source_reference": "case snapshot"},
        {"section": "2", "evidence_type": "harmonised hazard evidence", "value": "H360D", "source_reference": "EUR-Lex"},
    ])
    assert {item["section"] for item in findings} == {"2", "3"}
    assert all(item["severity"] == "MANUAL REVIEW REQUIRED" for item in findings)
