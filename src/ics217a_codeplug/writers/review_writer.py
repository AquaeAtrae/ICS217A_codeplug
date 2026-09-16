# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 AquaeAtrae
from __future__ import annotations

import csv
import io
from pathlib import Path
from typing import Iterable

from ..models import Channel, CodeplugOptions, NAME_LENGTHS
from ..utils import resolve_tone_mode, _build_comment_str
from . import register_writer
from .base import Writer

_CHIRP_COLS = [
    "Location", "Frequency", "Duplex", "Offset", "Tone",
    "rToneFreq", "cToneFreq", "DtcsCode", "DtcsPolarity", "Mode",
    "TStep", "Skip", "Comment", "URCALL", "RPT1CALL", "RPT2CALL", "DVCODE",
    "ColorCode", "TimeSlot", "TalkGroup",
]

_NAME_COLS = [f"Name_{n}" for n in NAME_LENGTHS]

REVIEW_COLUMNS = (
    ["Location"]
    + _NAME_COLS
    + _CHIRP_COLS[1:]       # Frequency … DVCODE (Location already listed)
    + ["_Band", "_Protocol", "_SourceFile", "_SourceName", "_Notes"]
)


def _build_comment(ch: Channel) -> str:
    return _build_comment_str(ch)


@register_writer
class ReviewWriter(Writer):
    format_name = "review"

    def write(self, channels: Iterable[Channel], dest: Path | None) -> str:
        buf = io.StringIO()
        writer = csv.DictWriter(
            buf, fieldnames=REVIEW_COLUMNS, lineterminator="\r\n", extrasaction="ignore"
        )
        writer.writeheader()
        for ch in channels:
            writer.writerow(self._channel_to_row(ch))
        output = buf.getvalue()
        if dest is not None:
            with dest.open("w", newline="", encoding="utf-8") as f:
                f.write(output)
            return ""
        return output

    def _channel_to_row(self, ch: Channel) -> dict:
        tone, rtone, ctone, dtcs, dtcs_pol = resolve_tone_mode(ch.tx_tone, ch.rx_tone)
        comment = _build_comment(ch)
        chirp_mode = "NFM" if ch.narrow else "FM"

        row: dict = {
            "Location": ch.location,
            "Frequency": f"{ch.rx_freq:.6f}",
            "Duplex":    ch.duplex,
            "Offset":    f"{ch.offset:.6f}",
            "Tone":      tone,
            "rToneFreq": f"{rtone:.1f}",
            "cToneFreq": f"{ctone:.1f}",
            "DtcsCode":  f"{dtcs:03d}",
            "DtcsPolarity": dtcs_pol,
            "Mode":      chirp_mode,
            "TStep":     "5.00",
            "Skip":      "",
            "Comment":   comment,
            "URCALL": "", "RPT1CALL": "", "RPT2CALL": "", "DVCODE": "",
            "ColorCode":   "" if ch.color_code is None else ch.color_code,
            "TimeSlot":    "" if ch.timeslot is None else ch.timeslot,
            "TalkGroup":   "" if ch.talkgroup is None else ch.talkgroup,
            "_Band":       ch.band,
            "_Protocol":   ch.protocol,
            "_SourceFile": ch.source_file,
            "_SourceName": ch.source_name,
            "_Notes":      " | ".join(ch.notes),
        }
        for n in NAME_LENGTHS:
            row[f"Name_{n}"] = ch.name(n)
        return row
