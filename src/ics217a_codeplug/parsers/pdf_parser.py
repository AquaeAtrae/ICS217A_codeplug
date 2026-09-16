# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 AquaeAtrae
from __future__ import annotations

import logging
from pathlib import Path
from typing import Iterator

from ..models import Channel, CodeplugOptions
from .base import Parser
from ._table_logic import (
    find_header_row,
    map_ics217a_columns,
    extract_ics217a_channels,
)

log = logging.getLogger(__name__)

_TABLE_SETTINGS = {
    "vertical_strategy": "lines",
    "horizontal_strategy": "lines",
    "snap_tolerance": 5,
}


class PdfParser(Parser):
    def __init__(self, options: CodeplugOptions, ocr: bool = False) -> None:
        super().__init__(options)
        self.ocr = ocr

    @classmethod
    def can_handle(cls, path: Path) -> bool:
        return path.suffix.lower() == ".pdf"

    def parse(self, source: Path | None = None) -> Iterator[Channel]:
        assert source is not None

        # Tier 1: AcroForm fields (optional dependency)
        acroform_channels = list(self._try_acroform(source))
        if acroform_channels:
            yield from acroform_channels
            return

        # Tier 2: text-layer table extraction
        import pdfplumber

        location = self.options.start_location
        with pdfplumber.open(str(source)) as pdf:
            for page in pdf.pages:
                tables = page.extract_tables(_TABLE_SETTINGS)
                if not tables and self.ocr:
                    tables = self._ocr_tables(page)
                for table in (tables or []):
                    rows: list[list[object]] = [
                        [cell for cell in row] for row in table
                    ]
                    header_idx, fmt = find_header_row(rows)
                    if header_idx is None:
                        continue
                    col_map = map_ics217a_columns(rows[header_idx])
                    channels = extract_ics217a_channels(
                        rows, header_idx, col_map,
                        self.options, f"p{page.page_number}", source.name, location,
                    )
                    location += len(channels)
                    yield from channels

    def _try_acroform(self, source: Path) -> list[Channel]:
        try:
            from pypdf import PdfReader
        except ImportError:
            return []

        try:
            reader = PdfReader(str(source))
            fields = reader.get_fields()
            if not fields:
                return []
            log.debug("AcroForm fields found in %s", source.name)
            # AcroForm parsing for ICS-217A is form-specific; emit a warning
            # and return empty so callers fall through to text extraction.
            log.warning(
                "%s has AcroForm fields but AcroForm-to-channel mapping is not "
                "yet implemented — falling back to text extraction.",
                source.name,
            )
            return []
        except Exception as e:
            log.debug("AcroForm check failed for %s: %s", source.name, e)
            return []

    def _ocr_tables(self, page: object) -> list[list[list[str | None]]]:
        try:
            import pytesseract
            from PIL import Image
        except ImportError:
            log.warning("OCR requested but pytesseract/Pillow not installed (pip install ics217a-codeplug[ocr])")
            return []

        img = page.to_image(resolution=200).original  # type: ignore[attr-defined]
        data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)

        # Group text items into rows by y-coordinate (tolerance 15px) then columns
        items: list[tuple[int, int, str]] = [
            (data["top"][i], data["left"][i], data["text"][i])
            for i in range(len(data["text"]))
            if data["text"][i].strip()
        ]
        if not items:
            return []

        items.sort(key=lambda t: (t[0], t[1]))
        rows: list[list[str]] = []
        current_row: list[str] = []
        last_top = items[0][0]
        for top, _left, text in items:
            if abs(top - last_top) > 15:
                if current_row:
                    rows.append(current_row)
                current_row = [text]
                last_top = top
            else:
                current_row.append(text)
        if current_row:
            rows.append(current_row)

        return [rows] if rows else []
