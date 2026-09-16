# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 AquaeAtrae
from __future__ import annotations

from pathlib import Path

from ..models import CodeplugOptions
from .base import Parser


def parser_for(path: Path, options: CodeplugOptions) -> Parser:
    from .spreadsheet_parser import SpreadsheetParser
    from .docx_parser import DocxParser
    from .pdf_parser import PdfParser

    for cls in (SpreadsheetParser, DocxParser, PdfParser):
        if cls.can_handle(path):
            return cls(options)
    raise ValueError(f"No parser available for suffix {path.suffix!r}")
