from __future__ import annotations

from dataclasses import replace

from .identity import IdentityResolver, normalize_cas, normalize_ec, normalize_name
from .models import ChemicalInput, RegulatoryEvidence, ScreeningResult
from .screening import CLPScreener, RestrictionScreener, SVHCScreener


def chemical_key(item: ChemicalInput) -> tuple[str, str]:
    if item.input_cas:
        return ("cas", normalize_cas(item.input_cas))
    if item.input_ec:
        return ("ec", normalize_ec(item.input_ec))
    return ("name", normalize_name(item.input_name))


def duplicate_rows(chemicals: list[ChemicalInput]) -> dict[tuple[str, str], list[int]]:
    found: dict[tuple[str, str], list[int]] = {}
    for index, chemical in enumerate(chemicals):
        found.setdefault(chemical_key(chemical), []).append(chemical.input_row or index + 1)
    return {key: rows for key, rows in found.items() if key[1] and len(rows) > 1}


class ScreeningService:
    def __init__(
        self,
        identity: IdentityResolver,
        svhc: SVHCScreener,
        restrictions: RestrictionScreener,
        clp: CLPScreener,
    ) -> None:
        self.identity = identity
        self.svhc = svhc
        self.restrictions = restrictions
        self.clp = clp

    def screen(self, chemicals: list[ChemicalInput]) -> list[ScreeningResult]:
        duplicates = duplicate_rows(chemicals)
        results: list[ScreeningResult] = []
        for chemical in chemicals:
            identity = self.identity.resolve(chemical)
            svhc = self.svhc.screen(identity)[0]
            restriction = self.restrictions.screen(identity)[0]
            clp = self.clp.screen(identity)
            note = ""
            key = chemical_key(chemical)
            if key in duplicates:
                note = f"Duplicate identifier appears on input rows {duplicates[key]}; each row is retained."
            results.append(ScreeningResult(chemical, identity, svhc, restriction, clp, note))
        return results

