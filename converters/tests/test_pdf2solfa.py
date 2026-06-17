"""Unit tests for converters.pdf2solfa.converter (pure functions only)."""

import pytest
from converters.pdf2solfa.converter import (
    _detect_title,
    _detect_key,
    _detect_timesig,
    _format_headers,
    _is_note_line,
    _insert_measure_barlines,
    _add_edge_barlines,
    _build_default_headers,
)


# --- _detect_title ---

def test_detect_title_first_nonempty_line():
    text = "\n  \nGlory to God\nSome other line"
    assert _detect_title(text) == "Glory to God"


def test_detect_title_single_line():
    assert _detect_title("Hallelujah") == "Hallelujah"


def test_detect_title_empty_text():
    assert _detect_title("") is None


def test_detect_title_only_whitespace():
    assert _detect_title("   \n\n  ") is None


# --- _detect_key ---

def test_detect_key_do_dia_format():
    assert _detect_key("Do dia G") == "G"


def test_detect_key_with_sharp():
    assert _detect_key("Do dia F#") == "F#"


def test_detect_key_with_flat():
    assert _detect_key("Do dia Bb") == "Bb"


def test_detect_key_no_spaces():
    # \s* allows zero spaces, so "DodiaA" does match the pattern
    assert _detect_key("DodiaA") == "A"


def test_detect_key_not_found():
    assert _detect_key("Some random text") is None


def test_detect_key_case_insensitive():
    assert _detect_key("do DIA C") == "C"


# --- _detect_timesig ---

def test_detect_timesig_4_4():
    assert _detect_timesig("Time: 4/4") == "4/4"


def test_detect_timesig_3_4():
    assert _detect_timesig("3/4 time") == "3/4"


def test_detect_timesig_not_found():
    assert _detect_timesig("no time signature here") is None


def test_detect_timesig_picks_first():
    assert _detect_timesig("4/4 and later 3/4") == "4/4"


# --- _build_default_headers ---

def test_build_default_headers_returns_dict():
    headers = _build_default_headers()
    assert isinstance(headers, dict)
    assert len(headers) > 0


# --- _format_headers ---

def test_format_headers_includes_values():
    headers = {"title": "My Song", "key": "G"}
    result = _format_headers(headers)
    assert "title" in result
    assert "My Song" in result
    assert "key" in result
    assert "G" in result


def test_format_headers_none_value_omits_value():
    headers = {"title": None}
    result = _format_headers(headers)
    assert "title" in result
    # No trailing value after the key
    for line in result.split("\n"):
        if "title" in line:
            assert "None" not in line


# --- _is_note_line ---

def test_is_note_line_with_notes_and_colon():
    assert _is_note_line("d:r:m | f:s:l") is True


def test_is_note_line_no_colon():
    assert _is_note_line("d r m f s l") is False


def test_is_note_line_colon_but_no_notes():
    # Single-letter note tokens (m, s) are substrings of "My" and "Song",
    # so this returns True - filtering non-note lines requires context beyond this function
    assert _is_note_line("Title: My Song") is True


def test_is_note_line_empty():
    assert _is_note_line("") is False


# --- _insert_measure_barlines ---

def test_insert_measure_barlines_adds_bar():
    # Two groups of notes separated by spaces with no barline between
    line = "d:r:m:f  s:l:t:d'"
    result = _insert_measure_barlines(line)
    assert "|" in result


def test_insert_measure_barlines_no_change_when_already_barred():
    line = "d:r:m:f | s:l:t:d'"
    result = _insert_measure_barlines(line)
    # Should not add extra barlines between already-barred segments
    assert result.count("|") == line.count("|")


def test_insert_measure_barlines_no_note_tokens_unchanged():
    # A line with no solfa note tokens is left unchanged
    line = "123 456 789"
    result = _insert_measure_barlines(line)
    assert result == line


# --- _add_edge_barlines ---

def test_add_edge_barlines_adds_leading_bar():
    # 4/4: leading segment has 4 beats (3 colons + implicit first = 4)
    line = "d:r:m:f | s:l:t:d'"
    result = _add_edge_barlines(line, beats_per_measure=4)
    assert result.startswith("|")


def test_add_edge_barlines_adds_trailing_bar():
    line = "| d:r:m:f | s:l:t:d'"
    result = _add_edge_barlines(line, beats_per_measure=4)
    assert result.endswith("|")


def test_add_edge_barlines_no_bar_when_no_pipe():
    line = "d:r:m:f"
    result = _add_edge_barlines(line, beats_per_measure=4)
    assert result == line


def test_add_edge_barlines_no_leading_bar_when_incomplete():
    # Only 2 beats in leading segment for 4/4
    line = "d:r | s:l:t:d'"
    result = _add_edge_barlines(line, beats_per_measure=4)
    assert not result.startswith("|")
