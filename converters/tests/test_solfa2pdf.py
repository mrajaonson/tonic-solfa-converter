"""Unit tests for converters.solfa2pdf - parser and data structures."""

import pytest
from converters.solfa2pdf.data_structures import (
    NoteType, Note, Beat, Measure, VoiceLine, LyricLine, Block, Song, Expression,
)
from converters.solfa2pdf.solfa_parser import TonicSolfaParser


# ──────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────

def _parse(text: str):
    return TonicSolfaParser().parse(text)


def _parser():
    return TonicSolfaParser()


# ──────────────────────────────────────────────────────────────────────
# Data structures
# ──────────────────────────────────────────────────────────────────────

class TestNote:
    def test_display_text_note(self):
        n = Note(type=NoteType.NOTE, solfa="d", octave_modifier="'")
        assert n.display_text() == "d'"

    def test_display_text_rest(self):
        assert Note(type=NoteType.REST).display_text() == ""

    def test_display_text_hold(self):
        assert Note(type=NoteType.HOLD).display_text() == "-"

    def test_display_text_modulation(self):
        n = Note(type=NoteType.MODULATION, modulation_to="s")
        assert n.display_text() == "s"

    def test_display_text_chord(self):
        chord_notes = [
            Note(type=NoteType.NOTE, solfa="d"),
            Note(type=NoteType.NOTE, solfa="m"),
            Note(type=NoteType.NOTE, solfa="s"),
        ]
        n = Note(type=NoteType.CHORD, chord_notes=chord_notes)
        assert n.display_text() == "<d.m.s>"


class TestBeat:
    def test_all_notes_not_subdivided(self):
        b = Beat(notes=[Note(type=NoteType.NOTE, solfa="d")])
        assert len(b.all_notes()) == 1

    def test_all_notes_subdivided(self):
        b = Beat(
            is_subdivided=True,
            first_half=[Note(type=NoteType.NOTE, solfa="d")],
            second_half=[Note(type=NoteType.NOTE, solfa="r")],
        )
        assert len(b.all_notes()) == 2

    def test_display_text_subdivided(self):
        b = Beat(
            is_subdivided=True,
            first_half=[Note(type=NoteType.NOTE, solfa="d")],
            second_half=[Note(type=NoteType.NOTE, solfa="r")],
        )
        assert b.display_text() == "d.r"

    def test_display_text_simple(self):
        b = Beat(notes=[Note(type=NoteType.NOTE, solfa="m")])
        assert b.display_text() == "m"


class TestMeasure:
    def test_display_text_normal(self):
        m = Measure(beats=[
            Beat(notes=[Note(type=NoteType.NOTE, solfa="d")]),
            Beat(notes=[Note(type=NoteType.NOTE, solfa="r")]),
        ])
        assert m.display_text() == "d:r"

    def test_display_text_empty(self):
        m = Measure(is_empty=True, beats=[Beat(), Beat()])
        assert ":" in m.display_text()


# ──────────────────────────────────────────────────────────────────────
# _parse_header_line / parse - header properties
# ──────────────────────────────────────────────────────────────────────

class TestParseHeader:
    def test_title(self):
        song = _parse(":title: Amazing Grace\n| d:r:m:f |")
        assert song.title == "Amazing Grace"

    def test_key(self):
        song = _parse(":key: G\n| d:r:m:f |")
        assert song.key == "G"

    def test_timesig(self):
        song = _parse(":timesig: 3/4\n| d:r:m |")
        assert song.time_sig == (3, 4)

    def test_tempo_as_int(self):
        song = _parse(":tempo: 96\n| d:r:m:f |")
        assert song.tempo == 96
        assert isinstance(song.tempo, int)

    def test_author_appended(self):
        song = _parse(":author: John Newton\n:author: William Cowper\n| d |")
        assert "John Newton" in song.authors
        assert "William Cowper" in song.authors

    def test_composer_appended(self):
        song = _parse(":composer: Bach\n| d |")
        assert "Bach" in song.composers

    def test_unknown_prop_ignored(self):
        song = _parse(":unknownprop: value\n:title: My Song\n| d |")
        assert song.title == "My Song"

    def test_comment_line_skipped(self):
        song = _parse("// a comment\n:title: My Song\n| d |")
        assert song.title == "My Song"

    def test_invalid_tempo_does_not_raise(self):
        # int() conversion fails silently; tempo stays as spec default (may be None)
        song = _parse(":tempo: notanumber\n| d |")
        assert song  # no exception raised

    def test_invalid_timesig_ignored(self):
        song = _parse(":timesig: bad\n| d |")
        assert song.time_sig == (4, 4)  # default unchanged


# ──────────────────────────────────────────────────────────────────────
# _split_into_measures
# ──────────────────────────────────────────────────────────────────────

class TestSplitIntoMeasures:
    def setup_method(self):
        self.p = _parser()

    def test_two_measures(self):
        parts = self.p._split_into_measures("| d:r:m:f | s:l:t:d' |")
        assert len(parts) == 2

    def test_strips_edge_barlines(self):
        parts = self.p._split_into_measures("| d:r |")
        assert parts[0].strip() == "d:r"

    def test_double_barline_at_end(self):
        parts = self.p._split_into_measures("| d:r:m:f ||")
        assert len(parts) == 1

    def test_no_empty_parts(self):
        parts = self.p._split_into_measures("| d | r |")
        assert all(p.strip() for p in parts)


# ──────────────────────────────────────────────────────────────────────
# _parse_beat / _parse_note_group / _parse_single_note_from_start
# ──────────────────────────────────────────────────────────────────────

class TestParseBeat:
    def setup_method(self):
        self.p = _parser()

    def test_single_note(self):
        beat = self.p._parse_beat("d")
        assert beat.notes[0].solfa == "d"
        assert beat.notes[0].type == NoteType.NOTE

    def test_hold(self):
        beat = self.p._parse_beat("-")
        assert beat.notes[0].type == NoteType.HOLD

    def test_explicit_rest(self):
        beat = self.p._parse_beat("*")
        assert beat.notes[0].type == NoteType.REST

    def test_empty_is_rest(self):
        beat = self.p._parse_beat("")
        assert beat.notes[0].type == NoteType.REST

    def test_octave_up(self):
        beat = self.p._parse_beat("d'")
        assert beat.notes[0].octave_modifier == "'"

    def test_octave_down(self):
        beat = self.p._parse_beat("d,")
        assert beat.notes[0].octave_modifier == ","

    def test_subdivided_beat(self):
        beat = self.p._parse_beat("d.r")
        assert beat.is_subdivided is True
        assert beat.first_half[0].solfa == "d"
        assert beat.second_half[0].solfa == "r"

    def test_staccato(self):
        beat = self.p._parse_beat(",d")
        assert beat.notes[0].is_staccato is True

    def test_dynamic_expression(self):
        beat = self.p._parse_beat("(p)d")
        assert any(e.type == "dynamic" for e in beat.notes[0].expressions)

    def test_fermata_expression(self):
        beat = self.p._parse_beat("(^)d")
        assert any(e.type == "fermata" for e in beat.notes[0].expressions)

    def test_chord_via_note_group(self):
        # _parse_beat splits on the first '.', so chords must be tested via
        # _parse_note_group which handles the full chord token correctly
        notes = self.p._parse_note_group("<d.m.s>")
        assert notes[0].type == NoteType.CHORD
        assert len(notes[0].chord_notes) == 3

    def test_modulation(self):
        beat = self.p._parse_beat("r/s")
        assert beat.notes[0].type == NoteType.MODULATION

    def test_modulation_with_key_change(self):
        beat = self.p._parse_beat("(G)r/s")
        assert beat.notes[0].type == NoteType.MODULATION
        assert beat.notes[0].key_change == "G"

    def test_all_solfa_notes_parsed(self):
        for note in ["d", "r", "m", "f", "s", "l", "t"]:
            beat = self.p._parse_beat(note)
            assert beat.notes[0].solfa == note, f"Failed for: {note}"

    def test_tuplet_three_notes(self):
        beat = self.p._parse_beat("drm")
        assert len(beat.notes) == 3

    def test_duration_fraction_single(self):
        beat = self.p._parse_beat("d")
        assert beat.notes[0].duration_fraction == pytest.approx(1.0)

    def test_duration_fraction_subdivided(self):
        beat = self.p._parse_beat("d.r")
        assert beat.first_half[0].duration_fraction == pytest.approx(0.5)
        assert beat.second_half[0].duration_fraction == pytest.approx(0.5)


# ──────────────────────────────────────────────────────────────────────
# _parse_measure
# ──────────────────────────────────────────────────────────────────────

class TestParseMeasure:
    def setup_method(self):
        self.p = _parser()

    def test_four_four(self):
        m = self.p._parse_measure("d:r:m:f")
        assert len(m.beats) == 4

    def test_soft_barline_recorded(self):
        m = self.p._parse_measure("d:r!m:f")
        assert m.soft_barline_after_beat >= 0

    def test_empty_measure(self):
        m = self.p._parse_measure("")
        assert m.is_empty is True


# ──────────────────────────────────────────────────────────────────────
# _parse_voice_line
# ──────────────────────────────────────────────────────────────────────

class TestParseVoiceLine:
    def setup_method(self):
        self.p = _parser()

    def test_explicit_soprano_label(self):
        vl = self.p._parse_voice_line("S | d:r:m:f | s:l:t:d' |", 0, 4)
        assert vl.voice_label == "S"
        assert len(vl.measures) == 2

    def test_implicit_label_by_order(self):
        vl = self.p._parse_voice_line("| d:r:m:f |", 1, 4)
        # Second line of 4 → "A"
        assert vl.voice_label == "A"

    def test_numbered_voice_label(self):
        vl = self.p._parse_voice_line("S1 | d:r:m:f |", 0, 2)
        assert vl.voice_label == "S1"

    def test_measure_numbers_increment(self):
        self.p.current_measure_num = 4
        vl = self.p._parse_voice_line("| d:r:m:f | s:l:t:d' |", 0, 1)
        assert vl.measures[0].number == 5
        assert vl.measures[1].number == 6


# ──────────────────────────────────────────────────────────────────────
# _parse_lyric_line
# ──────────────────────────────────────────────────────────────────────

class TestParseLyricLine:
    def setup_method(self):
        self.p = _parser()
        self.voices = ["S", "A", "T", "B"]

    def test_plain_lyrics(self):
        ll = self.p._parse_lyric_line("A-ma-zing grace", self.voices)
        assert "A-" in ll.syllables
        assert ll.verse == "1"

    def test_refrain_prefix(self):
        ll = self.p._parse_lyric_line("R Hal-le-lu-jah", self.voices)
        assert ll.verse == "R"

    def test_verse_number(self):
        ll = self.p._parse_lyric_line("2 second verse", self.voices)
        assert ll.verse == "2"

    def test_voice_prefix(self):
        ll = self.p._parse_lyric_line("SA words here", self.voices)
        assert ll.voices == ["S", "A"]

    def test_verse_and_voice(self):
        ll = self.p._parse_lyric_line("1SA words", self.voices)
        assert ll.verse == "1"
        assert "S" in ll.voices and "A" in ll.voices

    def test_empty_returns_none(self):
        result = self.p._parse_lyric_line("", self.voices)
        assert result is None

    def test_rest_skip_in_lyrics(self):
        ll = self.p._parse_lyric_line("word * next", self.voices)
        assert "*" in ll.syllables

    def test_join_char_becomes_space(self):
        from converters.shared import spec
        join = spec["lyrics"]["join"]
        ll = self.p._parse_lyric_line(f"two{join}words", self.voices)
        assert "two words" in ll.syllables


# ──────────────────────────────────────────────────────────────────────
# _parse_syllables
# ──────────────────────────────────────────────────────────────────────

class TestParseSyllables:
    def setup_method(self):
        self.p = _parser()

    def test_single_word(self):
        s = self.p._parse_syllables("Amazing")
        assert s == ["Amazing"]

    def test_hyphenated(self):
        s = self.p._parse_syllables("A-ma-zing")
        assert s == ["A-", "ma-", "zing"]

    def test_trailing_hyphen(self):
        s = self.p._parse_syllables("ma-")
        assert s == ["ma-"]

    def test_multiple_words(self):
        s = self.p._parse_syllables("how sweet the sound")
        assert s == ["how", "sweet", "the", "sound"]


# ──────────────────────────────────────────────────────────────────────
# _parse_voice_labels
# ──────────────────────────────────────────────────────────────────────

class TestParseVoiceLabels:
    def setup_method(self):
        self.p = _parser()

    def test_satb(self):
        assert self.p._parse_voice_labels("SATB") == ["S", "A", "T", "B"]

    def test_sa(self):
        assert self.p._parse_voice_labels("SA") == ["S", "A"]

    def test_numbered(self):
        assert self.p._parse_voice_labels("S1S2") == ["S1", "S2"]

    def test_invalid(self):
        assert self.p._parse_voice_labels("XYZ") == []

    def test_partial_invalid(self):
        # Stops at non-voice char, doesn't consume whole string → invalid
        assert self.p._parse_voice_labels("SX") == []


# ──────────────────────────────────────────────────────────────────────
# _parse_expression
# ──────────────────────────────────────────────────────────────────────

class TestParseExpression:
    def setup_method(self):
        self.p = _parser()

    def test_dynamic(self):
        e = self.p._parse_expression("p")
        assert e.type == "dynamic"
        assert e.value == "p"

    def test_fermata(self):
        e = self.p._parse_expression("^")
        assert e.type == "fermata"

    def test_navigation_dc(self):
        e = self.p._parse_expression("DC")
        assert e.type == "navigation"

    def test_numbered_navigation(self):
        e = self.p._parse_expression("DS1")
        assert e is not None
        assert e.type == "navigation"

    def test_unknown_returns_none(self):
        e = self.p._parse_expression("XYZ")
        assert e is None


# ──────────────────────────────────────────────────────────────────────
# Full parse integration (parser.parse)
# ──────────────────────────────────────────────────────────────────────

class TestParseIntegration:
    SIMPLE = """:title: Test Song
:key: G
:timesig: 4/4
| d:r:m:f | s:l:t:d' |
A-ma-zing grace
"""

    def test_block_count(self):
        song = _parse(self.SIMPLE)
        assert len(song.blocks) == 1

    def test_voice_line_count(self):
        song = _parse(self.SIMPLE)
        assert len(song.blocks[0].voice_lines) == 1

    def test_measure_count(self):
        song = _parse(self.SIMPLE)
        assert len(song.blocks[0].voice_lines[0].measures) == 2

    def test_lyric_line_parsed(self):
        song = _parse(self.SIMPLE)
        assert len(song.blocks[0].lyric_lines) == 1
        assert "A-" in song.blocks[0].lyric_lines[0].syllables

    def test_multiple_voice_lines(self):
        text = """:title: SATB
| d:r:m:f |
| s:l:t:d' |
| m:f:s:l |
| d,:r,:m,:f, |
words here
"""
        song = _parse(text)
        assert len(song.blocks[0].voice_lines) == 4

    def test_multiple_blocks(self):
        text = """:title: Multi
| d:r:m:f |

| s:l:t:d' |
"""
        song = _parse(text)
        assert len(song.blocks) == 2

    def test_comment_lines_excluded(self):
        text = """:title: T
// this is a comment
| d:r:m:f |
"""
        song = _parse(text)
        assert len(song.blocks) == 1
