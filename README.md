# ICS-217A → Codeplug

Turn ICS-217A Communications Resource Availability Worksheets — the frequency
tables ARES/EmComm groups publish as PDF, Word, and Excel — into
CHIRP-importable CSV codeplugs.

The parsing logic is tuned against a local corpus of ~290 real Colorado ARES
forms (242 PDF, 23 xlsx, 11 docx, 11 scanned JPG) spanning several template
generations. Those documents are not published in this repository — see
[Development](#development).

## Install

```sh
pip install -e .                    # core
pip install -e ".[ocr,acroform]"    # optional: scanned PDFs, AcroForm PDFs
pip install -e ".[dev]"             # pytest
```

Requires Python 3.10+.

## Usage

The normal path is two steps, so a human can review and correct the machine's
guesses before anything reaches a radio:

```sh
ics217a-codeplug parse form.pdf -o review.csv    # → wide Review CSV
# edit review.csv by hand
ics217a-codeplug finalize review.csv --name-len 8 -o chirp.csv
```

Other commands:

| Command | Purpose |
| --- | --- |
| `parse` | One or more input files → Review CSV (accepts multiple files; locations stay sequential) |
| `finalize` | Review CSV → final CHIRP CSV, picking one `Name_N` column as the radio's Name |
| `convert` | One-shot parse → CHIRP CSV, skipping the review step |
| `enter` | Interactive wizard for typing channels in by hand |

Flags of note: `--name-len {8,10,12,16}` (radio display width),
`--start-location`, `--ocr` (scanned PDFs), `--skip-digital`.

## Architecture

A parser/writer pipeline over a single `Channel` dataclass
([`models.py`](src/ics217a_codeplug/models.py)). Format-specific parsers each
reduce their input to rows, then share one table engine
([`_table_logic.py`](src/ics217a_codeplug/parsers/_table_logic.py)) that sniffs
the header row, maps columns by keyword, and emits channels. Two writers
produce the Review CSV and the final CHIRP CSV.

```
PDF / DOCX / XLSX / XLS / CSV / manual entry
        │
        ▼
   parsers/*  ──►  _table_logic  ──►  Channel  ──►  writers/*  ──►  Review CSV
                                                                    CHIRP CSV
```

### The Review CSV

The intermediate format is deliberately wider than CHIRP needs. It carries four
pre-truncated name columns (`Name_8` / `_10` / `_12` / `_16`) so you can see
what each radio's display will actually show, plus `_Band`, `_Protocol`,
`_SourceFile`, `_SourceName`, and `_Notes` — every assumption the parser made,
written down. `finalize` strips the metadata columns and promotes the
`Name_N` you choose. Nothing is silently lost before a human approves it.

## What's implemented

- **Inputs:** xlsx / xls / csv, docx, and PDF text-layer tables. The docx
  parser walks the full XML tree, so it finds tables buried in VML textboxes
  that `python-docx`'s `doc.tables` misses. Previously generated CHIRP and
  Review CSVs re-import cleanly for round-tripping.
- **Band classification:** three passes — HF amateur bands (160m–10m, WARC
  included) → named services (MURS, GMRS/FRS, Marine, NOAA-WX, Air, CB) →
  broad catch-alls (VHF, UHF, 220, 700/800/900).
- **Frequency parsing:** strips N/W and trailing mode words, rejects malformed
  values, and detects HF frequencies entered in kHz (`7103.000` → 7.103 MHz).
- **Tone parsing:** CTCSS, DCS with polarity, DMR `CC n/TS n`, and P25 NAC.
  DMR color code, timeslot, and TalkGroup get dedicated CHIRP columns rather
  than being buried in a comment; TalkGroups are dug out of remarks or the
  channel name.
- **Protocol inference:** ~15 digital and analog modes — DMR, P25, D-STAR,
  Fusion, NXDN, VARA / VARA FM, Packet, Pactor, JS8Call, Winlink, SSB, CW, AM,
  NFM, FM.
- **Tests:** 160 passing, run against the real sample files rather than
  synthetic fixtures.

## What's not done yet

- **AcroForm PDFs.** `PdfParser._try_acroform` detects form fields, logs a
  warning, and deliberately falls through to text extraction — the
  field-to-channel mapping is form-specific and unwritten.
- **OCR.** `--ocr` exists for the scanned JPG/PDF samples, but its
  y-coordinate row grouping is crude and needs work against real scans.
- **Unwired options.** `skip_digital` and `output_format` are declared on
  `CodeplugOptions` but never acted on, and `cli.py` imports the `writer_for`
  registry without using it. That registry is the intended seam for
  radio-specific output formats beyond generic CHIRP.
- **Version control.** This project is not yet a git repository.

## Development

```sh
python -m pytest tests/ -q
```

The 160 tests run against real ICS-217A forms rather than synthetic fixtures,
and those forms are deliberately not committed: they are working documents from
Colorado ARES districts and may carry operator names and contact details. To run
the suite you need a local `samples/` directory holding the files named in
[`tests/conftest.py`](tests/conftest.py) — seven forms covering the xlsx, xls,
docx, and PDF paths. Without it the parser tests will error on missing files.

## License

Copyright (C) 2026 AquaeAtrae

This program is free software: you can redistribute it and/or modify it
under the terms of the GNU General Public License as published by the Free
Software Foundation, version 3.

This program is distributed in the hope that it will be useful, but WITHOUT
ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
FOR A PARTICULAR PURPOSE. See the [GNU General Public License](LICENSE) for
more details.
