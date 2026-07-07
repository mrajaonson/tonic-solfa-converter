"""Unit tests for converters.solfa2musicxml (parser and duration modules)."""

import pytest
from converters.solfa2musicxml.models import NoteEvent, TimedEvent
from converters.solfa2musicxml.solfa_parser import (
    parse_header,
    parse_beat_tokens,
    parse_voice_line,
    parse_lyrics_line,
    _extract_voice_label,
    _split_measures,
    _detect_modulation,
    _protect_chord_dots,
    _restore_chord_dots,
)
from converters.shared import is_navigation_marker as _is_navigation_marker
from converters.solfa2musicxml.duration import (
    assign_durations,
    consolidate_holds,
)


# ──────────────────────────────────────────────────────────────────────
# parse_header
# ──────────────────────────────────────────────────────────────────────

def test_parse_header_reads_title():
    lines = [":title: Amazing Grace", ":key: G", "| d:r:m |"]
    props, remaining = parse_header(lines)
    assert props["title"] == "Amazing Grace"
    assert props["key"] == "G"
    assert any("d:r:m" in l for l in remaining)


def test_parse_header_int_prop_tempo():
    lines = [":tempo: 120"]
    props, _ = parse_header(lines)
    assert props["tempo"] == 120
    assert isinstance(props["tempo"], int)


def test_parse_header_unknown_prop_ignored():
    lines = [":unknownprop: value", ":title: My Song"]
    props, _ = parse_header(lines)
    assert "unknownprop" not in props
    assert props["title"] == "My Song"


def test_parse_header_stops_at_non_header_line():
    lines = [":title: Song", "This is body text", ":key: G"]
    props, remaining = parse_header(lines)
    # key G appears after body text - should not be parsed as header
    assert "key" not in props or props.get("key") != "G"
    assert any("body text" in l for l in remaining)


def test_parse_header_comment_lines_passed_through():
    lines = [":title: Song", "// a comment", "| d |"]
    _, remaining = parse_header(lines)
    assert any("// a comment" in l for l in remaining)


def test_parse_header_defaults_present():
    props, _ = parse_header([])
    assert "title" in props
    assert "key" in props
    assert "timesig" in props


# ──────────────────────────────────────────────────────────────────────
# parse_beat_tokens
# ──────────────────────────────────────────────────────────────────────

def test_parse_beat_tokens_single_note():
    events = parse_beat_tokens("d")
    assert len(events) == 1
    assert events[0].solfa == "d"
    assert not events[0].is_rest
    assert not events[0].is_hold


def test_parse_beat_tokens_hold():
    events = parse_beat_tokens("-")
    assert len(events) == 1
    assert events[0].is_hold


def test_parse_beat_tokens_rest_explicit():
    events = parse_beat_tokens("*")
    assert len(events) == 1
    assert events[0].is_rest


def test_parse_beat_tokens_empty_is_rest():
    events = parse_beat_tokens("")
    assert len(events) == 1
    assert events[0].is_rest


def test_parse_beat_tokens_octave_up():
    events = parse_beat_tokens("d'")
    assert events[0].octave_shift == 1


def test_parse_beat_tokens_octave_down():
    events = parse_beat_tokens("d,")
    assert events[0].octave_shift == -1


def test_parse_beat_tokens_dynamic_prefix():
    events = parse_beat_tokens("(p)d")
    assert events[0].dynamic == "p"
    assert events[0].solfa == "d"


def test_parse_beat_tokens_fermata_prefix():
    events = parse_beat_tokens("(^)d")
    assert events[0].fermata is True


def test_parse_beat_tokens_subbeat_split():
    # d.r → two events sharing the beat
    events = parse_beat_tokens("d.r")
    assert len(events) == 2
    assert events[0].solfa == "d"
    assert events[1].solfa == "r"


def test_parse_beat_tokens_staccato():
    events = parse_beat_tokens(",d")
    assert events[0].is_staccato is True


def test_parse_beat_tokens_all_solfa_notes():
    for note in ["d", "r", "m", "f", "s", "l", "t"]:
        events = parse_beat_tokens(note)
        assert events[0].solfa == note, f"Failed for note: {note}"


def test_parse_beat_tokens_navigation_marker():
    events = parse_beat_tokens("(DC)d")
    # navigation is extracted at measure level in parse_voice_line;
    # at token level it is still attached to the event
    assert events[0].navigation == "DC"


# ──────────────────────────────────────────────────────────────────────
# _extract_voice_label
# ──────────────────────────────────────────────────────────────────────

def test_extract_voice_label_soprano():
    label, rest = _extract_voice_label("S | d:r:m |")
    assert label == "S"
    assert "d:r:m" in rest


def test_extract_voice_label_none_when_missing():
    label, rest = _extract_voice_label("| d:r:m |")
    assert label is None


def test_extract_voice_label_tenor():
    label, rest = _extract_voice_label("T | s:l:t |")
    assert label == "T"


# ──────────────────────────────────────────────────────────────────────
# _split_measures
# ──────────────────────────────────────────────────────────────────────

def test_split_measures_two_bars():
    parts = _split_measures("| d:r:m:f | s:l:t:d' |")
    assert len(parts) == 2


def test_split_measures_strips_edge_bars():
    parts = _split_measures("| d:r |")
    assert parts[0].strip() == "d:r"


def test_split_measures_collapses_double_bar():
    parts = _split_measures("d:r || s:l")
    # || collapses to single separator
    assert len(parts) == 2


# ──────────────────────────────────────────────────────────────────────
# _detect_modulation
# ──────────────────────────────────────────────────────────────────────

def test_detect_modulation_found():
    mod, remaining, key_change = _detect_modulation("r/s")
    assert mod is not None
    assert "/" in mod


def test_detect_modulation_not_found():
    mod, remaining, key_change = _detect_modulation("d")
    assert mod is None
    assert remaining == "d"


def test_detect_modulation_with_key_change():
    mod, remaining, key_change = _detect_modulation("(G)r/s")
    assert key_change == "G"
    assert mod is not None


def test_detect_modulation_slash_in_invalid_position():
    # Slash not between valid solfa tokens → no modulation
    mod, remaining, key_change = _detect_modulation("3/4")
    assert mod is None


# ──────────────────────────────────────────────────────────────────────
# _is_navigation_marker
# ──────────────────────────────────────────────────────────────────────

def test_is_navigation_marker_dc():
    assert _is_navigation_marker("DC") is True


def test_is_navigation_marker_fine():
    assert _is_navigation_marker("FINE") is True


def test_is_navigation_marker_numbered():
    assert _is_navigation_marker("DS1") is True
    assert _is_navigation_marker("SEGNO2") is True


def test_is_navigation_marker_unknown():
    assert _is_navigation_marker("XYZ") is False


# ──────────────────────────────────────────────────────────────────────
# _protect_chord_dots / _restore_chord_dots
# ──────────────────────────────────────────────────────────────────────

def test_protect_chord_dots_replaces_inside():
    result = _protect_chord_dots("<d.m.s>")
    assert "." not in result
    assert "<" in result and ">" in result


def test_protect_chord_dots_leaves_outside_unchanged():
    result = _protect_chord_dots("d.r.<m.s>.l")
    # dots outside <> stay; dots inside <> are replaced
    assert result.startswith("d.r.")
    assert result.endswith(".l")


def test_restore_chord_dots_round_trips():
    original = "<d.m.s>"
    protected = _protect_chord_dots(original)
    restored = _restore_chord_dots(protected)
    assert restored == original


# ──────────────────────────────────────────────────────────────────────
# parse_voice_line
# ──────────────────────────────────────────────────────────────────────

def test_parse_voice_line_simple():
    label, measures = parse_voice_line("S | d:r:m:f | s:l:t:d' |")
    assert label == "S"
    assert len(measures) == 2


def test_parse_voice_line_no_label():
    label, measures = parse_voice_line("| d:r:m:f |")
    assert label is None
    assert len(measures) == 1


def test_parse_voice_line_navigation_extracted_to_measure():
    _, measures = parse_voice_line("| (DC)d:r:m:f |")
    assert measures[0]["navigation"] == ["DC"]
    # navigation cleared from the note event itself
    beats = measures[0]["beats"]
    for beat in beats:
        for evt in beat:
            assert evt.navigation is None


def test_parse_voice_line_nav_only_beat_dropped():
    # |(DC)| beat with navigation only should be dropped, not a real beat
    _, measures = parse_voice_line("| d:r:(DC):f |")
    assert measures[0]["navigation"] == ["DC"]
    # The nav-only beat is removed; remaining beats cover d, r, f
    total_beats = len(measures[0]["beats"])
    assert total_beats == 3


def test_parse_voice_line_multiple_navs_same_measure():
    # DC and CODA in the same measure - both must be preserved
    _, measures = parse_voice_line("| (DC)d : - ! - : (CODA)l |")
    assert measures[0]["navigation"] == ["DC", "CODA"]


def test_parse_voice_line_modulation_recorded():
    _, measures = parse_voice_line("| r/s |")
    assert len(measures[0]["modulations"]) == 1


# ──────────────────────────────────────────────────────────────────────
# parse_lyrics_line
# ──────────────────────────────────────────────────────────────────────

def test_parse_lyrics_line_single_word():
    voices, verse_id, syllables = parse_lyrics_line("Amazing")
    assert syllables[0] == ("Amazing", "single")


def test_parse_lyrics_line_hyphenated():
    voices, verse_id, syllables = parse_lyrics_line("A-ma-zing")
    assert syllables[0][1] == "begin"
    assert syllables[1][1] == "middle"
    assert syllables[2][1] == "end"


def test_parse_lyrics_line_refrain_prefix():
    voices, verse_id, syllables = parse_lyrics_line("R Hal-le-lu-jah")
    assert verse_id == "R"


def test_parse_lyrics_line_verse_number():
    voices, verse_id, syllables = parse_lyrics_line("2 second verse")
    assert verse_id == 2


def test_parse_lyrics_line_voice_prefix():
    voices, verse_id, syllables = parse_lyrics_line("SA words here")
    assert voices == ["S", "A"]


def test_parse_lyrics_line_verse_and_voice():
    voices, verse_id, syllables = parse_lyrics_line("1SA words")
    assert verse_id == 1
    assert voices == ["S", "A"]


def test_parse_lyrics_line_no_prefix_all_voices():
    voices, verse_id, syllables = parse_lyrics_line("just words")
    assert voices is None


# ──────────────────────────────────────────────────────────────────────
# assign_durations
# ──────────────────────────────────────────────────────────────────────

def _make_measure(n_beats: int) -> dict:
    """Helper: measure with n_beats of a single note each."""
    beats = [[NoteEvent(solfa="d", semitone=0)] for _ in range(n_beats)]
    return {"beats": beats, "modulations": [], "key_changes": [], "navigation": None}


def test_assign_durations_4_4_quarter_notes():
    measures = [_make_measure(4)]
    result = assign_durations(measures, "4/4")
    assert len(result) == 1
    for te in result[0]:
        assert te.quarter_length == pytest.approx(1.0)


def test_assign_durations_3_4_quarter_notes():
    measures = [_make_measure(3)]
    result = assign_durations(measures, "3/4")
    for te in result[0]:
        assert te.quarter_length == pytest.approx(1.0)


def test_assign_durations_subbeat_halves_duration():
    # 4 beat groups in 4/4; last group has 2 sub-events → each gets 0.5 ql
    beats = [
        [NoteEvent(solfa="d", semitone=0)],
        [NoteEvent(solfa="r", semitone=2)],
        [NoteEvent(solfa="m", semitone=4)],
        [NoteEvent(solfa="f", semitone=5), NoteEvent(solfa="s", semitone=7)],  # subbeat split
    ]
    measures = [{"beats": beats, "modulations": [], "key_changes": [], "navigation": None}]
    result = assign_durations(measures, "4/4")
    # First three events: 1.0 ql each; last two sub-events: 0.5 ql each
    assert result[0][0].quarter_length == pytest.approx(1.0)
    assert result[0][-1].quarter_length == pytest.approx(0.5)
    assert result[0][-2].quarter_length == pytest.approx(0.5)


def test_assign_durations_multiple_measures():
    measures = [_make_measure(4), _make_measure(4)]
    result = assign_durations(measures, "4/4")
    assert len(result) == 2


def test_assign_durations_6_8():
    measures = [_make_measure(6)]
    result = assign_durations(measures, "6/8")
    for te in result[0]:
        assert te.quarter_length == pytest.approx(0.5)


# ──────────────────────────────────────────────────────────────────────
# consolidate_holds
# ──────────────────────────────────────────────────────────────────────

def _te(is_hold=False, is_rest=False, ql=1.0, dynamic=None, fermata=False):
    evt = NoteEvent(is_hold=is_hold, is_rest=is_rest, solfa=None if (is_hold or is_rest) else "d",
                    semitone=0, dynamic=dynamic, fermata=fermata)
    return TimedEvent(evt, ql)


def test_consolidate_holds_merges_hold():
    measures = [[_te(ql=1.0), _te(is_hold=True, ql=1.0)]]
    result = consolidate_holds(measures)
    assert len(result[0]) == 1
    assert result[0][0].quarter_length == pytest.approx(2.0)


def test_consolidate_holds_no_hold_unchanged():
    measures = [[_te(ql=1.0), _te(ql=1.0)]]
    result = consolidate_holds(measures)
    assert len(result[0]) == 2


def test_consolidate_holds_transfers_fermata():
    measures = [[_te(ql=1.0), _te(is_hold=True, ql=1.0, fermata=True)]]
    result = consolidate_holds(measures)
    assert result[0][0].event.fermata is True


def test_consolidate_holds_transfers_dynamic():
    measures = [[_te(ql=1.0), _te(is_hold=True, ql=1.0, dynamic="p")]]
    result = consolidate_holds(measures)
    assert result[0][0].event.dynamic == "p"


def test_consolidate_holds_multiple_consecutive():
    measures = [[_te(ql=1.0), _te(is_hold=True, ql=1.0), _te(is_hold=True, ql=1.0)]]
    result = consolidate_holds(measures)
    assert len(result[0]) == 1
    assert result[0][0].quarter_length == pytest.approx(3.0)


def test_consolidate_holds_hold_at_start_not_merged():
    # Hold with no preceding note stays as-is
    measures = [[_te(is_hold=True, ql=1.0), _te(ql=1.0)]]
    result = consolidate_holds(measures)
    assert len(result[0]) == 2


# ──────────────────────────────────────────────────────────────────────
# Partial (boundary-pipe-optional) measures
# ──────────────────────────────────────────────────────────────────────

def test_parse_voice_line_partial_flags():
    label, measures = parse_voice_line("d | r : m : f : s | f", beats_per_measure=4)
    assert [m["is_partial"] for m in measures] == [True, False, True]
    assert measures[0]["partial_side"] == "leading"
    assert measures[2]["partial_side"] == "trailing"


def test_parse_voice_line_leading_colon_stripped():
    # ": d" -> 1-beat partial (bare leading ':' is a skip-marker, not a rest)
    label, measures = parse_voice_line(": d | r : m : f : s | f", beats_per_measure=4)
    assert measures[0]["is_partial"]
    assert len(measures[0]["beats"]) == 1


def test_parse_voice_line_boundary_full_warns(capsys):
    # 2/4: "d : r" is a full boundary fragment -> warn, not partial
    label, measures = parse_voice_line("d : r | m : d | s : l", beats_per_measure=2)
    assert all(not m["is_partial"] for m in measures)
    assert "without a barline" in capsys.readouterr().out


def test_parse_voice_line_no_beats_per_measure_is_backward_compatible():
    # Without beats_per_measure the old behavior holds (no partial handling)
    label, measures = parse_voice_line("| d:r:m:f | s:l:t:d' |")
    assert all(not m.get("is_partial") for m in measures)


def test_assign_durations_partial_is_short():
    # 1-beat pickup in 4/4 is a quarter note (1.0 ql), not a whole note (4.0)
    _, measures = parse_voice_line("d | r : m : f : s | f", beats_per_measure=4)
    timed = assign_durations(measures, "4/4")
    assert sum(te.quarter_length for te in timed[0]) == pytest.approx(1.0)
    assert sum(te.quarter_length for te in timed[1]) == pytest.approx(4.0)
    assert sum(te.quarter_length for te in timed[2]) == pytest.approx(1.0)


def test_parse_header_disambiguates_colon_note_line():
    # A note line starting with ':' must end the header, not be dropped as a prop
    props, remaining = parse_header([":title: Song", ": d | r : m : f : s | f"])
    assert props["title"] == "Song"
    assert any(": d" in line for line in remaining)


def test_build_score_partial_measures_are_pickups(tmp_path):
    from music21 import stream
    from converters.solfa2musicxml.solfa_parser import parse_file
    from converters.solfa2musicxml.builder import build_score

    src = tmp_path / "pickup.txt"
    src.write_text(
        ":title: Pickup\n:key: C\n:timesig: 4/4\n\n"
        "d | r : m : f : s | l : t : d' : r' | m'\n",
        encoding="utf-8",
    )
    part = build_score(parse_file(str(src))).parts[0]
    ms = list(part.getElementsByClass(stream.Measure))
    # leading pickup: short, padded on the left
    assert ms[0].duration.quarterLength == pytest.approx(1.0)
    assert ms[0].paddingLeft == pytest.approx(3.0)
    # trailing pickup: short, padded on the right
    assert ms[-1].duration.quarterLength == pytest.approx(1.0)
    assert ms[-1].paddingRight == pytest.approx(3.0)
    # full interior measures untouched
    assert ms[1].duration.quarterLength == pytest.approx(4.0)


def test_build_score_leading_pickup_is_implicit_anacrusis(tmp_path):
    from music21 import stream
    from music21.stream.enums import ShowNumber
    from converters.solfa2musicxml.solfa_parser import parse_file
    from converters.solfa2musicxml.builder import build_score

    src = tmp_path / "anacrusis.txt"
    src.write_text(
        ":title: Anacrusis\n:key: G\n:timesig: 3/4\n\n"
        "s.s | s : m : r | d : t, : d | s : r : m |\n",
        encoding="utf-8",
    )
    ms = list(build_score(parse_file(str(src))).parts[0].getElementsByClass(stream.Measure))
    # leading pickup is a true anacrusis (implicit="yes" on export)
    assert ms[0].showNumber == ShowNumber.NEVER
    # interior/full measures keep their numbering
    assert ms[1].showNumber != ShowNumber.NEVER


# ──────────────────────────────────────────────────────────────────────
# Measures split across system/block breaks
# ──────────────────────────────────────────────────────────────────────

def _split_src():
    return (
        ":title: Split\n:key: G\n:timesig: 3/4\n\n"
        "| d : r : m | s : l\n\n"      # block 1 ends on 2-beat trailing partial
        "f | m : r : d |\n"            # block 2 opens with 1-beat continuation
    )


def test_split_measures_joined_into_one_complete_bar(tmp_path):
    from converters.solfa2musicxml.solfa_parser import parse_file
    src = tmp_path / "split.txt"
    src.write_text(_split_src(), encoding="utf-8")
    voices = parse_file(str(src))["voices"]
    measures = next(iter(voices.values()))
    # 3 complete bars: full, joined(s:l + f), full
    assert [len(m["beats"]) for m in measures] == [3, 3, 3]
    assert all(not m.get("is_partial") for m in measures)


def test_split_measure_full_duration(tmp_path):
    from converters.solfa2musicxml.solfa_parser import parse_file
    src = tmp_path / "split.txt"
    src.write_text(_split_src(), encoding="utf-8")
    measures = next(iter(parse_file(str(src))["voices"].values()))
    timed = assign_durations(measures, "3/4")
    assert [sum(te.quarter_length for te in tm) for tm in timed] == [
        pytest.approx(3.0), pytest.approx(3.0), pytest.approx(3.0)
    ]


def test_split_measure_builds_three_measures(tmp_path):
    from music21 import stream
    from converters.solfa2musicxml.solfa_parser import parse_file
    from converters.solfa2musicxml.builder import build_score
    src = tmp_path / "split.txt"
    src.write_text(_split_src(), encoding="utf-8")
    ms = list(build_score(parse_file(str(src))).parts[0].getElementsByClass(stream.Measure))
    assert [m.number for m in ms] == [1, 2, 3]
    assert [m.duration.quarterLength for m in ms] == [3.0, 3.0, 3.0]


def test_split_measure_mismatch_warns(tmp_path, capsys):
    from converters.solfa2musicxml.solfa_parser import parse_file
    # trailing 2 + leading 2 = 4 beats in 3/4 → warn
    src = tmp_path / "bad.txt"
    src.write_text(
        ":key: G\n:timesig: 3/4\n\n| d : r : m | s : l\n\nf : m | r : d : m |\n",
        encoding="utf-8",
    )
    parse_file(str(src))
    assert "split across a system break" in capsys.readouterr().out


def test_incomplete_ending_uses_regular_barline(tmp_path):
    from music21 import stream, bar
    from converters.solfa2musicxml.solfa_parser import parse_file
    from converters.solfa2musicxml.builder import build_score
    # trailing partial at the very end (no continuation) stays incomplete
    src = tmp_path / "end.txt"
    src.write_text(":key: G\n:timesig: 3/4\n\n| d : r : m | s : l\n", encoding="utf-8")
    ms = list(build_score(parse_file(str(src))).parts[0].getElementsByClass(stream.Measure))
    assert ms[-1].paddingRight == pytest.approx(1.0)
    assert ms[-1].rightBarline.type == "regular"
