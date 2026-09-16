import pytest
from ics217a_codeplug.parsers.pdf_parser import PdfParser


class TestPdfParser:
    def test_parses_channels(self, r10d1_pdf, default_options):
        channels = list(PdfParser(default_options).parse(r10d1_pdf))
        assert len(channels) >= 5

    def test_frequencies_valid(self, r10d1_pdf, default_options):
        channels = list(PdfParser(default_options).parse(r10d1_pdf))
        for ch in channels:
            assert ch.rx_freq > 0

    def test_no_exception_on_v3_pdf(self, v3_pdf, default_options):
        channels = list(PdfParser(default_options).parse(v3_pdf))
        assert isinstance(channels, list)
