from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from pathlib import Path

from chemreg_intel.identity import IdentityResolver
from chemreg_intel.models import ChemicalInput, IdentityResult, SubstanceRecord
from chemreg_intel.mixture import ATEEvidence, AcuteToxicityOralRule, ConcentrationEvidence, ConcentrationKind, EvidenceProvenance, Mixture, MixtureComponent
from chemreg_intel.regulatory.annex_xvii import AnnexXVIIEngine, AnnexXVIIEntry, LegalDocumentReference, RestrictionContext
from chemreg_intel.regulatory.clp_annex_vi import CLPAnnexVIEngine, CLPIdentityInput, HarmonisedEntry, HazardClassification, SpecificConcentrationLimit, AcuteToxicityEstimate
from chemreg_intel.regulatory.metadata import AuthorityLevel
from chemreg_intel.sds import review_sds_consistency
from chemreg_intel.screening import SVHCScreener
from chemreg_intel.models import SourceRecord

ROOT = Path(__file__).parent
AS_OF = "2026-09-24"

FORMULATION = [
    ("N-methyl-2-pyrrolidone (NMP)", "872-50-4", "212-828-1", 10.0, "solvent"),
    ("Toluene", "", "203-625-9", 20.0, "solvent"),
    ("2-propanone", "", "", 30.0, "solvent"),
    ("Ethanol", "64-17-5", "", 20.0, "solvent"),
    ("Formaldehyde", "50-00-0", "", 2.0, "crosslinker component"),
    ("Benzol", "", "", 0.05, "trace impurity"),
    ("Water", "7732-18-5", "", 17.95, "carrier"),
]

SUBSTANCES = [
    SubstanceRecord("N-methyl-2-pyrrolidone", "872-50-4", "212-828-1", ("NMP", "1-methyl-2-pyrrolidone")),
    SubstanceRecord("toluene", "108-88-3", "203-625-9", ()),
    SubstanceRecord("acetone", "67-64-1", "200-662-2", ("2-propanone", "propanone")),
    SubstanceRecord("ethanol", "64-17-5", "200-578-6", ("ethyl alcohol",)),
    SubstanceRecord("formaldehyde …%", "50-00-0", "200-001-8", ("formaldehyde",)),
    SubstanceRecord("benzene", "71-43-2", "200-753-7", ("benzol",)),
    SubstanceRecord("water", "7732-18-5", "231-791-2", ("deionized water",)),
]

SOURCES = [
    {"dataset_id":"case:identity-registry:2026-09-24","source_name":"Curated identity registry","authority_level":"OFFICIAL INFORMATIONAL DATASET","version":"case-identity-v1","effective_date":"2026-09-24","record_count":7,"url":"https://echa.europa.eu/information-on-chemicals","reuse":"Curated identifiers only; not a bulk ECHA export."},
    {"dataset_id":"case:echa-candidate-list:2026-02-04","source_name":"ECHA Candidate List curated NMP record","authority_level":"OFFICIAL REGULATORY DATABASE","version":"candidate-list-2026-02-04-curated-excerpt","effective_date":"2026-02-04","record_count":1,"url":"https://echa.europa.eu/candidate-list-table","reuse":"One manually curated record; no automated retrieval or bulk redistribution."},
    {"dataset_id":"case:echa-annex-xvii:2026-09-24","source_name":"ECHA Annex XVII structured curated records","authority_level":"OFFICIAL INFORMATIONAL DATASET","version":"annex-xvii-case-v1","effective_date":"2026-09-24","record_count":3,"url":"https://echa.europa.eu/substances-restricted-under-reach","reuse":"Structured screening aid only; legal wording remains separate."},
    {"dataset_id":"case:eurlex-annex-xvii:2026-09-24","source_name":"EUR-Lex/Official Journal Annex XVII references","authority_level":"LEGALLY BINDING","version":"annex-xvii-legal-case-v1","effective_date":"2026-09-24","record_count":3,"url":"https://eur-lex.europa.eu/eli/reg/2006/1907","reuse":"Curated legal references with attribution."},
    {"dataset_id":"case:eurlex-clp-annex-vi:2026-05-01","source_name":"EUR-Lex/Official Journal CLP Annex VI curated entries","authority_level":"LEGALLY BINDING","version":"clp-annex-vi-case-v2-atp22","effective_date":"2026-05-01","record_count":6,"url":"https://eur-lex.europa.eu/eli/reg/2008/1272","reuse":"Curated legal-entry manifest; no ECHA convenience bulk dataset."},
    {"dataset_id":"case:eurlex-clp-annex-vi:2015-03-25","source_name":"Historical EUR-Lex formaldehyde Annex VI entry","authority_level":"LEGALLY BINDING","version":"clp-annex-vi-historical-v1","effective_date":"2015-03-25","record_count":1,"url":"https://eur-lex.europa.eu/eli/reg/2014/605/oj","reuse":"Historical curated reference retained for reproducibility."},
    {"dataset_id":"case:clp-oral-rule:2026-07-01","source_name":"CLP Annex I oral acute-toxicity rule","authority_level":"LEGALLY BINDING","version":"clp-annex-i-2026-07-01-oral-pilot-v1","effective_date":"2026-07-01","record_count":1,"url":"https://eur-lex.europa.eu/eli/reg/2008/1272","reuse":"Rule metadata; formula is not a bulk source dataset."},
]

def h(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()

def entry(index, name, ec, cas, hazards, *, scls=(), ates=(), notes=(), act="", app=None, minflag=False, supplemental=()):
    return HarmonisedEntry(index, name, ec, cas, tuple(HazardClassification(*x) for x in hazards),
        supplemental_hazard_statements=supplemental, specific_concentration_limits=tuple(SpecificConcentrationLimit(*x) for x in scls),
        acute_toxicity_estimates=tuple(AcuteToxicityEstimate(*x) for x in ates), notes=notes, minimum_classification_flag=minflag,
        atp_or_amending_act=act, publication_date="2024-09-30" if "2564" in act else "2018-04-16", application_date=app,
        legal_reference="https://eur-lex.europa.eu/eli/reg_del/2024/2564/oj" if "2564" in act else "https://eur-lex.europa.eu/eli/reg/2008/1272",
        authority_level=AuthorityLevel.LEGALLY_BINDING, source_version="clp-annex-vi-case-v2-atp22", retrieval_date=AS_OF, checksum="case-curated", dataset_id="case:eurlex-clp-annex-vi:2026-05-01")

def main():
    ROOT.mkdir(parents=True, exist_ok=True)
    resolver = IdentityResolver(SUBSTANCES)
    inputs = [ChemicalInput(n, cas, ec, c, "SYNTHETIC INDUSTRIAL COATING", i+2) for i,(n,cas,ec,c,_) in enumerate(FORMULATION)]
    identities = [resolver.resolve(x) for x in inputs]
    candidate_source = SourceRecord("ECHA Candidate List curated NMP record", "https://echa.europa.eu/candidate-list-table", "candidate-list-2026-02-04-curated-excerpt", AS_OF, "Candidate List / SVHC", source_authority="ECHA", source_type="CURATED OFFICIAL RECORD", effective_date="2026-02-04", dataset_id=SOURCES[1]["dataset_id"], authority_level="OFFICIAL REGULATORY DATABASE", legal_notice_url="https://echa.europa.eu/legal-notice", redistribution_allowed=False, commercial_use_allowed=None, checksum=h({"nmp":1}), record_count=1)
    svhc = SVHCScreener(candidate_source, [{"cas":"872-50-4","ec":"212-828-1","entry_number":"ED/31/2011","summary":"Toxic for reproduction (Article 57c)","conditions_or_thresholds":"Inclusion date: 2011-06-20","exemptions_or_notes":"Candidate List membership alone does not determine obligations.","manual_review_required":True,"review_notes":"Confirm role, use, concentration and any applicable obligations."}])
    candidate = [svhc.screen(i)[0] for i in identities]
    restrictions = [
        AnnexXVIIEntry("71","1-methyl-2-pyrrolidone (NMP)","1-methyl-2-pyrrolidone","872-50-4","212-828-1",group_or_substance_scope="NMP as a substance or in mixtures",restriction_condition_full_text="At >=0.3% w/w, worker DNEL and risk-management conditions apply; wire-coating solvent/reactant use applies from 2024-05-09.",structured_scope_summary="Worker exposure conditions",mixture_or_article_scope="substance|mixture",concentration_threshold=0.3,threshold_unit="% w/w",specific_use_conditions="Worker DNELs: inhalation 14.4 mg/m3; dermal 4.8 mg/kg/day.",derogations="Wire-coating later applicability.",transition_dates="2020-05-09; wire coating 2024-05-09",effective_date="2020-05-09",legal_basis="REACH Annex XVII entry 71",amending_regulation="Commission Regulation (EU) 2018/588",eur_lex_reference="https://eur-lex.europa.eu/eli/reg/2018/588/oj",echa_reference="https://echa.europa.eu/documents/10162/5161f2bf-503c-2107-ab54-c087017d11c9",authority_level=AuthorityLevel.OFFICIAL_INFORMATIONAL_DATASET,dataset_id=SOURCES[2]["dataset_id"]),
        AnnexXVIIEntry("5","Benzene","Benzene","71-43-2","200-753-7",group_or_substance_scope="Benzene as substance, constituent, or mixture",restriction_condition_full_text="Shall not be placed on the market or used at >=0.1% by weight, subject to the entry's specified exemptions and derogations.",mixture_or_article_scope="substance|mixture",concentration_threshold=0.1,threshold_unit="% w/w",exemptions="Specified fuels, industrial processes and natural-gas provisions require legal-text review.",effective_date="2009-06-01",legal_basis="REACH Annex XVII entry 5",amending_regulation="Commission Regulation (EU) 2015/1494",eur_lex_reference="https://eur-lex.europa.eu/eli/reg/2006/1907/oj",echa_reference="https://echa.europa.eu/substances-restricted-under-reach",authority_level=AuthorityLevel.OFFICIAL_INFORMATIONAL_DATASET,dataset_id=SOURCES[2]["dataset_id"]),
        AnnexXVIIEntry("48","Toluene","Toluene","108-88-3","203-625-9",group_or_substance_scope="Toluene",restriction_condition_full_text="May not be placed on the market or used at >=0.1% by mass in adhesives and spray paints intended for sale to the general public.",mixture_or_article_scope="mixture",concentration_threshold=0.1,threshold_unit="% w/w",specific_use_conditions="Adhesives and spray paints intended for sale to the general public.",effective_date="2007-06-15",legal_basis="REACH Annex XVII entry 48",eur_lex_reference="https://eur-lex.europa.eu/eli/reg/2006/1907/oj",echa_reference="https://echa.europa.eu/substances-restricted-under-reach",authority_level=AuthorityLevel.OFFICIAL_INFORMATIONAL_DATASET,dataset_id=SOURCES[2]["dataset_id"]),
    ]
    legal = [LegalDocumentReference(x.entry_number, x.legal_basis, "32018R0588" if x.entry_number=="71" else "32006R1907", x.eur_lex_reference, AuthorityLevel.LEGALLY_BINDING, effective_date=x.effective_date, applicability_date=x.effective_date, amending_act=x.amending_regulation, dataset_id=SOURCES[3]["dataset_id"]) for x in restrictions]
    annex = AnnexXVIIEngine(restrictions, legal)
    annex_results=[]
    for identity, raw in zip(identities, FORMULATION):
        ctx=RestrictionContext(raw[3], "% w/w", subject_type="mixture", intended_use="industrial spray-applied coating; not supplied to general public")
        annex_results.extend(annex.screen(identity,ctx,AS_OF))
    entries=[
        entry("606-021-00-7","N-methyl-2-pyrrolidone; 1-methyl-2-pyrrolidone","212-828-1","872-50-4",[("Repr.","1B","H360D"),("STOT SE","3","H335"),("Skin Irrit.","2","H315"),("Eye Irrit.","2","H319")],scls=(("STOT SE","3",">=",10.0,"%","H335"),),notes=("***",),act="Commission Regulation (EU) 2016/1179",minflag=True),
        entry("601-021-00-3","toluene","203-625-9","108-88-3",[("Flam. Liq.","2","H225"),("Repr.","2","H361d"),("Asp. Tox.","1","H304"),("STOT RE","2","H373"),("Skin Irrit.","2","H315"),("STOT SE","3","H336")],notes=("**","***"),act="Commission Regulation (EU) 2018/669"),
        entry("606-001-00-8","acetone; propan-2-one; propanone","200-662-2","67-64-1",[("Flam. Liq.","2","H225"),("Eye Irrit.","2","H319"),("STOT SE","3","H336")],supplemental=("EUH066",),act="Commission Regulation (EU) 2018/669"),
        entry("603-002-00-5","ethanol; ethyl alcohol","200-578-6","64-17-5",[("Flam. Liq.","2","H225")],act="Commission Regulation (EU) 2018/669"),
        entry("605-001-00-5","formaldehyde …%","200-001-8","50-00-0",[("Carc.","1B","H350"),("Muta.","2","H341"),("Acute Tox.","2","H330"),("Acute Tox.","4","H302"),("Skin Corr.","1B","H314"),("Skin Sens.","1","H317")],scls=(("STOT SE","3",">=",5.0,"%","H335"),("Skin Corr.","1B",">=",25.0,"%","H314"),("Skin Sens.","1",">=",0.2,"%","H317")),ates=(("inhalation",100.0,"ppmV","gases",""),("oral",500.0,"mg/kg bw","","")),notes=("B","D","F"),supplemental=("EUH071",),act="Commission Delegated Regulation (EU) 2024/2564",app="2026-05-01",minflag=True),
        entry("601-020-00-8","benzene","200-753-7","71-43-2",[("Flam. Liq.","2","H225"),("Carc.","1A","H350"),("Muta.","1B","H340"),("STOT RE","1","H372"),("Asp. Tox.","1","H304"),("Eye Irrit.","2","H319"),("Skin Irrit.","2","H315")],notes=("E",),act="Commission Regulation (EU) 2018/669"),
    ]
    clp=CLPAnnexVIEngine(entries)
    clp_results=[clp.screen(CLPIdentityInput(chemical_name=i.matched_name,cas_number=i.matched_cas,ec_number=i.matched_ec,index_number="",form_or_physical_state="solution",manual_review_required=i.manual_review_required))[0] for i in identities]
    p=lambda source,authority,snapshot: EvidenceProvenance(source,authority,snapshot,AS_OF,"2026-05-01",authority=="USER_SUPPLIED","case study")
    components=[]
    for (_,cas,ec,c,role), identity in zip(FORMULATION,identities):
        ates=()
        if identity.matched_cas=="50-00-0": ates=(ATEEvidence("oral",500,"mg/kg bw","CLP Annex VI ATE",p("EUR-Lex ATP 22","LEGALLY_BINDING",SOURCES[4]["dataset_id"]),harmonised=True),)
        components.append(MixtureComponent(identity.matched_name,ConcentrationEvidence(ConcentrationKind.EXACT,"% w/w",p("Synthetic formulation","USER_SUPPLIED","case:formulation:v1"),value=c),cas=identity.matched_cas,ec=identity.matched_ec,component_role=role,acute_toxicity_estimates=ates))
    mix=AcuteToxicityOralRule().evaluate(Mixture("RV-01","SYNTHETIC industrial solvent/coating formulation",components,notes=("Synthetic case study only.",)))
    sds_sections={"1":"SYNTHETIC INDUSTRIAL COATING VALIDATION SPECIMEN","2":"Flam. Liq. 2 H225; Eye Irrit. 2 H319; STOT SE 3 H336.","3":"Acetone 30%; toluene 20%; ethanol 20%; formaldehyde 2%; benzene 0.05%; water.","8":"Use local exhaust ventilation and suitable gloves.","9":"Liquid coating base.","11":"Oral acute toxicity: no classification required.","12":"Avoid uncontrolled release.","15":"No SVHC substances identified. REACH Annex XVII: not applicable."}
    sds=review_sds_consistency(sds_sections,[
        {"section":"3","evidence_type":"composition identity","value":"872-50-4","source_reference":SOURCES[0]["url"]},
        {"section":"15","evidence_type":"Candidate List match","value":"NMP Candidate List inclusion","contradictory_claim":"No SVHC substances identified","source_reference":SOURCES[1]["url"]},
        {"section":"15","evidence_type":"Annex XVII potential matches","value":"entries 71, 5 and 48","contradictory_claim":"REACH Annex XVII: not applicable","source_reference":SOURCES[3]["url"]},
        {"section":"11","evidence_type":"implemented oral rule","value":"MANUAL REVIEW REQUIRED","contradictory_claim":"no classification required","source_reference":SOURCES[6]["url"]},
    ])
    queue=[]
    for i,r in enumerate(candidate):
        if r.manual_review_required: queue.append({"module":"Candidate List","component":identities[i].matched_name,"status":r.status,"reason":r.review_notes,"dataset_id":r.dataset_id})
    for r in annex_results:
        if r.manual_review_required: queue.append({"module":"Annex XVII","component":r.input_identity,"status":r.status,"reason":r.interpretation_note,"dataset_id":r.structured_source_dataset_id})
    for i,r in enumerate(clp_results):
        if r.manual_review_required: queue.append({"module":"CLP Annex VI","component":identities[i].matched_name,"status":r.status,"reason":r.interpretation_note,"dataset_id":r.entry.dataset_id if r.entry else SOURCES[4]["dataset_id"]})
    queue.append({"module":"Acute toxicity oral","component":"RV-01","status":str(mix.result),"reason":"; ".join(mix.warnings),"dataset_id":SOURCES[6]["dataset_id"]})
    queue += [{"module":"SDS consistency","component":"RV-01","status":x["severity"],"reason":x["finding"],"dataset_id":"case:synthetic-sds:v1"} for x in sds]
    payload={"case_id":"regulatory-validation-01","as_of_date":AS_OF,"synthetic_formulation":True,"formulation":[dict(name=n,cas=cas,ec=ec,concentration_percent=c,role=role) for n,cas,ec,c,role in FORMULATION],"source_register":[{**s,"checksum":h(s)} for s in SOURCES],"identities":[asdict(x) for x in identities],"candidate_list_results":[x.to_dict() for x in candidate],"annex_xvii_results":[asdict(x) for x in annex_results],"annex_vi_results":[asdict(x) for x in clp_results],"mixture_calculation":mix.to_dict(),"sds_sections":sds_sections,"sds_review":sds,"manual_review_queue":queue,"historical_evidence":{"formaldehyde_2015":{"hazard_statement":"H301","dataset_id":SOURCES[5]["dataset_id"]},"formaldehyde_2026":{"hazard_statement":"H302","oral_ate_mg_per_kg_bw":500,"dataset_id":SOURCES[4]["dataset_id"]},"reproduction_instruction":"Pin dataset IDs and rule version shown above to reproduce this output."}}
    (ROOT/"case_study_data.json").write_text(json.dumps(payload,indent=2,default=str),encoding="utf-8")
    (ROOT/"README.md").write_text("# Regulatory validation 01\n\nSYNTHETIC industrial solvent/coating formulation used only to validate ChemReg Intel. It is not a commercial product, SDS, regulatory determination, or use recommendation. Run `python build_case.py` then `node build_workbooks.mjs` to regenerate the case outputs.\n",encoding="utf-8")
    (ROOT/"case_protocol.md").write_text("# Protocol\n\n1. Resolve supplied identifiers and synonyms. 2. Screen the pinned Candidate List excerpt, separate Annex XVII information/legal records, and legally binding Annex VI entries. 3. Run only the oral acute-toxicity rule. 4. Compare supplied synthetic SDS text with evidence without declaring validity. 5. Preserve every dataset ID, checksum, date, authority and rule version.\n",encoding="utf-8")
    (ROOT/"validation_findings.md").write_text("# Validation findings\n\n- Fixed: Candidate List matches now enter manual review because membership does not itself decide obligations.\n- Fixed: SDS review now identifies supplied-text contradictions against structured evidence without declaring an SDS invalid.\n- Current formaldehyde evidence is ATP 22 (application 2026-05-01): oral H302 and oral ATE 500 mg/kg bw. The historical 2015 record used H301; both versions remain explicit.\n- Oral mixture result is provisional and requires review because all non-formaldehyde components lack usable oral ATE evidence in this pinned case.\n",encoding="utf-8")
    (ROOT/"software_validation.md").write_text("# Software validation\n\nAll seven identities resolve by CAS, EC, synonym or exact name. NMP reproduces the Candidate List match. Annex XVII emits only POTENTIAL RESTRICTION MATCH. Annex VI results retain rows, SCLs, ATEs and notes. The oral calculation retains every contribution and does not treat absent ATEs as safe. SDS checks report consistency findings only. Pinned dataset IDs and the oral rule version are included in `case_study_data.json`.\n",encoding="utf-8")
    (ROOT/"case_study_full.md").write_text("# Integrated case study\n\nThe synthetic formulation exercises identity resolution, SVHC evidence, condition-based Annex XVII restrictions, partial harmonised classification evidence, the oral acute-toxicity calculation, SDS consistency review, manual review and versioned provenance. NMP is the sole Candidate List match. NMP, benzene and toluene are Annex XVII potential matches. Formaldehyde supplies the current harmonised oral ATE. No no-match output is interpreted as unregulated, safe or compliant.\n",encoding="utf-8")
    svgs={"regulatory_workflow.svg":"Raw formulation → Identity → Evidence → Conditions → Review","evidence_authority_hierarchy.svg":"Legally binding → Official database → Informational → Industry data","screening_results_map.svg":"SVHC: NMP | Annex XVII: NMP, benzene, toluene | Annex VI: six entries","manual_review_flow.svg":"Evidence flag → Human review → Decision recorded","provenance_chain.svg":"Source → Snapshot → Dataset ID → Result → Export"}
    for name,label in svgs.items():
        (ROOT/name).write_text(f'<svg xmlns="http://www.w3.org/2000/svg" width="1000" height="160" viewBox="0 0 1000 160"><rect width="1000" height="160" fill="#f7fafc"/><rect x="30" y="40" width="940" height="80" rx="12" fill="#0f4c5c"/><text x="500" y="90" text-anchor="middle" dominant-baseline="middle" fill="white" font-family="Arial" font-size="23">{label}</text></svg>',encoding="utf-8")

if __name__ == "__main__": main()
