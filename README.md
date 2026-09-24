# ChemReg Intel

**Chemical Regulatory Screening & Evidence Workbench**

ChemReg Intel is a zero-cost, local-first Python application for screening chemical lists against independently loadable regulatory evidence datasets. It preserves identity uncertainty, source provenance, and manual-review requirements. It is an evidence tool, not a legal certification system.

> ChemReg Intel is public-source software. Regulatory datasets may be subject to separate licensing and redistribution restrictions and are therefore user-supplied or stored locally where required.

## Current MVP

- CSV, XLSX, and manual chemical input
- CAS checksum validation, EC normalization, exact identity matching, synonyms, and suggestion-only fuzzy matching
- Independent SVHC, REACH restriction, and CLP/GHS evidence screeners
- Structured SDS completeness review for Sections 1, 2, 3, 8, 9, 11, 12, and 15
- Excel, CSV summary, and JSON exports
- Provenance retained in every evidence record and a dedicated Source Register
- Explicit ambiguity and manual-review handling
- Clearly labeled synthetic demo records; no bundled record is an official regulatory claim

## Run locally

```powershell
cd D:\ChemReg_Intel
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
streamlit run app.py
```

Run tests:

```powershell
pytest -q
```

## Input columns

Imports accept common headings such as `chemical name`, `CAS number`, `EC number`, `concentration`, and `supplier`. CSV and XLSX are supported.

## Dataset integration

The screeners accept independent record collections plus a required `SourceRecord`. A source cannot be created without its name, reference, version, retrieval date, and regulatory-list name. Production use should replace `chemreg_intel/demo.py` with separately acquired, legally reusable, versioned public datasets and add dataset-specific parsers and validation tests.

### Official Candidate List snapshots

Milestone 2 adds a production source-adapter contract and an immutable SQLite snapshot store. Automatic ECHA collection is intentionally disabled based on the ECHA legal notice. Export the Candidate List manually from the official page, then import the user-supplied file privately:

```powershell
python -m chemreg_intel.regulatory.cli --store data/regulatory import-candidate-list .\candidate-list.csv --retrieval-date 2026-09-24 --effective-date 2026-02-04 --version "official-export-2026-02"
python -m chemreg_intel.regulatory.cli --store data/regulatory list
python -m chemreg_intel.regulatory.cli --store data/regulatory check-update "echa-candidate-list:DATASET_HASH"
```

Each import retains the raw snapshot, normalized records, SHA-256 checksum, record count, effective date, source authority, legal-notice details, and validation report. Changed content creates a new dataset ID; historical snapshots and pinned screening runs are immutable.

See [regulatory source governance](docs/regulatory_sources.md) and the [official-data validation protocol](docs/validation_protocol.md).

### REACH Annex XVII snapshots

Annex XVII uses two separately versioned sources. Import a user-supplied ECHA CSV/XLSX snapshot for structured screening, then a reviewer-curated EUR-Lex JSON reference manifest for legal authority:

```powershell
python -m chemreg_intel.regulatory.cli --store data/regulatory import-annex-xvii .\annex-xvii.csv --retrieval-date 2026-09-24 --effective-date 2026-07-14 --version "echa-export-2026-07-14"
python -m chemreg_intel.regulatory.cli --store data/regulatory import-annex-xvii-legal .\annex-xvii-legal.json --retrieval-date 2026-09-24 --effective-date 2026-07-14 --version "legal-references-v1"
```

Restriction results are entry-centric and return `POTENTIAL RESTRICTION MATCH`, never pass/fail. Exact identifiers, explicit group evidence, possible group matches, article/mixture/use scope, thresholds, exemptions, derogations, transition dates, and future-effective entries remain visible and require manual review.

### CLP Annex VI Part 3 snapshots

The harmonised-classification module keeps ECHA convenience data separate from legally binding Official Journal entries:

```powershell
python -m chemreg_intel.regulatory.cli --store data/regulatory import-clp-annex-vi .\echa-annex-vi.xlsx --retrieval-date 2026-09-24 --version "user-supplied-echa-version"
python -m chemreg_intel.regulatory.cli --store data/regulatory import-clp-annex-vi-legal .\clp-legal-entries.json --retrieval-date 2026-09-24 --version "reviewed-legal-manifest-v1"
```

The model preserves each hazard row, SCL, M-factor, ATE, note, form scope, ATP, and application date independently. It does not perform mixture classification and every match warns that other hazard classes may require classification separately.

### CLP mixture-classification foundation

Milestone 2D adds a hazard-specific rule framework and a deliberately narrow pilot for **acute toxicity — oral route**. It keeps mixture-level data, component evidence, harmonised classifications, other classifications, ATEs, SCLs, M-factors, concentration bounds, and provenance separate. The oral pilot follows the evidence order of mixture data, bridging evidence, component calculation, then insufficient evidence.

The pilot evaluates exact concentrations and the bounds of disclosed/confidential ranges without inventing a midpoint. Its exportable result includes the legal basis and rule version, applicability date, evidence route, category threshold, calculated ATE or ATE range, unknown-component percentage, assumptions, warnings, and a component-by-component calculation trace. Historical results can be stored with the immutable screening-run store.

Bridging-principle types are represented but intentionally return `BRIDGING PRINCIPLE NOT YET IMPLEMENTED` and require manual review. Dermal and inhalation ATEs are never converted to oral values. SCLs, GCLs, acute-toxicity cut-off values, classification bands, M-factors, and ATEs remain distinct.

See the [CLP oral mixture validation record](docs/validation/clp_mixture_oral_validation.md).

## Data, privacy, and licensing

This repository contains source code, tests, schemas, synthetic demonstration data, small legally redistributable fixtures, documentation, public case-study assets, and adapters for datasets supplied by the user. The formulation in the validation case study is synthetic and does not represent a commercial product.

The repository does **not** contain official bulk ECHA exports, proprietary CAS datasets, client files or SDS documents, confidential regulatory data, private dataset snapshots, local regulatory databases, credentials, or secrets. Imported source datasets and generated local databases are ignored by Git and must remain in access-controlled local storage. Before contributing data, confirm its provenance and redistribution terms; when reuse is unclear, contribute only the importer, schema, and a synthetic or manually curated minimal fixture.

No software license has been added because the project's intended reuse terms have not yet been confirmed. In the absence of a license, copyright law reserves reuse rights by default. Regulatory data and third-party materials remain subject to their own terms regardless of any future software license.

See [SECURITY.md](SECURITY.md) for private vulnerability reporting and sensitive-data handling.

## Decision language

Only these statuses are emitted: `CONFIRMED MATCH`, `NO MATCH IN CHECKED SOURCE`, `AMBIGUOUS`, `MANUAL REVIEW REQUIRED`, and `NOT ASSESSED`. A no-match result is limited to the checked dataset and never means compliant, safe, legal, approved, or unrestricted.

## Known gaps

- The ECHA Candidate List adapter is implemented, but no official ECHA dataset is bundled or automatically refreshed due to ECHA database-reuse restrictions.
- Broad C&L Inventory/self-classification, full mixture classification, automated bridging, non-oral acute-toxicity calculations, and ECHA CHEM remain intentionally unimplemented. Harmonised CLP Annex VI Part 3 is supported through separate ECHA informational and EUR-Lex legal layers; the only mixture calculation is the scoped acute-toxicity oral pilot.
- Annex XVII scope, conditions, thresholds, and exemptions still require expert interpretation.
- The CLP/GHS module does not infer missing classifications. The oral acute-toxicity pilot derives only the result supported by its implemented rule and supplied evidence; it makes no whole-mixture safety or compliance determination.
- SDS review checks structured completeness only; it does not author or certify an SDS.
- Concentration-specific limits, group entries, salts, hydrates, UVCBs, polymers, and jurisdictional applicability need dedicated data and expert review.

## Notice

Regulatory databases change over time. Substance identity errors can invalidate screening. Mixture classification may depend on concentration and specific concentration limits. Harmonised classification and supplier self-classification are not the same. Regulatory interpretation may require expert review.
