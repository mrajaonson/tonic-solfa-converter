"""Build a music21 Score from parsed tonic solfa data."""

from datetime import date
from music21 import (
    stream, note, pitch, key, meter, tempo, clef, bar,
    duration, metadata, tie, repeat, expressions, dynamics, chord,
    articulations,
)
import re
from ..shared import spec
from music21 import instrument as m21instrument
from .solfa_pitch import solfa_to_pitch, resolve_modulation

_NUMBERED_NAV_RE = re.compile(
    r'^(DS|DSF|DSC|SEGNO|CODA|TC|DC|DCF|DCC|FINE)(\d+)$'
)


def _nav_base(nav_str: str) -> str:
    """Return the base marker name, stripping any trailing number."""
    m = _NUMBERED_NAV_RE.match(nav_str)
    return m.group(1) if m else nav_str


def _nav_number(nav_str: str) -> str | None:
    """Return the trailing number of a numbered marker, or None."""
    m = _NUMBERED_NAV_RE.match(nav_str)
    return m.group(2) if m else None


def _nav_display(nav_str: str) -> str:
    """Return display text for a navigation marker (plain or numbered)."""
    m = _NUMBERED_NAV_RE.match(nav_str)
    if m:
        base, num = m.group(1), m.group(2)
        base_display = spec["navigation"]["markers"].get(base, base)
        return f"{base_display} {num}"
    return spec["navigation"]["markers"].get(nav_str, nav_str)

_INSTRUMENT_CLASS_MAP = {
    "Soprano": m21instrument.Soprano,
    "Alto":    m21instrument.Alto,
    "Tenor":   m21instrument.Tenor,
    "Bass":    m21instrument.Bass,
    "Piano":   m21instrument.Piano,
}

def _build_voice_config() -> dict:
    result = {}
    for label, cfg in spec["voices"]["voice_config"].items():
        result[label] = {
            "name":          cfg["name"],
            "instrument":    _INSTRUMENT_CLASS_MAP.get(cfg["instrument_class"]),
            "clef":          cfg["clef"],
            "octave_offset": cfg["octave_offset"],
            "range":         (cfg["range_low"], cfg["range_high"]),
        }
    return result

_VOICE_CONFIG = _build_voice_config()
from .duration import assign_durations, consolidate_holds


# ──────────────────────────────────────────────────────────────────────
#  VOICE HELPERS
# ──────────────────────────────────────────────────────────────────────

def _get_voice_base(voice_label: str) -> str:
    """
    Extract base config key for a voice label.
    'S1' → 'S', 'T2' → 'T', 'PR' → 'PR', 'PL' → 'PL'.
    """
    # Direct match (handles PR, PL, OR, OL, OP, S, A, T, B)
    if voice_label in _VOICE_CONFIG:
        return voice_label
    # Numbered voice: S1 → S, T2 → T
    if voice_label and voice_label[0] in spec["voices"]["base_labels"]:
        return voice_label[0]
    return voice_label


def _get_voice_config(voice_label: str) -> dict:
    """Get voice config entry, inheriting from base for numbered voices."""
    base = _get_voice_base(voice_label)
    return _VOICE_CONFIG.get(base, _VOICE_CONFIG["S"])


def _get_voice_full_name(voice_label: str) -> str:
    """'S' → 'Soprano', 'S1' → 'Soprano 1', 'PR' → 'Piano (R)'."""
    cfg = _get_voice_config(voice_label)
    base_name = cfg["name"]
    base = _get_voice_base(voice_label)
    suffix = voice_label[len(base):]
    return f"{base_name} {suffix}" if suffix else base_name


def _get_clef(voice_label: str):
    """Return a music21 Clef object for the given voice."""
    name = _get_voice_config(voice_label)["clef"]
    clef_map = {
        "treble": clef.TrebleClef,
        "treble8vb": clef.Treble8vbClef,
        "bass": clef.BassClef,
    }
    return clef_map.get(name, clef.TrebleClef)()


def _get_instrument(voice_label: str):
    """Return a music21 Instrument instance for the given voice."""
    return _get_voice_config(voice_label)["instrument"]()


def _get_octave_offset(voice_label: str) -> int:
    """Return octave offset for the voice (e.g. -1 for Tenor/Bass)."""
    return _get_voice_config(voice_label)["octave_offset"]


# ──────────────────────────────────────────────────────────────────────
#  NOTE / REST / DYNAMICS HELPERS
# ──────────────────────────────────────────────────────────────────────

def _make_note(p: pitch.Pitch, ql: float) -> note.Note:
    """Create a music21 Note with the given pitch and quarter length."""
    n = note.Note(p)
    n.duration = duration.Duration(quarterLength=ql)
    return n


def _make_rest(ql: float) -> note.Rest:
    """Create a music21 Rest with the given quarter length."""
    r = note.Rest()
    r.duration = duration.Duration(quarterLength=ql)
    return r


def _make_chord(pitches: list, ql: float) -> chord.Chord:
    """Create a music21 Chord with the given pitches and quarter length."""
    c = chord.Chord(pitches)
    c.duration = duration.Duration(quarterLength=ql)
    return c


def _apply_dynamic(measure: stream.Measure, dyn_str: str):
    """Append a dynamic, hairpin, or text expression to a measure (placed above staff)."""
    if dyn_str in spec["dynamics"]["valid_dynamics"]:
        d = dynamics.Dynamic(dyn_str)
        d.placement = "above"
        measure.append(d)
    elif dyn_str == spec["dynamics"]["hairpins"]["crescendo"]:
        # Crescendo hairpin needs start+end notes (spanner) which is complex.
        # Use italic text "cresc." which MuseScore reads reliably.
        te = expressions.TextExpression("cresc.")
        te.style.fontStyle = "italic"
        te.placement = "above"
        measure.append(te)
    elif dyn_str == spec["dynamics"]["hairpins"]["diminuendo"]:
        te = expressions.TextExpression("dim.")
        te.style.fontStyle = "italic"
        te.placement = "above"
        measure.append(te)
    elif dyn_str in spec["dynamics"]["text_expressions"]:
        te = expressions.TextExpression(spec["dynamics"]["text_expressions"][dyn_str])
        te.style.fontStyle = "italic"
        te.placement = "above"
        measure.append(te)
    else:
        te = expressions.TextExpression(dyn_str)
        te.style.fontStyle = "italic"
        te.placement = "above"
        measure.append(te)


def _apply_navigation(measure: stream.Measure, nav_str: str):
    """Append navigation marker above staff + barline (first voice only)."""
    base = _nav_base(nav_str)

    # Segno and Coda signs go at the START of the measure (offset 0)
    num = _nav_number(nav_str)
    if base == "SEGNO":
        text = f"S.{num}" if num else "S."
        te = expressions.TextExpression(text)
        te.placement = "above"
        te.style.fontStyle = "bold"
        te.style.fontSize = 14
        measure.insert(0, te)
        return
    elif base == "CODA":
        text = f"Coda {num}" if num else "Coda"
        te = expressions.TextExpression(text)
        te.placement = "above"
        te.style.fontStyle = "bold"
        te.style.fontSize = 14
        measure.insert(0, te)
        return
    elif base == "TC":
        text = f"To Coda {num}" if num else "To Coda"
        te = expressions.TextExpression(text)
        te.placement = "above"
        te.style.fontStyle = "bold"
        te.style.fontSize = 14
        last_offset = 0
        for el in measure.notesAndRests:
            if el.offset >= last_offset:
                last_offset = el.offset
        measure.insert(last_offset, te)
        return

    # All others go above the last note (left of barline)
    display = _nav_display(nav_str)
    te = expressions.TextExpression(display)
    te.placement = "above"
    te.style.fontStyle = "bold"
    te.style.fontSize = 12
    # Find offset of last note/rest to place text there, not on the barline
    last_offset = 0
    for el in measure.notesAndRests:
        if el.offset >= last_offset:
            last_offset = el.offset
    measure.insert(last_offset, te)
    # DC, DCF, DCC → final barline (not a repeat barline - avoids music21
    # collapsing multiple backward repeats and dropping the first marker)
    if base in ("DC", "DCF", "DCC"):
        measure.rightBarline = bar.Barline("final")
    # DS, DSF, DSC → double barline (no dots)
    elif base in ("DS", "DSF", "DSC"):
        measure.rightBarline = bar.Barline("double")
    # FINE → final barline (thin + thick)
    elif base == "FINE":
        measure.rightBarline = bar.Barline("final")


def _apply_navigation_barline_only(measure: stream.Measure, nav_str: str):
    """Apply only the barline (no text) for non-first voices."""
    base = _nav_base(nav_str)
    if base in ("DC", "DCF", "DCC"):
        measure.rightBarline = bar.Barline("final")
    elif base in ("DS", "DSF", "DSC"):
        measure.rightBarline = bar.Barline("double")
    elif base == "FINE":
        measure.rightBarline = bar.Barline("final")


# ──────────────────────────────────────────────────────────────────────
#  SCORE BUILDING
# ──────────────────────────────────────────────────────────────────────

def build_score(parsed: dict) -> stream.Score:
    """Convert fully parsed data into a music21 Score."""
    props = parsed["properties"]
    voices = parsed["voices"]
    lyrics_data = parsed["lyrics"]

    score = stream.Score()

    # ── Metadata ──
    md = metadata.Metadata()
    md.title = props.get("title", spec["defaults"]["title"])
    md.composer = props.get("composer", spec["defaults"]["composer"])
    if props.get("author"):
        md.lyricist = props["author"]
    md.date = date.today().isoformat()
    md.copyright = f"Generated on {date.today().strftime('%Y-%m-%d')}"
    if parsed.get("notes"):
        md.miscellaneous = {"notes": parsed["notes"]}
    score.metadata = md

    time_sig_str = props.get("timesig", spec["defaults"]["timesig"])
    current_key = props.get("key", spec["defaults"]["key"])
    base_octave = props.get("octave", spec["defaults"]["octave"])
    bpm = props.get("tempo", spec["defaults"]["tempo"])

    ts_num, ts_den = map(int, time_sig_str.split("/"))
    measure_ql = ts_num * (4.0 / ts_den)

    # ── Pad voices to equal length ──
    # If some voices have fewer measures (partial blocks), pad with
    # whole-measure rests so all voices have the same total measures.
    if voices:
        from .models import NoteEvent
        max_measures = max(len(m) for m in voices.values())
        for voice_label in voices:
            while len(voices[voice_label]) < max_measures:
                # Create a measure with one rest beat per time sig beat
                rest_beats = [[NoteEvent(is_rest=True, raw=" ")] for _ in range(ts_num)]
                voices[voice_label].append({
                    "beats": rest_beats,
                    "modulations": [],
                })

    is_first_part = True
    nav_markers: dict[int, str] = {}  # measure_index → nav_str (collected from first voice)
    key_changes: dict[int, str] = {}  # measure_index → new_key (collected from first voice)

    # ── Build each voice part ──
    for voice_label, measures_raw in voices.items():
        part = stream.Part()
        part.id = voice_label
        part.partName = _get_voice_full_name(voice_label)

        part.insert(0, _get_instrument(voice_label))

        # Fresh objects per part (music21 objects can only belong to one stream)
        part.append(_get_clef(voice_label))
        part.append(key.Key(current_key))
        part.append(meter.TimeSignature(time_sig_str))

        voice_octave = base_octave + _get_octave_offset(voice_label)

        timed = assign_durations(measures_raw, time_sig_str)
        timed = consolidate_holds(timed)

        # Lyrics cursors - attach all lyrics, cursor advances on singable notes only
        voice_lyrics = lyrics_data.get(voice_label, {})
        sorted_verses = sorted(
            ((vid, syls) for vid, syls in voice_lyrics.items()),
            key=lambda x: (isinstance(x[0], str), x[0])
        )
        lyrics_cursors: dict[int, tuple[list, int]] = {}
        for lyric_num, (vid, syls) in enumerate(sorted_verses, start=1):
            lyrics_cursors[lyric_num] = (syls, 0)

        active_key = current_key
        prev_note_obj = None
        needs_tie_start = False

        for m_idx, events in enumerate(timed):
            m21_measure = stream.Measure(number=m_idx + 1)

            # Tempo mark: only in measure 1 of the first part
            if m_idx == 0 and is_first_part:
                beat_dur = duration.Duration(quarterLength=4.0 / ts_den)
                m21_measure.insert(0, tempo.MetronomeMark(
                    referent=beat_dur, number=bpm))

            # Key changes: each voice resolves its own modulations.
            # First voice also stores key changes for voices without modulations.
            modulations = measures_raw[m_idx].get("modulations", []) if m_idx < len(measures_raw) else []

            if modulations:
                for mod in modulations:
                    new_key = resolve_modulation(mod, active_key, base_octave)
                    if new_key != active_key:
                        active_key = new_key
                        m21_measure.append(key.Key(active_key))
                        if is_first_part:
                            key_changes[m_idx] = active_key
            elif m_idx in key_changes:
                # No modulation in this voice but first voice changed key here
                if active_key != key_changes[m_idx]:
                    active_key = key_changes[m_idx]
                    m21_measure.append(key.Key(active_key))

            first_event_in_measure = True

            # Navigation: read from measure level (parser extracted it from events)
            measure_nav = measures_raw[m_idx].get("navigation") if m_idx < len(measures_raw) else None

            # Whole-measure rest detection:
            # all events are rests, OR no events at all
            all_rests = all(te.event.is_rest for te in events) if events else True
            if all_rests:
                r = note.Rest()
                r.duration = duration.Duration(quarterLength=measure_ql)
                r.fullMeasure = True
                for te in events:
                    if te.event.dynamic:
                        _apply_dynamic(m21_measure, te.event.dynamic)
                m21_measure.append(r)
                prev_note_obj = None
            else:
                for te in events:
                    evt = te.event
                    ql = te.quarter_length

                    if evt.dynamic:
                        _apply_dynamic(m21_measure, evt.dynamic)

                    if evt.is_rest:
                        r = _make_rest(ql)
                        if evt.fermata:
                            r.expressions.append(expressions.Fermata())
                        m21_measure.append(r)
                        # Rests only skip * markers in lyrics
                        for lyric_num, (syls, cursor) in list(lyrics_cursors.items()):
                            if cursor < len(syls) and syls[cursor][0] == spec["lyrics"]["rest_skip"]:
                                lyrics_cursors[lyric_num] = (syls, cursor + 1)
                        prev_note_obj = None
                        needs_tie_start = False
                    elif evt.is_hold:
                        if prev_note_obj is not None and first_event_in_measure:
                            # Create tied continuation - note or chord
                            if isinstance(prev_note_obj, chord.Chord):
                                tied_n = _make_chord(list(prev_note_obj.pitches), ql)
                            else:
                                tied_n = _make_note(prev_note_obj.pitch, ql)
                            prev_note_obj.tie = tie.Tie("start")
                            tied_n.tie = tie.Tie("stop")
                            if evt.fermata:
                                tied_n.expressions.append(expressions.Fermata())
                            m21_measure.append(tied_n)
                            prev_note_obj = tied_n
                        else:
                            m21_measure.append(_make_rest(ql))
                            prev_note_obj = None
                    else:
                        # Normal note or chord
                        if evt.is_chord:
                            pitches = [solfa_to_pitch(cn, active_key, voice_octave)
                                       for cn in evt.chord_notes]
                            n = _make_chord(pitches, ql)
                        else:
                            p = solfa_to_pitch(evt, active_key, voice_octave)
                            n = _make_note(p, ql)

                        if evt.fermata:
                            n.expressions.append(expressions.Fermata())

                        if evt.is_staccato:
                            n.articulations.append(articulations.Staccato())

                        if not evt.is_melisma:
                            mute_delim = spec["lyrics"]["mute_open"]
                            for lyric_num, (syls, cursor) in list(lyrics_cursors.items()):
                                if cursor < len(syls):
                                    syl_text, syl_type = syls[cursor]
                                    if syl_text == spec["lyrics"]["rest_skip"]:
                                        # * = skip, advance cursor but don't add lyric
                                        lyrics_cursors[lyric_num] = (syls, cursor + 1)
                                    else:
                                        # Strip mute delimiters (purely visual in PDF)
                                        syl_text = syl_text.replace(mute_delim, "")
                                        lyric_obj = note.Lyric(
                                            text=syl_text,
                                            number=lyric_num,
                                            syllabic=syl_type,
                                        )
                                        n.lyrics.append(lyric_obj)
                                        lyrics_cursors[lyric_num] = (syls, cursor + 1)

                        m21_measure.append(n)
                        prev_note_obj = n

                    first_event_in_measure = False

            # Apply navigation after all notes/rests are in the measure
            if measure_nav and is_first_part:
                nav_list = measure_nav if isinstance(measure_nav, list) else [measure_nav]
                nav_markers[m_idx] = nav_list
                for nav in nav_list:
                    _apply_navigation(m21_measure, nav)
            elif not is_first_part and m_idx in nav_markers:
                for nav in nav_markers[m_idx]:
                    _apply_navigation_barline_only(m21_measure, nav)

            part.append(m21_measure)

        if part.getElementsByClass(stream.Measure):
            last_meas = part.getElementsByClass(stream.Measure)[-1]
            if not isinstance(last_meas.rightBarline, bar.Repeat):
                last_meas.rightBarline = bar.Barline("final")

        score.append(part)
        is_first_part = False

    return score
