# Regulatory source governance

Reviewed on 2026-09-24. This register records implementation decisions, not legal advice. Terms must be rechecked when a source or its notice changes.

| Priority | Source | Authority level | Integration decision | Automated retrieval | Private local snapshot | Redistribution | Commercial reuse |
|---|---|---|---|---|---|---|---|
| A | ECHA Candidate List / SVHC | Official regulatory database | Implemented as user-supplied CSV/XLSX export | No | Yes, user-supplied only | No | Unknown; permission review required |
| B | REACH Annex XVII | Two layers: Official Journal/EUR-Lex legal acts are legally binding; ECHA restriction data is official informational/navigation material | Implemented as separate ECHA snapshot and EUR-Lex reference adapters | No ECHA automation; legal references are curated | Yes, user-supplied or curated references | ECHA snapshot: no; curated reference manifest: yes with attribution/conditions | ECHA snapshot: unknown; curated EUR-Lex references: permitted subject to reuse conditions |
| C | CLP Annex VI Part 3 | Two layers: Official Journal/EUR-Lex ATP acts are legally binding; ECHA convenience data is official informational | Implemented as a private ECHA CSV/XLSX adapter plus curated EUR-Lex legal-entry manifest | No ECHA automation | Yes, user-supplied ECHA snapshot or curated legal manifest | ECHA snapshot: no; small legal-reference manifest: yes subject to conditions | ECHA snapshot: no; curated legal references: subject to EU reuse conditions |
| D | ECHA CHEM | Depends on record; may contain industry-submitted and third-party data | Intentionally deferred pending downloadable-data-specific terms and schema stability | No | No adapter yet | Unclear | Unclear |
| E | EUR-Lex legal texts | Legally binding wording is in the Official Journal; EUR-Lex provides access | Curated legal-reference manifests implemented for Annex XVII and CLP Annex VI; CLP mixture rules cite the applicable consolidated legal text | No bulk-text automation | Curated references and rule-version records only | Subject to EUR-Lex/Commission reuse terms and third-party exclusions | Generally supported by the reuse framework subject to conditions |

## ECHA legal-notice decision

Source: <https://echa.europa.eu/legal-notice>, version displayed as **Version 10 - 04/06/2026** when reviewed.

The notice permits certain uses of ECHA material with attribution, integrity, and non-liability conditions, but excludes whole or substantial parts of databases from that general permission. It generally prohibits systematic automated collection, including scraping, mining, extraction, and reutilisation. It also identifies third-party rights in CAS information. Consequently:

- ChemReg Intel does not scrape ECHA.
- The Candidate List adapter accepts a snapshot the user exported from the official page.
- The snapshot is cached only in the user's private local store.
- Metadata records redistribution as disallowed and commercial use as unknown.
- The app stores a checksum, notice URL/version, source URL, retrieval date, effective date, authority level, and reuse decision with every snapshot.

The Candidate List page states that only the list published on that website is authentic and that inclusion may trigger obligations. ChemReg Intel therefore treats a match as evidence of list membership only and never infers the user's obligations.

## EUR-Lex reuse basis identified for later adapters

Commission Decision 2011/833/EU provides a reuse framework for Commission documents and allows conditions such as attribution, preservation of meaning, and non-liability. A source-specific review is still required before implementing automated retrieval or redistribution, particularly for excluded third-party material. Reference: <https://eur-lex.europa.eu/eli/dec/2011/833/oj>.

The authoritative REACH restriction wording must be tied to the Official Journal and relevant amending acts; a consolidated EUR-Lex text is useful but is not itself an authentic legal act. The ECHA restriction table is an official search aid and is not silently promoted to `LEGALLY BINDING` authority.

## Annex XVII implementation decision

The ECHA Annex XVII adapter imports only user-supplied CSV/XLSX snapshots and assigns `OFFICIAL INFORMATIONAL DATASET`. It never scrapes ECHA. The EUR-Lex adapter imports a separately curated JSON manifest of CELEX identifiers, Official Journal links, publication/effective/applicability dates, and amending acts. Those records retain their own `LEGALLY BINDING` authority and dataset IDs. Screening results expose both layers and never collapse them into one source.

See the [manual Annex XVII validation record](validation/annex_xvii_validation.md).

For CLP, ECHA states that only Table 3 of Annex VI and subsequent ATPs published in the Official Journal are official and legally binding. ECHA's convenience XLSX is informational and its displayed disclaimer says it must not be used commercially or reproduced further. The implemented adapters therefore keep the EUR-Lex/OJ legal layer separate from any ECHA convenience spreadsheet.

## CLP Annex VI implementation decision

The ECHA adapter accepts only user-supplied CSV/XLSX snapshots, disables automated retrieval, records commercial use and redistribution as disallowed, and assigns `OFFICIAL INFORMATIONAL DATASET`. The EUR-Lex adapter accepts a small normalized JSON manifest tied to Official Journal acts and assigns `LEGALLY BINDING`. Each hazard, SCL, M-factor, ATE, note, ATP date, and source snapshot remains independently structured and versioned.

See the [CLP Annex VI validation record](validation/clp_annex_vi_validation.md).

## CLP mixture-rule source decision

The acute-toxicity oral pilot is executable regulatory logic, not a new bulk dataset. Its formula, category bands, cut-off rules, unknown-component handling, legal basis, applicability date, and rule version are tied to the applicable CLP Annex I text on EUR-Lex. Numerical mixture and component inputs retain their own provenance. Harmonised Annex VI ATE evidence remains distinguishable from supplier or user evidence. No ECHA or EUR-Lex bulk content is bundled for this rule.

See the [CLP oral mixture validation record](validation/clp_mixture_oral_validation.md).
