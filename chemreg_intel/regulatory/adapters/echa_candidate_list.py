from __future__ import annotations

import io
import re
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd

from ...identity import normalize_cas, normalize_ec, validate_cas, validate_ec
from ...models import SourceRecord
from ..metadata import AuthorityLevel, SourceMetadata, UpdateReport, UpdateStatus, ValidationIssue, ValidationReport
from .base import SourceAdapter


class ECHACandidateListAdapter(SourceAdapter):
    """Import a Candidate List export supplied by the user; never scrape ECHA."""

    adapter_id = "echa-candidate-list"
    supported_extensions = (".csv", ".xlsx")
    source_name = "Candidate List of substances of very high concern for Authorisation"
    source_authority = "European Chemicals Agency (ECHA)"
    source_url = "https://echa.europa.eu/candidate-list-table"
    legal_notice_url = "https://echa.europa.eu/legal-notice"
    legal_notice_version = "Version 10 - 04/06/2026"

    _aliases = {
        "substance name": "substance_name", "name": "substance_name",
        "ec no": "ec_number", "ec number": "ec_number",
        "cas no": "cas_number", "cas number": "cas_number",
        "date of inclusion": "date_of_inclusion", "inclusion date": "date_of_inclusion",
        "reason for inclusion": "reason_for_inclusion",
        "candidate list status": "candidate_list_status",
        "decision": "decision_reference", "decision reference": "decision_reference",
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
            raise ValueError(f"Unsupported Candidate List format: {suffix}")

        header_row = None
        for index, row in frame.head(25).iterrows():
            if any(self._aliases.get(self._header(value)) == "substance_name" for value in row if not pd.isna(value)):
                header_row = index
                break
        if header_row is None:
            raise ValueError("Candidate List export is missing a Substance name header in its first 25 rows")
        frame.columns = [self._clean(value) for value in frame.loc[header_row]]
        frame = frame.loc[header_row + 1:]

        mapped: dict[object, str] = {}
        for column in frame.columns:
            canonical = self._aliases.get(self._header(column))
            if canonical:
                mapped[column] = canonical
        frame = frame.rename(columns=mapped)
        if "substance_name" not in frame.columns:
            raise ValueError("Candidate List export is missing a Substance name column")

        records: list[dict[str, Any]] = []
        for index, row in frame.iterrows():
            name = self._clean(row.get("substance_name", ""))
            if not name:
                continue
            raw_ec = self._clean(row.get("ec_number", ""))
            raw_cas = self._clean(row.get("cas_number", ""))
            raw_date = self._clean(row.get("date_of_inclusion", ""))
            parsed_date = ""
            if raw_date:
                converted = pd.to_datetime(raw_date, dayfirst=True, errors="coerce")
                parsed_date = converted.date().isoformat() if not pd.isna(converted) else raw_date
            records.append({
                "substance_name": name,
                "ec_number": normalize_ec(raw_ec),
                "cas_number": normalize_cas(raw_cas) if re.fullmatch(r"\s*\d{2,7}-\d{2}-\d\s*", raw_cas) else "",
                "raw_ec_number": raw_ec,
                "raw_cas_number": raw_cas,
                "date_of_inclusion": parsed_date,
                "reason_for_inclusion": self._clean(row.get("reason_for_inclusion", "")),
                "candidate_list_status": self._clean(row.get("candidate_list_status", "")) or "included",
                "decision_reference": self._clean(row.get("decision_reference", "")),
                "source_row": int(index) + 1,
            })
        return records

    def validate(self, records: list[dict[str, Any]]) -> ValidationReport:
        issues: list[ValidationIssue] = []
        seen: set[tuple[str, str, str]] = set()
        if not records:
            issues.append(ValidationIssue(None, "dataset", "ERROR", "No Candidate List records were parsed"))
        for record in records:
            row = record.get("source_row")
            cas, ec = record["cas_number"], record["ec_number"]
            if record.get("raw_cas_number") and not cas:
                issues.append(ValidationIssue(row, "cas_number", "WARNING", "CAS field contains a group or multiple/unrecognized values; raw value retained for manual review"))
            if record.get("raw_ec_number") and not ec:
                issues.append(ValidationIssue(row, "ec_number", "WARNING", "EC field contains a group or multiple/unrecognized values; raw value retained for manual review"))
            if cas and not validate_cas(cas):
                issues.append(ValidationIssue(row, "cas_number", "ERROR", f"Invalid CAS format or checksum: {cas}"))
            if ec and not validate_ec(ec):
                issues.append(ValidationIssue(row, "ec_number", "ERROR", f"Invalid EC number: {ec}"))
            if not cas and not ec:
                issues.append(ValidationIssue(row, "identifiers", "WARNING", "Group/substance entry has no CAS or EC identifier and requires name/scope review"))
            if record["date_of_inclusion"]:
                try:
                    date.fromisoformat(record["date_of_inclusion"])
                except ValueError:
                    issues.append(ValidationIssue(row, "date_of_inclusion", "ERROR", f"Unparseable inclusion date: {record['date_of_inclusion']}"))
            key = (record["substance_name"].casefold(), cas, ec)
            if key in seen:
                issues.append(ValidationIssue(row, "record", "WARNING", "Duplicate normalized Candidate List row"))
            seen.add(key)
        return ValidationReport(
            valid=not any(issue.severity == "ERROR" for issue in issues),
            record_count=len(records), issues=issues, normalized_headers=dict(self._aliases),
        )

    def metadata(self, payload: bytes, records: list[dict[str, Any]], *, retrieval_date: str, effective_date: str | None, dataset_version: str | None) -> SourceMetadata:
        checksum = self.checksum_bytes(payload)
        return SourceMetadata(
            source_name=self.source_name, source_authority=self.source_authority,
            source_url=self.source_url, source_type="USER-SUPPLIED OFFICIAL EXPORT",
            retrieval_date=retrieval_date, effective_date=effective_date,
            dataset_version=dataset_version or f"sha256:{checksum[:16]}",
            legal_notice_url=self.legal_notice_url,
            redistribution_allowed=False, commercial_use_allowed=None,
            authoritative_status=AuthorityLevel.OFFICIAL_REGULATORY_DATABASE,
            checksum=checksum, record_count=len(records),
            automated_retrieval_allowed=False, local_caching_allowed=True,
            reuse_decision_notes=(
                "Private local caching of a user-supplied official export only. ECHA Legal Notice "
                "section 5.1 generally prohibits systematic automated collection and replication "
                "of whole/substantial database contents without permission; CAS information may "
                "carry third-party rights. Do not redistribute this snapshot. Commercial reuse is "
                "unknown pending source-specific permission review."
            ),
            legal_notice_version=self.legal_notice_version,
        )

    def check_for_update(self, local: SourceMetadata) -> UpdateReport:
        return UpdateReport(
            status=UpdateStatus.MANUAL_UPDATE_REQUIRED, checked_at=self.checked_now(),
            local_version=local.dataset_version,
            message=("Automatic collection is disabled. Compare with the Candidate List page, "
                     "export a fresh snapshot manually, and import it as a new dataset."),
        )

    @staticmethod
    def to_screening_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [
            {
                "cas": record["cas_number"],
                "ec": record["ec_number"],
                "entry_number": record["decision_reference"],
                "summary": record["reason_for_inclusion"],
                "conditions_or_thresholds": "",
                "exemptions_or_notes": (
                    "Candidate List membership alone does not determine all legal obligations; "
                    "evaluate substance, article, concentration, tonnage, role, use, and dates."
                ),
                "manual_review_required": True,
                "review_notes": (
                    f"Candidate List status: {record['candidate_list_status']}; inclusion date: "
                    f"{record['date_of_inclusion']}. Determine applicable obligations from the actual role, use, "
                    "form and concentration; membership alone is not a compliance conclusion."
                ),
            }
            for record in records
        ]

    @staticmethod
    def to_source_record(metadata: SourceMetadata, dataset_id: str) -> SourceRecord:
        return SourceRecord(
            source_name=metadata.source_name,
            source_reference=metadata.source_url,
            source_version=metadata.dataset_version,
            retrieval_date=metadata.retrieval_date,
            regulatory_list="ECHA Candidate List / SVHC",
            source_authority=metadata.source_authority,
            source_type=metadata.source_type,
            effective_date=metadata.effective_date,
            dataset_id=dataset_id,
            authority_level=str(metadata.authoritative_status),
            legal_notice_url=metadata.legal_notice_url,
            redistribution_allowed=metadata.redistribution_allowed,
            commercial_use_allowed=metadata.commercial_use_allowed,
            checksum=metadata.checksum,
            record_count=metadata.record_count,
        )
