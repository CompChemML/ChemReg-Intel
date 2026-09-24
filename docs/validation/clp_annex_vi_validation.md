# CLP Annex VI Part 3 validation record

Validation date: 2026-09-24

This validation set is a small, manually curated transcription of selected Official Journal entries. It is not an ECHA spreadsheet or an Annex VI bulk redistribution. Each entry is pinned to a EUR-Lex reference and immutable snapshot checksum.

## Authority sources checked

- CLP base regulation and amendment history: <https://eur-lex.europa.eu/eli/reg/2008/1272/oj>.
- Formaldehyde and acrolein: Commission Regulation (EU) No 605/2014, <https://eur-lex.europa.eu/eli/reg/2014/605/2015-03-25/eng>.
- Nicotine ATE update: Commission Regulation (EU) 2018/1480, <https://eur-lex.europa.eu/eli/reg/2018/1480/oj>.
- Ozone and ATP 23 future application: Commission Delegated Regulation (EU) 2025/1222, <https://eur-lex.europa.eu/eli/reg_del/2025/1222/oj>.
- ECHA convenience table and disclaimer: <https://echa.europa.eu/information-on-chemicals/annex-vi-to-clp>.

The Official Journal acts are recorded as `LEGALLY BINDING`. ECHA's convenience data is recorded as `OFFICIAL INFORMATIONAL DATASET` and is never substituted for the legal text.

## Curated comparisons

| Entry | Validation purpose | Fields compared | Outcome/discrepancy |
|---|---|---|---|
| Formaldehyde, index 605-001-00-5 | Index match, multiple hazards, SCLs, minimum-classification markers, notes | CAS/EC/index; seven hazard rows; five SCL structures; Notes B and D | Transcribed fields agree with cited act. Historical application date is left unknown pending a complete amendment-chain review. |
| Nicotine, index 614-001-00-4 | Exact CAS, three route-specific ATE values | CAS/EC/index; four hazard rows; inhalation, dermal, and oral ATEs | Values agree with Regulation 2018/1480. Historical application date is not asserted in the fixture. |
| Acrolein, index 605-008-00-3 | Exact EC, M-factors, SCL, supplemental statement, note | Seven hazard rows; acute/chronic M-factors; Skin Corr. SCL; EUH071; Note D | Transcribed fields agree with cited Regulation 605/2014 table. |
| Ozone, index 008-004-00-4 | Future-effective ATP, multiple hazards, SCL, M-factor, ATE | Eight hazard rows; four SCLs; two M-factors; inhalation ATE; ATP 23 dates | Entry and values agree with Regulation 2025/1222. Application date is 1 February 2027 and voluntary early application is preserved. |
| Group-entry control | Unsupported group membership | Synthetic labelled fixture only | Correctly returns `POSSIBLE GROUP ENTRY`; not a legal-source validation case. |
| No-match control | Safe result language | Substance absent from four-entry fixture | Returns `NO MATCH IN CHECKED DATASET`; never non-hazardous, safe, or unclassified. |

## Quantities validated

- 4 legally referenced substance entries
- 26 separate harmonised hazard rows
- 10 structured specific concentration limits
- 4 M-factor records
- 4 ATE records
- 3 note codes across two substances
- 1 published but not-yet-applicable ATP entry

## Findings and limitations

- No transcription discrepancies were found in identifiers or the selected hazard/SCL/M-factor/ATE fields.
- The formaldehyde and acrolein records use a consolidated form of Regulation 605/2014 cited by EUR-Lex; a full amendment-chain audit remains necessary before production reliance.
- The fixture demonstrates legal-data normalization but is not a complete Annex VI dataset.
- No ECHA convenience spreadsheet was downloaded or redistributed because its displayed disclaimer says it is informational, must not be used commercially, and must not be reproduced further.
- The adapter exposes SCL, M-factor, and ATE evidence but intentionally performs no mixture-classification calculation.

