"""Unit tests for converters.pdfimg2solfa.fixup."""

import pytest

from converters.pdfimg2solfa import fixup


def _tok(text, left=0, top=0, width=10, height=12, conf=90):
    return {
        "text": text,
        "left": left,
        "top": top,
        "width": width,
        "height": height,
        "conf": conf,
    }


# ---------------------------------------------------------------------------
# fixup_music_token
# ---------------------------------------------------------------------------

class TestFixupMusicToken:
    def test_clean_token_passes_through(self):
        assert fixup.fixup_music_token("d:r:m:f", 95) == "d:r:m:f"

    def test_unicode_dash_normalized(self):
        assert fixup.fixup_music_token("–.r:r:–", 95) == "-.r:r:-"

    def test_em_dash_normalized(self):
        assert fixup.fixup_music_token("-", 95) == "-"

    def test_semicolon_becomes_beat_separator(self):
        assert fixup.fixup_music_token("d;r;m", 95) == "d:r:m"

    def test_case_folded_to_lowercase(self):
        assert fixup.fixup_music_token("D:R:M:F", 95) == "d:r:m:f"

    def test_octave_low_marker_preserved(self):
        assert fixup.fixup_music_token("s,:l,:t,", 95) == "s,:l,:t,"

    def test_octave_high_marker_preserved(self):
        assert fixup.fixup_music_token("d':r':m'", 95) == "d':r':m'"

    def test_chromatic_tokens_recognized(self):
        # 'de', 're', 'fe' etc. are valid in the spec
        for token in ["de", "re", "fe", "se", "le", "ra", "ma", "ta"]:
            assert fixup.fixup_music_token(token, 95) == token

    def test_slur_underscore_preserved(self):
        assert fixup.fixup_music_token("l,._t,", 95) == "l,._t,"

    def test_subbeat_dot_preserved(self):
        assert fixup.fixup_music_token("m.f", 95) == "m.f"

    def test_bar_preserved(self):
        assert fixup.fixup_music_token("|m:r|", 95) == "|m:r|"

    def test_confusion_c_snaps_to_d(self):
        assert fixup.fixup_music_token("c:r:m", 95) == "d:r:m"

    def test_confusion_o_snaps_to_d(self):
        assert fixup.fixup_music_token("o", 95) == "d"

    def test_confusion_n_snaps_to_r(self):
        assert fixup.fixup_music_token("n", 95) == "r"

    def test_confusion_plus_snaps_to_t(self):
        assert fixup.fixup_music_token("+", 95) == "t"

    def test_confusion_5_snaps_to_s(self):
        assert fixup.fixup_music_token("5", 95) == "s"

    def test_confusion_zero_snaps_to_d(self):
        assert fixup.fixup_music_token("0", 95) == "d"

    def test_confusion_i_snaps_to_l(self):
        assert fixup.fixup_music_token("i", 95) == "l"

    def test_multiple_confusions_in_one_token(self):
        assert fixup.fixup_music_token("c:n:5:0", 95) == "d:r:s:d"

    def test_unsnappable_low_conf_wrapped_in_brackets(self):
        out = fixup.fixup_music_token(";xyz;", 30)
        assert "[?xyz]" in out

    def test_unsnappable_high_conf_passes_through(self):
        out = fixup.fixup_music_token(";xyz;", 95)
        assert "[?" not in out
        assert "xyz" in out

    def test_empty_string(self):
        assert fixup.fixup_music_token("", 95) == ""


# ---------------------------------------------------------------------------
# fixup_lyric_token
# ---------------------------------------------------------------------------

class TestFixupLyricToken:
    def test_clean_token_passes_through(self):
        assert fixup.fixup_lyric_token("Joyful") == "Joyful"

    def test_unicode_dash_normalized(self):
        assert fixup.fixup_lyric_token("Joy-ful") == "Joy-ful"

    def test_en_dash_normalized(self):
        assert fixup.fixup_lyric_token("Joy–ful") == "Joy-ful"

    def test_smart_quote_normalized(self):
        assert fixup.fixup_lyric_token("don’t") == "don't"

    def test_no_solfa_snapping_on_lyrics(self):
        # Words must not be mangled by the music confusion table.
        assert fixup.fixup_lyric_token("come") == "come"
        assert fixup.fixup_lyric_token("Lord") == "Lord"


# ---------------------------------------------------------------------------
# apply_fixup
# ---------------------------------------------------------------------------

class TestApplyFixup:
    def test_routes_by_line_kind(self):
        pages = [{
            "size": (2000, 3000),
            "lines": [
                {"kind": "music", "y": 100,
                 "tokens": [_tok("c:r:m"), _tok("-")]},
                {"kind": "lyric", "y": 200,
                 "tokens": [_tok("Joy-ful")]},
            ],
        }]
        fixup.apply_fixup(pages)
        # Music line: confusion fixed, dash normalized
        assert pages[0]["lines"][0]["tokens"][0]["text"] == "d:r:m"
        assert pages[0]["lines"][0]["tokens"][1]["text"] == "-"
        # Lyric line: dash normalized but words not snapped
        assert pages[0]["lines"][1]["tokens"][0]["text"] == "Joy-ful"

    def test_mutates_in_place_and_returns_same_object(self):
        pages = [{"lines": [{"kind": "music", "tokens": [_tok("c")]}]}]
        result = fixup.apply_fixup(pages)
        assert result is pages
        assert pages[0]["lines"][0]["tokens"][0]["text"] == "d"

    def test_missing_kind_defaults_to_lyric(self):
        # No 'kind' key: should not crash and should not snap as music
        pages = [{"lines": [{"tokens": [_tok("come")]}]}]
        fixup.apply_fixup(pages)
        assert pages[0]["lines"][0]["tokens"][0]["text"] == "come"

    def test_empty_pages(self):
        assert fixup.apply_fixup([]) == []

    def test_low_conf_unsnappable_brackets_on_music(self):
        pages = [{"lines": [
            {"kind": "music", "tokens": [_tok("zzz", conf=20)]},
        ]}]
        fixup.apply_fixup(pages)
        assert "[?zzz]" == pages[0]["lines"][0]["tokens"][0]["text"]


# ---------------------------------------------------------------------------
# extract_headers
# ---------------------------------------------------------------------------

def _page(lines, size=(2480, 3300)):
    return {"size": size, "lines": lines}


def _lyric_line(text, y):
    return {"kind": "lyric", "y": y, "tokens": [_tok(text, top=y)]}


def _music_line(text, y):
    return {"kind": "music", "y": y, "tokens": [_tok(text, top=y)]}


class TestExtractHeaders:
    def test_returns_empty_for_empty_pages(self):
        assert fixup.extract_headers([]) == {}

    def test_returns_empty_when_no_lines(self):
        assert fixup.extract_headers([_page([])]) == {}

    def test_detects_title(self):
        pages = [_page([_lyric_line("Joyful, joyful, we adore Thee", 200)])]
        assert fixup.extract_headers(pages).get("title") == "Joyful, joyful, we adore Thee"

    def test_detects_composer_from_by(self):
        pages = [_page([_lyric_line("by Henry Van Dyke", 200)])]
        result = fixup.extract_headers(pages)
        assert result.get("composer") == "Henry Van Dyke"

    def test_detects_composer_from_composed_by(self):
        pages = [_page([_lyric_line("composed by Beethoven", 200)])]
        result = fixup.extract_headers(pages)
        assert result.get("composer") == "Beethoven"

    def test_detects_key_with_colon(self):
        pages = [_page([_lyric_line("Key: G", 200)])]
        assert fixup.extract_headers(pages).get("key") == "G"

    def test_detects_key_with_of(self):
        pages = [_page([_lyric_line("Key of D", 200)])]
        assert fixup.extract_headers(pages).get("key") == "D"

    def test_detects_key_with_sharp(self):
        pages = [_page([_lyric_line("Key: F#", 200)])]
        assert fixup.extract_headers(pages).get("key") == "F#"

    def test_invalid_key_ignored(self):
        pages = [_page([_lyric_line("Key: X", 200)])]
        assert "key" not in fixup.extract_headers(pages)

    def test_detects_timesig_simple(self):
        pages = [_page([_lyric_line("4/4 time", 200)])]
        assert fixup.extract_headers(pages).get("timesig") == "4/4"

    def test_detects_timesig_compound(self):
        pages = [_page([_lyric_line("written in 6/8", 200)])]
        assert fixup.extract_headers(pages).get("timesig") == "6/8"

    def test_invalid_timesig_denominator_ignored(self):
        pages = [_page([_lyric_line("size 4/3 here", 200)])]
        assert "timesig" not in fixup.extract_headers(pages)

    def test_skips_music_lines(self):
        pages = [_page([_music_line("| m : m : f : s |", 200)])]
        assert fixup.extract_headers(pages) == {}

    def test_skips_lines_below_top_cut(self):
        # Page height 3300 → top_cut = 825. Line at y=2000 should be ignored.
        pages = [_page([_lyric_line("Joyful, joyful", 2000)])]
        assert "title" not in fixup.extract_headers(pages)

    def test_uses_page_size_when_present(self):
        # Tall page → bigger top_cut → header at y=600 still inside.
        pages = [_page([_lyric_line("My Title", 600)], size=(2480, 3300))]
        assert fixup.extract_headers(pages).get("title") == "My Title"

    def test_title_skips_lines_that_match_other_patterns(self):
        pages = [_page([
            _lyric_line("Key: G", 200),
            _lyric_line("My Actual Title", 250),
        ])]
        result = fixup.extract_headers(pages)
        assert result.get("title") == "My Actual Title"
        assert result.get("key") == "G"

    def test_title_skips_too_short_lines(self):
        pages = [_page([
            _lyric_line("II", 200),
            _lyric_line("Real Title Here", 250),
        ])]
        assert fixup.extract_headers(pages).get("title") == "Real Title Here"

    def test_full_header_block(self):
        pages = [_page([
            _lyric_line("Joyful, joyful, we adore Thee", 200),
            _lyric_line("by Henry Van Dyke", 300),
            _lyric_line("Key: G   4/4", 400),
            _music_line("| m : m |", 1000),
        ])]
        result = fixup.extract_headers(pages)
        assert result == {
            "title": "Joyful, joyful, we adore Thee",
            "composer": "Henry Van Dyke",
            "key": "G",
            "timesig": "4/4",
        }

    def test_only_first_page_consulted(self):
        # Title only on page 2 should not be picked up.
        pages = [
            _page([]),
            _page([_lyric_line("Second Page Title", 200)]),
        ]
        assert "title" not in fixup.extract_headers(pages)
