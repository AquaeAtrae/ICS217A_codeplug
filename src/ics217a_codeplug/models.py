# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 AquaeAtrae
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

ToneMode = Literal["", "Tone", "TSQL", "DTCS", "Cross", "DMR"]

NAME_LENGTHS: tuple[int, ...] = (8, 10, 12, 16)


@dataclass
class ToneInfo:
    mode: ToneMode = ""
    ctcss_freq: float = 88.5
    dcs_code: int = 23
    dcs_polarity: str = "NN"
    raw: str = ""
    # DMR-specific fields (populated when mode == "DMR")
    color_code: int | None = None   # 0–15
    timeslot: int | None = None     # 1 or 2
    talkgroup: int | None = None    # DMR TalkGroup ID


@dataclass
class Channel:
    location: int        # CHIRP memory slot
    source_name: str     # original untruncated name; never modified after parse
    rx_freq: float       # MHz
    tx_freq: float       # MHz
    narrow: bool = False
    tx_tone: ToneInfo = field(default_factory=ToneInfo)
    rx_tone: ToneInfo = field(default_factory=ToneInfo)
    mode: str = "A"      # A=Analog, D=Digital, M=Mixed (raw ICS-217A field)
    remarks: str = ""
    notes: list[str] = field(default_factory=list)
    source_sheet: str = ""
    source_file: str = ""

    def name(self, max_len: int) -> str:
        return self.source_name.strip()[:max_len]

    @property
    def color_code(self) -> int | None:
        return self.tx_tone.color_code

    @property
    def timeslot(self) -> int | None:
        return self.tx_tone.timeslot

    @property
    def talkgroup(self) -> int | None:
        return self.tx_tone.talkgroup

    @property
    def band(self) -> str:
        from .utils import classify_band
        return classify_band(self.rx_freq)

    @property
    def protocol(self) -> str:
        from .utils import infer_protocol, _build_comment_str
        return infer_protocol(
            mode=self.mode,
            narrow=self.narrow,
            tx_tone_raw=self.tx_tone.raw,
            rx_tone_raw=self.rx_tone.raw,
            band=self.band,
            source_sheet=self.source_sheet,
            source_name=self.source_name,
            remarks=self.remarks,
            comment=_build_comment_str(self),
        )

    @property
    def duplex(self) -> str:
        delta = round(self.tx_freq - self.rx_freq, 6)
        if abs(delta) < 0.0005:
            return ""
        return "+" if delta > 0 else "-"

    @property
    def offset(self) -> float:
        return round(abs(self.tx_freq - self.rx_freq), 6)


@dataclass
class CodeplugOptions:
    name_len: int = 8          # which Name_N column becomes CHIRP Name at finalize
    start_location: int = 0
    skip_digital: bool = False
    output_format: str = "chirp"
