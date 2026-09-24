from __future__ import annotations

import io
import re
from collections import OrderedDict
from pathlib import Path
from typing import Any

import pandas as pd

from ...identity import normalize_cas, normalize_ec, validate_cas, validate_ec
from ..clp_annex_vi import HarmonisedEntry
from ..metadata import AuthorityLevel, SourceMetadata, UpdateReport, UpdateStatus, ValidationIssue, ValidationReport
from .base import SourceAdapter


class ECHACLPAnnexVIAdapter(SourceAdapter):
    """Imports a private user-supplied ECHA Annex VI convenience snapshot."""

    adapter_id = "echa-clp-annex-vi"
    supported_extensions = (".csv", ".xlsx")
    source_name = "ECHA table of harmonised entries in Annex VI to CLP"
    source_authority = "European Chemicals Agency (ECHA)"
    source_url = "https://echa.europa.eu/information-on-chemicals/annex-vi-to-clp"
    legal_notice_url = "https://echa.europa.eu/legal-notice"

    _aliases = {
        "index no": "index_number", "index number": "index_number",
        "chemical name": "chemical_name", "international chemical identification": "chemical_name",
        "ec no": "ec_number", "ec number": "ec_number", "cas no": "cas_number", "cas number": "cas_number",
        "hazard class code": "hazard_class_code", "hazard class": "hazard_class_code",
        "hazard category code": "hazard_category_code", "hazard category": "hazard_category_code",
        "hazard class and category codes": "hazard_class_and_category_codes",
        "hazard statement code": "hazard_statement_code", "hazard statement codes": "hazard_statement_codes",
        "pictogram code": "pictogram_codes", "pictogram signal word codes": "pictogram_signal_word_codes",
        "signal word code": "signal_word_code", "supplemental hazard statement": "supplemental_hazard_statements",
        "scl hazard class": "scl_hazard_class", "scl category": "scl_category", "scl operator": "scl_operator",
        "scl threshold": "scl_threshold", "scl unit": "scl_unit", "scl classification trigger": "scl_trigger",
        "specific conc limits m factors and ates": "combined_limits",
        "m factor context": "m_factor_context", "m factor": "m_factor",
        "ate route": "ate_route", "ate value": "ate_value", "ate unit": "ate_unit", "ate physical form": "ate_physical_form",
        "notes": "notes", "form or physical state scope": "form_or_physical_state_scope",
        "minimum classification flag": "minimum_classification_flag", "atp or amending act": "atp_or_amending_act",
        "publication date": "publication_date", "application date": "application_date",
        "voluntary early application allowed": "voluntary_early_application_allowed",
        "legal reference": "legal_reference", "informational reference": "informational_reference",
        "group entry": "is_group_entry", "group keys": "group_keys", "superseded date": "superseded_date",
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

    @staticmethod
    def _tokens(value: str) -> list[str]:
        return [item.strip() for item in re.split(r"\s*(?:\||\r?\n)\s*", value) if item.strip()]

    @staticmethod
    def _truth(value: str) -> bool:
        return value.strip().lower() in {"1", "true", "yes", "y", "x", "*"}

    def _read(self, payload: bytes, filename: str) -> pd.DataFrame:
        if Path(filename).suffix.lower() == ".csv":
            try:
                return pd.read_csv(io.BytesIO(payload), dtype=str, encoding="utf-8-sig", sep=None, engine="python", header=None)
            except UnicodeDecodeError:
                return pd.read_csv(io.BytesIO(payload), dtype=str, encoding="latin-1", sep=None, engine="python", header=None)
        return pd.read_excel(io.BytesIO(payload), dtype=str, header=None)

    def parse(self, payload: bytes, filename: str) -> list[dict[str, Any]]:
        frame = self._read(payload, filename)
        header_row = None
        for index, row in frame.head(30).iterrows():
            if any(self._aliases.get(self._header(value)) == "index_number" for value in row if not pd.isna(value)):
                header_row = index
                break
        if header_row is None:
            raise ValueError("Annex VI snapshot is missing an Index number header in its first 30 rows")
        frame.columns = [self._clean(value) for value in frame.loc[header_row]]
        frame = frame.loc[header_row + 1:]
        frame = frame.rename(columns={column: self._aliases.get(self._header(column), str(column)) for column in frame.columns})
        grouped: OrderedDict[tuple[str, ...], dict[str, Any]] = OrderedDict()
        for index, row in frame.iterrows():
            index_number = self._clean(row.get("index_number", ""))
            if not index_number:
                continue
            raw_cas, raw_ec = self._clean(row.get("cas_number", "")), self._clean(row.get("ec_number", ""))
            key = (
                index_number, self._clean(row.get("chemical_name", "")), raw_ec, raw_cas,
                self._clean(row.get("atp_or_amending_act", "")), self._clean(row.get("form_or_physical_state_scope", "")),
            )
            if key not in grouped:
                grouped[key] = {
                    "index_number": index_number, "chemical_name": key[1],
                    "ec_number": normalize_ec(raw_ec),
                    "cas_number": normalize_cas(raw_cas) if re.fullmatch(r"\s*\d{2,7}-\d{2}-\d\s*", raw_cas) else "",
                    "raw_ec_number": raw_ec, "raw_cas_number": raw_cas,
                    "hazards": [], "pictogram_codes": [], "signal_word_code": "",
                    "supplemental_hazard_statements": [], "specific_concentration_limits": [],
                    "m_factors": [], "acute_toxicity_estimates": [], "notes": [],
                    "form_or_physical_state_scope": key[5], "minimum_classification_flag": False,
                    "atp_or_amending_act": key[4], "publication_date": self._clean(row.get("publication_date", "")) or None,
                    "application_date": self._clean(row.get("application_date", "")) or None,
                    "voluntary_early_application_allowed": self._truth(self._clean(row.get("voluntary_early_application_allowed", ""))),
                    "legal_reference": self._clean(row.get("legal_reference", "")),
                    "informational_reference": self._clean(row.get("informational_reference", "")) or self.source_url,
                    "authority_level": str(AuthorityLevel.OFFICIAL_INFORMATIONAL_DATASET),
                    "is_group_entry": self._truth(self._clean(row.get("is_group_entry", ""))),
                    "group_keys": self._tokens(self._clean(row.get("group_keys", ""))),
                    "superseded_date": self._clean(row.get("superseded_date", "")) or None,
                    "source_rows": [], "unparsed_limit_text": [],
                }
            record = grouped[key]
            record["source_rows"].append(int(index) + 1)
            self._append_hazards(record, row)
            self._append_structured_values(record, row)
        return list(grouped.values())

    def _append_hazards(self, record: dict[str, Any], row: pd.Series) -> None:
        class_code = self._clean(row.get("hazard_class_code", ""))
        category = self._clean(row.get("hazard_category_code", ""))
        statement = self._clean(row.get("hazard_statement_code", ""))
        if class_code:
            record["hazards"].append({"hazard_class_code": class_code, "hazard_category_code": category, "hazard_statement_code": statement})
        else:
            classes = self._tokens(self._clean(row.get("hazard_class_and_category_codes", "")))
            statements = self._tokens(self._clean(row.get("hazard_statement_codes", "")))
            for position, combined in enumerate(classes):
                match = re.match(r"^(.*?)(?:\s+([1-4](?:A|B|C)?))?$", combined)
                record["hazards"].append({
                    "hazard_class_code": (match.group(1) or combined).strip(),
                    "hazard_category_code": (match.group(2) or "").strip(),
                    "hazard_statement_code": statements[position] if position < len(statements) else "",
                })
        label_codes = self._clean(row.get("pictogram_codes", "")) or self._clean(row.get("pictogram_signal_word_codes", ""))
        record["pictogram_codes"].extend(code for code in re.findall(r"GHS\d{2}", label_codes) if code not in record["pictogram_codes"])
        signal = self._clean(row.get("signal_word_code", "")) or next((code for code in ("Dgr", "Wng") if re.search(rf"\b{code}\b", label_codes)), "")
        record["signal_word_code"] = record["signal_word_code"] or signal
        supplements = self._tokens(self._clean(row.get("supplemental_hazard_statements", "")))
        record["supplemental_hazard_statements"].extend(value for value in supplements if value not in record["supplemental_hazard_statements"])

    def _append_structured_values(self, record: dict[str, Any], row: pd.Series) -> None:
        threshold = self._clean(row.get("scl_threshold", ""))
        if threshold:
            record["specific_concentration_limits"].append({
                "hazard_class": self._clean(row.get("scl_hazard_class", "")),
                "category": self._clean(row.get("scl_category", "")),
                "operator": self._clean(row.get("scl_operator", "")), "threshold": float(threshold.replace(",", ".")),
                "unit": self._clean(row.get("scl_unit", "")), "classification_trigger": self._clean(row.get("scl_trigger", "")),
                "raw_text": self._clean(row.get("combined_limits", "")),
            })
        m_factor = self._clean(row.get("m_factor", ""))
        if m_factor:
            record["m_factors"].append({"hazard_context": self._clean(row.get("m_factor_context", "")), "value": float(m_factor.replace(",", ".")), "raw_text": self._clean(row.get("combined_limits", ""))})
        ate = self._clean(row.get("ate_value", ""))
        if ate:
            record["acute_toxicity_estimates"].append({
                "route": self._clean(row.get("ate_route", "")), "value": float(ate.replace(",", ".")),
                "unit": self._clean(row.get("ate_unit", "")), "physical_form": self._clean(row.get("ate_physical_form", "")),
                "raw_text": self._clean(row.get("combined_limits", "")),
            })
        notes = self._tokens(self._clean(row.get("notes", "")))
        record["notes"].extend(value for value in notes if value not in record["notes"])
        record["minimum_classification_flag"] = record["minimum_classification_flag"] or self._truth(self._clean(row.get("minimum_classification_flag", ""))) or any("*" in hazard["hazard_category_code"] or "*" in hazard["hazard_statement_code"] for hazard in record["hazards"])
        combined = self._clean(row.get("combined_limits", ""))
        if combined and not (threshold or m_factor or ate):
            record["unparsed_limit_text"].append(combined)

    def validate(self, records: list[dict[str, Any]]) -> ValidationReport:
        issues: list[ValidationIssue] = []
        if not records:
            issues.append(ValidationIssue(None, "dataset", "ERROR", "No Annex VI entries were parsed"))
        for record in records:
            row = record["source_rows"][0]
            if not record["chemical_name"]:
                issues.append(ValidationIssue(row, "chemical_name", "ERROR", "Chemical name is required"))
            if not record["hazards"]:
                issues.append(ValidationIssue(row, "hazards", "ERROR", "At least one hazard classification is required"))
            if record["cas_number"] and not validate_cas(record["cas_number"]):
                issues.append(ValidationIssue(row, "cas_number", "ERROR", f"Invalid CAS checksum: {record['cas_number']}"))
            if record["ec_number"] and not validate_ec(record["ec_number"]):
                issues.append(ValidationIssue(row, "ec_number", "ERROR", f"Invalid EC number: {record['ec_number']}"))
            if record["unparsed_limit_text"]:
                issues.append(ValidationIssue(row, "limits", "WARNING", "Combined SCL/M-factor/ATE text was retained but not interpreted; supply normalized structured columns"))
            if record["notes"]:
                issues.append(ValidationIssue(row, "notes", "WARNING", "NOTE_PRESENT: manual review required"))
        return ValidationReport(not any(issue.severity == "ERROR" for issue in issues), len(records), issues, dict(self._aliases))

    def metadata(self, payload: bytes, records: list[dict[str, Any]], *, retrieval_date: str, effective_date: str | None, dataset_version: str | None) -> SourceMetadata:
        checksum = self.checksum_bytes(payload)
        return SourceMetadata(
            self.source_name, self.source_authority, self.source_url, "USER-SUPPLIED ECHA CONVENIENCE SNAPSHOT",
            retrieval_date, effective_date, dataset_version or f"sha256:{checksum[:16]}", self.legal_notice_url,
            False, False, AuthorityLevel.OFFICIAL_INFORMATIONAL_DATASET, checksum, len(records),
            automated_retrieval_allowed=False, local_caching_allowed=True,
            reuse_decision_notes=("ECHA labels the Annex VI convenience spreadsheet informational, not legally binding, "
                                  "and states that it must not be used commercially or reproduced further. Private user-supplied snapshots only."),
            legal_notice_version="ECHA Annex VI page disclaimer and ECHA Legal Notice reviewed 2026-09-24",
        )

    def check_for_update(self, local: SourceMetadata) -> UpdateReport:
        return UpdateReport(UpdateStatus.MANUAL_UPDATE_REQUIRED, self.checked_now(), local.dataset_version, message="Automatic ECHA retrieval is disabled. Import a newly supplied snapshot as a separate version.")

    @staticmethod
    def to_entries(records: list[dict[str, Any]], dataset_id: str, source: SourceMetadata) -> list[HarmonisedEntry]:
        entries = []
        ignored = {"source_rows", "raw_ec_number", "raw_cas_number", "unparsed_limit_text"}
        for record in records:
            values = {key: value for key, value in record.items() if key not in ignored}
            values.update(dataset_id=dataset_id, source_version=source.dataset_version, retrieval_date=source.retrieval_date, checksum=source.checksum, authority_level=AuthorityLevel.OFFICIAL_INFORMATIONAL_DATASET)
            entries.append(HarmonisedEntry.from_dict(values))
        return entries

