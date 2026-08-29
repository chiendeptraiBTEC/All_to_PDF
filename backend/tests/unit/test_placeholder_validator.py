import pytest

from all_to_pdf.domain.provider import PlaceholderValidationError, ProtectedTokenValidator


def test_validator_accepts_preserved_tokens() -> None:
    validator = ProtectedTokenValidator()
    validator.validate(
        "Energy {v1} and <style id='2'>mass</style> %s",
        'Năng lượng { v1 } và <style id="2">khối lượng</style> %s',
    )


def test_validator_accepts_babeldoc_b_tags() -> None:
    validator = ProtectedTokenValidator()
    validator.validate(
        "Energy <b1>E=mc²</b1>",
        "Năng lượng <b1>E=mc²</b1>",
    )


def test_validator_rejects_missing_formula_token() -> None:
    validator = ProtectedTokenValidator()
    with pytest.raises(PlaceholderValidationError):
        validator.validate("Energy {v1}", "Năng lượng")


def test_validator_rejects_reordered_tokens() -> None:
    validator = ProtectedTokenValidator()
    with pytest.raises(PlaceholderValidationError):
        validator.validate("A {v1} B {v2}", "A {v2} B {v1}")
