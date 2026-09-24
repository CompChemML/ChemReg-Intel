from __future__ import annotations

import json
from datetime import date
from typing import Any

from ..annex_xvii import LegalDocumentReference
from ..metadata import AuthorityLevel, SourceMetadata, UpdateReport, UpdateStatus, ValidationIssue, ValidationReport
from .base import SourceAdapter


class EURLexAnnexXVIIReferenceAdapter(SourceAdapter):
    """Imports curated EUR-Lex/OJ references, keeping legal authority separate."""

    adapter_id = "eurlex-annex-xvii-references"
    supported_extensions = (".json",)
    source_name = "EUR-Lex / Official Journal Annex XVII legal references"
    source_authority = "European Union / Publications Office of the European Union"
    source_url = "https://eur-lex.europa.eu/eli/reg/2006/1907"
    legal_notice_url = "https://eur-lex.europa.eu/content/help/data-reuse/reuse-contents-eurlex-details.html"

    def parse(self, payload: bytes, filename: str) -> list[dict[str, Any]]:
        parsed = json.loads(payload.decode("utf-8-sig"))
        records = parsed.get("records", parsed) if isinstance(parsed, dict) else parsed
        if not isinstance(records, list):
            raise ValueError("EUR-Lex reference manifest must be a JSON list or contain a records list")
        normalized = []
        for index, record in enumerate(records, 1):
            item = dict(record)
            item["entry_number"] = str(item.get("entry_number", "")).strip()
            item["celex_number"] = str(item.get("celex_number", "")).strip()
            item["eur_lex_reference"] = str(item.get("eur_lex_reference", "")).strip()
            item["authority_level"] = str(item.get("authority_level") or AuthorityLevel.LEGALLY_BINDING)
            item["source_row"] = index
            normalized.append(item)
        return normalized

    def validate(self, records: list[dict[str, Any]]) -> ValidationReport:
        issues: list[ValidationIssue] = []
        if not records:
            issues.append(ValidationIssue(None, "dataset", "ERROR", "No EUR-Lex references were parsed"))
        for record in records:
            row = record["source_row"]
            for field in ("entry_number", "document_title", "celex_number", "eur_lex_reference"):
                if not record.get(field):
                    issues.append(ValidationIssue(row, field, "ERROR", f"{field} is required"))
            if record.get("eur_lex_reference") and not record["eur_lex_reference"].startswith("https://eur-lex.europa.eu/"):
                issues.append(ValidationIssue(row, "eur_lex_reference", "ERROR", "Legal reference must use the EUR-Lex HTTPS origin"))
            for field in ("publication_date", "effective_date", "applicability_date", "consolidated_text_date"):
                if record.get(field):
                    try:
                        date.fromisoformat(record[field])
                    except ValueError:
                        issues.append(ValidationIssue(row, field, "ERROR", f"{field} must be ISO YYYY-MM-DD"))
        return ValidationReport(not any(issue.severity == "ERROR" for issue in issues), len(records), issues)

    def metadata(self, payload: bytes, records: list[dict[str, Any]], *, retrieval_date: str, effective_date: str | None, dataset_version: str | None) -> SourceMetadata:
        checksum = self.checksum_bytes(payload)
        return SourceMetadata(
            source_name=self.source_name, source_authority=self.source_authority,
            source_url=self.source_url, source_type="CURATED OFFICIAL LEGAL REFERENCE MANIFEST",
            retrieval_date=retrieval_date, effective_date=effective_date,
            dataset_version=dataset_version or f"sha256:{checksum[:16]}", legal_notice_url=self.legal_notice_url,
            redistribution_allowed=True, commercial_use_allowed=True,
            authoritative_status=AuthorityLevel.LEGALLY_BINDING,
            checksum=checksum, record_count=len(records), automated_retrieval_allowed=None,
            local_caching_allowed=True,
            reuse_decision_notes=("Manifest contains curated citations and metadata, not a bulk copy of legal text. "
                                  "EU document reuse remains subject to attribution, integrity, non-liability, and third-party-rights conditions."),
            legal_notice_version="Commission Decision 2011/833/EU; source notice must be rechecked",
        )

    def check_for_update(self, local: SourceMetadata) -> UpdateReport:
        return UpdateReport(UpdateStatus.MANUAL_UPDATE_REQUIRED, self.checked_now(), local.dataset_version, message="Check the current consolidated act and later amending regulations on EUR-Lex; import a new reference manifest without replacing history.")

    @staticmethod
    def to_references(records: list[dict[str, Any]], dataset_id: str) -> list[LegalDocumentReference]:
        references = []
        for record in records:
            values = {key: value for key, value in record.items() if key != "source_row"}
            values["dataset_id"] = dataset_id
            values["authority_level"] = AuthorityLevel(values.get("authority_level", AuthorityLevel.LEGALLY_BINDING))
            references.append(LegalDocumentReference(**values))
        return references
