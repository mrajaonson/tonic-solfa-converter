"""Shared low-level token-matching helpers for tonic solfa parsers.

These are pure functions that match notation primitives (solfa note tokens,
octave modifiers, navigation markers, voice labels, lyric prefixes) against
the constants in ``spec``. Each converter still owns its own assembly logic
(measures, beats, data model) on top of these primitives.
"""

import re
from typing import Optional, Tuple

from .solfa_spec import spec

NUMBERED_NAV_RE = re.compile(
    r'^(DS|DSF|DSC|SEGNO|CODA|TC|DC|DCF|DCC|FINE)(\d+)$'
)


def match_solfa_token(text: str, ignore_case: bool = False) -> Optional[str]:
    """Return the longest solfa token ``spec`` recognizes at the start of
    *text*, or None. Tokens are tried longest-first so e.g. "ta" matches
    before "t"."""
    haystack = text.lower() if ignore_case else text
    for token in spec["notes"]["tokens_sorted"]:
        if haystack.startswith(token):
            return token
    return None


def consume_octave_modifiers(text: str) -> Tuple[str, str]:
    """Consume leading octave-modifier chars (the up/down chars from
    ``spec["octave"]``) from the start of *text*.

    Returns (modifiers, remaining_text). Modifiers are returned in the
    order they appeared so callers needing a net shift can simply count
    up-chars minus down-chars.
    """
    up = spec["octave"]["up_char"]
    down = spec["octave"]["down_char"]
    i = 0
    while i < len(text) and text[i] in (up, down):
        i += 1
    return text[:i], text[i:]


def nav_base(nav_str: str) -> str:
    """Return the base marker name, stripping any trailing number."""
    m = NUMBERED_NAV_RE.match(nav_str)
    return m.group(1) if m else nav_str


def nav_number(nav_str: str) -> Optional[str]:
    """Return the trailing number of a numbered marker, or None."""
    m = NUMBERED_NAV_RE.match(nav_str)
    return m.group(2) if m else None


def is_navigation_marker(value: str) -> bool:
    """True if *value* is a plain or numbered navigation marker
    (e.g. "DC", "FINE", "DS1", "SEGNO2")."""
    if value in spec["navigation"]["markers"]:
        return True
    return bool(NUMBERED_NAV_RE.match(value))


def navigation_display(nav_str: str) -> str:
    """Return display text for a navigation marker, plain or numbered.

    Numbered symbol markers (segno/coda) get the digit appended directly
    ("\U0001D10B1"); numbered text markers get a space before the digit
    ("D.S. 1").
    """
    base = nav_base(nav_str)
    number = nav_number(nav_str)
    base_display = spec["navigation"]["markers"].get(base, base)
    if number is None:
        return base_display
    symbols = (spec["navigation"]["segno_symbol"], spec["navigation"]["coda_symbol"])
    if base_display in symbols:
        return f"{base_display}{number}"
    return f"{base_display} {number}"


def voice_label_alternation() -> str:
    """Regex alternation of all configured voice labels (e.g. "PR|PL|S|A|T|B"),
    longest first and escaped, for composing line-start label patterns."""
    labels = sorted(spec["voices"]["voice_config"].keys(), key=len, reverse=True)
    return "|".join(re.escape(lbl) for lbl in labels)


def extract_voice_label_sequence(s: str, allowed_labels, allow_numbered: bool = False) -> list:
    """Greedily split a concatenated voice-label string (e.g. "SATB", "S1S2T")
    into individual labels drawn from *allowed_labels*, longest match first.

    If *allow_numbered* is True, a single trailing digit right after a
    matched label is folded into that label (e.g. "S1" matches if "S" is
    in *allowed_labels*).

    Returns [] if the labels don't consume the entire string.
    """
    sorted_labels = sorted(allowed_labels, key=len, reverse=True)
    labels = []
    pos = 0
    while pos < len(s):
        matched = None
        for lbl in sorted_labels:
            if s[pos:].startswith(lbl):
                matched = lbl
                break
        if not matched:
            break
        if allow_numbered and pos + len(matched) < len(s) and s[pos + len(matched)].isdigit():
            matched = matched + s[pos + len(matched)]
        labels.append(matched)
        pos += len(matched)
    if pos == len(s) and labels:
        return labels
    return []


def split_lyric_prefix(prefix: str) -> Tuple[str, str]:
    """Split a lyrics-line prefix into (verse_part, voice_part).

    "R" -> ("R", ""); "1SA" -> ("1", "SA"); "SA" -> ("", "SA"); "2" -> ("2", "").
    """
    if prefix.startswith('R'):
        return 'R', prefix[1:]
    if prefix and prefix[0].isdigit():
        i = 0
        while i < len(prefix) and prefix[i].isdigit():
            i += 1
        return prefix[:i], prefix[i:]
    return '', prefix


def extract_parenthesized_prefix(line: str) -> Optional[Tuple[str, str]]:
    """If *line* starts with a ``(...)`` token, return (content, rest) where
    content is the text inside the parens and rest is the lyric text after ``)``.

    Returns None when there is no leading parenthesized token. Lyric prefixes are
    recognized ONLY in this parenthesized form; anything else is literal lyric text.
    """
    m = re.match(r'^\s*\(([^)]*)\)\s*(.*)$', line)
    return (m.group(1), m.group(2)) if m else None


def parse_lyric_prefix(token: str, allowed_labels, allow_numbered: bool = True):
    """Parse the CONTENT of a lyric prefix under the dot grammar.

    Grammar (``.`` is ``spec["lyrics"]["verse_voice_separator"]``)::

        PREFIX := verse | R | voices | (verse | R) '.' voices
        verse  := [0-9]+
        voices := (voice)+     voice := [SATB][0-9]?

    Returns (verse, voices) or None:
        verse  : None (no verse marker) | "R" | a digit string
        voices : None (no voice marker -> all voices) | non-empty list of labels
        None   : *token* is not a valid prefix.
    """
    sep = spec["lyrics"]["verse_voice_separator"]
    if sep in token:
        left, _, right = token.partition(sep)
        if not right or sep in right:      # need exactly one separator, voices non-empty
            return None
        v, vrest = split_lyric_prefix(left)  # left must be a bare verse / R
        if not v or vrest:
            return None
        labels = extract_voice_label_sequence(right, allowed_labels, allow_numbered)
        return (v, labels) if labels else None

    v, vrest = split_lyric_prefix(token)
    if v:
        return None if vrest else (v, None)  # bare verse/R; concatenated combo -> invalid
    labels = extract_voice_label_sequence(token, allowed_labels, allow_numbered)
    return (None, labels) if labels else None
