#!/usr/bin/env python3
"""
Scanned PDF / Image → Solfa Text Converter (OCR)
==================================================
Extracts text from scanned PDFs or images using OCR (tesseract)
and adds solfa metadata headers.

Requirements:
    sudo apt install tesseract-ocr libtesseract-dev
    python3 -m pip install pytesseract pdf2image Pillow opencv-python numpy

Supports:
    - PDF files (scanned / no text layer)
    - PNG, JPG, TIFF, BMP images

Usage:
    python3 -m converters.pdfimg2solfa.converter <input.pdf|image> [output.txt]

Generates .txt with solfa metadata headers in the same directory as the input file.
"""

import re
import sys
from pathlib import Path
from ..shared import spec
from .fixup import apply_fixup, extract_headers

try:
    import pytesseract
    from PIL import Image
    import pdf2image
    import cv2
    import numpy as np
    OCR_DEPS_AVAILABLE = True
except ImportError:
    OCR_DEPS_AVAILABLE = False


# ---------------------------------------------------------------------------
# Tier 1 tunables
# ---------------------------------------------------------------------------

DISCOVERY_CONFIG = "--oem 1 --psm 6"

# Per-line second pass (Tier 3). psm 7 = single text line.
# Whitelist is honored by legacy oem but often ignored by LSTM; harmless either way.
# Tier 4 will normalize tokens regardless.
MUSIC_WHITELIST = "drmfsltaeDRMFSLTAE|:,.'-_()[] 0123456789"
MUSIC_CONFIG = f'--oem 1 --psm 7 -c tessedit_char_whitelist="{MUSIC_WHITELIST}"'
LYRIC_CONFIG = "--oem 1 --psm 7"

PDF_RENDER_DPI = 300

# Music-line classifier thresholds.
_MUSIC_TOKEN_RE = re.compile(r"^[drmfsltaeDRMFSLTAE|:,.'\-_()\[\]0-9]+$")
MUSIC_RATIO_THRESHOLD = 0.6           # no bar separator detected
MUSIC_RATIO_THRESHOLD_WITH_BAR = 0.4  # bar separator present in line

LINE_CROP_PADDING_PX = 8

# Upscale anything narrower than this before OCR (helps low-DPI scans).
MIN_WIDTH_PX = 2200
UPSCALE_FACTOR_MAX = 2.0

# Only rotate if skew exceeds this - avoids resampling clean pages.
DESKEW_THRESHOLD_DEG = 0.3

# Adaptive threshold parameters (cv2.adaptiveThreshold).
ADAPTIVE_BLOCK_SIZE = 31
ADAPTIVE_C = 15


# ---------------------------------------------------------------------------
# Headers
# ---------------------------------------------------------------------------

def _build_headers(overrides: dict | None = None) -> str:
    """Build solfa metadata headers, applying any extracted overrides."""
    prefix = spec["header"]["prop_prefix"]
    suffix = spec["header"]["prop_suffix"]
    overrides = overrides or {}
    lines = []
    for k, default_val in spec["defaults"].items():
        val = overrides.get(k, default_val)
        rendered = "" if val is None else val
        lines.append(f"{prefix}{k}{suffix} {rendered}")
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Preprocessing
# ---------------------------------------------------------------------------

def _to_gray(image):
    arr = np.array(image)
    if arr.ndim == 2:
        return arr
    if arr.shape[2] == 4:
        return cv2.cvtColor(arr, cv2.COLOR_RGBA2GRAY)
    return cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)


def _upscale_if_small(gray):
    h, w = gray.shape[:2]
    if w >= MIN_WIDTH_PX:
        return gray
    scale = min(UPSCALE_FACTOR_MAX, MIN_WIDTH_PX / w)
    new_size = (int(w * scale), int(h * scale))
    return cv2.resize(gray, new_size, interpolation=cv2.INTER_CUBIC)


def _denoise(gray):
    return cv2.fastNlMeansDenoising(gray, h=10, templateWindowSize=7, searchWindowSize=21)


def _deskew(gray):
    """Estimate skew from the text mask and rotate if non-trivial."""
    inv = cv2.bitwise_not(gray)
    _, bw = cv2.threshold(inv, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)
    coords = np.column_stack(np.where(bw > 0))
    if coords.size == 0:
        return gray
    angle = cv2.minAreaRect(coords)[-1]
    # cv2 returns the rect angle in [-90, 0); normalize to a small signed angle.
    angle = -(90 + angle) if angle < -45 else -angle
    if abs(angle) < DESKEW_THRESHOLD_DEG:
        return gray
    h, w = gray.shape[:2]
    M = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)
    return cv2.warpAffine(
        gray, M, (w, h),
        flags=cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_REPLICATE,
    )


def _binarize(gray):
    return cv2.adaptiveThreshold(
        gray, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        blockSize=ADAPTIVE_BLOCK_SIZE,
        C=ADAPTIVE_C,
    )


def _preprocess(image):
    """grayscale → upscale-if-small → denoise → deskew → adaptive threshold."""
    gray = _to_gray(image)
    gray = _upscale_if_small(gray)
    gray = _denoise(gray)
    gray = _deskew(gray)
    bw = _binarize(gray)
    return Image.fromarray(bw)


# ---------------------------------------------------------------------------
# OCR (structured)
# ---------------------------------------------------------------------------

def _ocr_page(image, config: str = DISCOVERY_CONFIG):
    """
    Run tesseract and return a list of lines, each line carrying its tokens
    with bbox + confidence. Downstream tiers consume this structured form;
    Tier 1 renders it back to plain text via _render_text.

    Line shape:
        {"block": int, "y": int, "tokens": [
            {"text": str, "left": int, "top": int,
             "width": int, "height": int, "conf": int},
            ...
        ]}
    """
    data = pytesseract.image_to_data(
        image,
        config=config,
        output_type=pytesseract.Output.DICT,
    )

    groups: dict = {}
    for i in range(len(data["text"])):
        text = data["text"][i]
        try:
            conf = int(float(data["conf"][i]))
        except (ValueError, TypeError):
            conf = -1
        if conf < 0 or not text or not text.strip():
            continue
        key = (data["block_num"][i], data["par_num"][i], data["line_num"][i])
        groups.setdefault(key, []).append({
            "text": text,
            "left": int(data["left"][i]),
            "top": int(data["top"][i]),
            "width": int(data["width"][i]),
            "height": int(data["height"][i]),
            "conf": conf,
        })

    lines = []
    for key in sorted(groups.keys()):
        tokens = sorted(groups[key], key=lambda w: w["left"])
        lines.append({
            "block": key[0],
            "y": min(t["top"] for t in tokens),
            "tokens": tokens,
        })
    return lines


# ---------------------------------------------------------------------------
# Tier 3 - line classification + per-line second-pass OCR
# ---------------------------------------------------------------------------

def _classify_line(tokens) -> str:
    """Return 'music' or 'lyric' for a discovery-pass line.

    Conservative toward 'music' - misclassifying a lyric as music would
    apply the solfa whitelist to it and mangle words. Misclassifying
    music as lyric just falls back to a generic LSTM pass.
    """
    if not tokens:
        return "lyric"
    n = len(tokens)
    music_count = sum(1 for t in tokens if _MUSIC_TOKEN_RE.match(t["text"]))
    has_bar = any("|" in t["text"] for t in tokens)
    threshold = MUSIC_RATIO_THRESHOLD_WITH_BAR if has_bar else MUSIC_RATIO_THRESHOLD
    return "music" if (music_count / n) >= threshold else "lyric"


def _line_bbox(tokens, image_size, padding: int = LINE_CROP_PADDING_PX):
    left = min(t["left"] for t in tokens) - padding
    top = min(t["top"] for t in tokens) - padding
    right = max(t["left"] + t["width"] for t in tokens) + padding
    bottom = max(t["top"] + t["height"] for t in tokens) + padding
    w, h = image_size
    return (max(0, left), max(0, top), min(w, right), min(h, bottom))


def _ocr_line_crop(image, bbox, config: str):
    """Run tesseract on a cropped line strip; return tokens in page coords."""
    crop = image.crop(bbox)
    data = pytesseract.image_to_data(
        crop,
        config=config,
        output_type=pytesseract.Output.DICT,
    )
    tokens = []
    for i in range(len(data["text"])):
        text = data["text"][i]
        try:
            conf = int(float(data["conf"][i]))
        except (ValueError, TypeError):
            conf = -1
        if conf < 0 or not text or not text.strip():
            continue
        tokens.append({
            "text": text,
            "left": int(data["left"][i]) + bbox[0],
            "top": int(data["top"][i]) + bbox[1],
            "width": int(data["width"][i]),
            "height": int(data["height"][i]),
            "conf": conf,
        })
    tokens.sort(key=lambda w: w["left"])
    return tokens


def _refine_lines(image, lines):
    """Per-line classify + targeted re-OCR. Tags each line with `kind`."""
    refined = []
    for line in lines:
        kind = _classify_line(line["tokens"])
        config = MUSIC_CONFIG if kind == "music" else LYRIC_CONFIG
        bbox = _line_bbox(line["tokens"], image.size)
        new_tokens = _ocr_line_crop(image, bbox, config)
        refined.append({
            "block": line["block"],
            "y": line["y"],
            "kind": kind,
            "tokens": new_tokens if new_tokens else line["tokens"],
        })
    return refined


def _count_kinds(lines) -> tuple[int, int]:
    music = sum(1 for l in lines if l.get("kind") == "music")
    lyric = sum(1 for l in lines if l.get("kind") == "lyric")
    return music, lyric


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

def _render_text(pages) -> str:
    """Flatten structured pages back to plain text, preserving block breaks."""
    out = []
    for page in pages:
        prev_block = None
        for line in page["lines"]:
            if prev_block is not None and line["block"] != prev_block:
                out.append("")
            out.append(" ".join(t["text"] for t in line["tokens"]))
            prev_block = line["block"]
        out.append("")
    return "\n".join(out)


def _mean_conf(lines) -> float:
    confs = [t["conf"] for line in lines for t in line["tokens"]]
    return sum(confs) / len(confs) if confs else 0.0


# ---------------------------------------------------------------------------
# I/O
# ---------------------------------------------------------------------------

def _load_images(input_p: Path):
    suffix = input_p.suffix.lower()
    if suffix == ".pdf":
        print("Converting PDF to images...")
        return pdf2image.convert_from_path(str(input_p), dpi=PDF_RENDER_DPI)
    if suffix in (".png", ".jpg", ".jpeg", ".tiff", ".tif", ".bmp"):
        print("Loading image...")
        return [Image.open(str(input_p))]
    raise ValueError(
        f"Unsupported file type '{input_p.suffix}'. "
        "Supported: .pdf, .png, .jpg, .jpeg, .tiff, .bmp"
    )


def convert(input_path: str, output_path: str = None):
    """Convert scanned PDF or image to solfa text via OCR."""
    if not OCR_DEPS_AVAILABLE:
        print("Error: Required packages not found.")
        print("Install with:")
        print("  pip install pytesseract pdf2image Pillow opencv-python numpy")
        print("  apt install tesseract-ocr libtesseract-dev")
        sys.exit(1)

    input_p = Path(input_path)
    output_p = Path(output_path) if output_path else input_p.with_suffix(".txt")

    print(f"Processing: {input_p}")

    try:
        images = _load_images(input_p)
    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Error loading input: {e}")
        sys.exit(1)

    print(f"Running OCR on {len(images)} page(s)...")
    pages = []
    for i, image in enumerate(images, 1):
        print(f"  Page {i}/{len(images)}: preprocessing...", end=" ", flush=True)
        try:
            cleaned = _preprocess(image)
        except Exception as e:
            print(f"preprocess error: {e}")
            pages.append({"size": image.size, "lines": []})
            continue
        try:
            lines = _ocr_page(cleaned)
        except Exception as e:
            print(f"ocr error: {e}")
            pages.append({"size": cleaned.size, "lines": []})
            continue
        try:
            lines = _refine_lines(cleaned, lines)
        except Exception as e:
            print(f"refine error: {e}")
            # fall back to discovery-pass lines without classification
        token_count = sum(len(l["tokens"]) for l in lines)
        music_n, lyric_n = _count_kinds(lines)
        print(
            f"{len(lines)} lines ({music_n} music, {lyric_n} lyric), "
            f"{token_count} words, mean conf {_mean_conf(lines):.0f}"
        )
        pages.append({"size": cleaned.size, "lines": lines})

    apply_fixup(pages)
    overrides = extract_headers(pages)
    if overrides:
        print(f"Detected headers: {', '.join(overrides.keys())}")
    full_text = _build_headers(overrides) + "\n" + _render_text(pages)

    print(f"Writing solfa text: {output_p}")
    output_p.write_text(full_text, encoding="utf-8")

    print(f"✓ Conversion complete: {output_p}")
    print("Note: OCR results may contain errors. Please review and correct:")
    print("  - Metadata headers (:title:, :composer:, etc.)")
    print("  - Note symbols (d, r, m, f, s, l, t)")
    print("  - Measure separators (|) and beat separators (:)")
    return str(output_p)


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 -m converters.pdfimg2solfa.converter <input.pdf|image> [output.txt]")
        sys.exit(1)
    convert(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)


if __name__ == "__main__":
    main()
