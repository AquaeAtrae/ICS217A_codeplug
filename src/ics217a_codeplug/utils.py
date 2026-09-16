# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 AquaeAtrae
from __future__ import annotations

import re
import logging
from .models import ToneInfo

log = logging.getLogger(__name__)


class FrequencyParseError(ValueError):
    pass


# ---------------------------------------------------------------------------
# HF amateur bands (Pass 1 — most specific)
# ---------------------------------------------------------------------------
_HF_BANDS: list[tuple[str, float, float]] = [
    ("160m",  1.800,  2.000),
    ("80m",   3.500,  4.000),
    ("60m",   5.330,  5.407),   # 5 US channelized freqs: 5.3305–5.4035 MHz
    ("40m",   7.000,  7.300),
    ("30m",  10.100, 10.150),   # WARC; CW/digital only
    ("20m",  14.000, 14.350),
    ("17m",  18.068, 18.168),   # WARC
    ("15m",  21.000, 21.450),
    ("12m",  24.890, 24.990),   # WARC
    ("10m",  28.000, 29.700),
]

# ---------------------------------------------------------------------------
# Named service bands (Pass 2 — specific allocations before broad catch-alls)
# Aviation checked before VHF-Lo; NOAA-WX checked before Marine.
# MURS has two non-contiguous sub-ranges.
# ---------------------------------------------------------------------------
_SERVICE_BANDS: list[tuple[str, float, float]] = [
    ("CB",       26.965,  27.406),   # Citizens Band 40 ch
    ("Air",     108.000, 136.000),   # aviation VOR/ILS/voice
    ("MURS",    151.815, 151.945),   # ch 1–3: 151.820, 151.880, 151.940
    ("MURS",    154.565, 154.605),   # ch 4–5: 154.570, 154.600
    ("Marine",  156.000, 162.026),   # ITU marine VHF
    ("NOAA-WX", 162.400, 162.551),   # 7 NOAA weather broadcast channels
    ("GMRS/FRS", 462.550, 467.726),  # GMRS outputs + shared FRS/GMRS ch 1–22
]

# ---------------------------------------------------------------------------
# Broad catch-all bands (Pass 3)
# ---------------------------------------------------------------------------
_CATCH_ALL_BANDS: list[tuple[str, float, float]] = [
    # HF catch-all covers inter-band HF: MARS, SHARES, ALE, maritime HF,
    # SWBC, WWV/WWVH. MARS frequencies that fall within named amateur bands
    # (Pass 1) get that band label; inter-band MARS freqs land here.
    ("HF",       0.100,  30.000),
    ("VHF-Lo",  30.000, 136.000),   # 6m amateur, low VHF commercial
    ("VHF",    136.000, 174.000),   # 2m amateur, commercial VHF hi
    ("220",    216.000, 225.000),   # 1.25m amateur
    ("UHF",    380.000, 512.000),   # 70cm amateur, commercial UHF, T-Band
    ("700",    698.000, 806.000),   # 700 MHz public safety / FirstNet
    ("800",    806.000, 870.000),   # 800 MHz public safety trunked / cellular
    ("900",    896.000, 941.000),   # 900 MHz trunked / ISM
]


def parse_talkgroup(text: str) -> int | None:
    """Extract a DMR TalkGroup number from a remarks or channel-name string.

    Handles formats seen in Colorado ARES ICS-217A forms:
      - "DMR TG 3108"                → 3108
      - "BM TG K0IMT 1108410"        → 1108410  (callsign between TG and number)
      - "simplex DMR | TX:AllCall*"  → None
    """
    m = _TG_RE.search(text)
    return int(m.group(1)) if m else None


def _build_comment_str(ch: object) -> str:
    """Build the CHIRP Comment field string for a channel.

    DMR color code and timeslot are NOT embedded here — they live in the
    dedicated ColorCode / TimeSlot columns.  Only truly unstructured raw
    strings (P25 NAC, unrecognized tones) are embedded in the comment.
    """
    parts = []
    remarks = getattr(ch, "remarks", "")
    tx_tone = getattr(ch, "tx_tone", None)
    rx_tone = getattr(ch, "rx_tone", None)
    if remarks:
        parts.append(remarks)
    # Only embed raw if mode is blank AND it's not a DMR tone (which has its own columns)
    if tx_tone and tx_tone.raw and tx_tone.mode == "":
        parts.append(f"TX:{tx_tone.raw}")
    if rx_tone and rx_tone.raw and rx_tone.mode == "" and rx_tone.raw != (tx_tone.raw if tx_tone else ""):
        parts.append(f"RX:{rx_tone.raw}")
    return " | ".join(parts)[:256]


_HF_BAND_LABELS = {b[0] for b in _HF_BANDS} | {"HF"}

_P25_NAC_RE   = re.compile(r"\bNAC\s*[0-9A-Fa-f]{3,4}\b|\bP-?25\b|\bAPCO\b", re.IGNORECASE)
_BAUD_RE      = re.compile(r"\b(1200|9600|300)\s*(BAUD|BD)?\b")


def infer_protocol(
    mode: str,
    narrow: bool,
    tx_tone_raw: str,
    rx_tone_raw: str,
    band: str,
    source_sheet: str,
    source_name: str,
    remarks: str,
    comment: str = "",
) -> str:
    """Return the most specific transmission protocol label for a channel.

    Checks in priority order: digital modes identified from tone/name/comment
    first, then analog modes inferred from band and bandwidth.
    """
    haystack = " ".join([
        source_name, remarks, comment, tx_tone_raw, rx_tone_raw,
    ]).upper()
    sheet = source_sheet.upper()

    # --- Digital modes ---
    if _DMR_RE.search(tx_tone_raw) or _DMR_RE.search(rx_tone_raw):
        return "DMR"
    if "DMR" in haystack or sheet == "DMR" or "BM TG" in haystack or "BRANDMEISTER" in haystack:
        return "DMR"

    if _P25_NAC_RE.search(haystack):
        return "P25"

    if "DSTAR" in haystack or "D-STAR" in haystack or "D STAR" in haystack:
        return "D-STAR"

    if "FUSION" in haystack or "YSF" in haystack or "C4FM" in haystack:
        return "Fusion"

    if "NXDN" in haystack:
        return "NXDN"

    # VARA FM before plain VARA
    if "VARA FM" in haystack or "VARAFM" in haystack:
        return "VARA FM"

    if "VARA" in haystack:
        return "VARA"

    if (
        "PACKET" in haystack
        or "AX.25" in haystack
        or "AX25" in haystack
        or "APRS" in haystack
        or sheet in ("PACKET", "PKT", "APRS")
        or _BAUD_RE.search(haystack)
    ):
        return "Packet"

    if "PACTOR" in haystack:
        return "Pactor"

    if "JS8" in haystack:
        return "JS8Call"

    if "WINLINK" in haystack:
        return "Winlink"

    # --- Analog modes ---
    # HF bands default to SSB (most common EmComm HF voice mode)
    if band in _HF_BAND_LABELS:
        if "CW" in haystack:
            return "CW"
        if "AM" in haystack:
            return "AM"
        return "SSB"

    # VHF / UHF / etc.
    if narrow:
        return "NFM"
    return "FM"


def classify_band(freq_mhz: float) -> str:
    for name, lo, hi in _HF_BANDS:
        if lo <= freq_mhz < hi:
            return name
    for name, lo, hi in _SERVICE_BANDS:
        if lo <= freq_mhz < hi:
            return name
    for name, lo, hi in _CATCH_ALL_BANDS:
        if lo <= freq_mhz < hi:
            return name
    return "Unknown"


# ---------------------------------------------------------------------------
# Frequency parsing
# ---------------------------------------------------------------------------

def parse_frequency(raw: str) -> tuple[float, bool | None, list[str]]:
    """Return (freq_mhz, is_narrow, notes).

    is_narrow is True/False when an N/W suffix was explicit, None otherwise.
    Raises FrequencyParseError on unparseable input.
    """
    notes: list[str] = []
    s = str(raw).strip()
    if not s:
        raise FrequencyParseError("empty frequency string")

    # Extract trailing N/W (narrow/wide) suffix
    is_narrow: bool | None = None
    m = re.search(r"[NnWw]$", s)
    if m:
        is_narrow = s[m.start()].upper() == "N"
        s = s[: m.start()].strip()

    # Strip trailing +/- offset indicators embedded in some templates
    s = s.rstrip("+-").strip()

    # Strip trailing mode/descriptor words (e.g. "FM W", "USB Dial", "LSB", "1200")
    # Keep stripping known suffixes until nothing changes.
    _MODE_WORDS = re.compile(
        r"\s+(USB|LSB|CW|AM|FM|NFM|SSB|DIAL|[NW]|\d{3,5})\s*$", re.IGNORECASE
    )
    prev = None
    while prev != s:
        prev = s
        s = _MODE_WORDS.sub("", s).strip()

    # Guard against multiple decimal points (e.g. "5.330.5" from HF entries)
    if s.count(".") > 1:
        raise FrequencyParseError(f"malformed frequency: {raw!r}")

    try:
        raw_float = float(s)
    except ValueError:
        raise FrequencyParseError(f"cannot parse frequency: {raw!r}")

    # Detect kHz entry for HF frequencies (e.g. "7103.000" means 7103 kHz = 7.103 MHz).
    # Range 1000–30000 maps unambiguously to the HF spectrum in kHz; no practical
    # public-service or amateur channel exists at 1–30 GHz.
    if 1000.0 <= raw_float < 30000.0:
        raw_float = raw_float / 1000.0
        notes.append(f"frequency interpreted as kHz -> {raw_float:.6f} MHz")

    rounded = round(raw_float, 6)
    if rounded != raw_float:
        notes.append(f"frequency rounded: {raw_float} -> {rounded}")

    return rounded, is_narrow, notes


# ---------------------------------------------------------------------------
# Tone parsing
# ---------------------------------------------------------------------------

_CTCSS_RE = re.compile(r"^\d{2,3}(\.\d{1,2})?$")
_DCS_RE   = re.compile(r"^D(\d{3})([NIni]?)$|^(\d{3})$")
_DMR_RE   = re.compile(r"CC\s*(\d+)\s*/\s*TS\s*(\d+)", re.IGNORECASE)  # groups: cc, ts
# TalkGroup: "TG <optional-callsign> <number>"
# The optional callsign token starts with a letter so the regex backtracks correctly
# to leave the trailing digit string for the capture group.
_TG_RE    = re.compile(r"\bTG\s+(?:[A-Z][A-Z0-9/]*\s+)*(\d+)", re.IGNORECASE)
_P25_RE   = re.compile(r"^[0-9A-Fa-f]{3,4}$")
_CSQ_RE   = re.compile(r"^(CSQ?|CS|PL\s*0|None|-)$", re.IGNORECASE)


def parse_tone(raw: str) -> tuple[ToneInfo, list[str]]:
    """Return (ToneInfo, notes)."""
    notes: list[str] = []
    s = str(raw).strip()

    if not s or _CSQ_RE.match(s):
        return ToneInfo(mode="", raw=s), notes

    m = _DMR_RE.search(s)
    if m:
        cc = int(m.group(1))
        ts = int(m.group(2))
        return ToneInfo(mode="DMR", raw=s, color_code=cc, timeslot=ts), notes

    if _CTCSS_RE.match(s):
        try:
            freq = float(s)
            return ToneInfo(mode="Tone", ctcss_freq=freq, raw=s), notes
        except ValueError:
            pass

    m = _DCS_RE.match(s)
    if m:
        code_str = m.group(1) or m.group(3)
        polarity = "NR" if (m.group(2) or "").upper() == "I" else "NN"
        return ToneInfo(mode="DTCS", dcs_code=int(code_str), dcs_polarity=polarity, raw=s), notes

    if _P25_RE.match(s) and not _CTCSS_RE.match(s):
        notes.append(f"P25 NAC stored in Comment: {s!r}")
        return ToneInfo(mode="", raw=s), notes

    notes.append(f"tone not recognized: {s!r} — stored in Comment")
    return ToneInfo(mode="", raw=s), notes


# ---------------------------------------------------------------------------
# Tone mode resolution for CHIRP output
# ---------------------------------------------------------------------------

def resolve_tone_mode(
    tx: ToneInfo, rx: ToneInfo
) -> tuple[str, float, float, int, str]:
    """Return (chirp_tone, rToneFreq, cToneFreq, DtcsCode, DtcsPolarity).

    DMR channels carry no analog squelch tone; the CHIRP Tone field is left
    blank and CC/TS data goes into the dedicated ColorCode/TimeSlot columns.
    """
    if tx.mode == "DMR":
        return "", 88.5, 88.5, 23, "NN"
    if tx.mode == "DTCS":
        return "DTCS", 88.5, 88.5, tx.dcs_code, tx.dcs_polarity
    if tx.mode == "Tone" and rx.mode == "Tone":
        return "TSQL", tx.ctcss_freq, rx.ctcss_freq, 23, "NN"
    if tx.mode == "Tone":
        return "Tone", tx.ctcss_freq, 88.5, 23, "NN"
    if rx.mode == "Tone":
        return "TSQL", 88.5, rx.ctcss_freq, 23, "NN"
    return "", 88.5, 88.5, 23, "NN"
