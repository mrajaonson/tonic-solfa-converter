#!/usr/bin/env python3
"""
Solfa Text Reformatter
======================
Reformats .solfa/.txt tonic solfa files:
- Replaces multiple spaces with a single space
- Adds one space before and after : and ! separators (note lines only)

Note lines are identified by containing both : and ! separators.

Usage:
    python3 -m converters.solfafmt.converter <input.txt> [output.txt]
"""

import sys
import re
from pathlib import Path
from ..shared import spec


def _is_note_line(line: str) -> bool:
    """A note line contains a barline | and a beat separator :."""
    return '|' in line and ':' in line


def _align_block(note_lines: list[str]) -> list[str]:
    """Pad cells so separators align vertically across all lines.

    Lines with different lengths are supported as long as at each separator
    position all lines that reach it agree on the separator character.  Shorter
    lines (fewer measures) simply contribute only to the positions they have,
    so their measure columns are aligned with the corresponding positions in
    longer lines.
    """
    if not note_lines:
        return []

    cells_list = [[c.strip() for c in re.split(r'\s*[|:!]\s*', line)] for line in note_lines]
    seps_list  = [re.findall(r'[|:!]', line) for line in note_lines]

    # Ensure separator characters are compatible at every position they share.
    max_sep = max(len(s) for s in seps_list)
    for j in range(max_sep):
        chars = {s[j] for s in seps_list if j < len(s)}
        if len(chars) > 1:
            return note_lines  # incompatible separators - skip alignment

    # Max cell width per position, considering only lines that reach that position.
    max_cells = max(len(c) for c in cells_list)
    max_widths = [
        max(len(c[j]) for c in cells_list if j < len(c))
        for j in range(max_cells)
    ]

    has_voice_label = max_widths[0] > 0

    aligned = []
    for cells, seps in zip(cells_list, seps_list):
        parts = []
        for i, cell in enumerate(cells):
            parts.append(cell.ljust(max_widths[i]))
            if i < len(seps):
                c = seps[i]
                is_first = (i == 0)
                is_last  = (i == len(seps) - 1)
                if is_first and not has_voice_label:
                    parts.append(c + ' ')        # '| ' - opening pipe, no leading space
                elif is_last:
                    parts.append(' ' + c)        # ' |' - closing pipe, no trailing space
                else:
                    parts.append(' ' + c + ' ')  # ' : ' / ' ! ' / ' | '
        aligned.append(''.join(parts).rstrip())

    return aligned


def _reformat_note_line(line: str) -> str:
    """Normalize spacing around :, !, and | separators in a note line."""
    # Collapse multiple spaces to one
    line = re.sub(r' +', ' ', line)

    # Normalize spacing: remove spaces around separators, then add exactly one
    line = re.sub(r'\s*:\s*', ' : ', line)
    line = re.sub(r'\s*!\s*', ' ! ', line)
    line = re.sub(r'\s*\|\s*', ' | ', line)

    # Clean up any double spaces introduced
    line = re.sub(r' +', ' ', line)

    # strip() removes the extra leading space added before the opening pipe
    return line.strip()


def reformat(input_path: str, output_path: str = None):
    """Reformat a solfa text file."""
    input_p = Path(input_path)

    if output_path is None:
        output_path = str(input_p)

    output_p = Path(output_path)

    text = input_p.read_text(encoding="utf-8")
    lines = text.split('\n')
    result: list[str | None] = []
    note_positions: list[tuple[int, str]] = []  # (index_in_result, reformatted_line)

    marker = spec["notes_section"]["marker"]
    in_notes = False

    for line in lines:
        if line.strip() == marker:
            in_notes = True

        if in_notes:
            result.append(line)
        elif _is_note_line(line):
            note_positions.append((len(result), _reformat_note_line(line)))
            result.append(None)  # placeholder - filled after global alignment
        else:
            result.append(line)

    # Align all note lines globally - shorter lines (fewer measures) share
    # column widths with longer lines for their common positions.
    aligned = _align_block([line for _, line in note_positions])
    for (idx, _), aligned_line in zip(note_positions, aligned):
        result[idx] = aligned_line

    output_p.write_text('\n'.join(result), encoding="utf-8")
    print(f"Done: {output_p}")

    return str(output_p)


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 -m converters.solfafmt.converter <input.txt> [output.txt]")
        sys.exit(1)

    input_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else None

    reformat(input_file, output_file)


if __name__ == "__main__":
    main()
