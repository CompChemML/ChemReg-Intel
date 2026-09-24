from __future__ import annotations

REQUIRED_SECTIONS = ("1", "2", "3", "8", "9", "11", "12", "15")


def review_sds(sections: dict[str, str]) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    normalized = {str(key).replace("Section", "").strip(): str(value or "").strip() for key, value in sections.items()}
    for section in REQUIRED_SECTIONS:
        if not normalized.get(section):
            findings.append({"section": section, "severity": "MANUAL REVIEW REQUIRED", "finding": "Required review content is missing."})
    if normalized.get("2") and not normalized.get("15"):
        findings.append({"section": "15", "severity": "MANUAL REVIEW REQUIRED", "finding": "Hazard information exists but regulatory information is absent."})
    return findings


def review_sds_consistency(
    sections: dict[str, str],
    evidence_expectations: list[dict[str, str]],
) -> list[dict[str, str]]:
    """Compare structured SDS text with evidence without judging legal validity.

    Each expectation supplies ``section``, ``evidence_type``, ``value`` and
    ``source_reference``. Optional ``contradictory_claim`` identifies an SDS
    statement that conflicts with the evidence. This is deliberately a text
    consistency check; it does not decide whether a substance must legally be
    disclosed or whether the mixture is correctly classified.
    """
    findings = review_sds(sections)
    normalized = {str(key).replace("Section", "").strip(): str(value or "").strip() for key, value in sections.items()}
    for expectation in evidence_expectations:
        section = str(expectation.get("section", "")).strip()
        expected = str(expectation.get("value", "")).strip()
        contradictory = str(expectation.get("contradictory_claim", "")).strip()
        text = normalized.get(section, "")
        finding = ""
        if contradictory and contradictory.casefold() in text.casefold():
            finding = (
                f"SDS text contains '{contradictory}', which conflicts with checked "
                f"{expectation.get('evidence_type', 'regulatory evidence')}: {expected}."
            )
        elif expected and expected.casefold() not in text.casefold():
            finding = (
                f"Checked {expectation.get('evidence_type', 'evidence')} was not found in the supplied "
                f"Section {section} text: {expected}."
            )
        if finding:
            findings.append({
                "section": section,
                "severity": "MANUAL REVIEW REQUIRED",
                "finding": finding,
                "source_reference": str(expectation.get("source_reference", "")),
                "interpretation": (
                    "Potential consistency issue only. This check does not determine that the SDS is legally invalid."
                ),
            })
    return findings
