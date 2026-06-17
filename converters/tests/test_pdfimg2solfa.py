"""Unit tests for converters.pdfimg2solfa.converter."""

import pytest
from unittest.mock import patch, MagicMock

import converters.pdfimg2solfa.converter as mod
from converters.shared import spec


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
# _build_headers
# ---------------------------------------------------------------------------

class TestBuildHeaders:
    def test_returns_string_ending_with_newline(self):
        result = mod._build_headers()
        assert isinstance(result, str)
        assert result.endswith("\n")

    def test_contains_all_default_keys(self):
        result = mod._build_headers()
        for key in spec["defaults"]:
            assert f":{key}:" in result

    def test_uses_prop_prefix(self):
        prefix = spec["header"]["prop_prefix"]
        assert prefix in mod._build_headers()

    def test_none_defaults_render_blank(self):
        result = mod._build_headers()
        # `:tempo:` default is None - should render as `:tempo: ` (no value)
        assert ":tempo: \n" in result or result.endswith(":tempo: \n")

    def test_overrides_replace_defaults(self):
        result = mod._build_headers({"title": "My Song", "key": "G"})
        assert ":title: My Song" in result
        assert ":key: G" in result
        assert ":title: Untitled" not in result

    def test_overrides_ignored_when_key_unknown(self):
        # Unknown keys silently ignored - defaults still emitted unchanged.
        result = mod._build_headers({"bogus_key": "whatever"})
        assert "bogus_key" not in result
        assert ":title: Untitled" in result


# ---------------------------------------------------------------------------
# _classify_line
# ---------------------------------------------------------------------------

class TestClassifyLine:
    def test_empty_tokens_are_lyric(self):
        assert mod._classify_line([]) == "lyric"

    def test_satb_measure_is_music(self):
        toks = [_tok(t) for t in ["|", "m", ":", "m", ":", "f", ":", "s", "|"]]
        assert mod._classify_line(toks) == "music"

    def test_lyric_hyphenated_is_lyric(self):
        toks = [_tok(t) for t in ["Joy-ful,", "joy-ful,", "we", "a-do-re", "You,"]]
        assert mod._classify_line(toks) == "lyric"

    def test_plain_title_words_are_lyric(self):
        toks = [_tok(t) for t in ["Joyful,", "joyful,", "we", "adore", "Thee"]]
        assert mod._classify_line(toks) == "lyric"

    def test_bar_lowers_threshold(self):
        # Mixed line with `|` should still classify as music when ratio >= 0.4
        toks = [_tok("|"), _tok("m"), _tok(":"), _tok("m"), _tok("garbage")]
        assert mod._classify_line(toks) == "music"

    def test_low_solfa_ratio_without_bar_is_lyric(self):
        toks = [_tok("Hello"), _tok("world"), _tok("m")]
        assert mod._classify_line(toks) == "lyric"

    def test_octave_markers_count_as_music(self):
        toks = [_tok("s,"), _tok(":"), _tok("l,"), _tok(":"), _tok("d'")]
        assert mod._classify_line(toks) == "music"


# ---------------------------------------------------------------------------
# _line_bbox
# ---------------------------------------------------------------------------

class TestLineBbox:
    def test_includes_padding(self):
        toks = [_tok("x", left=100, top=50, width=20, height=12)]
        l, t, r, b = mod._line_bbox(toks, image_size=(1000, 1000), padding=8)
        assert l == 92 and t == 42
        assert r == 128 and b == 70

    def test_clamps_to_image_bounds(self):
        toks = [_tok("x", left=0, top=0, width=10, height=10)]
        l, t, r, b = mod._line_bbox(toks, image_size=(20, 20), padding=50)
        assert l == 0 and t == 0
        assert r == 20 and b == 20

    def test_spans_multiple_tokens(self):
        toks = [
            _tok("a", left=10, top=10, width=20, height=10),
            _tok("b", left=100, top=15, width=20, height=10),
        ]
        l, t, r, b = mod._line_bbox(toks, image_size=(500, 500), padding=0)
        assert (l, t, r, b) == (10, 10, 120, 25)


# ---------------------------------------------------------------------------
# _count_kinds / _mean_conf
# ---------------------------------------------------------------------------

class TestCountKinds:
    def test_counts_each_kind(self):
        lines = [
            {"kind": "music", "tokens": []},
            {"kind": "music", "tokens": []},
            {"kind": "lyric", "tokens": []},
        ]
        assert mod._count_kinds(lines) == (2, 1)

    def test_handles_missing_kind(self):
        lines = [{"tokens": []}, {"kind": "music", "tokens": []}]
        assert mod._count_kinds(lines) == (1, 0)


class TestMeanConf:
    def test_returns_zero_for_empty(self):
        assert mod._mean_conf([]) == 0.0

    def test_averages_token_confidences(self):
        lines = [
            {"tokens": [_tok("a", conf=80), _tok("b", conf=100)]},
            {"tokens": [_tok("c", conf=60)]},
        ]
        assert mod._mean_conf(lines) == pytest.approx(80.0)


# ---------------------------------------------------------------------------
# _render_text
# ---------------------------------------------------------------------------

class TestRenderText:
    def test_joins_tokens_with_spaces(self):
        pages = [{"lines": [
            {"block": 1, "y": 0, "tokens": [_tok("d"), _tok(":"), _tok("r")]},
        ]}]
        out = mod._render_text(pages)
        assert "d : r" in out

    def test_inserts_blank_line_between_blocks(self):
        pages = [{"lines": [
            {"block": 1, "y": 0, "tokens": [_tok("foo")]},
            {"block": 2, "y": 10, "tokens": [_tok("bar")]},
        ]}]
        out = mod._render_text(pages)
        lines = out.split("\n")
        assert "foo" in lines
        assert "bar" in lines
        assert lines.index("") < lines.index("bar")
        assert lines.index("foo") < lines.index("")

    def test_empty_pages_yields_empty_output(self):
        assert mod._render_text([]) == ""

    def test_multiple_pages_preserved(self):
        pages = [
            {"lines": [{"block": 1, "y": 0, "tokens": [_tok("page1")]}]},
            {"lines": [{"block": 1, "y": 0, "tokens": [_tok("page2")]}]},
        ]
        out = mod._render_text(pages)
        assert "page1" in out and "page2" in out


# ---------------------------------------------------------------------------
# convert() - orchestration (preprocess/OCR/refine all mocked)
# ---------------------------------------------------------------------------

@pytest.fixture
def fake_lines():
    return [
        {"block": 1, "y": 200, "kind": "lyric",
         "tokens": [_tok("Joyful,"), _tok("joyful,"), _tok("we"), _tok("adore"), _tok("Thee")]},
        {"block": 2, "y": 800, "kind": "music",
         "tokens": [_tok("|"), _tok("m"), _tok(":"), _tok("m"), _tok("|")]},
    ]


def _patch_convert_pipeline(fake_lines, page_size=(2480, 3300)):
    """Patch the heavy stages so convert() runs without OCR/cv2 deps."""
    fake_image = MagicMock()
    fake_image.size = page_size
    return patch.multiple(
        mod,
        OCR_DEPS_AVAILABLE=True,
        _preprocess=MagicMock(return_value=fake_image),
        _ocr_page=MagicMock(return_value=fake_lines),
        _refine_lines=MagicMock(return_value=fake_lines),
    )


class TestConvertOrchestration:
    def test_unsupported_extension_exits(self, tmp_path):
        bad = tmp_path / "score.xyz"
        bad.write_text("dummy")
        with patch.object(mod, "OCR_DEPS_AVAILABLE", True):
            with pytest.raises(SystemExit):
                mod.convert(str(bad))

    def test_exits_when_deps_unavailable(self, tmp_path):
        fake_pdf = tmp_path / "score.pdf"
        fake_pdf.write_bytes(b"%PDF-1.4")
        with patch.object(mod, "OCR_DEPS_AVAILABLE", False):
            with pytest.raises(SystemExit):
                mod.convert(str(fake_pdf))

    def test_pdf_writes_output(self, tmp_path, fake_lines):
        fake_pdf = tmp_path / "score.pdf"
        fake_pdf.write_bytes(b"%PDF-1.4")
        out = tmp_path / "score.txt"

        with _patch_convert_pipeline(fake_lines), \
             patch("converters.pdfimg2solfa.converter.pdf2image", create=True) as mock_pdf:
            mock_pdf.convert_from_path.return_value = [MagicMock()]
            result = mod.convert(str(fake_pdf), str(out))

        assert out.exists()
        assert result == str(out)

    def test_pdf_default_output_path(self, tmp_path, fake_lines):
        fake_pdf = tmp_path / "score.pdf"
        fake_pdf.write_bytes(b"%PDF-1.4")

        with _patch_convert_pipeline(fake_lines), \
             patch("converters.pdfimg2solfa.converter.pdf2image", create=True) as mock_pdf:
            mock_pdf.convert_from_path.return_value = [MagicMock()]
            result = mod.convert(str(fake_pdf))

        assert result == str(tmp_path / "score.txt")
        assert (tmp_path / "score.txt").exists()

    def test_output_contains_headers_block(self, tmp_path, fake_lines):
        fake_pdf = tmp_path / "score.pdf"
        fake_pdf.write_bytes(b"%PDF-1.4")
        out = tmp_path / "score.txt"

        with _patch_convert_pipeline(fake_lines), \
             patch("converters.pdfimg2solfa.converter.pdf2image", create=True) as mock_pdf:
            mock_pdf.convert_from_path.return_value = [MagicMock()]
            mod.convert(str(fake_pdf), str(out))

        content = out.read_text(encoding="utf-8")
        assert ":title:" in content
        assert ":key:" in content
        assert ":timesig:" in content

    def test_output_contains_ocr_text(self, tmp_path, fake_lines):
        fake_pdf = tmp_path / "score.pdf"
        fake_pdf.write_bytes(b"%PDF-1.4")
        out = tmp_path / "score.txt"

        with _patch_convert_pipeline(fake_lines), \
             patch("converters.pdfimg2solfa.converter.pdf2image", create=True) as mock_pdf:
            mock_pdf.convert_from_path.return_value = [MagicMock()]
            mod.convert(str(fake_pdf), str(out))

        content = out.read_text(encoding="utf-8")
        assert "Joyful," in content
        assert "m" in content

    def test_image_path_uses_pil_open(self, tmp_path, fake_lines):
        fake_png = tmp_path / "score.png"
        fake_png.write_bytes(b"\x89PNG\r\n\x1a\n")
        out = tmp_path / "score.txt"

        with _patch_convert_pipeline(fake_lines), \
             patch("converters.pdfimg2solfa.converter.Image", create=True) as mock_pil:
            mock_pil.open.return_value = MagicMock()
            result = mod.convert(str(fake_png), str(out))

        assert result == str(out)
        mock_pil.open.assert_called_once()

    def test_jpg_extension_accepted(self, tmp_path, fake_lines):
        fake_jpg = tmp_path / "score.jpg"
        fake_jpg.write_bytes(b"\xff\xd8\xff")
        out = tmp_path / "score.txt"

        with _patch_convert_pipeline(fake_lines), \
             patch("converters.pdfimg2solfa.converter.Image", create=True) as mock_pil:
            mock_pil.open.return_value = MagicMock()
            result = mod.convert(str(fake_jpg), str(out))

        assert result == str(out)

    def test_multipage_pdf_processes_all_pages(self, tmp_path, fake_lines):
        fake_pdf = tmp_path / "score.pdf"
        fake_pdf.write_bytes(b"%PDF-1.4")
        out = tmp_path / "score.txt"

        mock_preprocess = MagicMock(return_value=MagicMock(size=(2480, 3300)))
        mock_ocr = MagicMock(return_value=fake_lines)
        mock_refine = MagicMock(return_value=fake_lines)

        with patch.object(mod, "OCR_DEPS_AVAILABLE", True), \
             patch.object(mod, "_preprocess", mock_preprocess), \
             patch.object(mod, "_ocr_page", mock_ocr), \
             patch.object(mod, "_refine_lines", mock_refine), \
             patch("converters.pdfimg2solfa.converter.pdf2image", create=True) as mock_pdf:
            mock_pdf.convert_from_path.return_value = [MagicMock(), MagicMock(), MagicMock()]
            mod.convert(str(fake_pdf), str(out))

        assert mock_preprocess.call_count == 3
        assert mock_ocr.call_count == 3
        assert mock_refine.call_count == 3
