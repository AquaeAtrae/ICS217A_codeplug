# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 AquaeAtrae
"""Shared table parsing logic used by SpreadsheetParser, DocxParser, and PdfParser."""
from __future__ import annotations

import logging
import re
from typing import Literal

from ..models import Channel, CodeplugOptions, ToneInfo
from ..utils import FrequencyParseError, parse_frequency, parse_tone, parse_talkgroup

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Column keyword matching
# ---------------------------------------------------------------------------

# Each entry: (canonical_key, list-of-substrings-to-match, case-insensitive)
_ICS217A_COL_KEYWORDS: dict[str, list[str]] = {
    "channel_name": ["channel name", "talkgroup", "4. channel", "chan name"],
    "rx_freq":      ["rx freq", "6. rx", "8.rx", "receive freq", "rx frequency"],
    "tx_freq":      ["tx freq", "8.tx", "6. tx", "transmit freq", "tx frequency"],
    "rx_tone":      ["rx tone", "7. rx tone", "rx tone/nac", "rx pl", "rec tone"],
    "tx_tone":      ["tx tone", "9. tx tone", "tx tone/nac", "tx pl", "xmt tone"],
    "mode":         ["mode a", "10. mode", "mode a,", "mode (a"],
    "config":       ["channel config", "3. channel config", "ch config"],
    "eligible":     ["eligible", "5. eligible"],
    "remarks":      ["remarks", "11. remarks", "comment"],
    "nw_rx":        ["n/w 7", "n/w rx"],
    "nw_tx":        ["n/w 9", "n/w tx"],
}

_CHIRP_COL_KEYWORDS: list[str] = [
    "location", "name", "frequency", "duplex", "offset",
]

_REVIEW_MARKER = "name_8"   # presence indicates our own Review CSV


def _norm(s: object) -> str:
    return str(s).strip().lower() if s is not None else ""


def detect_format(
    header_row: list[object],
) -> Literal["chirp", "review", "ics217a", "unknown"]:
    normed = [_norm(c) for c in header_row]
    if _REVIEW_MARKER in normed:
        return "review"
    if all(k in normed for k in _CHIRP_COL_KEYWORDS):
        return "chirp"
    # ICS-217A: must have at least channel_name + one of rx_freq/tx_freq
    has_name = any(
        any(kw in n for kw in _ICS217A_COL_KEYWORDS["channel_name"])
        for n in normed
    )
    has_freq = any(
        any(kw in n for kw in _ICS217A_COL_KEYWORDS["rx_freq"])
        or any(kw in n for kw in _ICS217A_COL_KEYWORDS["tx_freq"])
        for n in normed
    )
    if has_name and has_freq:
        return "ics217a"
    return "unknown"


def find_header_row(
    rows: list[list[object]],
) -> tuple[int, Literal["chirp", "review", "ics217a", "unknown"]] | tuple[None, None]:
    for i, row in enumerate(rows[:20]):
        if not any(c for c in row):
            continue
        fmt = detect_format(row)
        if fmt != "unknown":
            return i, fmt
    return None, None


def map_ics217a_columns(header_row: list[object]) -> dict[str, int]:
    col_map: dict[str, int] = {}
    for ci, cell in enumerate(header_row):
        n = _norm(cell)
        for key, keywords in _ICS217A_COL_KEYWORDS.items():
            if key in col_map:
                continue
            if any(kw in n for kw in keywords):
                col_map[key] = ci
    return col_map


def map_chirp_columns(header_row: list[object]) -> dict[str, int]:
    return {_norm(c): i for i, c in enumerate(header_row) if c is not None}


# ---------------------------------------------------------------------------
# ICS-217A row → Channel
# ---------------------------------------------------------------------------

def _cell(row: list[object], col_map: dict[str, int], key: str) -> str:
    idx = col_map.get(key)
    if idx is None or idx >= len(row):
        return ""
    return str(row[idx]).strip() if row[idx] is not None else ""


def _infer_narrow(
    channel_name: str, mode_field: str, freq_narrow: bool | None
) -> tuple[bool, list[str]]:
    notes: list[str] = []
    if freq_narrow is not None:
        return freq_narrow, notes
    if mode_field.strip().upper() in ("D", "M"):
        notes.append("narrow assumed from Mode field")
        return True, notes
    if re.search(r"\bD\b|D$", channel_name.strip()):
        notes.append("narrow assumed from 'D' suffix in channel name")
        return True, notes
    return False, notes


def _is_blank_row(row: list[object]) -> bool:
    return not any(str(c).strip() for c in row if c is not None)


def extract_ics217a_channels(
    rows: list[list[object]],
    header_idx: int,
    col_map: dict[str, int],
    options: CodeplugOptions,
    source_sheet: str,
    source_file: str,
    start_location: int = 0,
) -> list[Channel]:
    channels: list[Channel] = []
    location = start_location

    for row_idx, row in enumerate(rows[header_idx + 1 :], start=header_idx + 1):
        if _is_blank_row(row):
            continue

        name_raw = _cell(row, col_map, "channel_name")
        if not name_raw:
            continue
        # Skip repeated header rows
        if any(kw in name_raw.lower() for kw in ("channel name", "talkgroup")):
            continue

        rx_raw = _cell(row, col_map, "rx_freq")
        tx_raw = _cell(row, col_map, "tx_freq")
        rx_tone_raw = _cell(row, col_map, "rx_tone")
        tx_tone_raw = _cell(row, col_map, "tx_tone")
        mode_raw = _cell(row, col_map, "mode")
        remarks_raw = _cell(row, col_map, "remarks")
        nw_rx_raw = _cell(row, col_map, "nw_rx")
        nw_tx_raw = _cell(row, col_map, "nw_tx")

        # Merge separate N/W column into freq string for R10 template
        if nw_rx_raw and not re.search(r"[NnWw]$", rx_raw):
            rx_raw = rx_raw + " " + nw_rx_raw.strip()
        if nw_tx_raw and not re.search(r"[NnWw]$", tx_raw):
            tx_raw = tx_raw + " " + nw_tx_raw.strip()

        notes: list[str] = []

        try:
            rx_freq, rx_narrow, fn = parse_frequency(rx_raw)
            notes.extend(fn)
        except FrequencyParseError as e:
            log.warning("row %d: %s", row_idx, e)
            continue

        # TX freq optional; default to RX (simplex)
        if tx_raw:
            try:
                tx_freq, tx_narrow, fn = parse_frequency(tx_raw)
                notes.extend(fn)
            except FrequencyParseError as e:
                log.warning("row %d TX: %s", row_idx, e)
                tx_freq = rx_freq
                tx_narrow = rx_narrow
        else:
            tx_freq = rx_freq
            tx_narrow = rx_narrow

        # Narrow determination: prefer RX freq suffix, then TX, then name/mode
        freq_narrow = rx_narrow if rx_narrow is not None else tx_narrow
        narrow, n2 = _infer_narrow(name_raw, mode_raw, freq_narrow)
        notes.extend(n2)

        if round(abs(tx_freq - rx_freq), 6) < 0.0005:
            notes.append("simplex (TX freq equals RX freq)")

        tx_tone, tn = parse_tone(tx_tone_raw)
        notes.extend(tn)
        rx_tone, rn = parse_tone(rx_tone_raw)
        notes.extend(rn)

        # For DMR channels, extract TalkGroup from remarks then channel name
        if tx_tone.mode == "DMR":
            tg = parse_talkgroup(remarks_raw) or parse_talkgroup(name_raw)
            tx_tone.talkgroup = tg
            rx_tone.talkgroup = tg

        channels.append(Channel(
            location=location,
            source_name=name_raw,
            rx_freq=rx_freq,
            tx_freq=tx_freq,
            narrow=narrow,
            tx_tone=tx_tone,
            rx_tone=rx_tone,
            mode=mode_raw.strip().upper() or "A",
            remarks=remarks_raw,
            notes=notes,
            source_sheet=source_sheet,
            source_file=source_file,
        ))
        location += 1

    return channels


# ---------------------------------------------------------------------------
# CHIRP / Review CSV row → Channel
# ---------------------------------------------------------------------------

def extract_chirp_channels(
    rows: list[list[object]],
    header_idx: int,
    col_map: dict[str, int],  # lowercase key → col index
    fmt: Literal["chirp", "review"],
    options: CodeplugOptions,
    source_file: str,
    start_location: int = 0,
) -> list[Channel]:
    channels: list[Channel] = []
    location = start_location

    def get(row: list[object], key: str) -> str:
        idx = col_map.get(key)
        if idx is None or idx >= len(row):
            return ""
        return str(row[idx]).strip() if row[idx] is not None else ""

    for row in rows[header_idx + 1 :]:
        if _is_blank_row(row):
            continue

        freq_s = get(row, "frequency")
        if not freq_s:
            continue

        try:
            rx_freq = round(float(freq_s), 6)
        except ValueError:
            log.warning("skipping row with bad frequency: %r", freq_s)
            continue

        duplex = get(row, "duplex")
        try:
            offset = round(float(get(row, "offset") or "0"), 6)
        except ValueError:
            offset = 0.0

        if duplex == "+":
            tx_freq = round(rx_freq + offset, 6)
        elif duplex == "-":
            tx_freq = round(rx_freq - offset, 6)
        else:
            tx_freq = rx_freq

        mode_s = get(row, "mode")
        narrow = mode_s.upper() == "NFM"

        tone_s = get(row, "tone")
        try:
            rtone = float(get(row, "rtonefreq") or "88.5")
        except ValueError:
            rtone = 88.5
        try:
            ctone = float(get(row, "ctonefreq") or "88.5")
        except ValueError:
            ctone = 88.5
        try:
            dtcs = int(get(row, "dtcscode") or "23")
        except ValueError:
            dtcs = 23
        dtcs_pol = get(row, "dtcspolarity") or "NN"

        # Reconstruct DMR tone from dedicated columns (ColorCode / TimeSlot)
        cc_s = get(row, "colorcode").strip()
        ts_s = get(row, "timeslot").strip()
        try:
            cc = int(cc_s) if cc_s else None
        except ValueError:
            cc = None
        try:
            ts = int(ts_s) if ts_s else None
        except ValueError:
            ts = None

        tx_tone = ToneInfo(mode="", raw="")
        rx_tone = ToneInfo(mode="", raw="")
        tg_s = get(row, "talkgroup").strip()
        try:
            tg = int(tg_s) if tg_s else None
        except ValueError:
            tg = None

        if cc is not None and ts is not None:
            raw_dmr = f"CC{cc}/TS{ts}"
            tx_tone = ToneInfo(mode="DMR", raw=raw_dmr, color_code=cc, timeslot=ts, talkgroup=tg)
            rx_tone = ToneInfo(mode="DMR", raw=raw_dmr, color_code=cc, timeslot=ts, talkgroup=tg)
        elif tone_s == "Tone":
            tx_tone = ToneInfo(mode="Tone", ctcss_freq=rtone, raw=str(rtone))
        elif tone_s == "TSQL":
            tx_tone = ToneInfo(mode="Tone", ctcss_freq=rtone, raw=str(rtone))
            rx_tone = ToneInfo(mode="Tone", ctcss_freq=ctone, raw=str(ctone))
        elif tone_s == "DTCS":
            tx_tone = ToneInfo(mode="DTCS", dcs_code=dtcs, dcs_polarity=dtcs_pol, raw=str(dtcs))

        comment = get(row, "comment")
        remarks = comment

        # Restore source_name from Review CSV or fall back to Name column
        if fmt == "review":
            source_name = get(row, "_sourcename") or get(row, f"name_{options.name_len}") or get(row, "name_16") or ""
        else:
            source_name = get(row, "name") or ""

        sf = get(row, "_sourcefile") or source_file
        raw_notes = get(row, "_notes")
        notes = [n.strip() for n in raw_notes.split("|") if n.strip()] if raw_notes else []
        if fmt == "chirp" and not fmt == "review":
            notes.insert(0, "re-imported from CHIRP CSV — original name may be truncated")

        channels.append(Channel(
            location=location,
            source_name=source_name,
            rx_freq=rx_freq,
            tx_freq=tx_freq,
            narrow=narrow,
            tx_tone=tx_tone,
            rx_tone=rx_tone,
            remarks=remarks,
            notes=notes,
            source_file=sf,
        ))
        location += 1

    return channels
