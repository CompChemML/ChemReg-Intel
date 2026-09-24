from chemreg_intel.demo import SUBSTANCES
from chemreg_intel.identity import IdentityResolver, normalize_ec, validate_cas
from chemreg_intel.models import ChemicalInput, SubstanceRecord


def test_cas_validation_and_checksum():
    assert validate_cas(" 71-43-2 ")
    assert not validate_cas("71-43-3")
    assert not validate_cas("71432")


def test_ec_normalization():
    assert normalize_ec("200 753 7") == "200-753-7"


def test_exact_cas_identity_match():
    result = IdentityResolver(SUBSTANCES).resolve(ChemicalInput("", "71-43-2"))
    assert result.matched_name == "Benzene"
    assert result.match_method == "CAS exact"
    assert not result.manual_review_required


def test_synonym_match():
    result = IdentityResolver(SUBSTANCES).resolve(ChemicalInput("ethyl alcohol"))
    assert result.matched_name == "Ethanol"
    assert result.match_method == "synonym exact"


def test_fuzzy_match_is_suggestion_not_replacement():
    result = IdentityResolver(SUBSTANCES).resolve(ChemicalInput("benzen"))
    assert not result.matched_name
    assert result.manual_review_required
    assert result.suggestions


def test_ambiguous_name_requires_review():
    resolver = IdentityResolver([
        SubstanceRecord("Example", "71-43-2"), SubstanceRecord("Example", "108-88-3")
    ])
    result = resolver.resolve(ChemicalInput("Example"))
    assert result.ambiguity_flag
    assert result.manual_review_required


def test_conflicting_identifiers_are_flagged():
    result = IdentityResolver(SUBSTANCES).resolve(ChemicalInput("Toluene", "71-43-2", "203-625-9"))
    assert result.matched_name == "Benzene"
    assert result.ambiguity_flag
    assert result.manual_review_required

