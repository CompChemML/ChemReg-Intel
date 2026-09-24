from __future__ import annotations

import json
from datetime import date
from typing import Any

from ..clp_annex_vi import HarmonisedEntry
from ..metadata import AuthorityLevel, SourceMetadata, UpdateReport, UpdateStatus, ValidationIssue, ValidationReport
from .base import SourceAdapter


class EURLexCLPAnnexVIAdapter(SourceAdapter):
    """Imports a curated, normalized manifest of Official Journal Annex VI entries."""

    adapter_id = "eurlex-clp-annex-vi"
    supported_extensions = (".json",)
    source_name = "EUR-Lex / Official Journal CLP Annex VI Part 3 references"
    source_authority = "European Union / Publications Office of the European Union"
    source_url = "https://eur-lex.europa.eu/eli/reg/2008/1272"
    legal_notice_url = "https://eur-lex.europa.eu/content/help/data-reuse/reuse-contents-eurlex-details.html"

    def parse(self, payload: bytes, filename: str) -> list[dict[str, Any]]:
        parsed = json.loads(payload.decode("utf-8-sig"))
        records = parsed.get("records", parsed) if isinstance(parsed, dict) else parsed
        if not isinstance(records, list):
            raise ValueError("CLP legal manifest must be a JSON list or contain a records list")
        normalized = []
        for index, record in enumerate(records, 1):
            item = dict(record)
            item["authority_level"] = str(AuthorityLevel.LEGALLY_BINDING)
            item["source_row"] = index
            normalized.append(item)
        return normalized

    def validate(self, records: list[dict[str, Any]]) -> ValidationReport:
        issues: list[ValidationIssue] = []
        if not records:
            issues.append(ValidationIssue(None, "dataset", "ERROR", "No legal Annex VI entries were parsed"))
        for record in records:
            row = record["source_row"]
            try:
                entry = HarmonisedEntry.from_dict({key: value for key, value in record.items() if key != "source_row"})
            except (TypeError, ValueError) as exc:
                issues.append(ValidationIssue(row, "entry", "ERROR", str(exc)))
                continue
            if not entry.legal_reference.startswith("https://eur-lex.europa.eu/"):
                issues.append(ValidationIssue(row, "legal_reference", "ERROR", "Legal reference must use the EUR-Lex HTTPS origin"))
            if entry.notes:
                issues.append(ValidationIssue(row, "notes", "WARNING", "NOTE_PRESENT: manual review required"))
        return ValidationReport(not any(issue.severity == "ERROR" for issue in issues), len(records), issues)

    def metadata(self, payload: bytes, records: list[dict[str, Any]], *, retrieval_date: str, effective_date: str | None, dataset_version: str | None) -> SourceMetadata:
        checksum = self.checksum_bytes(payload)
        return SourceMetadata(
            self.source_name, self.source_authority, self.source_url, "CURATED OFFICIAL JOURNAL ENTRY MANIFEST",
            retrieval_date, effective_date, dataset_version or f"sha256:{checksum[:16]}", self.legal_notice_url,
            True, True, AuthorityLevel.LEGALLY_BINDING, checksum, len(records), automated_retrieval_allowed=None,
            local_caching_allowed=True,
            reuse_decision_notes=("Small curated legal-reference fixture, not an Official Journal bulk mirror. "
                                  "Reuse is subject to attribution, integrity, non-liability, and third-party-rights conditions."),
            legal_notice_version="Commission Decision 2011/833/EU; recheck source-specific notices",
        )

    def check_for_update(self, local: SourceMetadata) -> UpdateReport:
        return UpdateReport(UpdateStatus.MANUAL_UPDATE_REQUIRED, self.checked_now(), local.dataset_version, message="Review later ATPs and import a new curated manifest; do not replace historical law versions.")

    @staticmethod
    def to_entries(records: list[dict[str, Any]], dataset_id: str, source: SourceMetadata) -> list[HarmonisedEntry]:
        entries = []
        for record in records:
            values = {key: value for key, value in record.items() if key != "source_row"}
            values.update(dataset_id=dataset_id, source_version=source.dataset_version, retrieval_date=source.retrieval_date, checksum=source.checksum, authority_level=AuthorityLevel.LEGALLY_BINDING)
            entries.append(HarmonisedEntry.from_dict(values))
        return entries

