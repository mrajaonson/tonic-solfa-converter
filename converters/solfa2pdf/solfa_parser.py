import re
from typing import List, Optional, Tuple
from ..shared import (
    spec,
    match_solfa_token,
    consume_octave_modifiers,
    nav_base,
    nav_number,
    navigation_display,
    voice_label_alternation,
    extract_parenthesized_prefix,
    parse_lyric_prefix,
    resolve_beats_per_measure,
)
from .data_structures import (Song, VoiceLine, Measure, Note, NoteType, Block, LyricLine, Expression, Beat)

class TonicSolfaParser:
    """Parser for tonic solfa notation files"""

    def __init__(self):
        self.song = Song()
        self.current_measure_num = 0
        # True when the previous block's voice lines ended on a trailing partial
        # measure, meaning the next block may open with a continuation that
        # completes that same (split) measure and shares its number.
        self._prev_block_ended_trailing_partial = False
        self._prev_trailing_beats = 0  # beat count of that trailing partial

    def parse(self, text: str) -> Song:
        """Parse the complete tonic solfa text"""
        lines = text.strip().split('\n')

        # Extract [notes] section - everything from the marker to EOF
        marker = spec["notes_section"]["marker"]
        for i, line in enumerate(lines):
            if line.strip() == marker:
                self.song.notes = "\n".join(lines[i + 1:]).strip()
                lines = lines[:i]
                break

        # Initialize song with defaults
        for key, value in spec["defaults"].items():
            if key == "timesig":
                self.song.time_sig = (4, 4)
            elif hasattr(self.song, key.lower()):
                setattr(self.song, key.lower(), value)

        # Separate header and content
        content_lines = []
        for line in lines:
            stripped = line.strip()
            if not stripped:
                content_lines.append("")
                continue

            # Skip comment lines
            if stripped.startswith('//'):
                continue

            # Check if it's a header property line (:PROP_NAME: value).
            # A note line whose first beat is empty (e.g. ": d | r : m | f")
            # also starts with the prop_prefix ':', so _parse_header_line only
            # consumes the line if the keyword is a known property - otherwise
            # it's content and falls through to note parsing.
            if not self._parse_header_line(stripped):
                content_lines.append(line)

        # Beats per measure is counted from the music (a partial first measure or
        # a measure split across systems is skipped); the counted value wins over
        # the header numerator, which now only supplies the denominator.
        # Count over the file-aligned ``lines`` (not ``content_lines``, which drops
        # header/comment lines) so a mismatch warning can cite the real line number.
        den = self.song.time_sig[1]
        num = resolve_beats_per_measure(
            lines, header_timesig=f"{self.song.time_sig[0]}/{den}"
        )
        self.song.time_sig = (num, den)

        # Parse content blocks
        self._parse_blocks(content_lines)

        return self.song

    def _parse_header_line(self, line: str) -> bool:
        """Parse a header property line in :PROP_NAME: value format.

        Returns True if the line was a recognized header property (and was
        consumed), False otherwise. A note line whose first beat is empty
        (e.g. ": d | r : m | f" with no leading barline) also starts with the
        prop_prefix ':', so we only treat it as a header line when the text
        between the two colons is a known property name.
        """
        prefix = spec["header"]["prop_prefix"]
        suffix = spec["header"]["prop_suffix"]

        if not line.startswith(prefix) or suffix not in line[len(prefix):]:
            return False

        # Strip leading prefix, then split on suffix to get prop name and value
        rest = line[len(prefix):]
        idx = rest.index(suffix)
        prop = rest[:idx].strip()
        value = rest[idx + len(suffix):].strip()

        # Skip unknown property names - could be note notation starting with ':'
        all_props = set(spec["header"]["string_props"]) | set(spec["header"]["int_props"]) | set(spec["header"]["special_props"]) | set(spec["header"]["flag_props"])
        if prop not in all_props:
            return False

        if prop in set(spec["header"]["flag_props"]):
            if hasattr(self.song, prop):
                setattr(self.song, prop, value.lower() == "true")
        elif prop in set(spec["header"]["string_props"]):
            if prop in ("author", "composer"):
                attr = prop + "s"  # authors / composers
                getattr(self.song, attr).append(value)
            else:
                attr = prop.lower()
                if hasattr(self.song, attr):
                    setattr(self.song, attr, value)
        elif prop in set(spec["header"]["int_props"]):
            attr = prop.lower()
            try:
                setattr(self.song, attr, int(value))
            except ValueError:
                pass
        elif prop == "timesig":
            if "/" in value:
                num, denom = value.split("/")
                try:
                    self.song.time_sig = (int(num), int(denom))
                except ValueError:
                    pass

        return True

    def _parse_blocks(self, lines: List[str]):
        """Parse content into blocks of voice lines and lyrics"""
        current_block_lines = []

        for line in lines:
            stripped = line.strip()

            if not stripped:
                # Empty line might signal end of block
                if current_block_lines:
                    # Check if we have a complete block
                    has_notes = any(self._is_note_line(l) for l in current_block_lines)
                    if has_notes:
                        block = self._parse_single_block(current_block_lines)
                        if block:
                            self.song.blocks.append(block)
                        current_block_lines = []
                continue

            # Skip comment lines
            if stripped.startswith('//'):
                continue

            current_block_lines.append(stripped)

        # Don't forget the last block
        if current_block_lines:
            block = self._parse_single_block(current_block_lines)
            if block:
                self.song.blocks.append(block)

    def _is_note_line(self, line: str) -> bool:
        """Check if a line contains note notation (has barlines)"""
        return spec["rhythm"]["barline"] in line

    def _parse_single_block(self, lines: List[str]) -> Optional[Block]:
        """Parse a single block of voice lines and lyrics"""
        block = Block(measure_start=self.current_measure_num + 1)

        note_lines = []
        lyric_lines = []

        for line in lines:
            if self._is_note_line(line):
                note_lines.append(line)
            else:
                lyric_lines.append(line)

        if not note_lines:
            return None

        # Parse voice lines
        voice_labels_used = []
        for i, note_line in enumerate(note_lines):
            voice_line = self._parse_voice_line(note_line, i, len(note_lines))
            if voice_line:
                block.voice_lines.append(voice_line)
                voice_labels_used.append(voice_line.voice_label)

        # Assign measure numbers across all voices and update the running count.
        if block.voice_lines:
            self._number_block_measures(block)

        # Parse lyrics. Unprefixed lines are numbered by position (verse 1, 2, ...)
        # within the block; a voices-only prefix like (SA) is verse 1 and does not
        # count. The verse number is shown only when the block has >=2 such verses.
        parsed_lyrics = []
        for lyric_line in lyric_lines:
            res = self._parse_lyric_line(lyric_line, voice_labels_used)
            if res:
                parsed_lyrics.append(res)

        num_positional = sum(1 for _, prefixed in parsed_lyrics if not prefixed)
        positional = 0
        for lyric, prefixed in parsed_lyrics:
            if lyric.verse is not None:          # explicit verse / refrain
                verse_str = lyric.verse
                label = verse_str
            elif prefixed:                        # voices-only -> verse 1, no label
                verse_str = "1"
                label = ""
            else:                                 # unprefixed -> positional verse
                positional += 1
                verse_str = str(positional)
                label = verse_str if num_positional >= 2 else ""
            lyric.verse = verse_str
            lyric.display_prefix = label + lyric.display_prefix
            block.lyric_lines.append(lyric)

        return block

    def _parse_voice_line(self, line: str, line_index: int, total_lines: int) -> Optional[VoiceLine]:
        """Parse a single voice line with its measures"""
        # Check for explicit voice label at start
        voice_label = None
        notation = line

        # Try to match voice label at start (e.g., "S1 |d:r:m:f|", "S |d:r:m:f|",
        # or without a leading barline, "S1 d | r : m | f"). This is only called
        # on lines already confirmed to contain a barline, so the notation after
        # the label doesn't need to start with one.
        label_match = re.match(rf'^({voice_label_alternation()}|[SATB]\d+)\s+(.+)$', line)
        if label_match:
            voice_label = label_match.group(1)
            notation = label_match.group(2)
        else:
            # Implicit label based on line order
            if total_lines <= 4:
                voice_label = spec["voices"]["default_order"][line_index] if line_index < 4 else f"V{line_index + 1}"
            else:
                voice_label = f"V{line_index + 1}"

        voice_line = VoiceLine(voice_label=voice_label)

        # A boundary barline may be omitted only for a partial/pickup measure
        # (fewer beats than the time signature). Track whether it was present at
        # each edge so the first/last fragment can be treated accordingly.
        barline = spec["rhythm"]["barline"]
        trimmed = notation.strip()
        if trimmed.endswith(spec["rhythm"]["double_barline"]):
            trimmed_end = trimmed[:-2].rstrip()
        else:
            trimmed_end = trimmed
        has_leading_barline = trimmed.startswith(barline)
        has_trailing_barline = trimmed_end.endswith(barline)

        # Parse measures
        measures = self._split_into_measures(notation)

        for m_idx, measure_str in enumerate(measures):
            is_boundary_leading = m_idx == 0 and not has_leading_barline
            is_boundary_trailing = m_idx == len(measures) - 1 and not has_trailing_barline
            measure = self._parse_measure(measure_str, voice_label, is_boundary_leading, is_boundary_trailing)
            # measure.number is assigned centrally in _parse_single_block so all
            # voices share numbers and split measures count as one.
            voice_line.measures.append(measure)

        return voice_line

    def _warn_if_full_boundary_measure(self, voice_label: str, position: str, num_beats: int, beats_per_measure: int):
        """A measure without a barline at the line's edge is only valid as a
        partial/pickup fragment. Warn (but still parse leniently) if it actually
        has a full measure's worth of beats - it should have an explicit '|'."""
        if num_beats >= beats_per_measure:
            print(
                f"Warning: voice '{voice_label}' has a {position} measure without a barline "
                f"that contains a full measure ({num_beats} beats) - add an explicit '|' there."
            )

    def _number_block_measures(self, block: Block):
        """Assign measure numbers to every voice in a block by index.

        A block whose first measure is a leading partial completing the previous
        block's trailing partial is a continuation: its first measure shares the
        prior measure's number (the two halves of a split measure count as one).
        Subsequent measures increment normally. The same numbers are applied to
        every voice so they stay aligned.
        """
        ref_measures = block.voice_lines[0].measures
        num_measures = len(ref_measures)

        first = ref_measures[0] if ref_measures else None
        continuation = (
            self._prev_block_ended_trailing_partial
            and first is not None
            and first.is_partial
            and first.partial_side == "leading"
        )

        numbers = []
        n = self.current_measure_num
        for m_idx in range(num_measures):
            if m_idx == 0 and continuation:
                numbers.append(n)  # complete the split measure - same number
            else:
                n += 1
                numbers.append(n)
        self.current_measure_num = n

        # Warn if a split pair does not add up to a full measure.
        if continuation:
            total = self._prev_trailing_beats + len(first.beats)
            beats_per_measure = self.song.time_sig[0]
            if total != beats_per_measure:
                print(
                    f"Warning: split measure across a system break has {total} beats "
                    f"(expected {beats_per_measure}) - check the partial measures at the break."
                )

        for voice_line in block.voice_lines:
            for m_idx, measure in enumerate(voice_line.measures):
                if m_idx < len(numbers):
                    measure.number = numbers[m_idx]
                    if m_idx == 0 and continuation:
                        measure.is_continuation = True

        last = ref_measures[-1] if ref_measures else None
        if last is not None and last.is_partial and last.partial_side == "trailing":
            self._prev_block_ended_trailing_partial = True
            self._prev_trailing_beats = len(last.beats)
        else:
            self._prev_block_ended_trailing_partial = False
            self._prev_trailing_beats = 0

    def _split_into_measures(self, notation: str) -> List[str]:
        """Split notation string into individual measures"""
        # Remove leading/trailing barlines and split
        notation = notation.strip()

        # Handle double barline at end
        if notation.endswith(spec["rhythm"]["double_barline"]):
            notation = notation[:-2]

        # Split by single barlines
        parts = notation.split(spec["rhythm"]["barline"])

        # Filter out empty parts
        measures = [p.strip() for p in parts if p.strip()]

        return measures

    def _parse_measure(self, measure_str: str, voice_label: str = "",
                       is_boundary_leading: bool = False, is_boundary_trailing: bool = False) -> Measure:
        """Parse a single measure into beats.

        is_boundary_leading/is_boundary_trailing mark a measure at the very
        start/end of a line that has no barline there (e.g. "d | r : m | f").
        Bare separators at that edge (before the first or after the last real
        beat) are skip-markers for beats outside the partial fragment - not
        real rest beats - so they are dropped rather than rendered. A boundary
        fragment with fewer beats than the time signature is flagged is_partial
        (rendered narrow); one that is actually full is warned about but kept.
        """
        measure = Measure()

        if not measure_str:
            measure.is_empty = True
            return measure

        # Replace soft barline with beat separator, recording its position
        soft_barline_char = spec["rhythm"]["soft_barline"]["char"]
        beat_sep = spec["rhythm"]["beat_separator"]
        soft_barline_pos = -1
        if soft_barline_char in measure_str:
            # Count beats before the soft barline to find its position
            soft_idx = measure_str.index(soft_barline_char)
            beats_before = measure_str[:soft_idx].count(beat_sep)
            soft_barline_pos = beats_before
            measure_str = measure_str.replace(soft_barline_char, beat_sep, 1)

        # Split into beats by ':'
        beat_strs = measure_str.split(beat_sep)

        # Boundary fragments: strip bare edge beat-slots (skip-markers) and
        # decide whether this is a narrow partial measure or a full one.
        if is_boundary_leading or is_boundary_trailing:
            if is_boundary_leading:
                skipped = 0
                while len(beat_strs) > 1 and not beat_strs[0].strip():
                    beat_strs.pop(0)
                    skipped += 1
                if skipped and soft_barline_pos >= 0:
                    soft_barline_pos = soft_barline_pos - skipped if soft_barline_pos > skipped else -1
            if is_boundary_trailing:
                while len(beat_strs) > 1 and not beat_strs[-1].strip():
                    beat_strs.pop()
            beats_per_measure = self.song.time_sig[0]
            position = "leading" if is_boundary_leading else "trailing"
            if len(beat_strs) < beats_per_measure:
                measure.is_partial = True
                measure.partial_side = position
            else:
                self._warn_if_full_boundary_measure(voice_label, position, len(beat_strs), beats_per_measure)

        # Check if all beats are empty (whole-measure rest)
        all_empty = all(not b.strip() or b.strip() == "" for b in beat_strs)
        if all_empty:
            measure.is_empty = True
            # Still create empty beats for structure
            for _ in beat_strs:
                measure.beats.append(Beat())
            measure.soft_barline_after_beat = soft_barline_pos
            return measure

        for beat_str in beat_strs:
            beat = self._parse_beat(beat_str)
            measure.beats.append(beat)

        measure.soft_barline_after_beat = soft_barline_pos

        return measure

    def _parse_beat(self, beat_str: str) -> Beat:
        """Parse a single beat, potentially subdivided"""
        beat = Beat()
        beat_str = beat_str.strip()

        if not beat_str:
            # Empty beat = rest
            beat.notes.append(Note(type=NoteType.REST))
            return beat

        # Check for subdivision (one dot splits the beat in half)
        if spec["rhythm"]["subbeat_separator"] in beat_str:
            beat.is_subdivided = True
            parts = beat_str.split(spec["rhythm"]["subbeat_separator"], 1)  # Split on first dot only

            # First half
            if parts[0]:
                first_half_notes = self._parse_note_group(parts[0])
                for n in first_half_notes:
                    n.duration_fraction = 0.5 / len(first_half_notes) if first_half_notes else 0.5
                beat.first_half = first_half_notes
            else:
                beat.first_half = [Note(type=NoteType.REST, duration_fraction=0.5)]

            # Second half
            if len(parts) > 1 and parts[1]:
                second_half_notes = self._parse_note_group(parts[1])
                for n in second_half_notes:
                    n.duration_fraction = 0.5 / len(second_half_notes) if second_half_notes else 0.5
                beat.second_half = second_half_notes
            else:
                beat.second_half = [Note(type=NoteType.REST, duration_fraction=0.5)]
        else:
            # No subdivision - parse as note group (could be tuplet)
            notes = self._parse_note_group(beat_str)
            for n in notes:
                n.duration_fraction = 1.0 / len(notes) if notes else 1.0
            beat.notes = notes

        return beat

    def _parse_note_group(self, group_str: str) -> List[Note]:
        """Parse a group of notes (could be single note, hold, rest, or tuplet)"""
        notes = []

        if not group_str:
            return [Note(type=NoteType.REST)]

        # Check for staccato prefix (comma at start after separator)
        is_staccato = False
        if group_str.startswith(spec["staccato"]["prefix"]):
            # Check if this is really staccato or octave modifier
            # Staccato is comma BEFORE the note letter, not after
            # So ",d" is staccato d, but "d," is d octave down
            is_staccato = True
            group_str = group_str[1:]

        # Parse expressions (in parentheses) and check for key change
        expressions = []
        key_change = ""
        while group_str.startswith('('):
            close_idx = group_str.find(')')
            if close_idx > 0:
                expr_content = group_str[1:close_idx]
                # Check if this is a key change (for modulation)
                # Key changes are like (Ab), (C#), (Db), etc.
                if expr_content in spec["keys"]["valid_keys"]:
                    key_change = expr_content
                else:
                    expr = self._parse_expression(expr_content)
                    if expr:
                        expressions.append(expr)
                group_str = group_str[close_idx + 1:]
            else:
                break

        # Strip any whitespace after expressions
        group_str = group_str.strip()

        # Check for special cases
        if group_str == spec["rhythm"]["hold"]:
            note = Note(type=NoteType.HOLD, expressions=expressions)
            return [note]

        if group_str == spec["rhythm"]["rest_explicit"]:
            note = Note(type=NoteType.REST, expressions=expressions)
            return [note]

        # Check for chord
        if group_str.startswith(spec["chords"]["open"]) and spec["chords"]["close"] in group_str:
            chord_end = group_str.index(spec["chords"]["close"])
            chord_content = group_str[1:chord_end]
            chord_notes = []
            for note_str in chord_content.split('.'):
                if note_str:
                    n = self._parse_single_note(note_str)
                    if n:
                        chord_notes.append(n)
            note = Note(type=NoteType.CHORD, chord_notes=chord_notes, expressions=expressions)
            return [note]

        # Check for modulation (old_note/new_note)
        if spec["modulation"]["separator"] in group_str:
            parts = group_str.split(spec["modulation"]["separator"])
            if len(parts) == 2:
                note = Note(
                    type=NoteType.MODULATION,
                    modulation_from=parts[0],
                    modulation_to=parts[1],
                    key_change=key_change,
                    expressions=expressions
                )
                # The modulation_to is also the played note
                played = self._parse_single_note(parts[1])
                if played:
                    note.solfa = played.solfa
                    note.octave_modifier = played.octave_modifier
                return [note]

        # Parse as regular note(s) - could be tuplet like "dms"
        remaining = group_str
        while remaining:
            # Check for melisma prefix
            is_melisma = False
            if remaining.startswith(spec["staccato"]["melisma_prefix"]):
                is_melisma = True
                remaining = remaining[1:]

            # Try to match a note
            note = self._parse_single_note_from_start(remaining)
            if note:
                note.is_melisma = is_melisma
                if is_staccato and len(notes) == 0:
                    note.is_staccato = True
                if expressions and len(notes) == 0:
                    note.expressions = expressions
                notes.append(note)
                # Consume the matched portion
                consumed = len(note.solfa) + len(note.octave_modifier)
                remaining = remaining[consumed:]
            else:
                # Couldn't parse - skip character
                if remaining:
                    remaining = remaining[1:]

        if not notes:
            return [Note(type=NoteType.REST)]

        return notes

    def _parse_single_note(self, note_str: str) -> Optional[Note]:
        """Parse a single note string completely"""
        note = self._parse_single_note_from_start(note_str)
        return note

    def _parse_single_note_from_start(self, text: str) -> Optional[Note]:
        """Parse a note from the start of text, return Note with solfa and octave_modifier"""
        if not text:
            return None

        # Try to match solfa tokens (longest first)
        matched_solfa = match_solfa_token(text, ignore_case=True)

        if not matched_solfa:
            return None

        # Get octave modifiers after the solfa
        octave_mod, _ = consume_octave_modifiers(text[len(matched_solfa):])

        return Note(type=NoteType.NOTE, solfa=matched_solfa, octave_modifier=octave_mod)

    def _parse_expression(self, content: str) -> Optional[Expression]:
        """Parse expression content inside parentheses"""
        if content in spec["dynamics"]["valid_dynamics"]:
            return Expression(type="dynamic", value=content)
        elif content == spec["dynamics"]["hairpins"]["crescendo"]:
            return Expression(type="hairpin", value="cresc.")
        elif content == spec["dynamics"]["hairpins"]["diminuendo"]:
            return Expression(type="hairpin", value="dim.")
        elif content == spec["dynamics"]["fermata"]:
            return Expression(type="fermata", value="fermata")
        elif content in spec["navigation"]["markers"]:
            return Expression(type="navigation", value=spec["navigation"]["markers"][content])
        elif content in spec["dynamics"]["text_expressions"]:
            return Expression(type="text", value=spec["dynamics"]["text_expressions"][content])
        else:
            # Check for numbered navigation markers (DS1, DS2, S1, S2, DSF1, etc.)
            if nav_base(content) in spec["navigation"]["markers"] and nav_number(content) is not None:
                return Expression(type="navigation", value=navigation_display(content))
        return None

    def _parse_lyric_line(self, line: str, available_voices: List[str]) -> Optional[Tuple[LyricLine, bool]]:
        """Parse a lyrics line with an optional parenthesized prefix.

        Returns (lyric_line, prefixed) or None. ``lyric_line.verse`` holds the
        explicit verse ("2"/"R") or None (voices-only or unprefixed);
        ``display_prefix`` holds only the voice letters (when the voice set is
        restricted). The caller (_parse_single_block) resolves the final verse
        from the line's position and prepends the verse label.
        """
        line = line.strip()
        if not line:
            return None

        voices = list(available_voices) if available_voices else spec["voices"]["default_order"][:]
        voice_display = ""
        verse: Optional[str] = None
        prefixed = False
        text = line

        p = extract_parenthesized_prefix(line)
        if p is not None:
            content, rest = p
            result = parse_lyric_prefix(content, spec["voices"]["base_labels"], allow_numbered=True)
            if result is not None:
                v, labels = result
                prefixed = True
                verse = v  # digit string, "R", or None (voices-only)
                if labels:
                    voices = labels
                    full = set(spec["voices"]["default_order"][:len(available_voices)])
                    if set(labels) != full:
                        voice_display = "".join(labels)
                text = rest.strip()
            # Invalid prefix content: treat the whole line as literal lyrics.

        # Parse syllables
        syllables = self._parse_syllables(text)

        if not syllables:
            return None

        lyric = LyricLine(
            verse=verse,
            voices=voices,
            syllables=syllables,
            display_prefix=voice_display,
        )
        return lyric, prefixed

    def _parse_syllables(self, text: str) -> List[str]:
        """Parse lyrics text into syllables"""
        syllables = []

        # Replace join (^) with placeholder, split, then restore as space
        _JOIN_PLACEHOLDER = "\x00"
        text = text.replace(spec["lyrics"]["join"], _JOIN_PLACEHOLDER)

        # Split by spaces and hyphens
        words = text.split()

        for word in words:
            if word == spec["lyrics"]["rest_skip"]:
                syllables.append("*")
            elif spec["lyrics"]["hyphen"] in word:
                # Split hyphenated word
                # Trailing hyphen (e.g. "ma-") indicates word continues on next line
                # and is rendered as "ma-" without consuming an extra note
                parts = word.split(spec["lyrics"]["hyphen"])
                for i, part in enumerate(parts):
                    if part:
                        if i < len(parts) - 1:
                            syllables.append(part + "-")
                        else:
                            syllables.append(part)
            else:
                syllables.append(word)

        # Restore join placeholders to spaces for display
        return [s.replace(_JOIN_PLACEHOLDER, " ") for s in syllables]
