"""Parsing logic for tonic solfa .txt files."""

import re
from pathlib import Path
from .models import NoteEvent
from ..shared import spec


# ──────────────────────────────────────────────────────────────────────
#  HEADER PARSING
# ──────────────────────────────────────────────────────────────────────

_HEADER_STRING_PROPS = set(spec["header"]["string_props"])
_HEADER_INT_PROPS = set(spec["header"]["int_props"])
_HEADER_SPECIAL_PROPS = set(spec["header"]["special_props"])
_HEADER_KEYWORDS = _HEADER_STRING_PROPS | _HEADER_INT_PROPS | _HEADER_SPECIAL_PROPS


def parse_header(lines: list[str]) -> tuple[dict, list[str]]:
    """Extract property lines (:PROP: value) from the top of the file."""
    prefix = spec["header"]["prop_prefix"]
    suffix = spec["header"]["prop_suffix"]
    props = dict(spec["defaults"])
    remaining = []
    header_done = False

    for line in lines:
        stripped = line.strip()
        if stripped.startswith('//'):
            remaining.append(line)
            continue
        if not header_done and stripped:
            # Match :PROP: value format
            if stripped.startswith(prefix) and suffix in stripped[len(prefix):]:
                rest = stripped[len(prefix):]
                idx = rest.index(suffix)
                keyword = rest[:idx].strip()
                value = rest[idx + len(suffix):].strip()

                if keyword not in _HEADER_KEYWORDS:
                    continue  # unknown prop, skip silently

                if keyword in _HEADER_INT_PROPS:
                    try:
                        props[keyword] = int(value)
                    except ValueError:
                        pass
                else:
                    props[keyword] = value
                continue
            else:
                header_done = True
        if header_done or not stripped:
            if stripped:
                header_done = True
            remaining.append(line)
    return props, remaining


# ──────────────────────────────────────────────────────────────────────
#  NOTE TOKEN PARSING
# ──────────────────────────────────────────────────────────────────────

_DYNAMIC_PREFIX_RE = re.compile(r'^\(([^)]+)\)')

# Regex for numbered navigation markers (DS1, SEGNO2, S1, CODA1, etc.)
# S is a short alias for SEGNO, C for CODA
_NUMBERED_NAV_RE = re.compile(
    r'^(DS|DSF|DSC|SEGNO|CODA|TC|DC|DCF|DCC|FINE)(\d+)$'
)


def _is_navigation_marker(value: str) -> bool:
    """Check if a paren value is a navigation marker (plain or numbered)."""
    if value in spec["navigation"]["markers"]:
        return True
    return bool(_NUMBERED_NAV_RE.match(value))


def _parse_single_token(s: str) -> tuple[NoteEvent | None, str]:
    """Parse one note token from the beginning of *s*."""
    if not s:
        return None, s

    # --- parenthesized prefixes: dynamics, fermata, navigation, text expressions ---
    # Can have multiple: (^)(FINE)(p)d = fermata + Fine + piano on d
    dyn = None
    nav = None
    has_fermata = False
    while s:
        dm = _DYNAMIC_PREFIX_RE.match(s)
        if not dm:
            break
        value = dm.group(1)
        s = s[dm.end():]
        if value == spec["dynamics"]["fermata"]:
            has_fermata = True
        elif _is_navigation_marker(value):
            nav = value
        elif value in spec["dynamics"]["valid_dynamics"]:
            dyn = value
        elif value in spec["dynamics"]["text_expressions"]:
            dyn = value  # text expressions (cresc, dim, etc.) treated like dynamics
        # else: unknown paren content, ignore

    if not s and (dyn or has_fermata or nav):
        return NoteEvent(is_rest=True, raw=" ", dynamic=dyn, fermata=has_fermata, navigation=nav), s

    # --- chord: <d.m.s> ---
    if s and s[0] == spec["chords"]["open"]:
        close_idx = s.find(spec["chords"]["close"])
        if close_idx > 0:
            chord_str = s[1:close_idx]
            s = s[close_idx + 1:]
            chord_parts = chord_str.split(".")
            chord_notes = []
            for cp in chord_parts:
                cp = cp.strip()
                if not cp:
                    continue
                cn, _ = _parse_single_token(cp)
                if cn and not cn.is_rest and not cn.is_hold:
                    chord_notes.append(cn)
            if chord_notes:
                first = chord_notes[0]
                return NoteEvent(
                    solfa=first.solfa, semitone=first.semitone,
                    octave_shift=first.octave_shift,
                    is_chromatic_sharp=first.is_chromatic_sharp,
                    is_chromatic_flat=first.is_chromatic_flat,
                    raw=f"<{chord_str}>",
                    dynamic=dyn, fermata=has_fermata, navigation=nav,
                    chord_notes=chord_notes,
                ), s

    # --- melisma prefix ---
    is_melisma = False
    if s and s.startswith(spec["staccato"]["melisma_prefix"]):
        is_melisma = True
        s = s[1:]
        if not s:
            return None, s

    if not s:
        return None, s

    # --- hold ---
    if s[0] == spec["rhythm"]["hold"]:
        return NoteEvent(is_hold=True, raw="-", dynamic=dyn, fermata=has_fermata, navigation=nav), s[1:]

    # --- rest (*) ---
    if s.startswith(spec["rhythm"]["rest_explicit"]):
        return NoteEvent(is_rest=True, raw="*", dynamic=dyn, fermata=has_fermata, navigation=nav), s[1:]

    # --- solfa note (longest match) ---
    matched_solfa = None
    for tok in spec["notes"]["tokens_sorted"]:
        if s.startswith(tok):
            matched_solfa = tok
            break
    if matched_solfa is None:
        if dyn or has_fermata or nav:
            return NoteEvent(is_rest=True, raw=" ", dynamic=dyn, fermata=has_fermata, navigation=nav), s
        return None, s

    s = s[len(matched_solfa):]
    semitone = spec["notes"]["all_notes"][matched_solfa]
    is_sharp = matched_solfa in spec["notes"]["chromatic_sharp"]
    is_flat = matched_solfa in spec["notes"]["chromatic_flat"]

    # --- octave modifiers ---
    octave_shift = 0
    while s and s[0] == spec["octave"]["up_char"]:
        octave_shift += 1
        s = s[1:]
    while s and s[0] == spec["octave"]["down_char"]:
        octave_shift -= 1
        s = s[1:]

    evt = NoteEvent(
        solfa=matched_solfa, semitone=semitone, octave_shift=octave_shift,
        is_melisma=is_melisma,
        is_chromatic_sharp=is_sharp, is_chromatic_flat=is_flat,
        raw=matched_solfa + spec["octave"]["up_char"] * max(0, octave_shift)
                         + spec["octave"]["down_char"] * max(0, -octave_shift),
        dynamic=dyn, fermata=has_fermata, navigation=nav,
    )
    return evt, s


_CHORD_DOT_PLACEHOLDER = "\x00"  # temp replacement for dots inside < >


def _protect_chord_dots(s: str) -> str:
    """Replace dots inside <> with placeholder so they aren't split as sub-beats."""
    result = []
    inside = False
    for ch in s:
        if ch == spec["chords"]["open"]:
            inside = True
        elif ch == spec["chords"]["close"]:
            inside = False
        if ch == spec["rhythm"]["subbeat_separator"] and inside:
            result.append(_CHORD_DOT_PLACEHOLDER)
        else:
            result.append(ch)
    return "".join(result)


def _restore_chord_dots(s: str) -> str:
    """Restore placeholder back to dots."""
    return s.replace(_CHORD_DOT_PLACEHOLDER, spec["rhythm"]["subbeat_separator"])


def parse_beat_tokens(beat_str: str) -> list[NoteEvent]:
    """Parse a beat string (between : separators) into NoteEvents."""
    beat_str = beat_str.strip()

    if not beat_str:
        return [NoteEvent(is_rest=True, raw=" ")]

    # Protect dots inside chord brackets <d.m.s> from being split
    beat_str = _protect_chord_dots(beat_str)

    groups = beat_str.split(spec["rhythm"]["subbeat_separator"])
    events: list[NoteEvent] = []
    has_multiple_groups = len(groups) > 1

    for group in groups:
        g = _restore_chord_dots(group.strip())
        if not g:
            # Empty group: if part of a sub-beat split (e.g. ".s" → ["","s"]),
            # produce a rest so it takes its share of the beat duration.
            if has_multiple_groups:
                events.append(NoteEvent(is_rest=True, raw=" "))
            continue

        # Leading comma = staccato marker (not octave down)
        is_staccato = False
        if g.startswith(spec["staccato"]["prefix"]):
            is_staccato = True
            g = g[1:]  # strip the leading comma

        while g:
            evt, g = _parse_single_token(g)
            if evt is None:
                g = g[1:] if g else ""
            else:
                if is_staccato:
                    evt.is_staccato = True
                    is_staccato = False  # only first event in group
                events.append(evt)

    if not events:
        return [NoteEvent(is_rest=True, raw=" ")]
    return events


# ──────────────────────────────────────────────────────────────────────
#  MEASURE / VOICE LINE PARSING
# ──────────────────────────────────────────────────────────────────────

# Build voice label regex from config
_label_alts = "|".join(re.escape(lbl) for lbl in sorted(spec["voices"]["voice_config"].keys(), key=len, reverse=True))
_VOICE_LABEL_RE = re.compile(rf'^({_label_alts}|[SATB]\d+)(?=\s|\t|\|)')


def _extract_voice_label(line: str) -> tuple[str | None, str]:
    """Strip a leading voice label from a note line."""
    stripped = line.strip()
    m = _VOICE_LABEL_RE.match(stripped)
    if m:
        return m.group(1), stripped[m.end():].strip()
    return None, stripped


def _split_measures(raw: str) -> list[str]:
    """Split a voice's bar content into measure strings."""
    raw = raw.strip().strip("|")
    raw = raw.replace("||", "|")
    return [m for m in raw.split("|")]


def _detect_modulation(beat_str: str) -> tuple[str | None, str, str | None]:
    """
    Check for a modulation marker like r/s inside a beat.
    The right side token is both the modulation target AND the first note
    to play in the new key.

    Before the modulation there can be parenthesized prefixes (dynamics,
    navigation, fermata, key change).  Only the key change is extracted here;
    the rest are left for _parse_single_token to handle.

    Format: [(expr)]... [(KEY)]old_note/new_note [remaining_notes]
    Example: "(f)(CODA)(Ab)r/s,.t,"
             → key_change="Ab", mod="r/s,", remaining="(f)(CODA)s,.t,"

    Returns: (modulation_str, remaining_beat, key_change)
    """
    if spec["modulation"]["separator"] not in beat_str:
        return None, beat_str, None

    # Skip over all parenthesized prefixes to find the modulation slash.
    # Collect non-key parens to re-prepend them to the remaining beat.
    key_change = None
    prefix_parens = []  # non-key parens to preserve
    work_str = beat_str.strip()
    while work_str.startswith('('):
        close_idx = work_str.find(')')
        if close_idx < 0:
            break
        candidate = work_str[1:close_idx]
        rest_after = work_str[close_idx + 1:]
        if candidate in spec["keys"]["valid_keys"] and key_change is None:
            key_change = candidate
        else:
            prefix_parens.append(f"({candidate})")
        work_str = rest_after

    if spec["modulation"]["separator"] not in work_str:
        return None, beat_str, None

    slash_idx = work_str.index(spec["modulation"]["separator"])
    left_str = work_str[:slash_idx].strip()
    right_str = work_str[slash_idx + 1:]

    # Validate left side: strip octave modifiers (' ,) then check for solfa token
    left_bare = left_str.rstrip(spec["octave"]["up_char"] + spec["octave"]["down_char"])
    left_valid = any(left_bare == t for t in spec["notes"]["tokens_sorted"])
    if not left_valid:
        return None, beat_str, None

    # Parse the right side: consume solfa token + octave modifiers
    right_stripped = right_str.lstrip()
    matched_right = None
    for tok in spec["notes"]["tokens_sorted"]:
        if right_stripped.startswith(tok):
            matched_right = tok
            break
    if matched_right is None:
        return None, beat_str, None

    # Consume octave modifiers (they're part of the modulation target,
    # e.g. s, means "sol octave down" - pitch class is the same but
    # we consume to avoid leaving a dangling comma)
    pos = len(matched_right)
    while pos < len(right_stripped) and right_stripped[pos] in (spec["octave"]["up_char"], spec["octave"]["down_char"]):
        pos += 1

    right_token = right_stripped[:pos]
    remaining = right_stripped  # right token is also the first note to play

    mod_str = f"{left_str}/{right_token}"
    # Re-prepend non-key parens (dynamics, nav, fermata) so _parse_single_token handles them
    remaining = "".join(prefix_parens) + remaining
    return mod_str, remaining, key_change


def parse_voice_line(line: str) -> tuple[str | None, list]:
    """Parse one note line into (voice_label, list_of_measures)."""
    label, content = _extract_voice_label(line)
    raw_measures = _split_measures(content)

    measures = []
    for mstr in raw_measures:
        mstr = mstr.strip()
        if not mstr:
            continue

        # Soft barline is purely visual - treat as beat separator
        mstr = mstr.replace(spec["rhythm"]["soft_barline"]["char"], spec["rhythm"]["beat_separator"])
        beats_raw = mstr.split(spec["rhythm"]["beat_separator"])
        beats = []
        modulations = []
        key_changes = []
        for b in beats_raw:
            mod, b_clean, key_change = _detect_modulation(b)
            if mod:
                modulations.append(mod)
                if key_change:
                    key_changes.append(key_change)
            # Parse remaining content as notes (even after a modulation)
            if b_clean.strip():
                tokens = parse_beat_tokens(b_clean)
                beats.append(tokens)
            else:
                # Empty beat (or modulation consumed all content) = rest
                beats.append(parse_beat_tokens(""))

        # Extract navigation markers to measure level.
        # Navigation is always applied to the measure (barline + text),
        # never creates extra events.
        # Correct usage: (DC)f  → nav is prefix on the note
        #                (DC)   → nav alone as a beat (beat is dropped)
        measure_navs = []
        cleaned_beats = []
        for beat_events in beats:
            # Check if this beat is just a nav-only rest: |(DC)|
            if (len(beat_events) == 1
                    and beat_events[0].is_rest
                    and beat_events[0].navigation
                    and not beat_events[0].dynamic
                    and not beat_events[0].fermata):
                measure_navs.append(beat_events[0].navigation)
                # Drop this beat entirely - it's not real music
                continue
            # Extract nav from note events: |(DC)f|
            for evt in beat_events:
                if evt.navigation:
                    measure_navs.append(evt.navigation)
                    evt.navigation = None
            cleaned_beats.append(beat_events)

        measures.append({
            "beats": cleaned_beats,
            "modulations": modulations,
            "key_changes": key_changes,
            "navigation": measure_navs if measure_navs else None,
        })

    return label, measures


# ──────────────────────────────────────────────────────────────────────
#  LYRICS PARSING
# ──────────────────────────────────────────────────────────────────────

def _extract_voice_labels(s: str) -> list[str]:
    """Greedily extract concatenated voice labels from a string.
    E.g. 'SATB' → ['S','A','T','B'], 'S1S2T' → ['S1','S2','T']"""
    labels = []
    pos = 0
    while pos < len(s):
        matched = None
        for lbl in sorted(spec["voices"]["voice_config"].keys(), key=len, reverse=True):  # sorted longest first
            if s[pos:].startswith(lbl):
                matched = lbl
                break
        if matched:
            labels.append(matched)
            pos += len(matched)
        else:
            break  # not a voice label, stop
    # Only valid if we consumed the entire string
    if pos == len(s) and labels:
        return labels
    return []


def parse_lyrics_line(line: str) -> tuple[list[str] | None, str | int, list]:
    """
    Parse a lyrics line into (voices, verse_id, syllables).

    Returns:
        voices: list of voice labels, or None for all voices
        verse_id: int (verse number) or "R" (refrain)
        syllables: list of (text, syllabic) tuples

    Prefix format:
        (none)          → verse 1, all voices
        R               → refrain, all voices
        1               → verse 1, all voices
        1SA             → verse 1, S and A
        1S1S2           → verse 1, S1 S2
        RSA             → refrain, S and A
        RTB             → refrain, T and B
    """
    stripped = line.strip()
    voices = None
    verse_id: str | int = 1

    # Try to match prefix before the first space
    space_idx = stripped.find(" ")
    if space_idx > 0:
        prefix = stripped[:space_idx]
        rest = stripped[space_idx + 1:].strip()
        parsed = False

        # Check for verse+voices (e.g. "1SA", "2B", "RS1S2") or verse/refrain only
        vpart = ""
        vlist = ""
        if prefix.startswith("R"):
            vpart = "R"
            vlist = prefix[1:]
        elif prefix[0].isdigit():
            i = 0
            while i < len(prefix) and prefix[i].isdigit():
                i += 1
            vpart = prefix[:i]
            vlist = prefix[i:]

        if vpart:
            if vpart == "R":
                verse_id = "R"
            else:
                verse_id = int(vpart)

            if vlist:
                labels = _extract_voice_labels(vlist)
                if labels:
                    voices = labels
            stripped = rest
            parsed = True

        # Check for voice-only prefix (e.g. "S", "SA", "SAT", "S1S2")
        if not parsed:
            labels = _extract_voice_labels(prefix)
            if labels:
                voices = labels
                stripped = rest
                parsed = True

        # If prefix wasn't recognized, treat entire line as lyrics (stripped unchanged)

    # Split into syllables using MusicXML syllabic types for hyphen rendering
    # "A-ma-zing" → begin/middle/end, "ni-" (trailing) → begin only (no extra syllable)
    syllables = []
    words = stripped.split()
    for word in words:
        parts = [p for p in word.split(spec["lyrics"]["hyphen"]) if p]
        if not parts:
            continue
        for j, part in enumerate(parts):
            part = part.replace(spec["lyrics"]["join"], " ")
            has_next = j < len(parts) - 1
            had_prev = j > 0
            trailing_hyphen = word.endswith(spec["lyrics"]["hyphen"]) and not has_next
            if len(parts) == 1 and not trailing_hyphen:
                syllables.append((part, "single"))
            elif not had_prev and has_next:
                syllables.append((part, "begin"))
            elif had_prev and has_next:
                syllables.append((part, "middle"))
            elif had_prev and not has_next and not trailing_hyphen:
                syllables.append((part, "end"))
            else:
                # trailing hyphen (e.g. "ni-"): begin with no closing end
                syllables.append((part, "begin"))

    return voices, verse_id, syllables


# ──────────────────────────────────────────────────────────────────────
#  FILE PARSING  (top-level)
# ──────────────────────────────────────────────────────────────────────

def _is_note_line(line: str) -> bool:
    """Heuristic: a note line contains barlines |."""
    return "|" in line


def _extract_notes_section(lines: list[str]) -> tuple[list[str], str]:
    """Split lines into music lines and plain-text notes content.
    The [notes] marker (alone on a line) starts the notes section; everything
    after it (to EOF) is notes content."""
    marker = spec["notes_section"]["marker"]
    for i, line in enumerate(lines):
        if line.strip() == marker:
            notes_content = "\n".join(lines[i + 1:]).strip()
            return lines[:i], notes_content
    return lines, ""


def _make_rest_measure(beats_per_measure: int) -> dict:
    """Return a measure dict filled with rests (used for voice padding)."""
    return {
        "beats": [[NoteEvent(is_rest=True, raw=" ")] for _ in range(beats_per_measure)],
        "modulations": [],
        "key_changes": [],
        "navigation": None,
    }


def parse_file(filepath: str) -> dict:
    """
    Parse a tonic solfa .txt file.
    Returns dict with keys: properties, voices, lyrics, notes.
    """
    text = Path(filepath).read_text(encoding="utf-8")
    lines = text.splitlines()

    lines, notes_content = _extract_notes_section(lines)
    props, remaining = parse_header(lines)

    # Beats per measure — needed to build rest-fill measures for absent voices.
    time_sig = props.get("timesig", spec["defaults"]["timesig"])
    beats_per_measure = int(time_sig.split("/")[0])

    # ── Group remaining lines into blocks (separated by blank lines) ──
    raw_blocks: list[list[str]] = []
    current: list[str] = []
    for line in remaining:
        stripped = line.strip()
        if not stripped or stripped.startswith("//"):
            if current:
                raw_blocks.append(current)
                current = []
        else:
            current.append(stripped)
    if current:
        raw_blocks.append(current)

    voice_data: dict[str, list] = {}   # label → [measure, ...]  (all blocks, temporally ordered)
    lyrics_data: dict[str, dict] = {}  # label → {verse_id: [syllables]}
    default_voice_order = list(spec["voices"]["default_order"])

    # Total measures accumulated so far across all processed blocks
    total_measures_so_far = 0

    for block_lines in raw_blocks:
        note_lines = [l for l in block_lines if _is_note_line(l)]
        lyric_lines = [l for l in block_lines if not _is_note_line(l)]

        if not note_lines:
            continue

        # ── Parse this block's voices ──
        block_voices: dict[str, list] = {}
        for i, line in enumerate(note_lines):
            label, measures = parse_voice_line(line)
            if label is None:
                label = default_voice_order[i] if i < len(default_voice_order) else f"V{i + 1}"
            block_voices[label] = measures

        block_measure_count = max(len(m) for m in block_voices.values())

        # ── Merge into voice_data with correct temporal alignment ──
        all_labels = set(voice_data.keys()) | set(block_voices.keys())
        for label in all_labels:
            if label not in voice_data:
                # Voice is new: back-fill with rests for all prior blocks
                voice_data[label] = [_make_rest_measure(beats_per_measure)
                                     for _ in range(total_measures_so_far)]

            if label in block_voices:
                voice_data[label].extend(block_voices[label])
            else:
                # Voice absent in this block: fill with rest measures
                for _ in range(block_measure_count):
                    voice_data[label].append(_make_rest_measure(beats_per_measure))

        total_measures_so_far += block_measure_count

        # ── Parse lyrics, targeting only this block's active voices ──
        block_labels = list(block_voices.keys())
        for lyric_line in lyric_lines:
            voices_prefix, verse_id, syllables = parse_lyrics_line(lyric_line)
            targets = voices_prefix if voices_prefix is not None else block_labels

            for target in targets:
                if target not in lyrics_data:
                    lyrics_data[target] = {}
                if verse_id not in lyrics_data[target]:
                    lyrics_data[target][verse_id] = []
                lyrics_data[target][verse_id].extend(syllables)

    return {
        "properties": props,
        "voices": voice_data,
        "lyrics": lyrics_data,
        "notes": notes_content,
    }
