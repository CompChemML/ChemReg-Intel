from __future__ import annotations

import re
import unicodedata
from collections import defaultdict

from rapidfuzz import fuzz, process

from .models import ChemicalInput, IdentityResult, MatchMethod, SubstanceRecord

CAS_PATTERN = re.compile(r"^(\d{2,7})-(\d{2})-(\d)$")
EC_PATTERN = re.compile(r"^(\d{3})-(\d{3})-(\d)$")


def normalize_cas(value: object) -> str:
    return re.sub(r"\s+", "", str(value or "").strip())


def validate_cas(value: object) -> bool:
    cas = normalize_cas(value)
    match = CAS_PATTERN.fullmatch(cas)
    if not match:
        return False
    digits = "".join(match.groups()[:2])
    check = sum(int(digit) * weight for weight, digit in enumerate(reversed(digits), 1)) % 10
    return check == int(match.group(3))


def normalize_ec(value: object) -> str:
    digits = re.sub(r"\D", "", str(value or ""))
    return f"{digits[:3]}-{digits[3:6]}-{digits[6]}" if len(digits) == 7 else ""


def validate_ec(value: object) -> bool:
    return bool(EC_PATTERN.fullmatch(normalize_ec(value)))


def normalize_name(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value or "")).encode("ascii", "ignore").decode()
    return " ".join(re.sub(r"[^a-z0-9]+", " ", text.lower()).split())


class IdentityResolver:
    def __init__(self, substances: list[SubstanceRecord], fuzzy_threshold: float = 82.0):
        self.substances = substances
        self.fuzzy_threshold = fuzzy_threshold
        self._by_cas: dict[str, list[SubstanceRecord]] = defaultdict(list)
        self._by_ec: dict[str, list[SubstanceRecord]] = defaultdict(list)
        self._by_name: dict[str, list[SubstanceRecord]] = defaultdict(list)
        for substance in substances:
            if substance.cas:
                self._by_cas[normalize_cas(substance.cas)].append(substance)
            if substance.ec:
                self._by_ec[normalize_ec(substance.ec)].append(substance)
            self._by_name[normalize_name(substance.name)].append(substance)
            for synonym in substance.synonyms:
                self._by_name[normalize_name(synonym)].append(substance)

    def resolve(self, chemical: ChemicalInput) -> IdentityResult:
        base = dict(
            input_name=chemical.input_name,
            input_cas=chemical.input_cas,
            input_ec=chemical.input_ec,
            input_row=chemical.input_row,
        )
        invalid_ids: list[str] = []
        candidates: list[SubstanceRecord] = []
        method = MatchMethod.NONE

        if chemical.input_cas:
            cas = normalize_cas(chemical.input_cas)
            if not validate_cas(cas):
                invalid_ids.append("Invalid CAS checksum or format")
            else:
                candidates = self._by_cas.get(cas, [])
                method = MatchMethod.CAS_EXACT
        if not candidates and chemical.input_ec:
            ec = normalize_ec(chemical.input_ec)
            if not validate_ec(ec):
                invalid_ids.append("Invalid EC number format")
            else:
                candidates = self._by_ec.get(ec, [])
                method = MatchMethod.EC_EXACT
        if not candidates and chemical.input_name:
            normalized = normalize_name(chemical.input_name)
            candidates = self._by_name.get(normalized, [])
            if candidates:
                method = MatchMethod.NAME_EXACT if normalized == normalize_name(candidates[0].name) else MatchMethod.SYNONYM_EXACT

        unique = {item.cas or item.ec or item.name: item for item in candidates}
        candidates = list(unique.values())
        if len(candidates) == 1:
            item = candidates[0]
            conflict = bool(
                (chemical.input_cas and validate_cas(chemical.input_cas) and normalize_cas(chemical.input_cas) != normalize_cas(item.cas))
                or (chemical.input_ec and validate_ec(chemical.input_ec) and normalize_ec(chemical.input_ec) != normalize_ec(item.ec))
            )
            return IdentityResult(
                **base, matched_name=item.name, matched_cas=item.cas, matched_ec=item.ec,
                match_method=method, match_confidence=1.0,
                ambiguity_flag=conflict, manual_review_required=conflict,
                suggestions=["Conflicting supplied identifiers"] if conflict else [],
            )
        if len(candidates) > 1:
            return IdentityResult(
                **base, match_method=method, ambiguity_flag=True, manual_review_required=True,
                suggestions=[f"{item.name} | {item.cas or item.ec}" for item in candidates],
            )

        suggestions: list[str] = invalid_ids
        if chemical.input_name and self._by_name:
            matches = process.extract(
                normalize_name(chemical.input_name), self._by_name.keys(), scorer=fuzz.WRatio, limit=3
            )
            suggestions.extend(
                f"{self._by_name[name][0].name} ({score:.0f}% suggestion only)"
                for name, score, _ in matches if score >= self.fuzzy_threshold
            )
        return IdentityResult(
            **base, match_method=MatchMethod.NAME_SUGGESTION if suggestions else MatchMethod.NONE,
            match_confidence=0.0, ambiguity_flag=bool(suggestions), manual_review_required=True,
            suggestions=suggestions,
        )

