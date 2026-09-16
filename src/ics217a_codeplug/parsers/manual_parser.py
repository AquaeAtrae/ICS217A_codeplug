# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 AquaeAtrae
from __future__ import annotations

from pathlib import Path
from typing import Iterator

from ..models import Channel, CodeplugOptions
from ..utils import parse_frequency, parse_tone, FrequencyParseError
from .base import Parser


class ManualParser(Parser):
    @classmethod
    def can_handle(cls, path: Path) -> bool:
        return False  # invoked directly by the `enter` CLI command

    def parse(self, source: Path | None = None) -> Iterator[Channel]:
        import click

        click.echo("ICS-217A Manual Entry Wizard")
        click.echo("Press Enter with a blank Name to finish.\n")

        location = self.options.start_location
        while True:
            name = click.prompt("Channel Name (blank to finish)", default="")
            if not name.strip():
                return

            rx_raw = click.prompt("RX Frequency (MHz)")
            tx_raw = click.prompt("TX Frequency (MHz)", default=rx_raw)
            tx_tone_raw = click.prompt("TX Tone/NAC", default="CSQ")
            rx_tone_raw = click.prompt("RX Tone/NAC", default="CSQ")
            nw = click.prompt("Narrow (N) or Wide (W)", default="W")
            remarks = click.prompt("Remarks", default="")

            notes: list[str] = []

            try:
                rx_freq, rx_narrow, fn = parse_frequency(rx_raw)
                notes.extend(fn)
            except FrequencyParseError as e:
                click.echo(f"  Bad RX frequency: {e} — try again.")
                continue

            try:
                tx_freq, _, fn = parse_frequency(tx_raw)
                notes.extend(fn)
            except FrequencyParseError as e:
                click.echo(f"  Bad TX frequency: {e} — try again.")
                continue

            if round(abs(tx_freq - rx_freq), 6) < 0.0005:
                notes.append("simplex (TX freq equals RX freq)")

            freq_narrow = rx_narrow
            narrow = freq_narrow if freq_narrow is not None else (nw.upper() == "N")

            tx_tone, tn = parse_tone(tx_tone_raw)
            notes.extend(tn)
            rx_tone, rn = parse_tone(rx_tone_raw)
            notes.extend(rn)

            yield Channel(
                location=location,
                source_name=name,
                rx_freq=rx_freq,
                tx_freq=tx_freq,
                narrow=narrow,
                tx_tone=tx_tone,
                rx_tone=rx_tone,
                remarks=remarks,
                notes=notes,
            )
            location += 1
