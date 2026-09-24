from __future__ import annotations

import json
from dataclasses import asdict

import pandas as pd
import streamlit as st

from chemreg_intel.demo import DEMO_WARNING, demo_inputs, demo_service, demo_sources
from chemreg_intel.io import export_excel, export_json, read_chemical_file
from chemreg_intel.models import ChemicalInput
from chemreg_intel.sds import review_sds

st.set_page_config(page_title="ChemReg Intel", page_icon="🧪", layout="wide")
st.markdown("""
<style>
:root { --navy:#0B3558; --blue:#1687C9; --teal:#1FA7A0; --green:#2E9D75; --amber:#E7A63A; --red:#C94C4C; }
.stApp { background:#F7F9FC; }
h1,h2,h3 { color:#0B3558; }
.warning { padding:1rem; border-left:5px solid #E7A63A; background:#fff8e8; border-radius:4px; }
</style>
""", unsafe_allow_html=True)

st.title("ChemReg Intel")
st.caption("Chemical Regulatory Screening & Evidence Workbench")
st.markdown("**From Chemical Identity to Traceable Regulatory Evidence**")

with st.sidebar:
    page = st.radio("Workspace", ["Dashboard", "Chemical Screening", "SDS Review", "Source Register"])
    st.markdown("---")
    st.warning("Evidence screening only — not legal certification.")

if "results" not in st.session_state:
    st.session_state.results = []

if page == "Dashboard":
    st.subheader("Responsible regulatory screening")
    st.markdown("""
    <div class="warning"><b>Important interpretation rules</b><br>
    Regulatory databases change over time. No-match does not prove absence of regulation.
    Substance identity errors can invalidate screening. Mixture classification may depend on
    concentration and specific concentration limits. Harmonised and supplier self-classification
    are not the same. Regulatory interpretation may require expert review.</div>
    """, unsafe_allow_html=True)
    a, b, c = st.columns(3)
    a.metric("Chemicals screened", len(st.session_state.results))
    b.metric("Permitted conclusion types", 5)
    c.metric("Compliance claims", 0)

elif page == "Chemical Screening":
    st.subheader("Import chemicals")
    mode = st.radio("Input method", ["Demo data", "Upload CSV/XLSX", "Manual entry"], horizontal=True)
    chemicals: list[ChemicalInput] = []
    if mode == "Demo data":
        st.error(DEMO_WARNING)
        chemicals = demo_inputs()
        st.dataframe(pd.DataFrame([asdict(item) for item in chemicals]), use_container_width=True)
    elif mode == "Upload CSV/XLSX":
        uploaded = st.file_uploader("Choose a chemical list", type=["csv", "xlsx"])
        if uploaded:
            try:
                chemicals = read_chemical_file(uploaded, uploaded.name)
                st.success(f"Loaded {len(chemicals)} rows.")
            except Exception as exc:
                st.error(f"Import failed: {exc}")
    else:
        with st.form("manual"):
            name = st.text_input("Chemical name")
            cas = st.text_input("CAS number")
            ec = st.text_input("EC number")
            concentration = st.number_input("Concentration (optional)", min_value=0.0, value=None)
            supplier = st.text_input("Supplier / product (optional)")
            submitted = st.form_submit_button("Add and screen")
            if submitted:
                chemicals = [ChemicalInput(name, cas, ec, concentration, supplier, 1)]

    if chemicals and st.button("Run evidence screening", type="primary"):
        st.session_state.results = demo_service().screen(chemicals)

    results = st.session_state.results
    if results:
        rows = []
        for result in results:
            rows.append({
                "Input chemical": result.chemical.input_name,
                "CAS": result.identity.matched_cas,
                "EC": result.identity.matched_ec,
                "Resolved identity": result.identity.matched_name,
                "Identity confidence": result.identity.match_confidence,
                "SVHC status": result.svhc.status,
                "REACH restriction": result.restriction.status,
                "CLP / GHS": "; ".join(item.status for item in result.clp),
                "Ambiguity": result.identity.ambiguity_flag,
                "Manual review required": result.identity.manual_review_required or result.restriction.manual_review_required or any(item.manual_review_required for item in result.clp),
                "Reviewer notes": result.reviewer_notes,
            })
        st.subheader("Evidence table")
        st.dataframe(pd.DataFrame(rows), use_container_width=True)
        st.download_button("Download Excel evidence workbook", export_excel(results, demo_sources()), "chemreg_evidence.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        st.download_button("Download JSON", export_json(results), "chemreg_evidence.json", "application/json")
        st.download_button("Download CSV summary", pd.DataFrame(rows).to_csv(index=False), "chemreg_evidence.csv", "text/csv")
        with st.expander("Full traceable evidence"):
            st.json(json.loads(export_json(results)))

elif page == "SDS Review":
    st.subheader("Structured SDS consistency review")
    st.info("This module flags missing review content and does not generate an authoritative SDS.")
    sections = {}
    for section in ("1", "2", "3", "8", "9", "11", "12", "15"):
        sections[section] = st.text_area(f"Section {section}", height=80)
    if st.button("Review SDS fields"):
        findings = review_sds(sections)
        st.dataframe(pd.DataFrame(findings), use_container_width=True) if findings else st.success("No missing required review fields detected. This is not a compliance determination.")

else:
    st.subheader("Source register")
    st.error(DEMO_WARNING)
    st.dataframe(pd.DataFrame([asdict(source) for source in demo_sources()]), use_container_width=True)

