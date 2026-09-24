from __future__ import annotations

from datetime import date

from .identity import IdentityResolver
from .models import ChemicalInput, SourceRecord, SubstanceRecord
from .screening import CLPScreener, RestrictionScreener, SVHCScreener
from .service import ScreeningService

DEMO_WARNING = "SYNTHETIC DEMONSTRATION DATA — NOT AN OFFICIAL REGULATORY SOURCE"

SUBSTANCES = [
    SubstanceRecord("Benzene", "71-43-2", "200-753-7", ("benzol",)),
    SubstanceRecord("Toluene", "108-88-3", "203-625-9", ("methylbenzene",)),
    SubstanceRecord("Ethanol", "64-17-5", "200-578-6", ("ethyl alcohol",)),
    SubstanceRecord("Acetone", "67-64-1", "200-662-2", ("propan-2-one",)),
]


def _source(regulatory_list: str) -> SourceRecord:
    return SourceRecord(
        source_name=DEMO_WARNING,
        source_reference="Bundled file: chemreg_intel/demo.py",
        source_version="demo-1",
        retrieval_date=date.today().isoformat(),
        regulatory_list=regulatory_list,
        synthetic=True,
    )


SVHC_SOURCE = _source("Synthetic SVHC-style training list")
RESTRICTION_SOURCE = _source("Synthetic restriction-style training list")
CLP_SOURCE = _source("Synthetic CLP/GHS-style training list")

SVHC_RECORDS = [
    {
        "cas": "71-43-2", "entry_number": "DEMO-SVHC-001",
        "summary": "Synthetic positive match included solely to demonstrate evidence flow.",
        "review_notes": DEMO_WARNING,
    }
]

RESTRICTION_RECORDS = [
    {
        "cas": "108-88-3", "entry_number": "DEMO-R-001",
        "summary": "Synthetic restriction scope for workflow demonstration only.",
        "conditions_or_thresholds": "Illustrative threshold; consult an official current source.",
        "exemptions_or_notes": DEMO_WARNING,
        "manual_review_required": True,
    }
]

CLP_RECORDS = [
    {
        "cas": "67-64-1", "entry_number": "DEMO-CLP-001",
        "summary": "Synthetic hazard evidence for interface testing.",
        "classification_fields": {
            "hazard_class": "DEMO ONLY", "hazard_category": "DEMO ONLY",
            "H_statement": "DEMO ONLY", "signal_word": "DEMO ONLY",
            "pictogram": "DEMO ONLY", "harmonised_or_other_status": "synthetic",
        },
        "review_notes": DEMO_WARNING,
    }
]


def demo_service() -> ScreeningService:
    return ScreeningService(
        IdentityResolver(SUBSTANCES),
        SVHCScreener(SVHC_SOURCE, SVHC_RECORDS),
        RestrictionScreener(RESTRICTION_SOURCE, RESTRICTION_RECORDS),
        CLPScreener(CLP_SOURCE, CLP_RECORDS),
    )


def demo_inputs() -> list[ChemicalInput]:
    return [ChemicalInput(name, cas, ec, input_row=index + 2) for index, (name, cas, ec) in enumerate([
        ("Benzene", "71-43-2", "200-753-7"),
        ("Toluene", "108-88-3", "203-625-9"),
        ("Ethanol", "64-17-5", "200-578-6"),
        ("Acetone", "67-64-1", "200-662-2"),
    ])]


def demo_sources() -> list[SourceRecord]:
    return [SVHC_SOURCE, RESTRICTION_SOURCE, CLP_SOURCE]

