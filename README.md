# Tonic Solfa Converter

A suite of converters for working with Tonic Solfa notation.

## Converters

- **solfa2pdf** - Tonic Solfa text to PDF (direct hymnal rendering)
- **solfa2musicxml** - Tonic Solfa text to MusicXML (for MuseScore, Finale, etc.)
- **pdf2solfa** - Digital PDF to Tonic Solfa text (text extraction + metadata headers)
- **pdfimg2solfa** - Scanned PDF/Images to Tonic Solfa text (OCR + metadata headers)
- **solfareformat** - Reformat/normalize Tonic Solfa text files

## Usage

```bash
python3 -m converters.solfa2pdf input.txt [output.pdf]
python3 -m converters.solfa2musicxml input.txt
python3 -m converters.pdf2solfa input.pdf [output.txt]
python3 -m converters.pdfimg2solfa input.pdf [output.txt]
python3 -m converters.solfareformat input.txt [output.txt]
```

## Input Format

Solfa text files use a header + notation format. Comments start with `//`.

```
:title: Amazing Grace
:author: John Newton
:composer: William Walker
:key: G
:tempo: 80
:tempomarking: Andante
:timesig: 3/4
:meter: 6.6.8.6.
:copyright: © Public Domain

S d : r : m ! f : m : f
A m : d : d ! d : d : d

1 Amaz- ing grace, how sweet the sound
```

### Available Headers

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

## Requirements

- Python 3.10+
- `reportlab` (for solfa2pdf)
- `music21` (for solfa2musicxml)
- `pdftotext` (for pdf2solfa)
- `tesseract-ocr`, `pytesseract`, `pdf2image`, `Pillow` (for pdfimg2solfa)

## Sonarqube

```shell
tox

pysonar -Dsonar.token=SONAR_TOKEN
```

## License

See [LICENSE](LICENSE).
