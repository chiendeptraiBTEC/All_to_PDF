import pytest

from all_to_pdf.engine.upstream import ALL_UPSTREAM_PINS, UpstreamPin


def test_upstream_pins_are_full_commits() -> None:
    assert {pin.name for pin in ALL_UPSTREAM_PINS} == {
        "BabelDOC",
        "PDFMathTranslate-next",
    }
    assert all(len(pin.commit) == 40 for pin in ALL_UPSTREAM_PINS)


def test_upstream_pin_validation() -> None:
    with pytest.raises(ValueError, match="HTTPS GitHub"):
        UpstreamPin("bad", "http://example.com/repo", "main")
