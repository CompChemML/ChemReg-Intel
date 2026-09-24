from __future__ import annotations

import io
import re
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd

from ...identity import normalize_cas, normalize_ec, validate_cas, validate_ec
from ..annex_xvii import AnnexXVIIEntry
from ..metadata import AuthorityLevel, SourceMetadata, UpdateReport, UpdateStatus, ValidationIssue, ValidationReport
from .base import SourceAdapter


class ECHAAnnexXVIIAdapter(SourceAdapter):
    """Imports a user-supplied ECHA Annex XVII export; no website scraping."""

    adapter_id = "echa-annex-xvii"
    supported_extensions = (".csv", ".xlsx")
    source_name = "ECHA substances restricted under REACH (Annex XVII)"
    source_authority = "European Chemicals Agency (ECHA)"
    source_url = "https://echa.europa.eu/substances-restricted-under-reach"
    legal_notice_url = "https://echa.europa.eu/legal-notice"
    legal_notice_version = "Version 10 - 04/06/2026"

    _aliases = {
        "entry no": "entry_number", "entry number": "entry_number",
        "entry title": "entry_title", "title": "entry_title",
        "substance name": "substance_name", "name": "substance_name",
        "cas no": "cas_number", "cas number": "cas_number",
        "ec no": "ec_number", "ec number": "ec_number",
        "index no": "index_number", "index number": "index_number",
        "group or substance scope": "group_or_substance_scope", "scope": "group_or_substance_scope",
        "conditions": "restriction_condition_full_text", "restriction condition full text": "restriction_condition_full_text",
        "structured scope summary": "structured_scope_summary", "screening summary": "structured_scope_summary",
        "mixture or article scope": "mixture_or_article_scope",
        "concentration threshold": "concentration_threshold", "threshold": "concentration_threshold",
        "threshold unit": "threshold_unit",
        "specific use conditions": "specific_use_conditions", "uses": "specific_use_conditions",
        "exemptions": "exemptions", "derogations": "derogations",
        "transition dates": "transition_dates", "effective date": "effective_date",
        "appendices": "appendix_references", "appendix references": "appendix_references",
        "legal basis": "legal_basis", "amending regulation": "amending_regulation",
        "eur lex reference": "eur_lex_reference", "echa reference": "echa_reference",
        "group keys": "group_keys", "scope tags": "scope_tags",
        "base entry version": "base_entry_version",
    }

    @staticmethod
    def _header(value: object) -> str:
        return " ".join(re.sub(r"[^a-z0-9]+", " ", str(value).lower()).split())

    @staticmethod
    def _clean(value: object) -> str:
        if pd.isna(value):
            return ""
        text = str(value).strip()
        return "" if text.lower() in {"nan", "none", "-"} else text

    def parse(self, payload: bytes, filename: str) -> list[dict[str, Any]]:
        suffix = Path(filename).suffix.lower()
        if suffix == ".csv":
            try:
                frame = pd.read_csv(io.BytesIO(payload), dtype=str, encoding="utf-8-sig", sep=None, engine="python", header=None)
            except UnicodeDecodeError:
                frame = pd.read_csv(io.BytesIO(payload), dtype=str, encoding="latin-1", sep=None, engine="python", header=None)
        elif suffix == ".xlsx":
            frame = pd.read_excel(io.BytesIO(payload), dtype=str, header=None)
        else:
            raise ValueError(f"Unsupported Annex XVII format: {suffix}")
        header_row = None
        for index, row in frame.head(25).iterrows():
            if any(self._aliases.get(self._header(value)) == "entry_number" for value in row if not pd.isna(value)):
                header_row = index
                break
        if header_row is None:
            raise ValueError("Annex XVII export is missing an Entry number header in its first 25 rows")
        frame.columns = [self._clean(value) for value in frame.loc[header_row]]
        frame = frame.loc[header_row + 1:]
        frame = frame.rename(columns={column: self._aliases.get(self._header(column), str(column)) for column in frame.columns})

        records: list[dict[str, Any]] = []
        for index, row in frame.iterrows():
            entry_number = self._clean(row.get("entry_number", ""))
            if not entry_number:
                continue
            raw_cas = self._clean(row.get("cas_number", ""))
            raw_ec = self._clean(row.get("ec_number", ""))
            raw_threshold = self._clean(row.get("concentration_threshold", ""))
            threshold = None
            if raw_threshold:
                try:
                    threshold = float(raw_threshold.replace(",", "."))
                except ValueError:
                    threshold = raw_threshold
            effective = self._clean(row.get("effective_date", ""))
            if effective:
                parsed = pd.to_datetime(effective, dayfirst=True, errors="coerce")
                effective = parsed.date().isoformat() if not pd.isna(parsed) else effective
            substance = self._clean(row.get("substance_name", ""))
            group_scope = self._clean(row.get("group_or_substance_scope", ""))
            records.append({
                "entry_number": entry_number,
                "entry_title": self._clean(row.get("entry_title", "")) or substance or group_scope or f"Annex XVII entry {entry_number}",
                "substance_name": substance,
                "cas_number": normalize_cas(raw_cas) if re.fullmatch(r"\s*\d{2,7}-\d{2}-\d\s*", raw_cas) else "",
                "ec_number": normalize_ec(raw_ec),
                "raw_cas_number": raw_cas, "raw_ec_number": raw_ec,
                "index_number": self._clean(row.get("index_number", "")),
                "group_or_substance_scope": group_scope,
                "restriction_condition_full_text": self._clean(row.get("restriction_condition_full_text", "")),
                "structured_scope_summary": self._clean(row.get("structured_scope_summary", "")),
                "mixture_or_article_scope": self._clean(row.get("mixture_or_article_scope", "")),
                "concentration_threshold": threshold, "threshold_unit": self._clean(row.get("threshold_unit", "")),
                "specific_use_conditions": self._clean(row.get("specific_use_conditions", "")),
                "exemptions": self._clean(row.get("exemptions", "")), "derogations": self._clean(row.get("derogations", "")),
                "transition_dates": self._clean(row.get("transition_dates", "")), "effective_date": effective,
                "appendix_references": self._clean(row.get("appendix_references", "")),
                "legal_basis": self._clean(row.get("legal_basis", "")),
                "amending_regulation": self._clean(row.get("amending_regulation", "")),
                "eur_lex_reference": self._clean(row.get("eur_lex_reference", "")),
                "echa_reference": self._clean(row.get("echa_reference", "")) or self.source_url,
                "authority_level": str(AuthorityLevel.OFFICIAL_INFORMATIONAL_DATASET),
                "manual_review_required": True,
                "group_keys": [value.strip() for value in self._clean(row.get("group_keys", "")).split("|") if value.strip()],
                "scope_tags": [value.strip() for value in self._clean(row.get("scope_tags", "")).split("|") if value.strip()],
                "base_entry_version": self._clean(row.get("base_entry_version", "")),
                "amending_acts": [], "source_row": int(index) + 1,
            })
        return records

    def validate(self, records: list[dict[str, Any]]) -> ValidationReport:
        issues: list[ValidationIssue] = []
        if not records:
            issues.append(ValidationIssue(None, "dataset", "ERROR", "No Annex XVII entries were parsed"))
        for record in records:
            row = record["source_row"]
            if not (record["substance_name"] or record["group_or_substance_scope"]):
                issues.append(ValidationIssue(row, "scope", "ERROR", "Substance name or group/scope is required"))
            if record["cas_number"] and not validate_cas(record["cas_number"]):
                issues.append(ValidationIssue(row, "cas_number", "ERROR", f"Invalid CAS checksum: {record['cas_number']}"))
            if record["ec_number"] and not validate_ec(record["ec_number"]):
                issues.append(ValidationIssue(row, "ec_number", "ERROR", f"Invalid EC number: {record['ec_number']}"))
            if record["raw_cas_number"] and not record["cas_number"]:
                issues.append(ValidationIssue(row, "cas_number", "WARNING", "Group or multi-valued CAS field retained only as raw evidence"))
            if record["raw_ec_number"] and not record["ec_number"]:
                issues.append(ValidationIssue(row, "ec_number", "WARNING", "Group or multi-valued EC field retained only as raw evidence"))
            if not record["restriction_condition_full_text"] and not record["eur_lex_reference"]:
                issues.append(ValidationIssue(row, "legal_text", "WARNING", "No legal wording or EUR-Lex reference is present in this ECHA row; link a separate legal-reference snapshot before interpretation"))
            if record["concentration_threshold"] is not None and not isinstance(record["concentration_threshold"], float):
                issues.append(ValidationIssue(row, "concentration_threshold", "ERROR", f"Invalid numeric threshold: {record['concentration_threshold']}"))
            if record["concentration_threshold"] is not None and not record["threshold_unit"]:
                issues.append(ValidationIssue(row, "threshold_unit", "ERROR", "Threshold unit is required when a threshold is present"))
            if record["effective_date"]:
                try:
                    date.fromisoformat(record["effective_date"])
                except ValueError:
                    issues.append(ValidationIssue(row, "effective_date", "ERROR", f"Unparseable effective date: {record['effective_date']}"))
        return ValidationReport(not any(issue.severity == "ERROR" for issue in issues), len(records), issues, dict(self._aliases))

    def metadata(self, payload: bytes, records: list[dict[str, Any]], *, retrieval_date: str, effective_date: str | None, dataset_version: str | None) -> SourceMetadata:
        checksum = self.checksum_bytes(payload)
        return SourceMetadata(
            source_name=self.source_name, source_authority=self.source_authority,
            source_url=self.source_url, source_type="USER-SUPPLIED OFFICIAL INFORMATION EXPORT",
            retrieval_date=retrieval_date, effective_date=effective_date,
            dataset_version=dataset_version or f"sha256:{checksum[:16]}", legal_notice_url=self.legal_notice_url,
            redistribution_allowed=False, commercial_use_allowed=None,
            authoritative_status=AuthorityLevel.OFFICIAL_INFORMATIONAL_DATASET,
            checksum=checksum, record_count=len(records), automated_retrieval_allowed=False,
            local_caching_allowed=True,
            reuse_decision_notes=("Private local caching of a user-supplied ECHA snapshot only. No scraping. "
                                  "Do not redistribute; commercial reuse remains unknown without permission review."),
            legal_notice_version=self.legal_notice_version,
        )

    def check_for_update(self, local: SourceMetadata) -> UpdateReport:
        return UpdateReport(UpdateStatus.MANUAL_UPDATE_REQUIRED, self.checked_now(), local.dataset_version, message="Export and import a new ECHA snapshot manually; historical snapshots remain unchanged.")

    @staticmethod
    def to_entries(records: list[dict[str, Any]], dataset_id: str) -> list[AnnexXVIIEntry]:
        entries = []
        for record in records:
            values = {key: value for key, value in record.items() if key not in {"source_row", "raw_cas_number", "raw_ec_number"}}
            values["dataset_id"] = dataset_id
            entries.append(AnnexXVIIEntry.from_dict(values))
        return entries
