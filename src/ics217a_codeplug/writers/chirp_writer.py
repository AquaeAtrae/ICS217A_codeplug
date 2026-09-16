# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 AquaeAtrae
from __future__ import annotations

import csv
import io
import sys
from pathlib import Path
from typing import Iterable

from ..models import Channel, CodeplugOptions, NAME_LENGTHS
from ..utils import resolve_tone_mode, _build_comment_str
from . import register_writer
from .base import Writer
from .review_writer import _NAME_COLS

CHIRP_COLUMNS = [
    "Location", "Name", "Frequency", "Duplex", "Offset", "Tone",
    "rToneFreq", "cToneFreq", "DtcsCode", "DtcsPolarity", "Mode",
    "TStep", "Skip", "Comment", "URCALL", "RPT1CALL", "RPT2CALL", "DVCODE",
    "ColorCode", "TimeSlot", "TalkGroup",
]

_META_COLS = set(_NAME_COLS) | {"_Band", "_Protocol", "_SourceFile", "_SourceName", "_Notes"}


@register_writer
class ChirpWriter(Writer):
    format_name = "chirp"

    def write(self, channels: Iterable[Channel], dest: Path | None) -> str:
        buf = io.StringIO()
        writer = csv.DictWriter(
            buf, fieldnames=CHIRP_COLUMNS, lineterminator="\r\n", extrasaction="ignore"
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
        comment = _build_comment_str(ch)
        chirp_mode = "NFM" if ch.narrow else "FM"
        return {
            "Location":    ch.location,
            "Name":        ch.name(self.options.name_len),
            "Frequency":   f"{ch.rx_freq:.6f}",
            "Duplex":      ch.duplex,
            "Offset":      f"{ch.offset:.6f}",
            "Tone":        tone,
            "rToneFreq":   f"{rtone:.1f}",
            "cToneFreq":   f"{ctone:.1f}",
            "DtcsCode":    f"{dtcs:03d}",
            "DtcsPolarity": dtcs_pol,
            "Mode":        chirp_mode,
            "TStep":       "5.00",
            "Skip":        "",
            "Comment":     comment,
            "URCALL": "", "RPT1CALL": "", "RPT2CALL": "", "DVCODE": "",
            "ColorCode":  "" if ch.color_code is None else ch.color_code,
            "TimeSlot":   "" if ch.timeslot is None else ch.timeslot,
            "TalkGroup":  "" if ch.talkgroup is None else ch.talkgroup,
        }

    # ------------------------------------------------------------------
    # Finalize path: read a Review CSV, select Name_N, strip meta columns

    def finalize_from_review(self, review_path: Path, dest: Path | None) -> str:
        name_col = f"Name_{self.options.name_len}"
        fallback_col = f"Name_{NAME_LENGTHS[0]}"

        buf = io.StringIO()
        writer = csv.DictWriter(
            buf, fieldnames=CHIRP_COLUMNS, lineterminator="\r\n", extrasaction="ignore"
        )
        writer.writeheader()

        with review_path.open(newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames or []
            if name_col not in fieldnames:
                available = [c for c in fieldnames if c.startswith("Name_")]
                chosen = available[0] if available else "Name"
                print(
                    f"Warning: Name_{self.options.name_len} not found; "
                    f"using {chosen!r} instead.",
                    file=sys.stderr,
                )
                name_col = chosen

            for row in reader:
                freq_s = row.get("Frequency", "")
                try:
                    float(freq_s)
                except ValueError:
                    print(
                        f"Warning: row {row.get('Location', '?')} has invalid "
                        f"Frequency {freq_s!r} — writing anyway.",
                        file=sys.stderr,
                    )
                duplex = row.get("Duplex", "")
                if duplex not in ("", "+", "-", "split"):
                    print(
                        f"Warning: row {row.get('Location', '?')} has unexpected "
                        f"Duplex {duplex!r}.",
                        file=sys.stderr,
                    )

                out_row = {k: row.get(k, "") for k in CHIRP_COLUMNS}
                # Strip all meta columns; Name comes from the selected Name_N column
                out_row["Name"] = row.get(name_col, row.get(fallback_col, ""))
                writer.writerow(out_row)

        output = buf.getvalue()
        if dest is not None:
            with dest.open("w", newline="", encoding="utf-8") as f:
                f.write(output)
            return ""
        return output
