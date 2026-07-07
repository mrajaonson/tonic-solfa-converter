"""Unit tests for converters.solfareformat."""

import pytest
from converters.solfareformat.converter import _align_block, _is_note_line, _reformat_note_line, reformat


# ──────────────────────────────────────────────────────────────────────
# _is_note_line
# ──────────────────────────────────────────────────────────────────────

def test_is_note_line_true_with_pipe_and_colon():
    assert _is_note_line("| d : m : f : s |") is True

def test_is_note_line_true_with_soft_barline():
    assert _is_note_line("| d : m ! s |") is True

def test_is_note_line_false_no_pipe():
    assert _is_note_line(":title: My Song") is False

def test_is_note_line_false_empty():
    assert _is_note_line("") is False

def test_is_note_line_false_pipe_without_colon():
    assert _is_note_line("| just text |") is False



# ──────────────────────────────────────────────────────────────────────
# _reformat_note_line - pipe normalization
# ──────────────────────────────────────────────────────────────────────

def test_pipe_no_spaces_added():
    # pipes without spaces get spaces added
    assert _reformat_note_line("|d:m!s|") == "| d : m ! s |"

def test_pipe_starting_pipe_no_leading_space():
    result = _reformat_note_line("| d : m ! s |")
    assert not result.startswith(" ")
    assert result.startswith("|")

def test_pipe_no_trailing_space():
    result = _reformat_note_line("| d : m ! s |")
    assert not result.endswith(" ")

def test_pipe_middle_pipes_get_space_both_sides():
    result = _reformat_note_line("| d : m ! s | r : f ! l |")
    # each interior pipe has exactly one space on each side
    assert " | " in result

def test_pipe_multiple_spaces_collapsed():
    assert _reformat_note_line("|  d  :  m  !  s  |") == "| d : m ! s |"

def test_pipe_already_clean_idempotent():
    line = "| d : m ! s |"
    assert _reformat_note_line(line) == line

def test_pipe_multi_measure():
    result = _reformat_note_line("|d:m!s|r:f!l|")
    assert result == "| d : m ! s | r : f ! l |"


# ──────────────────────────────────────────────────────────────────────
# _reformat_note_line - colon and soft-barline normalization
# ──────────────────────────────────────────────────────────────────────

def test_colon_no_spaces_added():
    assert _reformat_note_line("|d:m!s|") == "| d : m ! s |"

def test_soft_barline_no_spaces_added():
    assert _reformat_note_line("|d:m!s|") == "| d : m ! s |"

def test_real_line_already_clean():
    line = "| d : m.,s ! d' : t.,l | s : f ! m : - |"
    assert _reformat_note_line(line) == line

def test_real_line_missing_spaces():
    result = _reformat_note_line("|d:m.,s!d':t.,l|s:f!m:-|")
    assert result == "| d : m.,s ! d' : t.,l | s : f ! m : - |"

def test_voice_label_prefix_preserved():
    result = _reformat_note_line("S|d:m!s|")
    assert result == "S | d : m ! s |"

def test_voice_label_already_spaced():
    result = _reformat_note_line("S | d : m ! s |")
    assert result == "S | d : m ! s |"


# ──────────────────────────────────────────────────────────────────────
# reformat - integration via temp file
# ──────────────────────────────────────────────────────────────────────

def test_reformat_note_lines_normalized(tmp_path):
    src = tmp_path / "song.txt"
    src.write_text("|d:m!s|\n", encoding="utf-8")
    reformat(str(src))
    assert src.read_text(encoding="utf-8") == "| d : m ! s |\n"

def test_reformat_header_lines_untouched(tmp_path):
    src = tmp_path / "song.txt"
    src.write_text(":title:  My  Song\n", encoding="utf-8")
    reformat(str(src))
    assert src.read_text(encoding="utf-8") == ":title:  My  Song\n"

def test_reformat_colon_only_note_line_normalized(tmp_path):
    # 3/4 lines have | and : but no ! - must still be reformatted
    src = tmp_path / "song.txt"
    src.write_text("| d :-.d : d | r :-.r:r |\n", encoding="utf-8")
    reformat(str(src))
    assert src.read_text(encoding="utf-8") == "| d : -.d : d | r : -.r : r |\n"

def test_reformat_comment_lines_untouched(tmp_path):
    src = tmp_path / "song.txt"
    src.write_text("//  a  comment\n", encoding="utf-8")
    reformat(str(src))
    assert src.read_text(encoding="utf-8") == "//  a  comment\n"

def test_reformat_notes_section_untouched(tmp_path):
    src = tmp_path / "song.txt"
    content = "[notes]\nThis  has  extra  spaces.\n"
    src.write_text(content, encoding="utf-8")
    reformat(str(src))
    assert src.read_text(encoding="utf-8") == content

def test_reformat_notes_section_marker_preserved(tmp_path):
    src = tmp_path / "song.txt"
    content = ":title: Song\n[notes]\nSome notes.\n"
    src.write_text(content, encoding="utf-8")
    reformat(str(src))
    result = src.read_text(encoding="utf-8")
    assert "[notes]" in result
    assert "Some notes." in result

# ──────────────────────────────────────────────────────────────────────
# _align_block
# ──────────────────────────────────────────────────────────────────────

def test_align_block_single_line_unchanged():
    line = "| d : m : f |"
    assert _align_block([line]) == [line]

def test_align_block_pads_short_cells():
    lines = [
        "| (p)d : -.d : d |",
        "| s, : -.s, : s, |",
    ]
    result = _align_block(lines)
    assert result == [
        "| (p)d : -.d  : d  |",
        "| s,   : -.s, : s, |",
    ]

def test_align_block_separators_are_vertically_aligned():
    lines = [
        "| (p)d : -.d : d |",
        "| s, : -.s, : s, |",
    ]
    result = _align_block(lines)
    # Every separator column must be the same across all lines
    import re as _re
    cols = [[m.start() for m in _re.finditer(r'[|:!]', r)] for r in result]
    assert cols[0] == cols[1]

def test_align_block_already_aligned_idempotent():
    lines = [
        "| (p)d : -.d : d |",
        "| s, : -.s, : s, |",
    ]
    first  = _align_block(lines)
    second = _align_block(first)
    assert first == second

def test_align_block_compatible_shorter_line():
    # 1-measure line aligns with first measure of 2-measure line
    lines = [
        "| (p)d : d |",   # 1 measure
        "| s, : s, | t, : t, |",  # 2 measures
    ]
    result = _align_block(lines)
    import re as _re
    # Column of first ':' must match across both lines
    col0 = result[0].index(' : ')
    col1 = result[1].index(' : ')
    assert col0 == col1

def test_align_block_incompatible_separators_passthrough():
    # Same position has different separator chars - can't align
    lines = [
        "| d : m ! s |",   # position 2 is '!'
        "| d : m : f |",   # position 2 is ':'
    ]
    assert _align_block(lines) == lines

def test_align_block_trailing_partial_keeps_space_after_last_separator():
    # A line ending on a partial measure (no closing '|') must keep a space
    # after its final ':' - it is not a closing pipe.
    result = _align_block(["| d : r : m | s : l"])
    assert result == ["| d : r : m | s : l"]
    assert " : l" in result[0] and ":l" not in result[0]

def test_align_block_voice_label_prefix():
    lines = [
        "S | d : m |",
        "SA | d : m |",
    ]
    result = _align_block(lines)
    assert result[0].startswith("S  |")
    assert result[1].startswith("SA |")

def test_align_block_cross_block_same_structure(tmp_path):
    # Two blocks with same structure separated by a lyric line should align globally
    src = tmp_path / "song.txt"
    content = (
        "| (p)d : d |\n"    # block 1
        "| s, : s, |\n"     # block 1
        "lyric line\n"
        "| m : m |\n"       # block 2 - same structure as block 1
        "| t, : t, |\n"     # block 2
    )
    src.write_text(content, encoding="utf-8")
    reformat(str(src))
    result = src.read_text(encoding="utf-8")
    result_lines = result.splitlines()
    # All four note lines must have separators at the same columns
    import re as _re
    note_lines = [l for l in result_lines if _is_note_line(l)]
    assert len(note_lines) == 4
    cols = [[m.start() for m in _re.finditer(r'[|:]', l)] for l in note_lines]
    assert all(c == cols[0] for c in cols)

def test_reformat_lyric_lines_untouched(tmp_path):
    src = tmp_path / "song.txt"
    src.write_text("A-ma-zing  grace!\n", encoding="utf-8")
    reformat(str(src))
    assert src.read_text(encoding="utf-8") == "A-ma-zing  grace!\n"

def test_reformat_full_file(tmp_path):
    src = tmp_path / "song.txt"
    content = (
        ":title:  Joyful\n"
        "//  comment\n"
        "|d:m!s|\n"
        "| d : m : f : s |\n"
        "A-ma-zing  grace\n"
        "[notes]\n"
        "Some  notes  here.\n"
    )
    src.write_text(content, encoding="utf-8")
    reformat(str(src))
    result = src.read_text(encoding="utf-8")

    assert ":title:  Joyful\n" in result          # header untouched
    assert "//  comment\n" in result              # comment untouched
    assert "| d : m ! s |\n" in result            # note line with ! reformatted
    assert "| d : m : f : s |\n" in result        # note line with | and : reformatted
    assert "A-ma-zing  grace\n" in result         # lyric untouched
    assert "[notes]\n" in result                   # marker preserved
    assert "Some  notes  here.\n" in result        # notes section untouched
