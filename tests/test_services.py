import pytest

from app.services import SetsParseError, epley, parse_sets


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("5x100", [(5, 100.0)]),
        ("5x100, 5x100, 3x105", [(5, 100.0), (5, 100.0), (3, 105.0)]),
        ("3x5x80", [(5, 80.0)] * 3),
        ("8×22,5", [(8, 22.5)]),
        ("10; 8; 8", [(10, 0.0), (8, 0.0), (8, 0.0)]),
        ("5 x 60kg", [(5, 60.0)]),
        ("5@60", [(5, 60.0)]),
        ("", []),
        ("  ", []),
    ],
)
def test_parse_sets(text, expected):
    assert parse_sets(text) == expected


@pytest.mark.parametrize("text", ["abc", "0x100", "5x2000", "5x100x", "60x60x60"])
def test_parse_sets_invalid(text):
    with pytest.raises(SetsParseError):
        parse_sets(text)


def test_epley():
    assert epley(100, 1) == 100
    assert epley(100, 5) == pytest.approx(116.7)
    assert epley(100, 10) == pytest.approx(133.3)
    assert epley(0, 5) == 0
    assert epley(100, 0) == 0
