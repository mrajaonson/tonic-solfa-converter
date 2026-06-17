# Tonic Solfa Converter Suite

Five specialized converters for tonic solfa notation.

## Requirements

* MuseScore 4 (optional, for PDF generation)

```shell
python3 -m venv .venv

source .venv/bin/activate
pip install --upgrade pip
pip install -r converters/requirements.txt

# linux
sudo apt install poppler-utils tesseract-ocr libtesseract-dev fonts-freefont-ttf

# mac
brew install poppler
```

## Usage

```shell
# Solfa → PDF (direct hymnal-style rendering)
# Converts tonic solfa text directly to a traditional hymnal-style PDF with voice parts and aligned lyrics.
python3 -m converters.solfa2pdf sample.txt [output.pdf]

# Solfa → MusicXML (compatible with MuseScore 4)
# Converts tonic solfa text notation to MusicXML, then optionally to PDF via MuseScore.
python3 -m converters.solfa2musicxml sample.txt

# Digital PDF → Solfa text** (text extraction)
# Extracts text from digital (non-scanned) PDFs and wraps it with tonic solfa metadata headers.
python3 -m converters.pdf2solfa input.pdf [output.txt]

# Scanned PDF / Images → Solfa text** (OCR-based)
# Uses OCR (tesseract) to extract text from scanned PDFs or images and wraps it with tonic solfa metadata headers.
python3 -m converters.pdfimg2solfa scanned.pdf [output.txt]
python3 -m converters.pdfimg2solfa page.jpg [output.txt]

# Solfa text → Reformatted Solfa text
# Normalizes spacing and beat separators in note lines of a tonic solfa text file.
python3 -m converters.solfareformat input.txt [output.txt]
```

## Shared Utilities

`shared/` contains common utilities:
- `solfa_spec.py` - Loads `solfadoc-spec.yaml` (the notation spec) and exposes it as a plain dict; import via `from shared import spec`
- `solfa_metadata.py` - Default metadata headers for converters

---

## File Format

Solfa text files use a header + notation format. Comments start with `//`.

### Headers

| Header            | Description                                           |
|-------------------|-------------------------------------------------------|
| `:title:`         | Song title                                            |
| `:author:`        | Author - repeatable for multiple authors              |
| `:composer:`      | Composer - repeatable for multiple composers          |
| `:key:`           | Key signature (e.g. `G`, `Ab`)                        |
| `:keyheader:`     | Custom label for key display (default: `Key:`)        |
| `:tempo:`         | BPM (e.g. `80`)                                       |
| `:tempomarking:`  | Tempo name (e.g. `Andante`)                           |
| `:timesig:`       | Time signature (e.g. `4/4`)                           |
| `:meter:`         | Meter pattern (e.g. `12.13.11.11.`)                   |
| `:comment:`       | Free comment                                          |
| `:date:`          | Date of creation                                      |
| `:transcription:` | Name of transcriber                                   |
| `:copyright:`     | Copyright notice                                      |
| `:gendate:`       | Show generation date in footer (flag, off by default) |

### Notation

- **Notes:** `d` (do), `r` (re), `m` (mi), `f` (fa), `s` (sol), `l` (la), `t` (ti)
- **Octave modifiers:** `'` (up), `,` (down) - e.g. `d'` (do up), `d,` (do down)
- **Barlines:** `|` (measure), `||` (double barline), `!` (soft barline)
- **Beat separators:** `:` (beat), `.` (sub-beat)
- **Rest:** `*` (explicit rest)
- **Hold:** `-` (extend previous note)
- **Staccato:** `,d` (leading comma)
- **Dynamics:** `(p)`, `(f)`, `(ff)`, `(cresc)`, etc.
- **Fermata:** `(^)`
- **Chords:** `<d m s>` (notes separated by spaces)
- **Modulation:** `r/s` (old note / new note)
- **Mute letters:** `__e__` (italic/silent letter in lyrics)

### Example

```
// Amazing Grace - 3/4
:title: Amazing Grace
:author: John Newton
:composer: William Walker
:key: G
:tempo: 80
:tempomarking: Andante
:timesig: 3/4
:meter: 6.6.8.6.
:copyright: © Public Domain

| d : r : m | f : m : r | d : - : m |
| m : m : m | d : d : d | d : - : - |

1 A- maz- ing grace how sweet the sound
```

---

## Common Workflow

1. **Start with a scanned hymnal:**
   ```bash
   python3 -m converters.pdfimg2solfa hymnal_page.pdf hymn.txt
   # Edit hymn.txt - fix OCR errors, fill metadata headers
   ```

2. **Render directly to PDF:**
   ```bash
   python3 -m converters.solfa2pdf hymn.txt hymn.pdf
   ```

3. **Or convert to MusicXML for MuseScore:**
   ```bash
   python3 -m converters.solfa2musicxml hymn.txt
   ```

---

## References

- **Music21:** https://music21.org/music21docs/
- **MuseScore:** https://musescore.org/
- **MusicXML:** https://www.musicxml.com/
- **Tesseract OCR:** https://github.com/UB-Mannheim/tesseract/wiki
