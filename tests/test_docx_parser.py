import pytest
from ics217a_codeplug.parsers.docx_parser import DocxParser
from ics217a_codeplug.parsers.spreadsheet_parser import SpreadsheetParser


class TestDocxParser:
    def test_parses_channels(self, v3_docx, default_options):
        channels = list(DocxParser(default_options).parse(v3_docx))
        assert len(channels) >= 5

    def test_frequencies_vhf(self, v3_docx, default_options):
        channels = list(DocxParser(default_options).parse(v3_docx))
        vhf = [c for c in channels if 136 <= c.rx_freq < 174]
        assert len(vhf) > 0

    def test_source_file_set(self, v3_docx, default_options):
        channels = list(DocxParser(default_options).parse(v3_docx))
        assert all(c.source_file == v3_docx.name for c in channels)

    def test_frequencies_parseable(self, v3_docx, default_options):
        """All extracted channels should have valid positive frequencies."""
        channels = list(DocxParser(default_options).parse(v3_docx))
        assert len(channels) > 0
        for ch in channels:
            assert ch.rx_freq > 0, f"Invalid rx_freq {ch.rx_freq} for {ch.source_name!r}"
            assert ch.tx_freq > 0, f"Invalid tx_freq {ch.tx_freq} for {ch.source_name!r}"
