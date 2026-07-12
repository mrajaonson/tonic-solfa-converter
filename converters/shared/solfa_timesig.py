"""Shared time-signature (beats-per-measure) detection for tonic solfa parsers.

The number of beats per measure is inferred from the music itself rather than
trusted blindly from the ``:timesig:`` header: the header can be missing, wrong,
or absent. Because the first measure of a piece may be a partial/pickup measure
(and a measure may be split across systems), we count only *complete* measures -
those delimited by a barline on both sides - and take the most common beat count.

A ``!`` soft barline is a purely visual mid-measure separator (see the spec) and
is counted as an ordinary ``:`` beat separator here.

These are pure functions over ``spec``; each converter still owns its own measure
assembly and data model on top of the resolved beats-per-measure value.
"""

from collections import Counter
from typing import Iterable, List, Optional

from .solfa_spec import spec


def is_note_line(line: str) -> bool:
    """A note line contains both a barline ``|`` and a beat separator ``:``."""
    return spec["rhythm"]["barline"] in line and spec["rhythm"]["beat_separator"] in line


def count_measure_beats(measure_str: str) -> int:
    """Count beat slots in a single measure, treating ``!`` as ``:``.

    The soft barline is visual only and has no effect on beat counts, so it is
    normalized to the beat separator before splitting.
    """
    beat_sep = spec["rhythm"]["beat_separator"]
    soft = spec["rhythm"]["soft_barline"]["char"]
    return len(measure_str.replace(soft, beat_sep).split(beat_sep))


def _complete_measures(line: str) -> List[str]:
    """Return the complete (barline-delimited on both sides) measures of a note
    line, excluding the possibly-partial leading/trailing edge fragments.

    A measure at the very start of a line with no leading barline, or at the very
    end with no trailing barline, is a boundary fragment (pickup / split measure)
    and is dropped - mirroring the boundary rule used by the converters'
    ``parse_voice_line``.
    """
    barline = spec["rhythm"]["barline"]
    double = spec["rhythm"]["double_barline"]

    trimmed = line.strip()
    # A trailing double barline still counts as a trailing barline.
    trimmed_end = trimmed[:-len(double)].rstrip() if trimmed.endswith(double) else trimmed
    has_leading_barline = trimmed.startswith(barline)
    has_trailing_barline = trimmed_end.endswith(barline)

    measures = [m.strip() for m in trimmed.split(barline)]
    measures = [m for m in measures if m]
    if not measures:
        return []

    last_idx = len(measures) - 1
    complete = []
    for i, m in enumerate(measures):
        if i == 0 and not has_leading_barline:
            continue  # leading pickup fragment
        if i == last_idx and not has_trailing_barline:
            continue  # trailing partial / split fragment
        complete.append(m)
    return complete


def find_beats_per_measure(lines: Iterable[str], with_line: bool = False):
    """Infer beats-per-measure by counting beats in every complete measure across
    all note lines and returning the most common count.

    Ties are broken toward the larger count (favouring the fuller measure).
    Returns ``None`` when no complete measure can be found.

    When *with_line* is True, returns ``(beats, line_number)`` where
    ``line_number`` is the 1-based index (within *lines*) of the first note line
    that establishes the winning count, or ``None`` when there is no count.
    """
    counts: Counter = Counter()
    first_line: dict = {}  # beat count -> 1-based line number of first occurrence
    for idx, line in enumerate(lines):
        if not is_note_line(line):
            continue
        for measure in _complete_measures(line):
            beats = count_measure_beats(measure)
            counts[beats] += 1
            first_line.setdefault(beats, idx + 1)

    if not counts:
        return (None, None) if with_line else None
    # Most common; tie-break toward the larger beat count.
    best_freq = max(counts.values())
    best = max(n for n, freq in counts.items() if freq == best_freq)
    return (best, first_line[best]) if with_line else best


def resolve_beats_per_measure(lines: Iterable[str], header_timesig: Optional[str] = None,
                              warn: bool = True) -> int:
    """Resolve the authoritative beats-per-measure for a document.

    The count from the music wins. The ``header_timesig`` (``"N/D"``) is used only
    as a fallback when no complete measure can be counted, and - when both exist
    and disagree - to emit a single warning. Falls back to the spec default
    numerator when neither a count nor a header numerator is available.
    """
    lines = list(lines)
    counted, line_no = find_beats_per_measure(lines, with_line=True)

    header_num = None
    if header_timesig and "/" in header_timesig:
        try:
            header_num = int(header_timesig.split("/")[0])
        except ValueError:
            header_num = None

    if counted is None:
        if header_num is not None:
            return header_num
        return int(spec["defaults"]["timesig"].split("/")[0])

    if warn and header_num is not None and header_num != counted:
        loc = f" (line {line_no})" if line_no else ""
        print(
            f"Warning: :timesig: header numerator ({header_num}) disagrees with the "
            f"music ({counted} beats per measure){loc} - using {counted}."
        )
    return counted
