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


def _all_tables_as_rows(doc: object) -> list[list[list[str]]]:
    """Return every w:tbl found anywhere in the document (including textboxes).

    python-docx's doc.tables only finds top-level tables. ICS-217A docx files
    often embed the channel table inside a VML textbox shape, which lives inside
    a w:pict element. We walk the full XML tree to catch those.
    """
    from docx.oxml.ns import qn  # type: ignore[import]

    W_TBL = qn("w:tbl")
    W_TR  = qn("w:tr")
    W_TC  = qn("w:tc")
    W_T   = qn("w:t")

    tables: list[list[list[str]]] = []
    for tbl_elem in doc.element.body.iter(W_TBL):  # type: ignore[attr-defined]
        rows: list[list[str]] = []
        for tr_elem in tbl_elem.iterchildren(W_TR):
            cells: list[str] = []
            for tc_elem in tr_elem.iterchildren(W_TC):
                texts: list[str] = []
                for child in tc_elem.iterchildren():
                    if child.tag == W_TBL:
                        continue  # skip nested tables
                    for t_elem in child.iter(W_T):
                        texts.append(t_elem.text or "")
                cells.append("".join(texts).strip())
            if cells:
                rows.append(cells)
        if rows:
            tables.append(rows)
    return tables


class DocxParser(Parser):
    @classmethod
    def can_handle(cls, path: Path) -> bool:
        return path.suffix.lower() == ".docx"

    def parse(self, source: Path | None = None) -> Iterator[Channel]:
        assert source is not None
        import docx

        doc = docx.Document(str(source))
        location = self.options.start_location

        for table_idx, rows in enumerate(_all_tables_as_rows(doc)):
            header_idx, fmt = find_header_row(rows)  # type: ignore[arg-type]
            if header_idx is None:
                log.debug("table %d in %s: no ICS-217A header found", table_idx, source.name)
                continue

            col_map = map_ics217a_columns(rows[header_idx])  # type: ignore[arg-type]
            sheet_name = f"Table{table_idx + 1}"
            channels = extract_ics217a_channels(
                rows,  # type: ignore[arg-type]
                header_idx, col_map,
                self.options, sheet_name, source.name, location,
            )
            location += len(channels)
            yield from channels
