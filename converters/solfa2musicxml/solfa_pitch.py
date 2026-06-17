"""Pitch conversion and key modulation resolution."""

from music21 import pitch, key
from .models import NoteEvent
from ..shared import spec


# Map key name → MIDI note number for that key at octave 4
_KEY_NAME_TO_MIDI_BASE = {}
for _kn in spec["keys"]["valid_keys"]:
    _p = pitch.Pitch(_kn + "4")
    _KEY_NAME_TO_MIDI_BASE[_kn] = _p.midi


def solfa_to_pitch(evt: NoteEvent, current_key: str, base_octave: int) -> pitch.Pitch:
    """Convert a NoteEvent to a music21 Pitch, respecting key and octave."""
    tonic_midi = _KEY_NAME_TO_MIDI_BASE.get(current_key, 60)
    tonic_midi += (base_octave - 4) * 12

    midi_val = tonic_midi + evt.semitone + (evt.octave_shift * 12)
    p = pitch.Pitch(midi=midi_val)

    # Fix enharmonic spelling based on key
    k = key.Key(current_key)
    scale_pitches = [sp.name for sp in k.getScale("major").getPitches()]
    degree_map = {0: 0, 2: 1, 4: 2, 5: 3, 7: 4, 9: 5, 11: 6}

    if not evt.is_chromatic_sharp and not evt.is_chromatic_flat:
        if evt.semitone in degree_map:
            idx = degree_map[evt.semitone]
            if idx < len(scale_pitches):
                p.name = scale_pitches[idx]
                # music21 may shift octave after name change - fix it
                while abs(p.midi - midi_val) > 6:
                    if p.midi > midi_val:
                        p.octave -= 1
                    else:
                        p.octave += 1

    elif evt.is_chromatic_sharp:
        base_solfa = evt.solfa[0]
        base_semi = spec["notes"]["solfa_to_semitone"].get(base_solfa, 0)
        if base_semi in degree_map:
            idx = degree_map[base_semi]
            if idx < len(scale_pitches):
                base_name = scale_pitches[idx]
                raised = pitch.Pitch(base_name)
                accidental_count = raised.accidental.alter if raised.accidental else 0
                p.name = base_name
                p.accidental = pitch.Accidental(accidental_count + 1)
                while abs(p.midi - midi_val) > 6:
                    if p.midi > midi_val:
                        p.octave -= 1
                    else:
                        p.octave += 1

    elif evt.is_chromatic_flat:
        _flat_base = {"ra": "r", "ma": "m", "sa": "s", "la": "l", "ta": "t"}
        base_solfa = _flat_base.get(evt.solfa, evt.solfa[0])
        base_semi = spec["notes"]["solfa_to_semitone"].get(base_solfa, 0)
        if base_semi in degree_map:
            idx = degree_map[base_semi]
            if idx < len(scale_pitches):
                base_name = scale_pitches[idx]
                p.name = base_name
                accidental_count = p.accidental.alter if p.accidental else 0
                p.accidental = pitch.Accidental(accidental_count - 1)
                while abs(p.midi - midi_val) > 6:
                    if p.midi > midi_val:
                        p.octave -= 1
                    else:
                        p.octave += 1

    return p


def resolve_modulation(mod_str: str, current_key: str, base_octave: int) -> str:
    """
    Given a modulation string like 'r/s,' or 'l,/r,', compute the new key.
    Both old and new notes can have octave modifiers (' ,), which don't
    affect the key calculation (only pitch class matters).
    Imports _parse_single_token locally to avoid circular imports.
    """
    from .solfa_parser import _parse_single_token

    parts = mod_str.split(spec["modulation"]["separator"])
    old_solfa_str = parts[0].strip()
    new_solfa_str = parts[1].strip()

    old_evt, _ = _parse_single_token(old_solfa_str)
    new_evt, _ = _parse_single_token(new_solfa_str)
    if old_evt is None or new_evt is None:
        return current_key

    old_pitch = solfa_to_pitch(old_evt, current_key, base_octave)

    new_tonic_midi = old_pitch.midi - new_evt.semitone
    while new_tonic_midi < 60:
        new_tonic_midi += 12
    while new_tonic_midi >= 72:
        new_tonic_midi -= 12

    new_tonic = pitch.Pitch(midi=new_tonic_midi)

    # Find matching key, preferring flat/sharp based on current key context.
    # If current key is flat (Db, Ab, etc.), prefer flat enharmonic (Ab over G#).
    # If current key is sharp (D#, G#, etc.), prefer sharp enharmonic.
    current_is_flat = "b" in current_key
    current_is_sharp = "#" in current_key

    candidates = []
    for kn in spec["keys"]["valid_keys"]:
        kp = pitch.Pitch(kn)
        if kp.pitchClass == new_tonic.pitchClass:
            candidates.append(kn)

    if not candidates:
        return current_key

    # Prefer matching accidental style
    for kn in candidates:
        if current_is_flat and "b" in kn:
            return kn
        if current_is_sharp and "#" in kn:
            return kn
        if not current_is_flat and not current_is_sharp and len(kn) == 1:
            return kn

    # Fallback: prefer flats over sharps (more common in choral music)
    for kn in candidates:
        if "b" in kn:
            return kn
    return candidates[0]
