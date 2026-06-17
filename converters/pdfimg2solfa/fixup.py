"""
Tier 4 - grammar-aware post-OCR fixup
=====================================
Operates on the structured pages produced by Tier 1/3:

    [{"lines": [{"kind": "music"|"lyric", "tokens": [...], "y": int, ...}]}]

Responsibilities:
  1. Character-level normalization (unicode dashes, smart quotes, ...).
  2. Music-token snapping against the spec's valid solfa tokens, gated by
     per-token tesseract confidence.
  3. Header extraction (title / composer / key / timesig) from lyric lines
     near the top of page 1.

Out of scope for Tier 4 (intentionally):
  - Beat-count validation per measure (needs meter awareness).
  - Navigation-marker normalization.
"""

import re
from ..shared import spec


# ---------------------------------------------------------------------------
# Character-level tables
# ---------------------------------------------------------------------------

# Applied to every token regardless of kind.
_GLOBAL_NORMALIZE = {
    "-": "-", "–": "-", "‐": "-", "‒": "-", "−": "-",
    "‘": "'", "’": "'",
    "“": '"', "”": '"',
}

# Additional normalizations for music tokens.
_MUSIC_NORMALIZE = {
    ";": ":",
    "÷": ":",
    "•": ":",
    "·": ".",
}

# Per-char OCR confusions, applied to an atomic music substring after the
# stem has been isolated from its octave markers.
_MUSIC_CHAR_FIXUPS = {
    "c": "d",
    "o": "d",
    "0": "d",
    "n": "r",
    "+": "t",
    "5": "s",
    "i": "l",
    "1": "l",
    "$": "s",
}

# Structural separators inside a music token.
_MUSIC_SPLIT_RE = re.compile(r"([|:\.\-_()\[\] ])")

_VALID_NOTES = set(spec["notes"]["tokens_sorted"])

# Confidence below this triggers `[?orig]` wrapping when snap fails.
LOW_CONF_THRESHOLD = 60


# ---------------------------------------------------------------------------
# Token-level fixup
# ---------------------------------------------------------------------------

def _normalize_chars(text: str, table: dict) -> str:
    return "".join(table.get(ch, ch) for ch in text)


def _snap_atomic(atomic: str) -> str | None:
    """Map an atomic music substring to a valid solfa token, or None."""
    if not atomic:
        return None
    lc = atomic.lower()
    stem = lc.rstrip(",'")
    suffix = lc[len(stem):]
    if not stem:
        return None
    if stem in _VALID_NOTES:
        return stem + suffix
    fixed = "".join(_MUSIC_CHAR_FIXUPS.get(c, c) for c in stem)
    if fixed in _VALID_NOTES:
        return fixed + suffix
    return None


def fixup_music_token(text: str, conf: int) -> str:
    """Normalize + snap a tesseract token from a music line."""
    text = _normalize_chars(text, _GLOBAL_NORMALIZE)
    text = _normalize_chars(text, _MUSIC_NORMALIZE)
    parts = [p for p in _MUSIC_SPLIT_RE.split(text) if p]
    out = []
    for part in parts:
        # Pure structural / whitespace chunks pass through.
        if _MUSIC_SPLIT_RE.fullmatch(part):
            out.append(part)
            continue
        snapped = _snap_atomic(part)
        if snapped is not None:
            out.append(snapped)
        elif conf < LOW_CONF_THRESHOLD:
            out.append(f"[?{part}]")
        else:
            out.append(part)
    return "".join(out)


def fixup_lyric_token(text: str) -> str:
    return _normalize_chars(text, _GLOBAL_NORMALIZE)


def apply_fixup(pages):
    """Rewrite token text in place per line kind. Returns the same pages."""
    for page in pages:
        for line in page.get("lines", []):
            kind = line.get("kind", "lyric")
            for tok in line["tokens"]:
                if kind == "music":
                    tok["text"] = fixup_music_token(tok["text"], tok.get("conf", 100))
                else:
                    tok["text"] = fixup_lyric_token(tok["text"])
    return pages


# ---------------------------------------------------------------------------
# Header extraction
# ---------------------------------------------------------------------------

_KEY_RE = re.compile(
    r"\bkey\s*(?:of\s+|:\s*)([A-G][#b]?)(?![A-Za-z])",
    re.IGNORECASE,
)
_TIMESIG_RE = re.compile(r"\b(\d{1,2})\s*/\s*(\d{1,2})\b")
_BY_RE = re.compile(
    r"\b(?:music by|composed by|words by|by)\s+(.+)$",
    re.IGNORECASE,
)

_VALID_KEYS = set(spec["keys"]["valid_keys"])
_VALID_DENOMS = {1, 2, 4, 8, 16, 32}

# Top-of-page fraction in which to look for headers.
HEADER_TOP_FRACTION = 0.25
HEADER_TOP_MIN_PX = 100
MIN_TITLE_LEN = 4


def _line_text(line) -> str:
    return " ".join(t["text"] for t in line["tokens"]).strip()


def extract_headers(pages) -> dict:
    """Best-effort header sniff from top of page 1. Returns override dict."""
    out: dict = {}
    if not pages:
        return out
    page = pages[0]
    lines = page.get("lines", [])
    if not lines:
        return out

    size = page.get("size")
    if size and size[1] > 0:
        page_h = size[1]
    else:
        page_h = max((l["y"] for l in lines), default=0) + 100
    top_cut = max(page_h * HEADER_TOP_FRACTION, HEADER_TOP_MIN_PX)
    candidates = [
        l for l in lines
        if l.get("kind") == "lyric" and l["y"] <= top_cut
    ]

    for line in candidates:
        text = _line_text(line)
        if not text:
            continue

        if "key" not in out:
            m = _KEY_RE.search(text)
            if m and m.group(1) in _VALID_KEYS:
                out["key"] = m.group(1)

        if "timesig" not in out:
            m = _TIMESIG_RE.search(text)
            if m:
                num, den = int(m.group(1)), int(m.group(2))
                if 1 <= num <= 32 and den in _VALID_DENOMS:
                    out["timesig"] = f"{num}/{den}"

        if "composer" not in out:
            m = _BY_RE.search(text)
            if m:
                out["composer"] = m.group(1).strip()

    for line in candidates:
        text = _line_text(line)
        if not text or len(text) < MIN_TITLE_LEN:
            continue
        if _KEY_RE.search(text) or _TIMESIG_RE.search(text) or _BY_RE.search(text):
            continue
        out["title"] = text
        break

    return out
