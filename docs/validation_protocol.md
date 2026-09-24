# Official-data validation protocol

No ECHA dataset is committed to this repository. This avoids redistributing a whole regulatory dataset or third-party CAS information. Validation is performed against a user-supplied official export stored privately and pinned by checksum.

## Procedure

1. Export the current Candidate List as CSV or XLSX from <https://echa.europa.eu/candidate-list-table>.
2. Record the retrieval date, page/list effective date if known, displayed version, and legal-notice version.
3. Import it with `python -m chemreg_intel.regulatory.cli import-candidate-list ...`.
4. Record the generated dataset ID and SHA-256 checksum.
5. Select cases directly in the official page/export covering exact CAS, exact EC, group/no-identifier, name-only suggestion, positive Candidate List match, no-match, and ambiguous/conflicting supplied identity.
6. Compare substance name, EC, CAS, inclusion date, reason, status, decision reference, and match method field by field.
7. Record discrepancies without altering the imported snapshot. Correct parser logic in a new code revision and rerun against the same dataset ID.

## Validation log template

| Case | Dataset ID | Official page/export result | ChemReg result | Match | Discrepancy/reviewer |
|---|---|---|---|---|---|
| Exact CAS | | | | | |
| Exact EC | | | | | |
| Synonym/name | | | | | |
| Candidate List match | | | | | |
| Group entry | | | | | |
| No-match | | | | | |
| Ambiguous identity | | | | | |

Annex XVII group restriction and harmonised CLP cases remain blocked until their respective adapters are implemented; they must not be simulated with Candidate List data.

