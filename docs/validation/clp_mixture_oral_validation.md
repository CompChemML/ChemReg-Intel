# CLP mixture foundation — acute toxicity (oral) validation

Validation date: 2026-09-24  
Implementation: `AcuteToxicityOralRule`  
Rule version: `clp-annex-i-2026-07-01-oral-pilot-v1`  
Applicability date recorded by the rule: 2026-07-01

## Scope and authority

This is a narrow calculation-validation record, not a regulatory opinion. The implemented rule covers only acute toxicity by the oral route. It does not determine compliance, legality, general safety, a complete hazard profile, dermal or inhalation acute toxicity, or any other CLP mixture hazard class.

The legal source is Regulation (EC) No 1272/2008 (CLP), Annex I, especially sections 3.1.3.2, 3.1.3.3, 3.1.3.6.1 and 3.1.3.6.2.3 and Tables 1.1, 3.1.1 and 3.1.2. The stable legal landing page is <https://eur-lex.europa.eu/eli/reg/2008/1272>. The consolidated version checked for this rule was CELEX `02008R1272-20260701`.

ECHA Guidance on the Application of the CLP Criteria, Part 1, version 5.0 (November 2024), was used as official interpretive guidance for the additivity examples and unknown-component treatment: <https://echa.europa.eu/documents/10162/2324906/clp_part1_en.pdf>. Guidance is not assigned the same authority as the legal text.

No official bulk snapshot was imported or redistributed for Milestone 2D. Annex VI ATE values may be supplied from an existing versioned Annex VI snapshot, while composition and supplier values are marked with their actual provenance, including `USER_SUPPLIED` for manual input.

## Rules manually checked

| Item | Implemented behavior | Manual comparison outcome |
|---|---|---|
| Evidence hierarchy | Mixture oral data; bridging evidence; component calculation; insufficient evidence | Aligned; the engine stops at the first applicable route |
| Additivity formula | `100 / ATE_mix = sum(C_i / ATE_i)` | Aligned |
| Unknown components above 10% | Uses the adjusted numerator `100 - sum(C_unknown)` | Aligned |
| Unknown component at or above 1% | Calculation is retained as provisional and result requires manual review | Conservative handling aligned with the legal limitation on a definitive estimate |
| Oral category 1 | `0 < ATE <= 5 mg/kg bw` | Aligned |
| Oral category 2 | `5 < ATE <= 50 mg/kg bw` | Aligned |
| Oral category 3 | `50 < ATE <= 300 mg/kg bw` | Aligned |
| Oral category 4 | `300 < ATE <= 2000 mg/kg bw` | Aligned |
| Acute-toxicity cut-offs | Categories 1–3: 0.1%; category 4: 1% | Aligned and labelled as cut-off values, not GCLs/SCLs |
| Route specificity | Dermal/inhalation evidence is ignored for the oral calculation | Aligned; no route conversion is inferred |
| Concentration ranges | Lower and upper bounds are both evaluated | Conservative implementation choice; no midpoint is invented |
| Bridging | Types are represented but no automated conclusion is made | Intentionally not implemented |

## Curated validation cases

The regression suite contains the following manually curated cases:

1. One oral-toxic component at 100%.
2. Several oral-toxic components using the additivity formula.
3. A harmonised oral ATE whose legal provenance must survive into the trace.
4. A confidential concentration range whose two bounds remain visible.
5. A range spanning two classification categories, requiring manual review.
6. Unknown acute-toxicity components above 10%, invoking the adjusted formula.
7. A trace unknown component below 1%.
8. Missing concentration data, producing `INSUFFICIENT DATA`.
9. Dermal/inhalation-only ATE evidence, which is not reused for the oral route.
10. Mixture-level oral ATE evidence taking precedence over component calculation.
11. Category boundary values of 5, 50, 300 and 2000 mg/kg body weight.
12. An ATE above 2000 mg/kg body weight producing only `CLASSIFICATION NOT TRIGGERED UNDER IMPLEMENTED RULE`.
13. Acute-toxicity cut-off evidence kept distinct from an SCL, GCL, M-factor and classification threshold.
14. Ambiguous component identity, stopping the calculation.
15. Historical rule-version and applicability-date persistence in an immutable screening run.

## Discrepancies and conservative decisions

- No discrepancy was found in the implemented formula or oral category boundary tests.
- Concentration ranges do not have a single invented representative value. The engine evaluates both supplied bounds. If they cross categories, it requires manual review.
- If a component at or above 1% lacks usable oral acute-toxicity information, the engine exposes any calculable provisional ATE but does not present it as definitive.
- Multiple oral ATE values for the same evidence object are not silently ranked. The affected concentration is treated as unknown and surfaced for review.
- Unit conversion is intentionally absent. Unsupported units produce insufficient-data handling rather than an implicit conversion.

## Remaining gaps

- Bridging principles (dilution, batching, concentration, interpolation, similar mixtures and aerosols) require evidence models and expert-reviewed implementations.
- Dermal and inhalation acute-toxicity routes are not implemented.
- Full treatment of converted acute-toxicity point estimates and every special-case ingredient rule requires a separately validated extension.
- No other CLP mixture hazard class is implemented.
- The pilot does not generate labels, SDS content, transport classifications, exposure conclusions, or compliance determinations.
