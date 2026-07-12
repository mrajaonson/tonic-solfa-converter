"""Unit tests for the shared lyric-prefix helpers."""

import pytest

from converters.shared import spec
from converters.shared.solfa_tokens import (
    extract_parenthesized_prefix,
    parse_lyric_prefix,
)

BASE = spec["voices"]["base_labels"]


def _parse(token):
    return parse_lyric_prefix(token, BASE, allow_numbered=True)


# ──────────────────────────────────────────────────────────────────────
# extract_parenthesized_prefix
# ──────────────────────────────────────────────────────────────────────

def test_extract_basic():
    assert extract_parenthesized_prefix("(1.SA) Amazing") == ("1.SA", "Amazing")

def test_extract_no_space_after_paren():
    assert extract_parenthesized_prefix("(SA)words") == ("SA", "words")

def test_extract_leading_whitespace():
    assert extract_parenthesized_prefix("  (R) grace") == ("R", "grace")

def test_extract_none_when_unparenthesized():
    assert extract_parenthesized_prefix("Amazing grace") is None

def test_extract_none_when_paren_not_at_start():
    assert extract_parenthesized_prefix("Amazing (grace)") is None


# ──────────────────────────────────────────────────────────────────────
# parse_lyric_prefix - valid
# ──────────────────────────────────────────────────────────────────────

def test_bare_verse():
    assert _parse("2") == ("2", None)

def test_multi_digit_verse():
    assert _parse("12") == ("12", None)

def test_refrain():
    assert _parse("R") == ("R", None)

def test_bare_voices():
    assert _parse("SA") == (None, ["S", "A"])

def test_bare_voices_satb():
    assert _parse("SATB") == (None, ["S", "A", "T", "B"])

def test_numbered_voice():
    assert _parse("A1") == (None, ["A1"])

def test_combined_verse_voices():
    assert _parse("1.SA") == ("1", ["S", "A"])

def test_combined_verse_three_voices():
    assert _parse("1.SAT") == ("1", ["S", "A", "T"])

def test_combined_refrain_voices():
    assert _parse("R.TB") == ("R", ["T", "B"])


# ──────────────────────────────────────────────────────────────────────
# parse_lyric_prefix - invalid (None -> literal lyric)
# ──────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("token", [
    "1SA",    # concatenated combo without the dot
    "RA",     # concatenated refrain+voice
    "Ry",     # R-word, not a refrain
    "Rejoice",
    "2nd",    # digit-led word
    "1.",     # dot but no voices
    "1.5",    # right side not voices
    "1..A",   # multiple separators
    ".SA",    # empty verse
    "PR",     # instrument label excluded from base_labels
    "1.PR",
    "So",     # ordinary word starting with a voice letter
])
def test_invalid_returns_none(token):
    assert _parse(token) is None
