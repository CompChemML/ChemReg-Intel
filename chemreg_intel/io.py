from __future__ import annotations

import io
import json
from dataclasses import asdict
from pathlib import Path
from typing import BinaryIO

import pandas as pd

from .models import ChemicalInput, ScreeningResult, SourceRecord

ALIASES = {
    "name": "input_name", "chemical name": "input_name", "chemical": "input_name",
    "cas": "input_cas", "cas number": "input_cas",
    "ec": "input_ec", "ec number": "input_ec",
    "concentration": "concentration", "supplier": "supplier_product", "product": "supplier_product",
}


def dataframe_to_inputs(frame: pd.DataFrame) -> list[ChemicalInput]:
    renamed = frame.rename(columns={column: ALIASES.get(str(column).strip().lower(), str(column)) for column in frame.columns})
    inputs: list[ChemicalInput] = []
    for row_number, row in renamed.fillna("").iterrows():
        concentration = row.get("concentration", "")
        inputs.append(ChemicalInput(
            input_name=str(row.get("input_name", "")).strip(),
            input_cas=str(row.get("input_cas", "")).strip(),
            input_ec=str(row.get("input_ec", "")).strip(),
            concentration=float(concentration) if concentration not in ("", None) else None,
            supplier_product=str(row.get("supplier_product", "")).strip(),
            input_row=int(row_number) + 2,
        ))
    return inputs


def read_chemical_file(file: str | Path | BinaryIO, filename: str | None = None) -> list[ChemicalInput]:
    name = filename or getattr(file, "name", str(file))
    suffix = Path(name).suffix.lower()
    if suffix == ".csv":
        return dataframe_to_inputs(pd.read_csv(file))
    if suffix == ".xlsx":
        return dataframe_to_inputs(pd.read_excel(file))
    raise ValueError("Only CSV and XLSX chemical imports are supported")


def _result_rows(results: list[ScreeningResult]) -> dict[str, list[dict]]:
    identity, svhc, restrictions, clp, evidence, review = [], [], [], [], [], []
    for result in results:
        identity.append(asdict(result.identity))
        for target, items in ((svhc, [result.svhc]), (restrictions, [result.restriction]), (clp, result.clp)):
            for item in items:
                row = {"input_chemical": result.chemical.input_name, "CAS": result.identity.matched_cas, "EC": result.identity.matched_ec, **item.to_dict()}
                target.append(row)
                evidence.append(row)
                if item.manual_review_required:
                    review.append(row)
        if result.identity.manual_review_required:
            review.append({"input_chemical": result.chemical.input_name, "module": "Identity", "status": "MANUAL REVIEW REQUIRED", "review_notes": "; ".join(result.identity.suggestions)})
    return {"Chemical Identity": identity, "SVHC Screening": svhc, "REACH Restrictions": restrictions, "CLP - GHS": clp, "Evidence Log": evidence, "Manual Review Queue": review}


def export_excel(results: list[ScreeningResult], sources: list[SourceRecord]) -> bytes:
    rows = _result_rows(results)
    statuses = [row["status"] for row in rows["Evidence Log"]]
    summary = [{"metric": "Chemicals screened", "value": len(results)}, {"metric": "Confirmed evidence matches", "value": statuses.count("CONFIRMED MATCH")}, {"metric": "Manual review items", "value": len(rows["Manual Review Queue"])}, {"metric": "Important", "value": "No-match means only no match in the checked source."}]
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        pd.DataFrame(summary).to_excel(writer, sheet_name="Executive Summary", index=False)
        for sheet, data in rows.items():
            pd.DataFrame(data).to_excel(writer, sheet_name=sheet, index=False)
        pd.DataFrame([asdict(source) for source in sources]).to_excel(writer, sheet_name="Source Register", index=False)
    return buffer.getvalue()


def export_json(results: list[ScreeningResult]) -> str:
    return json.dumps([asdict(result) for result in results], indent=2, default=str)

