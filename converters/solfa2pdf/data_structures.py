from dataclasses import field
from enum import Enum
from dataclasses import dataclass
from typing import List, Optional, Tuple


class NoteType(Enum):
    NOTE = "note"
    REST = "rest"
    HOLD = "hold"
    CHORD = "chord"
    MODULATION = "modulation"


@dataclass
class Expression:
    """Represents an expression mark (dynamic, fermata, navigation, etc.)"""
    type: str  # "dynamic", "hairpin", "fermata", "navigation", "text"
    value: str


@dataclass
class Note:
    """Represents a single note, rest, hold, or chord"""
    type: NoteType
    solfa: str = ""  # e.g., "d", "r'", "s,"
    octave_modifier: str = ""  # combination of ' and ,
    is_staccato: bool = False
    is_melisma: bool = False  # underscore prefix - don't consume lyric
    expressions: List[Expression] = field(default_factory=list)
    chord_notes: List['Note'] = field(default_factory=list)  # for chords
    modulation_from: str = ""  # for modulation: old note
    modulation_to: str = ""  # for modulation: new note (also played)
    key_change: str = ""  # for key change: new key (e.g., "Ab")
    duration_fraction: float = 1.0  # fraction of beat (1.0 = full beat, 0.5 = half, etc.)

    def display_text(self) -> str:
        """Return the display text for this note"""
        if self.type == NoteType.REST:
            return ""
        elif self.type == NoteType.HOLD:
            return "-"
        elif self.type == NoteType.MODULATION:
            # Don't include old_note here - it will be drawn as superscript separately
            return self.modulation_to
        elif self.type == NoteType.CHORD:
            chord_str = ".".join(n.solfa + n.octave_modifier for n in self.chord_notes)
            return f"<{chord_str}>"
        else:
            # Don't show underscore for melisma - just the note
            # Underline will be drawn separately in PDF renderer
            text = self.solfa + self.octave_modifier
            return text


@dataclass
class Beat:
    """Represents a beat within a measure, possibly subdivided"""
    notes: List[Note] = field(default_factory=list)  # notes in this beat
    is_subdivided: bool = False  # True if beat has a dot separator
    first_half: List[Note] = field(default_factory=list)  # notes before dot
    second_half: List[Note] = field(default_factory=list)  # notes after dot

    def all_notes(self) -> List[Note]:
        """Return all notes in order"""
        if self.is_subdivided:
            return self.first_half + self.second_half
        return self.notes

    def display_text(self) -> str:
        """Return display text for this beat"""
        if self.is_subdivided:
            first_str = "".join(n.display_text() for n in self.first_half)
            second_str = "".join(n.display_text() for n in self.second_half)
            return f"{first_str}.{second_str}"
        else:
            return "".join(n.display_text() for n in self.notes)


@dataclass
class Measure:
    """Represents a measure with beats"""
    beats: List[Beat] = field(default_factory=list)
    number: int = 0
    is_empty: bool = False  # whole-measure rest
    soft_barline_after_beat: int = -1  # beat index after which to draw a thin courtesy barline (-1 = none)
    is_partial: bool = False  # boundary-omitted pickup fragment (fewer beats than the time sig) - rendered narrow
    partial_side: Optional[str] = None  # "leading" or "trailing" when is_partial
    is_continuation: bool = False  # leading partial completing the previous system's trailing partial (shares its number)

    def display_text(self) -> str:
        """Return display text for this measure"""
        if self.is_empty:
            return ":".join([""] * len(self.beats)) if self.beats else ""
        return ":".join(b.display_text() for b in self.beats)


@dataclass
class VoiceLine:
    """Represents a single voice's notation across measures"""
    voice_label: str  # S, A, T, B, S1, S2, etc.
    measures: List[Measure] = field(default_factory=list)


@dataclass
class LyricLine:
    """Represents a line of lyrics"""
    verse: str  # "1", "2", "R", etc.
    voices: List[str]  # ["S", "A", "T", "B"] or subset
    syllables: List[str] = field(default_factory=list)
    display_prefix: str = ""  # What to show before lyrics (e.g., "1S", "B", "")


@dataclass
class Block:
    """A block of notation with voice lines and lyrics"""
    voice_lines: List[VoiceLine] = field(default_factory=list)
    lyric_lines: List[LyricLine] = field(default_factory=list)
    measure_start: int = 1  # starting measure number

@dataclass
class Song:
    """Complete parsed song"""
    title: str = ""
    authors: List[str] = field(default_factory=list)
    composers: List[str] = field(default_factory=list)
    key: str = "C"
    keyheader: str = "Key:"
    tempo: int = 120
    time_sig: Tuple[int, int] = (4, 4)
    meter: str = ""
    octave: int = 4
    comment: str = ""
    copyright: str = ""
    date: str = ""
    transcription: str = ""
    tempomarking: str = ""
    gendate: bool = False
    notes: str = ""
    blocks: List[Block] = field(default_factory=list)
