from reportlab.lib.pagesizes import A4, letter
from reportlab.lib.units import mm, cm
from reportlab.lib import colors
from reportlab.pdfgen import canvas
from ..shared import spec
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

def _resolve_music_font() -> str:
    import os
    from pathlib import Path
    pref = spec["export"]["music_symbol_font_preference"]
    fallback = spec["export"]["music_symbol_font_fallback"]
    search_paths = [
        # Bundled font (always tried first)
        Path(__file__).parent / "fonts" / f"{pref}.ttf",
        # macOS system and Homebrew (cask)
        f"/Library/Fonts/{pref}.ttf",
        os.path.expanduser(f"~/Library/Fonts/{pref}.ttf"),
        f"/System/Library/Fonts/Supplemental/{pref}.ttf",
        # Debian/Ubuntu
        f"/usr/share/fonts/truetype/freefont/{pref}.ttf",
        # Fedora/RHEL
        f"/usr/share/fonts/gnu-free/{pref}.ttf",
        # Arch
        f"/usr/share/fonts/gnu-free-fonts/{pref}.ttf",
    ]
    for path in search_paths:
        try:
            pdfmetrics.registerFont(TTFont(pref, str(path)))
            return pref
        except Exception:
            continue
    return fallback

MUSIC_SYMBOL_FONT = _resolve_music_font()
from .data_structures import (Song)
from datetime import datetime
from typing import List, Dict, Tuple
from .data_structures import (NoteType, Measure, Beat, Note)

class TonicSolfaPDFRenderer:
    """Renders a parsed Song to PDF in traditional hymnal style"""

    def __init__(self, song: Song, output_path: str):
        self.c = None
        self.song = song
        self.output_path = output_path

        # Page settings
        self.page_size = A4
        self.page_width, self.page_height = self.page_size
        self.margin_left = 15 * mm
        self.margin_right = 15 * mm
        self.margin_top = 20 * mm
        self.margin_bottom = 20 * mm

        # Content area
        self.content_width = self.page_width - self.margin_left - self.margin_right
        self.content_height = self.page_height - self.margin_top - self.margin_bottom

        # Font settings
        self.notation_font = spec["export"]["notation_font"]
        self.title_font_size = 14
        self.subtitle_font_size = 10
        self.header_font_size = 9
        self.note_font_size = 9
        self.lyric_font_size = 9
        self.small_font_size = 7

        # Layout settings
        self.voice_row_height = 12  # Height per voice row
        self.lyric_row_height = 9  # Height per lyric row
        self.block_spacing = 12  # Space between blocks
        self.lyric_top_margin = 6  # Space above lyrics
        self.lyric_bottom_margin = 2  # Space below lyrics
        self.measure_padding = 2  # Padding inside measure cells

        # Calculate measures per line based on time signature
        beats_per_measure = song.time_sig[0]
        if beats_per_measure <= 3:
            self.measures_per_line = 6
        elif beats_per_measure <= 4:
            self.measures_per_line = 5
        else:
            self.measures_per_line = 4

        # Track state
        self.current_page = 1
        self.y_position = self.page_height - self.margin_top

    def render(self):
        """Render the complete PDF"""
        self.c = canvas.Canvas(self.output_path, pagesize=self.page_size)

        # Draw first page header
        self._draw_page_header()

        # Draw song header (title, composer, etc.)
        self._draw_song_header()

        # Draw all blocks
        self._draw_all_blocks()

        # Draw notes section if present
        if self.song.notes:
            self._draw_notes_section()

        # Draw footer on last page
        self._draw_page_footer()

        self.c.save()

    def _draw_notes_section(self):
        """Render the plain-text notes section at the end of the PDF."""
        # Render each line of the notes content with word wrapping
        self.c.setFont(self.notation_font, self.note_font_size)
        line_height = self.note_font_size + 3
        notes_x = getattr(self, '_block_start_x', self.margin_left)
        max_width = self.page_width - self.margin_right - notes_x

        for paragraph in self.song.notes.split("\n"):
            # Blank line = paragraph break
            if not paragraph.strip():
                self.y_position -= line_height // 2
                self._check_page_space(line_height)
                continue

            # Word-wrap the paragraph
            words = paragraph.split()
            current_line = ""
            for word in words:
                test_line = (current_line + " " + word).strip()
                if self.c.stringWidth(test_line, self.notation_font, self.note_font_size) <= max_width:
                    current_line = test_line
                else:
                    if current_line:
                        self._check_page_space(line_height)
                        self.c.drawString(notes_x, self.y_position, current_line)
                        self.y_position -= line_height
                    current_line = word

            if current_line:
                self._check_page_space(line_height)
                self.c.drawString(notes_x, self.y_position, current_line)
                self.y_position -= line_height

    def _draw_page_header(self):
        """Draw page header with measure numbers indicator"""
        pass  # Header info is in song header for first page

    def _draw_page_footer(self):
        """Draw page footer with page number, copyright, and generation date"""
        footer_y = self.margin_bottom - 8 * mm
        copyright_font_size = self.small_font_size - 1

        # Page number
        self.c.setFont("Helvetica", self.small_font_size)
        self.c.drawCentredString(self.page_width / 2, footer_y, f"-{self.current_page}-")

        # First page only: date (left), transcription (right), copyright (centered below page number)
        if self.current_page == 1:
            self.c.setFont("Helvetica", copyright_font_size)
            if self.song.date:
                self.c.drawString(self.margin_left, footer_y, self.song.date)
            if self.song.transcription:
                self.c.drawRightString(self.page_width - self.margin_right, footer_y, self.song.transcription)
            if self.song.copyright:
                self.c.drawCentredString(self.page_width / 2, footer_y - copyright_font_size - 1, self.song.copyright)

        # Generation date (first page only, only if :gendate: flag is set) - centered, below copyright
        if self.song.gendate and self.current_page == 1:
            self.c.setFont("Helvetica", copyright_font_size)
            date_text = f"Generated on {datetime.now().strftime('%Y-%m-%d')}"
            gen_y = footer_y - copyright_font_size - 1
            if self.song.copyright:
                gen_y -= copyright_font_size + 1
            self.c.drawCentredString(self.page_width / 2, gen_y, date_text)

    def _new_page(self):
        """Start a new page"""
        self._draw_page_footer()
        self.c.showPage()
        self.current_page += 1
        self.y_position = self.page_height - self.margin_top

        # Draw title reminder at top of subsequent pages - slightly larger, light grey
        if self.song.title:
            title_reminder_size = self.small_font_size + 2
            self.c.setFont("Helvetica", title_reminder_size)
            self.c.setFillColor(colors.Color(0.55, 0.55, 0.55))
            self.c.drawString(self.margin_left, self.y_position, self.song.title)
            self.c.setFillColor(colors.black)
            self.y_position -= title_reminder_size + 4

    def _check_page_space(self, needed_height: float) -> bool:
        """Check if there's enough space on current page, start new page if not"""
        if self.y_position - needed_height < self.margin_bottom + 12 * mm:
            self._new_page()
            return True
        return False

    def _draw_song_header(self):
        """Draw the song header (title, composer, key, etc.)"""
        # Title
        if self.song.title:
            self.c.setFont("Helvetica-Bold", self.title_font_size)
            self.c.drawCentredString(self.page_width / 2, self.y_position, self.song.title)
            self.y_position -= self.title_font_size + 3

        # Authors (left) and Composers (right), one per line
        self.c.setFont("Helvetica-Oblique", self.subtitle_font_size)
        for i in range(max(len(self.song.authors), len(self.song.composers))):
            if i < len(self.song.authors):
                self.c.drawString(self.margin_left, self.y_position, self.song.authors[i])
            if i < len(self.song.composers):
                self.c.drawRightString(self.page_width - self.margin_left, self.y_position, self.song.composers[i])
            self.y_position -= self.subtitle_font_size + 3

        # Comments (centered, under composer)
        if self.song.comment:
            self.c.setFont("Helvetica-Oblique", self.small_font_size)
            self.c.drawCentredString(self.page_width / 2, self.y_position, self.song.comment)
            self.y_position -= self.small_font_size + 3

        # Key, Time Signature line (bold)
        self.c.setFont("Helvetica-Bold", self.header_font_size)
        prefix_parts = [f"{self.song.keyheader} {self.song.key}", f"{self.song.time_sig[0]}/{self.song.time_sig[1]}"]
        prefix_text = "    ".join(prefix_parts) + "    "
        self.c.drawString(self.margin_left, self.y_position, prefix_text)
        x = self.margin_left + self.c.stringWidth(prefix_text, "Helvetica-Bold", self.header_font_size)

        # Tempo marking - split rendering so ♩ uses the music symbol font
        if self.song.tempomarking or self.song.tempo:
            if self.song.tempomarking:
                self.c.setFont("Helvetica-Bold", self.header_font_size)
                self.c.drawString(x, self.y_position, self.song.tempomarking + " ")
                x += self.c.stringWidth(self.song.tempomarking + " ", "Helvetica-Bold", self.header_font_size)
            if self.song.tempo:
                quarter = spec["navigation"]["quarter_note_symbol"]
                self.c.setFont(MUSIC_SYMBOL_FONT, self.header_font_size)
                self.c.drawString(x, self.y_position, quarter)
                x += self.c.stringWidth(quarter, MUSIC_SYMBOL_FONT, self.header_font_size)
                self.c.setFont("Helvetica-Bold", self.header_font_size)
                bpm_text = f" = {self.song.tempo}"
                self.c.drawString(x, self.y_position, bpm_text)
                x += self.c.stringWidth(bpm_text, "Helvetica-Bold", self.header_font_size)

        if self.song.meter:
            self.c.setFont("Helvetica-Bold", self.header_font_size)
            self.c.drawString(x, self.y_position, f"    {self.song.meter}")

        self.y_position -= self.header_font_size + 8

    def _draw_all_blocks(self):
        """Draw all blocks of the song, each block rendered with its own voice set."""
        if not self.song.blocks:
            return

        # Determine global label width: if any block is non-standard SATB, reserve label space
        # so that measure widths are consistent across all blocks.
        def _block_voice_order(block):
            labels = {vl.voice_label for vl in block.voice_lines}
            order = [v for v in spec["voices"]["default_order"] if v in labels]
            order += [v for v in labels if v not in order]
            return order

        has_any_non_satb = any(
            not (set(_block_voice_order(b)) == set(spec["voices"]["default_order"]) and len(b.voice_lines) == 4)
            for b in self.song.blocks if b.voice_lines
        )
        self._voice_label_width = 8 * mm if has_any_non_satb else 0
        available_width = self.content_width - self._voice_label_width
        self._measure_width = available_width / self.measures_per_line

        # Find the widest line across the entire song, center it, and use that
        # start_x for every line and the notes section — so all lines are left-aligned
        # relative to each other, with the widest one centered on the page.
        # Widths are summed from actual per-measure widths so lines with narrow
        # partial (pickup) measures are accounted for correctly.
        max_line_width = 0.0
        for block in self.song.blocks:
            if not block.voice_lines:
                continue
            ref_measures = block.voice_lines[0].measures
            n = len(ref_measures)
            idx = 0
            while idx < n:
                end = min(idx + self.measures_per_line, n)
                line_width = sum(self._measure_width_for(ref_measures[m]) for m in range(idx, end))
                max_line_width = max(max_line_width, line_width)
                idx = end
        if max_line_width == 0:
            max_line_width = self.measures_per_line * self._measure_width
        widest_content = self._voice_label_width + max_line_width
        self._block_start_x = self.margin_left + (self.content_width - widest_content) / 2

        # Render each block independently
        for block in self.song.blocks:
            if not block.voice_lines:
                continue

            voice_order = _block_voice_order(block)
            block_voice_data = {vl.voice_label: vl.measures for vl in block.voice_lines}
            num_measures = len(block.voice_lines[0].measures)

            block_lyrics = [{'start': 0, 'end': num_measures, 'lyrics': block.lyric_lines}]

            measure_idx = 0
            while measure_idx < num_measures:
                end_idx = min(measure_idx + self.measures_per_line, num_measures)

                # Skip trailing all-empty lines
                all_empty = all(
                    block_voice_data.get(v, [])[m].is_empty
                    for v in voice_order
                    for m in range(measure_idx, min(end_idx, len(block_voice_data.get(v, []))))
                )
                has_lyrics = bool(block.lyric_lines)
                if all_empty and not has_lyrics and measure_idx > 0:
                    measure_idx = end_idx
                    continue

                lyrics_by_voice = self._organize_lyrics_by_target_voice(
                    block_lyrics, measure_idx, end_idx, voice_order)
                num_lyric_rows = sum(len(lyrics_by_voice.get(v, [])) for v in voice_order)
                line_height = (len(voice_order) * self.voice_row_height +
                               max(num_lyric_rows, 1) * (self.lyric_row_height + self.lyric_bottom_margin) +
                               self.block_spacing + 9)

                self._check_page_space(line_height)
                self._draw_measure_group(block_voice_data, voice_order,
                                         measure_idx, end_idx, block_lyrics)
                measure_idx = end_idx

    # ─────────────────────────────────────────────────────────────────
    # Note center X computation (shared by fermatas, key changes, lyrics)
    # ─────────────────────────────────────────────────────────────────

    def _compute_note_center_x_full(self, measure_offset: float,
                                    beat_idx: int, note_idx: int, note: Note,
                                    beat: Beat, num_beats: int,
                                    start_x: float, label_width: float,
                                    measure_width: float) -> float:
        """Compute the center X for a specific note in a measure.
        Uses the same centering logic as lyric syllable placement so that
        fermatas, key changes, etc. are centered exactly over their note.
        ``measure_offset`` is the measure's x-offset within the line (relative
        to the start of the content area), which varies with partial measures."""
        beat_width = measure_width / num_beats if num_beats > 0 else measure_width

        if beat.is_subdivided:
            half_width = beat_width / 2
            if note in beat.first_half:
                idx_in_half = beat.first_half.index(note)
                num_in_half = len(beat.first_half)
                note_width = half_width / num_in_half if num_in_half > 0 else half_width
                center_x = (start_x + label_width +
                            measure_offset +
                            beat_idx * beat_width +
                            idx_in_half * note_width +
                            note_width / 2)
            elif note in beat.second_half:
                idx_in_half = beat.second_half.index(note)
                num_in_half = len(beat.second_half)
                note_width = half_width / num_in_half if num_in_half > 0 else half_width
                center_x = (start_x + label_width +
                            measure_offset +
                            beat_idx * beat_width +
                            half_width +
                            idx_in_half * note_width +
                            note_width / 2)
            else:
                # Fallback: center of beat
                center_x = (start_x + label_width +
                            measure_offset +
                            beat_idx * beat_width +
                            beat_width / 2)
        else:
            all_notes = beat.all_notes()
            num_notes = len(all_notes)
            note_width = beat_width / num_notes if num_notes > 0 else beat_width
            center_x = (start_x + label_width +
                        measure_offset +
                        beat_idx * beat_width +
                        note_idx * note_width +
                        note_width / 2)

        return center_x

    # ─────────────────────────────────────────────────────────────────
    # Draw a group of measures (one line of the score)
    # ─────────────────────────────────────────────────────────────────

    def _measure_width_for(self, measure: Measure) -> float:
        """Width of a single measure. A partial (pickup) measure is narrowed so
        each of its beats matches a full-measure beat; full measures keep the
        standard column width."""
        full_w = self._measure_width
        num = self.song.time_sig[0] if self.song.time_sig else 4
        if measure is not None and measure.is_partial and num > 0:
            return max(1, len(measure.beats)) * full_w / num
        return full_w

    def _line_measure_geometry(self, all_voice_data: Dict, voice_order: List[str],
                               start_idx: int, end_idx: int) -> Dict[int, Tuple[float, float]]:
        """Return {m_idx: (offset, width)} for measures in [start_idx, end_idx).

        Widths use the reference (first) voice so all voices, barlines, measure
        numbers, and lyrics share one horizontal grid. Offsets are relative to
        the start of the measure-content area (i.e. after the label width)."""
        ref_voice = voice_order[0] if voice_order else None
        ref_measures = all_voice_data.get(ref_voice, []) if ref_voice else []
        geo: Dict[int, Tuple[float, float]] = {}
        offset = 0.0
        for m_idx in range(start_idx, end_idx):
            measure = ref_measures[m_idx] if m_idx < len(ref_measures) else None
            width = self._measure_width_for(measure)
            geo[m_idx] = (offset, width)
            offset += width
        return geo

    def _draw_measure_group(self, all_voice_data: Dict, voice_order: List[str],
                            start_idx: int, end_idx: int, block_lyrics: List[Dict]):
        """Draw a group of measures (one line of the score) with lyrics under target voices"""
        num_measures = end_idx - start_idx

        # Show labels unless this block is exactly standard 4-voice SATB
        show_voice_labels = not (set(voice_order) == set(spec["voices"]["default_order"]) and len(voice_order) == 4)

        # Use globally-consistent widths (computed once in _draw_all_blocks)
        voice_label_width = self._voice_label_width

        # Per-measure geometry (partial pickup measures render narrower)
        geo = self._line_measure_geometry(all_voice_data, voice_order, start_idx, end_idx)

        # All lines in a block share the same start_x (set per-block in _draw_all_blocks)
        start_x = self._block_start_x
        start_y = self.y_position

        # ── Collect ALL above-staff markers into a unified list ──
        above_staff_items = self._collect_all_above_staff_items(
            all_voice_data, voice_order, start_idx, end_idx,
            start_x, voice_label_width, geo
        )

        # Draw all above-staff markers on the SAME line if any exist
        if above_staff_items:
            self._draw_above_staff_line(above_staff_items, start_y)
            start_y -= 9  # Single vertical offset for the combined row

        # Draw measure numbers above first voice
        self.c.setFont("Helvetica", self.small_font_size)
        self.c.setFillColor(colors.Color(0.4, 0.4, 0.4))
        x = start_x + voice_label_width
        ref_voice = voice_order[0] if voice_order else None
        ref_measures = all_voice_data.get(ref_voice, []) if ref_voice else []
        for m_idx in range(start_idx, end_idx):
            ref_m = ref_measures[m_idx] if m_idx < len(ref_measures) else None
            # A continuation (the leading half of a split measure) shares the
            # number of the trailing half already shown on the previous system,
            # so don't print it again.
            if ref_m is None or not ref_m.is_continuation:
                measure_num = ref_m.number if (ref_m is not None and ref_m.number) else m_idx + 1
                self.c.drawString(x + 1, start_y + 1, str(measure_num))
            x += geo[m_idx][1]
        self.c.setFillColor(colors.black)
        start_y -= 2

        # Organize lyrics by their target voice
        lyrics_by_target_voice = self._organize_lyrics_by_target_voice(block_lyrics, start_idx, end_idx, voice_order)

        # Pre-compute total barline height: from top of first voice to bottom of last voice's note row
        # (including lyrics rows between voices, but NOT the last voice's lyrics)
        total_barline_height = 0
        for voice_idx, voice_label in enumerate(voice_order):
            total_barline_height += self.voice_row_height
            # Add lyrics height for all voices except the last one
            if voice_idx < len(voice_order) - 1 and voice_label in lyrics_by_target_voice:
                num_lyric_lines = len(lyrics_by_target_voice[voice_label])
                total_barline_height += num_lyric_lines * (self.lyric_row_height + self.lyric_bottom_margin)

        # Draw barlines first (full height from first voice to bottom of last voice's notes)
        barline_top_y = start_y
        barline_bottom_y = start_y - total_barline_height
        self.c.setStrokeColor(colors.black)

        x = start_x + voice_label_width
        # Left (opening) barline - omitted when the line begins with a leading
        # partial/pickup measure, since its boundary '|' was intentionally left
        # out of the notation.
        first_is_leading_partial = (
            start_idx == 0
            and start_idx < len(ref_measures)
            and ref_measures[start_idx].is_partial
        )
        if not first_is_leading_partial:
            self.c.setLineWidth(0.5)
            self.c.line(x, barline_top_y, x, barline_bottom_y)

        # Barlines after each measure
        bx = x
        total_voice_measures = max(len(all_voice_data.get(v, [])) for v in voice_order) if voice_order else 0
        for m_idx in range(start_idx, end_idx):
            bx += geo[m_idx][1]
            is_last_measure = (m_idx == total_voice_measures - 1)

            # A trailing partial has no closing barline: either its measure
            # continues on the next system (split measure) or it is a genuinely
            # incomplete final bar. Mirror of the opening-barline skip above.
            ref_m = ref_measures[m_idx] if m_idx < len(ref_measures) else None
            if ref_m is not None and ref_m.is_partial and ref_m.partial_side == "trailing":
                continue

            if is_last_measure:
                # Double barline at end
                self.c.setLineWidth(0.5)
                self.c.line(bx - 2, barline_top_y, bx - 2, barline_bottom_y)
                self.c.setLineWidth(1.5)
                self.c.line(bx, barline_top_y, bx, barline_bottom_y)
                self.c.setLineWidth(0.5)
            else:
                self.c.setLineWidth(0.5)
                self.c.line(bx, barline_top_y, bx, barline_bottom_y)

        # Draw each voice with its lyrics underneath
        y = start_y
        for voice_idx, voice_label in enumerate(voice_order):
            measures = all_voice_data.get(voice_label, [])

            # Draw voice label only if not standard SATB
            if show_voice_labels:
                self.c.setFont("Helvetica-Bold", self.note_font_size)
                self.c.drawString(start_x, y - self.voice_row_height + 3, voice_label)

            # Draw measures for this voice (content only, no barlines)
            x = start_x + voice_label_width
            for m_idx in range(start_idx, end_idx):
                if m_idx < len(measures):
                    measure = measures[m_idx]
                    self._draw_measure_content(measure, x, y, geo[m_idx][1], self.voice_row_height)
                x += geo[m_idx][1]

            y -= self.voice_row_height

            # Draw lyrics for this voice if any
            if voice_label in lyrics_by_target_voice:
                for lyric_info in lyrics_by_target_voice[voice_label]:
                    self._draw_single_lyric_line(start_x, y, voice_label_width, geo,
                                                 start_idx, end_idx, lyric_info, all_voice_data, voice_order)
                    y -= (self.lyric_row_height + self.lyric_bottom_margin)

        # Update y position with block spacing
        self.y_position = y - self.block_spacing

    # ─────────────────────────────────────────────────────────────────
    # Draw above-staff markers (nav + fermata + key changes on ONE line)
    # ─────────────────────────────────────────────────────────────────

    def _collect_all_above_staff_items(self, all_voice_data: Dict, voice_order: List[str],
                                       start_idx: int, end_idx: int,
                                       start_x: float, label_width: float,
                                       geo: Dict[int, Tuple[float, float]]) -> List[Dict]:
        """Collect ALL above-staff items (dynamics, hairpins, text expressions, fermatas,
        navigation markers, key changes) from the first voice, grouped by note position.
        Each item has 'center_x', 'order' (notation order), and 'texts' (list of display strings)."""
        if not voice_order:
            return []

        # Collect items with their center_x and a global ordering index
        items_by_position = {}  # key: (m_idx, beat_idx, note_idx) -> list of texts in order
        order_counter = [0]

        def add_item(key, center_x, text):
            if key not in items_by_position:
                items_by_position[key] = {'center_x': center_x, 'texts': [], 'order': order_counter[0]}
            items_by_position[key]['texts'].append(text)
            order_counter[0] += 1

        # Use first voice for center_x computation, but collect marks from ALL voices
        first_voice = voice_order[0]
        first_measures = all_voice_data.get(first_voice, [])
        seen_texts = set()  # (key, text) to avoid duplicates across voices

        for voice_label in voice_order:
            measures = all_voice_data.get(voice_label, [])

            for m_idx in range(start_idx, min(end_idx, len(measures))):
                measure = measures[m_idx]
                # Use first voice's beat structure for center_x
                ref_measure = first_measures[m_idx] if m_idx < len(first_measures) else measure
                num_beats = len(ref_measure.beats)

                for beat_idx, beat in enumerate(measure.beats):
                    all_notes = beat.all_notes()
                    ref_beat = ref_measure.beats[beat_idx] if beat_idx < len(ref_measure.beats) else beat

                    for note_idx, note in enumerate(all_notes):
                        # Compute center_x using first voice's beat for consistent alignment
                        ref_notes = ref_beat.all_notes()
                        ref_note = ref_notes[note_idx] if note_idx < len(ref_notes) else note
                        m_offset, m_width = geo.get(m_idx, (0.0, self._measure_width))
                        center_x = self._compute_note_center_x_full(
                            m_offset, beat_idx, note_idx, ref_note,
                            ref_beat, num_beats, start_x, label_width, m_width
                        )
                        key = (m_idx, beat_idx, note_idx)

                        for expr in note.expressions:
                            dedup = (key, expr.type, expr.value)
                            if dedup in seen_texts:
                                continue
                            seen_texts.add(dedup)

                            if expr.type == "dynamic":
                                add_item(key, center_x, expr.value)
                            elif expr.type == "hairpin":
                                add_item(key, center_x, expr.value)
                            elif expr.type == "text":
                                add_item(key, center_x, expr.value)
                            elif expr.type == "fermata":
                                add_item(key, center_x, spec["navigation"]["fermata_symbol"])
                            elif expr.type == "navigation":
                                add_item(key, center_x, expr.value)

                        if note.type == NoteType.MODULATION and note.key_change:
                            dedup = (key, "key_change", note.key_change)
                            if dedup not in seen_texts:
                                seen_texts.add(dedup)
                                add_item(key, center_x, f"{self.song.keyheader} {note.key_change}")

        # Convert to sorted list
        result = sorted(items_by_position.values(), key=lambda x: x['order'])
        return result

    def _above_text_font(self, text: str) -> tuple:
        """Return (font_name, font_size) for an above-staff text item."""
        if text in spec["dynamics"]["valid_dynamics"]:
            return (self.notation_font.replace("-Roman", "-Italic"), self.small_font_size + 1)
        return ("Helvetica-Bold", self.small_font_size + 1)

    def _draw_above_staff_line(self, items: List[Dict], start_y: float):
        """Draw all above-staff items on ONE line. Each item's texts are joined by spaces
        and centered over the note's center_x, with overlap prevention."""
        self.c.setFillColor(colors.black)
        draw_y = start_y + 2
        min_gap = 4  # minimum pixel gap between above-staff items

        # Pre-compute widths and initial draw_x for each item
        music_symbols = {spec["navigation"]["coda_symbol"], spec["navigation"]["segno_symbol"], spec["navigation"]["fermata_symbol"]}
        for item in items:
            total_width = 0
            for i, text in enumerate(item['texts']):
                if i > 0:
                    total_width += self.c.stringWidth("  ", "Helvetica-Bold", self.small_font_size + 1)
                contains_music = any(sym in text for sym in music_symbols)
                if contains_music:
                    idx = len(text) - 1
                    while idx >= 0 and text[idx].isdigit():
                        idx -= 1
                    total_width += self.c.stringWidth(text[:idx + 1], MUSIC_SYMBOL_FONT, self.small_font_size + 9)
                    if text[idx + 1:]:
                        total_width += self.c.stringWidth(text[idx + 1:], "Helvetica-Bold", self.small_font_size)
                else:
                    font_name, font_size = self._above_text_font(text)
                    total_width += self.c.stringWidth(text, font_name, font_size)
            item['_width'] = total_width
            item['_draw_x'] = item['center_x'] - total_width / 2

        # Nudge to prevent overlap
        for i in range(1, len(items)):
            prev_end = items[i - 1]['_draw_x'] + items[i - 1]['_width']
            if items[i]['_draw_x'] < prev_end + min_gap:
                items[i]['_draw_x'] = prev_end + min_gap

        for item in items:
            # Draw at computed _draw_x instead of centered
            self._draw_above_text_at(item['texts'], item['_draw_x'], draw_y)

    def _draw_combined_above_text(self, texts: List[str], center_x: float, draw_y: float):
        """Draw a list of above-staff text items centered over center_x, separated by spaces.
        Music symbols (Coda, Segno, Fermata) use MUSIC_SYMBOL_FONT, others use Helvetica-Bold."""
        # Build segments: list of (text, font_name, font_size)
        segments = []
        music_symbols = {spec["navigation"]["coda_symbol"], spec["navigation"]["segno_symbol"], spec["navigation"]["fermata_symbol"]}

        for i, text in enumerate(texts):
            if i > 0:
                segments.append(("  ", "Helvetica-Bold", self.small_font_size + 1))

            # Check if text contains music symbols
            contains_music = any(sym in text for sym in music_symbols)
            if contains_music:
                # Split symbol from number suffix
                idx = len(text) - 1
                while idx >= 0 and text[idx].isdigit():
                    idx -= 1
                symbol_part = text[:idx + 1]
                number_suffix = text[idx + 1:]

                segments.append((symbol_part, MUSIC_SYMBOL_FONT, self.small_font_size + 9))
                if number_suffix:
                    segments.append((number_suffix, "Helvetica-Bold", self.small_font_size))
            else:
                segments.append((text, "Helvetica-Bold", self.small_font_size + 1))

        # Calculate total width
        total_width = 0
        for seg_text, seg_font, seg_size in segments:
            total_width += self.c.stringWidth(seg_text, seg_font, seg_size)

        # Draw centered
        draw_x = center_x - total_width / 2
        base_size = self.small_font_size + 1
        for seg_text, seg_font, seg_size in segments:
            seg_y = draw_y - (seg_size - base_size) / 2 if seg_size > base_size else draw_y
            self.c.setFont(seg_font, seg_size)
            self.c.drawString(draw_x, seg_y, seg_text)
            draw_x += self.c.stringWidth(seg_text, seg_font, seg_size)

    def _draw_above_text_at(self, texts: List[str], draw_x: float, draw_y: float):
        """Draw above-staff text items starting at draw_x (no centering)."""
        music_symbols = {spec["navigation"]["coda_symbol"], spec["navigation"]["segno_symbol"], spec["navigation"]["fermata_symbol"]}
        for i, text in enumerate(texts):
            if i > 0:
                self.c.setFont("Helvetica-Bold", self.small_font_size + 1)
                self.c.drawString(draw_x, draw_y, "  ")
                draw_x += self.c.stringWidth("  ", "Helvetica-Bold", self.small_font_size + 1)
            contains_music = any(sym in text for sym in music_symbols)
            if text in spec["dynamics"]["valid_dynamics"]:
                font_name, font_size = self._above_text_font(text)
                self.c.setFont(font_name, font_size)
                self.c.drawString(draw_x, draw_y, text)
                draw_x += self.c.stringWidth(text, font_name, font_size)
            elif contains_music:
                idx = len(text) - 1
                while idx >= 0 and text[idx].isdigit():
                    idx -= 1
                symbol_part = text[:idx + 1]
                number_suffix = text[idx + 1:]
                music_size = self.small_font_size + 9
                symbol_y = draw_y - (music_size - (self.small_font_size + 1)) / 2
                self.c.setFont(MUSIC_SYMBOL_FONT, music_size)
                self.c.drawString(draw_x, symbol_y, symbol_part)
                draw_x += self.c.stringWidth(symbol_part, MUSIC_SYMBOL_FONT, music_size)
                if number_suffix:
                    self.c.setFont("Helvetica-Bold", self.small_font_size)
                    self.c.drawString(draw_x, draw_y, number_suffix)
                    draw_x += self.c.stringWidth(number_suffix, "Helvetica-Bold", self.small_font_size)
            else:
                self.c.setFont("Helvetica-Bold", self.small_font_size + 1)
                self.c.drawString(draw_x, draw_y, text)
                draw_x += self.c.stringWidth(text, "Helvetica-Bold", self.small_font_size + 1)

    # ─────────────────────────────────────────────────────────────────
    # Lyric organization helpers
    # ─────────────────────────────────────────────────────────────────

    def _organize_lyrics_by_target_voice(self, block_lyrics: List[Dict], start_idx: int,
                                         end_idx: int, voice_order: List[str]) -> Dict[str, List]:
        """Organize lyrics by their target voice (last voice in prefix)"""
        result = {}

        for bl in block_lyrics:
            if bl['start'] < end_idx and bl['end'] > start_idx:
                for lyric in bl['lyrics']:
                    target_voice = self._get_target_voice(lyric.voices, voice_order)

                    if target_voice not in result:
                        result[target_voice] = []

                    result[target_voice].append({
                        'lyric': lyric,
                        'block_start': bl['start'],
                        'block_end': bl['end']
                    })

        return result

    def _get_target_voice(self, voices: List[str], voice_order: List[str]) -> str:
        """Get the last voice from the voices list (where lyrics should be placed)"""
        if not voices:
            return voice_order[-1] if voice_order else "B"

        for v in reversed(voices):
            if v in voice_order:
                return v

        return voice_order[-1] if voice_order else "B"

    # ─────────────────────────────────────────────────────────────────
    # Collect above-staff markers with precise center_x
    # ─────────────────────────────────────────────────────────────────


    # ─────────────────────────────────────────────────────────────────
    # Measure and beat content rendering
    # ─────────────────────────────────────────────────────────────────

    def _draw_measure_content(self, measure: Measure, x: float, y: float,
                              width: float, height: float):
        """Draw the content of a single measure"""
        if measure.is_empty:
            num_beats = len(measure.beats) if measure.beats else 4
            beat_width = width / num_beats
            self.c.setFont(self.notation_font, self.note_font_size)
            text_y = y - height + 3
            for beat_idx in range(num_beats - 1):
                sep_x = x + (beat_idx + 1) * beat_width
                if measure.soft_barline_after_beat == beat_idx:
                    self.c.drawCentredString(sep_x, text_y, "|")
                else:
                    self.c.drawCentredString(sep_x, text_y, ":")
            return

        num_beats = len(measure.beats)
        if num_beats == 0:
            return

        beat_width = width / num_beats

        self.c.setFont(self.notation_font, self.note_font_size)
        text_y = y - height + 3
        underline_y = text_y - 2

        # Collect per-note positions across all beats for melisma underlines
        all_note_positions = []  # list of {x, end_x, is_melisma, is_note}

        for beat_idx, beat in enumerate(measure.beats):
            beat_x = x + beat_idx * beat_width

            beat_result = self._draw_beat_content_with_positions(beat, beat_x, y, beat_width, height)
            all_note_positions.extend(beat_result.get('note_positions', []))

            if beat_idx < num_beats - 1:
                sep_x = beat_x + beat_width
                if measure.soft_barline_after_beat == beat_idx:
                    self.c.drawCentredString(sep_x, text_y, "|")
                else:
                    self.c.drawCentredString(sep_x, text_y, ":")

        # Build melisma underline ranges: include the note before the melisma chain
        # and any holds between the note and the melisma
        melisma_ranges = []
        i = 0
        while i < len(all_note_positions):
            pos = all_note_positions[i]
            if pos['is_melisma'] and pos['is_note']:
                # Find the start: look back past holds to find the preceding real note
                start_x_m = pos['x'] + pos.get('mod_offset', 0)
                j = i - 1
                while j >= 0 and not all_note_positions[j]['is_note']:
                    j -= 1
                if j >= 0 and all_note_positions[j]['is_note']:
                    start_x_m = all_note_positions[j]['x'] + all_note_positions[j].get('mod_offset', 0)
                # Extend through consecutive melisma notes
                end_x_m = pos['end_x']
                while i < len(all_note_positions) and all_note_positions[i]['is_melisma'] and all_note_positions[i]['is_note']:
                    end_x_m = all_note_positions[i]['end_x']
                    i += 1
                melisma_ranges.append((start_x_m, end_x_m))
            else:
                i += 1

        for start_x_m, end_x_m in melisma_ranges:
            self._draw_melisma_underline(start_x_m, underline_y, end_x_m - start_x_m)

    def _draw_beat_content_with_positions(self, beat: Beat, x: float, y: float,
                                          width: float, height: float) -> Dict:
        """Draw the content of a single beat and return per-note position info"""
        self.c.setFont(self.notation_font, self.note_font_size)

        text_y = y - height + 3
        above_y = y + 2

        result = {
            'note_positions': [],  # list of {x, end_x, is_melisma, is_note}
            'key_changes': []
        }

        if beat.is_subdivided:
            half_width = width / 2

            first_text, first_mods = self._notes_to_display_text(beat.first_half)
            second_text, second_mods = self._notes_to_display_text(beat.second_half)

            # Measure widths to pack tightly around the dot
            first_text_width = self._calc_text_width_with_mods(first_text, first_mods) if first_text else 0
            second_text_width = self._calc_text_width_with_mods(second_text, second_mods) if second_text else 0
            dot_width = self.c.stringWidth(".", self.notation_font, self.note_font_size)
            total_content = first_text_width + dot_width + second_text_width
            # Center the whole group (first_text + dot + second_text) within the beat width
            content_x = x + (width - total_content) / 2

            first_draw_x = None
            if first_text:
                first_draw_x = content_x
                self._draw_text_with_modulation(first_text, first_mods, first_draw_x, text_y, x, above_y)
                for mod in first_mods:
                    if mod.get('key_change'):
                        result['key_changes'].append((first_draw_x, mod['key_change']))

            # Per-note positions for first half
            self._add_note_positions(beat.first_half, x, half_width, first_draw_x, first_text_width, result)

            dot_x = content_x + first_text_width
            self.c.setFont(self.notation_font, self.note_font_size)
            self.c.drawString(dot_x, text_y, ".")

            second_draw_x = None
            if second_text:
                second_draw_x = dot_x + dot_width
                self._draw_text_with_modulation(second_text, second_mods, second_draw_x, text_y, x + half_width,
                                                above_y)
                for mod in second_mods:
                    if mod.get('key_change'):
                        result['key_changes'].append((second_draw_x, mod['key_change']))

            # Per-note positions for second half
            self._add_note_positions(beat.second_half, x + half_width, half_width, second_draw_x, second_text_width, result)

        else:
            text, mods = self._notes_to_display_text(beat.notes)
            if text:
                text_width = self._calc_text_width_with_mods(text, mods)
                draw_x = x + (width - text_width) / 2
                self._draw_text_with_modulation(text, mods, draw_x, text_y, x, above_y)

                for mod in mods:
                    if mod.get('key_change'):
                        result['key_changes'].append((draw_x, mod['key_change']))

            # Per-note positions
            draw_x_val = x + (width - self._calc_text_width_with_mods(text, mods)) / 2 if text else x
            self._add_note_positions(beat.notes, x, width, draw_x_val if text else None, self._calc_text_width_with_mods(text, mods) if text else 0, result)

        return result

    def _add_note_positions(self, notes: List[Note], half_x: float, half_width: float,
                            draw_x: float, text_width: float, result: Dict):
        """Add per-note position info for melisma underline computation."""
        if not notes:
            return
        num_notes = len(notes)
        note_width = half_width / num_notes if num_notes > 0 else half_width
        for i, note in enumerate(notes):
            is_real_note = note.type in (NoteType.NOTE, NoteType.MODULATION, NoteType.CHORD)
            # Approximate each note's drawn x range within the half
            note_x = half_x + i * note_width
            note_end_x = note_x + note_width
            # If we have actual draw coordinates, use proportional mapping
            if draw_x is not None and text_width > 0 and num_notes > 0:
                per_note_w = text_width / num_notes
                note_x = draw_x + i * per_note_w
                note_end_x = note_x + per_note_w
            # For modulations, track where the main note starts (after superscript)
            mod_offset = 0
            if note.type == NoteType.MODULATION and note.modulation_from and draw_x is not None:
                superscript_size = self.note_font_size - 1
                mod_offset = self.c.stringWidth(note.modulation_from, self.notation_font, superscript_size)
            result['note_positions'].append({
                'x': note_x,
                'end_x': note_end_x,
                'is_melisma': note.is_melisma,
                'is_note': is_real_note,
                'mod_offset': mod_offset
            })

    def _calc_text_width_with_mods(self, text: str, modulations: List[Dict]) -> float:
        """Calculate total width of text including modulation superscripts"""
        if not modulations:
            return self.c.stringWidth(text, self.notation_font, self.note_font_size)

        total_width = 0
        superscript_size = self.note_font_size - 1

        for mod in modulations:
            old_note_width = self.c.stringWidth(mod['old_note'], self.notation_font, superscript_size)
            total_width += old_note_width

        total_width += self.c.stringWidth(text, self.notation_font, self.note_font_size)

        return total_width

    def _draw_melisma_underline(self, x: float, y: float, width: float):
        """Draw underline for melisma notes"""
        self.c.setStrokeColor(colors.black)
        self.c.setLineWidth(0.5)
        self.c.line(x, y, x + width, y)

    def _notes_to_display_text(self, notes: List[Note]) -> Tuple[str, List[Dict]]:
        """Convert notes to display text and return modulation info"""
        parts = []
        modulations = []

        for note in notes:
            # Dynamics, hairpins, text expressions are rendered above staff, not inline

            if note.type == NoteType.MODULATION and note.modulation_from:
                modulations.append({
                    'old_note': note.modulation_from,
                    'position': len("".join(parts)),
                    'key_change': note.key_change
                })

            parts.append(note.display_text())

        return "".join(parts), modulations

    def _draw_text_with_modulation(self, text: str, modulations: List[Dict],
                                   x: float, y: float, beat_x: float, above_y: float):
        """Draw text with modulation superscripts"""
        if not modulations:
            self.c.setFont(self.notation_font, self.note_font_size)
            self.c.drawString(x, y, text)
            return

        self.c.setFont(self.notation_font, self.note_font_size)
        current_x = x
        text_idx = 0

        for mod in modulations:
            if mod['position'] > text_idx:
                pre_text = text[text_idx:mod['position']]
                self.c.setFont(self.notation_font, self.note_font_size)
                self.c.drawString(current_x, y, pre_text)
                current_x += self.c.stringWidth(pre_text, self.notation_font, self.note_font_size)
                text_idx = mod['position']

            superscript_size = self.note_font_size - 1
            self.c.setFont(self.notation_font, superscript_size)
            old_note_text = mod['old_note']
            self.c.drawString(current_x, y + 4, old_note_text)
            current_x += self.c.stringWidth(old_note_text, self.notation_font, superscript_size)

        if text_idx < len(text):
            remaining = text[text_idx:]
            self.c.setFont(self.notation_font, self.note_font_size)
            self.c.drawString(current_x, y, remaining)

    def _short_nav(self, nav_text: str) -> str:
        """Get short form of navigation marker for display"""
        reverse_map = {v: k for k, v in spec["navigation"]["markers"].items()}
        return reverse_map.get(nav_text, nav_text)

    # ─────────────────────────────────────────────────────────────────
    # Lyric rendering
    # ─────────────────────────────────────────────────────────────────

    def _draw_single_lyric_line(self, start_x: float, y: float,
                                label_width: float, geo: Dict[int, Tuple[float, float]],
                                start_idx: int, end_idx: int,
                                lyric_info: Dict,
                                all_voice_data: Dict, voice_order: List[str]):
        """Draw a single lyric line under the notes, synced to the target voice"""
        lyric = lyric_info['lyric']
        block_start = lyric_info['block_start']
        block_end = lyric_info['block_end']

        target_voice = self._get_target_voice(lyric.voices, voice_order)

        # For common/shared lyrics (spanning multiple voices), sync syllables to the
        # first (melody) voice rather than the last placement voice.
        if len(lyric.voices) > 1:
            ref_voice = next((v for v in voice_order if v in lyric.voices), target_voice)
        else:
            ref_voice = target_voice
        ref_measures = all_voice_data.get(ref_voice, [])

        if not ref_measures and voice_order:
            ref_measures = all_voice_data.get(voice_order[0], [])

        lyric_y = y - self.lyric_top_margin

        syllable_positions = []
        syllable_idx = 0

        for m_offset in range(block_end - block_start):
            m_idx = block_start + m_offset
            if m_idx >= len(ref_measures):
                continue
            if m_idx < start_idx or m_idx >= end_idx:
                measure = ref_measures[m_idx]
                for beat in measure.beats:
                    for note in beat.all_notes():
                        if note.type == NoteType.NOTE and not note.is_melisma:
                            syllable_idx += 1
                        elif note.type == NoteType.MODULATION:
                            syllable_idx += 1
                continue

            measure = ref_measures[m_idx]
            num_beats = len(measure.beats)
            m_offset, measure_width = geo.get(m_idx, (0.0, self._measure_width))
            beat_width = measure_width / num_beats if num_beats > 0 else measure_width

            for beat_idx, beat in enumerate(measure.beats):
                all_notes = beat.all_notes()
                num_notes_in_beat = len(all_notes)

                if beat.is_subdivided:
                    first_half_notes = beat.first_half
                    second_half_notes = beat.second_half

                    # Compute tight layout matching note rendering
                    first_text, first_mods = self._notes_to_display_text(first_half_notes)
                    second_text, second_mods = self._notes_to_display_text(second_half_notes)
                    first_tw = self._calc_text_width_with_mods(first_text, first_mods) if first_text else 0
                    second_tw = self._calc_text_width_with_mods(second_text, second_mods) if second_text else 0
                    dot_w = self.c.stringWidth(".", self.notation_font, self.note_font_size)
                    total_content = first_tw + dot_w + second_tw

                    beat_x = start_x + label_width + m_offset + beat_idx * beat_width
                    content_x = beat_x + (beat_width - total_content) / 2

                    # First half: notes packed from content_x over first_tw
                    num_first = len(first_half_notes)
                    per_note_first = first_tw / num_first if num_first > 0 and first_tw > 0 else beat_width / 2
                    for note_idx, note in enumerate(first_half_notes):
                        if (note.type == NoteType.NOTE and not note.is_melisma) or note.type == NoteType.MODULATION:
                            if syllable_idx < len(lyric.syllables):
                                syl = lyric.syllables[syllable_idx]
                                if syl != "*":
                                    note_center_x = content_x + note_idx * per_note_first + per_note_first / 2
                                    syllable_positions.append({
                                        'text': syl,
                                        'center_x': note_center_x
                                    })
                                syllable_idx += 1

                    # Second half: notes packed from after the dot
                    second_x = content_x + first_tw + dot_w
                    num_second = len(second_half_notes)
                    per_note_second = second_tw / num_second if num_second > 0 and second_tw > 0 else beat_width / 2
                    for note_idx, note in enumerate(second_half_notes):
                        if (note.type == NoteType.NOTE and not note.is_melisma) or note.type == NoteType.MODULATION:
                            if syllable_idx < len(lyric.syllables):
                                syl = lyric.syllables[syllable_idx]
                                if syl != "*":
                                    note_center_x = second_x + note_idx * per_note_second + per_note_second / 2
                                    syllable_positions.append({
                                        'text': syl,
                                        'center_x': note_center_x
                                    })
                                syllable_idx += 1
                else:
                    for note_idx, note in enumerate(all_notes):
                        if (note.type == NoteType.NOTE and not note.is_melisma) or note.type == NoteType.MODULATION:
                            if syllable_idx < len(lyric.syllables):
                                syl = lyric.syllables[syllable_idx]
                                if syl != "*":
                                    note_width = beat_width / num_notes_in_beat
                                    note_center_x = (start_x + label_width +
                                                     m_offset +
                                                     beat_idx * beat_width +
                                                     note_idx * note_width +
                                                     note_width / 2)
                                    syllable_positions.append({
                                        'text': syl,
                                        'center_x': note_center_x
                                    })
                                syllable_idx += 1

        if not syllable_positions:
            return

        self.c.setFont(self.notation_font, self.lyric_font_size)
        italic_font = self.notation_font.replace("-Roman", "-Italic").replace("-Bold", "-BoldItalic")
        if italic_font == self.notation_font and "Italic" not in italic_font:
            italic_font = self.notation_font + "-Italic"  # fallback
        mute_delim = spec["lyrics"]["mute_open"]

        min_gap = 2  # minimum pixel gap between syllables

        # Compute draw_x for each syllable, then nudge to avoid overlap
        for syl_info in syllable_positions:
            text = syl_info['text']
            tw = self._lyric_text_width(text, mute_delim, italic_font)
            syl_info['draw_x'] = syl_info['center_x'] - tw / 2
            syl_info['width'] = tw

        for i in range(1, len(syllable_positions)):
            prev = syllable_positions[i - 1]
            curr = syllable_positions[i]
            prev_end = prev['draw_x'] + prev['width']
            if curr['draw_x'] < prev_end + min_gap:
                curr['draw_x'] = prev_end + min_gap

        for syl_info in syllable_positions:
            self._draw_lyric_text(syl_info['draw_x'], lyric_y, syl_info['text'],
                                  mute_delim, italic_font)

    def _lyric_text_width(self, text: str, mute_delim: str, italic_font: str) -> float:
        """Compute total width of a lyric syllable, accounting for mute delimiters."""
        if mute_delim not in text:
            return self.c.stringWidth(text, self.notation_font, self.lyric_font_size)
        total = 0.0
        for segment in self._split_mute_segments(text, mute_delim):
            font = italic_font if segment['mute'] else self.notation_font
            total += self.c.stringWidth(segment['text'], font, self.lyric_font_size)
        return total

    def _draw_lyric_text(self, x: float, y: float, text: str,
                         mute_delim: str, italic_font: str):
        """Draw a lyric syllable, rendering mute portions in italic."""
        if mute_delim not in text:
            self.c.drawString(x, y, text)
            return
        cx = x
        for segment in self._split_mute_segments(text, mute_delim):
            font = italic_font if segment['mute'] else self.notation_font
            self.c.setFont(font, self.lyric_font_size)
            self.c.drawString(cx, y, segment['text'])
            cx += self.c.stringWidth(segment['text'], font, self.lyric_font_size)
        self.c.setFont(self.notation_font, self.lyric_font_size)

    @staticmethod
    def _split_mute_segments(text: str, delim: str) -> list:
        """Split text into normal and mute segments.

        e.g. 'ev__e__ry' → [{'text':'ev','mute':False}, {'text':'e','mute':True}, {'text':'ry','mute':False}]
        """
        segments = []
        while delim in text:
            before, _, rest = text.partition(delim)
            if before:
                segments.append({'text': before, 'mute': False})
            if delim in rest:
                mute_part, _, text = rest.partition(delim)
                if mute_part:
                    segments.append({'text': mute_part, 'mute': True})
            else:
                text = rest
                break
        if text:
            segments.append({'text': text, 'mute': False})
        return segments
