# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 AquaeAtrae
from __future__ import annotations

import csv
import logging
from pathlib import Path
from typing import Iterator

from ..models import Channel, CodeplugOptions
from .base import Parser
from ._table_logic import (
    find_header_row,
    map_ics217a_columns,
    map_chirp_columns,
    extract_ics217a_channels,
    extract_chirp_channels,
)

log = logging.getLogger(__name__)


class SpreadsheetParser(Parser):
    _SUFFIXES = {".xlsx", ".xls", ".csv"}

    @classmethod
    def can_handle(cls, path: Path) -> bool:
        return path.suffix.lower() in cls._SUFFIXES

    def parse(self, source: Path | None = None) -> Iterator[Channel]:
        assert source is not None
        suffix = source.suffix.lower()
        location = self.options.start_location

        if suffix == ".csv":
            yield from self._parse_csv(source, location)
        elif suffix == ".xls":
            yield from self._parse_xls(source, location)
        else:
            yield from self._parse_xlsx(source, location)

    # ------------------------------------------------------------------

    def _rows_to_channels(
        self,
        rows: list[list[object]],
        sheet_name: str,
        source_file: str,
        start_location: int,
    ) -> tuple[list[Channel], int]:
        header_idx, fmt = find_header_row(rows)
        if header_idx is None:
            log.debug("no header found in sheet %r", sheet_name)
            return [], start_location

        if fmt in ("chirp", "review"):
            col_map = map_chirp_columns(rows[header_idx])
            channels = extract_chirp_channels(
                rows, header_idx, col_map, fmt,
                self.options, source_file, start_location,
            )
        else:
            col_map = map_ics217a_columns(rows[header_idx])
            channels = extract_ics217a_channels(
                rows, header_idx, col_map,
                self.options, sheet_name, source_file, start_location,
            )

        return channels, start_location + len(channels)

    # ------------------------------------------------------------------

    def _parse_csv(self, source: Path, start_location: int) -> Iterator[Channel]:
        with source.open(newline="", encoding="utf-8-sig") as f:
            rows: list[list[object]] = list(csv.reader(f))
        channels, _ = self._rows_to_channels(
            rows, "CSV", source.name, start_location
        )
        yield from channels

    def _parse_xlsx(self, source: Path, start_location: int) -> Iterator[Channel]:
        import openpyxl
        wb = openpyxl.load_workbook(source, read_only=True, data_only=True)
        location = start_location
        for ws in wb.worksheets:
            rows = [[cell.value for cell in row] for row in ws.iter_rows()]
            channels, location = self._rows_to_channels(
                rows, ws.title, source.name, location
            )
            yield from channels
        wb.close()

    def _parse_xls(self, source: Path, start_location: int) -> Iterator[Channel]:
        import xlrd
        wb = xlrd.open_workbook(str(source))
        location = start_location
        for sheet in wb.sheets():
            rows = [sheet.row_values(i) for i in range(sheet.nrows)]
            channels, location = self._rows_to_channels(
                rows, sheet.name, source.name, location
            )
            yield from channels
