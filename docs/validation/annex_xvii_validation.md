# Annex XVII validation record

Validation date: 2026-09-24

This is a manual cross-check of the small curated regression fixture. It is not a redistributed ECHA snapshot and is not a legal opinion. The fixture stores structured screening summaries and traceable legal references; it deliberately does not reproduce the full Annex XVII database.

## Authority sources checked

- ECHA restriction list: <https://echa.europa.eu/substances-restricted-under-reach>. The page described itself as last updated 14 July 2026 and reported 79 unique entries when checked. It is treated as `OFFICIAL INFORMATIONAL DATASET`.
- Current/consolidated REACH access point: <https://eur-lex.europa.eu/eli/reg/2006/1907>. Consolidated texts are used for navigation and temporal context; the authentic Official Journal acts and amending regulations supply legally binding authority.
- NMP amending act: <https://eur-lex.europa.eu/eli/reg/2018/588/oj>.
- Lead amending act: <https://eur-lex.europa.eu/eli/reg/2015/628/oj>.
- ECHA NMP entry information: <https://echa.europa.eu/documents/10162/5161f2bf-503c-2107-ab54-c087017d11c9>.

## Cases compared

| Case | ECHA structured result | EUR-Lex/OJ result | ChemReg fixture/result | Discrepancy |
|---|---|---|---|---|
| Entry 71, NMP exact CAS | Entry 71; CAS 872-50-4; EC 212-828-1 | Regulation 2018/588 adds entry 71 | Exact identifier produces `POTENTIAL RESTRICTION MATCH` | None in identifiers |
| Entry 71, mixture threshold | ECHA entry information describes a 0.3% trigger and worker-exposure conditions | Regulation 2018/588 contains the threshold, DNEL conditions, general 2020 date, and later 2024 wire-coating date | Threshold, mixture scope, use condition, transition/derogation, and legal reference retained | Full legal text is referenced, not bundled; manual review remains required |
| Entry 63, lead article scope | ECHA restriction guidance/navigation identifies entry 63 | Regulation 2015/628 includes article scope, a 0.05% concentration condition, release-rate route, listed exemptions, and an earlier-market derogation | Article scope, threshold, exemptions, derogation, effective date, and legal reference retained | Fixture summary is not exhaustive; the current consolidated entry must be checked |
| Entry 5, benzene identity | ECHA list identifies benzene as entry 5 with CAS 71-43-2 and EC 200-753-7 | Base REACH/OJ reference and later consolidated wording govern | Exact identifier match with legal reference and mandatory review | Detailed current conditions are intentionally not transcribed in the fixture |
| No-match control | Not present in the three-entry fixture | Not assessed against the entire Annex | Returns `NO MATCH IN CHECKED DATASET` | Expected limited-fixture result; never means unrestricted |
| Group/scope controls | Not represented as official fixture facts | Not represented as official fixture facts | Synthetic, explicitly labelled test entries exercise group, possible-group, and scope matching | Not a real-data validation case |

## Findings

- ECHA and EUR-Lex authority levels remain separate in every result.
- No identifier discrepancy was found in the three manually checked entries.
- The curated fixture is intentionally incomplete. Conditions for entries 5 and 63 are summarized and point to the legal source rather than reproducing all paragraphs.
- ECHA group rows and group membership cannot safely be reduced to CAS matching. Synthetic regression cases verify that unsupported name evidence produces only `POSSIBLE_GROUP_MATCH`.
- No official bulk snapshot was imported or redistributed. Production validation still requires a user-supplied official ECHA export and a reviewer-approved legal-reference manifest.

