"""Unit tests for converters.shared.solfa_timesig."""

import pytest

from converters.shared.solfa_timesig import (
    is_note_line,
    count_measure_beats,
    find_beats_per_measure,
    resolve_beats_per_measure,
)


# ──────────────────────────────────────────────────────────────────────
# is_note_line
# ──────────────────────────────────────────────────────────────────────

def test_is_note_line_true():
    assert is_note_line("| d : m : f : s |") is True

def test_is_note_line_false_no_colon():
    assert is_note_line("| just bars |") is False

def test_is_note_line_false_no_barline():
    assert is_note_line("1 Joy-ful joy-ful") is False


# ──────────────────────────────────────────────────────────────────────
# count_measure_beats
# ──────────────────────────────────────────────────────────────────────

def test_count_measure_beats_plain():
    assert count_measure_beats("d : r : m : f") == 4

def test_count_measure_beats_soft_barline_counts_as_beat_sep():
    # '!' is visual only and must be counted like ':'
    assert count_measure_beats("d : m ! s : d") == 4

def test_count_measure_beats_single_beat():
    assert count_measure_beats("d") == 1


# ──────────────────────────────────────────────────────────────────────
# find_beats_per_measure
# ──────────────────────────────────────────────────────────────────────

def test_full_doc_all_complete():
    lines = [
        "| m : m : f : s | s : f : m : r | d : d : r : m |",
        "| d : d : t, : d | d : d : d : t, | d : d : t, : d |",
    ]
    assert find_beats_per_measure(lines) == 4

def test_leading_pickup_ignored():
    # First measure is a 1-beat pickup (no leading barline); the complete
    # interior measures drive the count.
    lines = ["d | r : m : f : s | l : s : f : m |"]
    assert find_beats_per_measure(lines) == 4

def test_soft_barline_measure_counts_correctly():
    lines = ["| d : m ! s : d | r : f ! l : r |"]
    assert find_beats_per_measure(lines) == 4

def test_trailing_partial_excluded():
    # Trailing fragment (no closing barline) is a split measure - excluded.
    lines = ["| d : r : m : f | s : l"]
    assert find_beats_per_measure(lines) == 4

def test_split_across_systems_both_edges_partial():
    # First and last measures of the line are both fragments; only the two
    # complete interior 3-beat measures count.
    lines = ["m : f | d : r : m | f : s : l | d :"]
    assert find_beats_per_measure(lines) == 3

def test_mode_across_lines():
    # A stray 3-beat measure loses to the majority 4-beat measures.
    lines = [
        "| d : r : m : f | s : l : t : d |",
        "| d : r : m | s : l : t : d |",
    ]
    assert find_beats_per_measure(lines) == 4

def test_no_complete_measure_returns_none():
    assert find_beats_per_measure(["d | r"]) is None

def test_lyric_lines_ignored():
    lines = [
        "1 Joy-ful, joy-ful, we a-dore",
        "| d : r : m : f | s : l : t : d |",
    ]
    assert find_beats_per_measure(lines) == 4


# ──────────────────────────────────────────────────────────────────────
# resolve_beats_per_measure
# ──────────────────────────────────────────────────────────────────────

def test_resolve_counted_wins_over_header():
    lines = ["| d : r : m : f | s : l : t : d |"]
    assert resolve_beats_per_measure(lines, header_timesig="3/4", warn=False) == 4

def test_resolve_warns_on_mismatch(capsys):
    lines = ["| d : r : m : f | s : l : t : d |"]
    resolve_beats_per_measure(lines, header_timesig="3/4")
    out = capsys.readouterr().out
    assert "3" in out and "4" in out and "Warning" in out

def test_resolve_warning_cites_line_number(capsys):
    # The winning count is established on the 3rd line (1-based).
    lines = [
        ":timesig: 3/4",
        "",
        "| d : r : m : f | s : l : t : d |",
    ]
    resolve_beats_per_measure(lines, header_timesig="3/4")
    out = capsys.readouterr().out
    assert "line 3" in out

def test_find_beats_per_measure_with_line():
    lines = ["ignored", "| d : r : m : f |"]
    assert find_beats_per_measure(lines, with_line=True) == (4, 2)

def test_find_beats_per_measure_with_line_none():
    assert find_beats_per_measure(["d | r"], with_line=True) == (None, None)

def test_resolve_no_warning_when_consistent(capsys):
    lines = ["| d : r : m : f | s : l : t : d |"]
    resolve_beats_per_measure(lines, header_timesig="4/4")
    assert capsys.readouterr().out == ""

def test_resolve_falls_back_to_header_when_no_music():
    assert resolve_beats_per_measure(["d | r"], header_timesig="3/4") == 3

def test_resolve_falls_back_to_spec_default_when_nothing():
    # No countable music and no header -> spec default numerator (4/4 -> 4).
    assert resolve_beats_per_measure(["d | r"]) == 4

def test_resolve_no_warning_when_suppressed(capsys):
    lines = ["| d : r : m : f | s : l : t : d |"]
    resolve_beats_per_measure(lines, header_timesig="3/4", warn=False)
    assert capsys.readouterr().out == ""
