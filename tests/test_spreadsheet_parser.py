import pytest
from ics217a_codeplug.parsers.spreadsheet_parser import SpreadsheetParser


class TestV3Xlsx:
    def test_parses_channels(self, v3_xlsx, default_options):
        channels = list(SpreadsheetParser(default_options).parse(v3_xlsx))
        assert len(channels) > 0

    def test_vhf_sheet_frequencies(self, v3_xlsx, default_options):
        channels = list(SpreadsheetParser(default_options).parse(v3_xlsx))
        vhf = [c for c in channels if c.source_sheet == "VHF"]
        assert len(vhf) >= 5
        freqs = [c.rx_freq for c in vhf]
        # All should be in VHF band
        assert all(136 <= f < 174 for f in freqs)

    def test_vhf_repeater_duplex(self, v3_xlsx, default_options):
        channels = list(SpreadsheetParser(default_options).parse(v3_xlsx))
        vhf = [c for c in channels if c.source_sheet == "VHF"]
        # Most Colorado VHF repeaters: TX < RX → duplex "-"
        repeaters = [c for c in vhf if c.duplex != ""]
        assert len(repeaters) > 0
        neg = sum(1 for c in repeaters if c.duplex == "-")
        assert neg >= len(repeaters) // 2  # majority should be negative offset

    def test_vhf_ctcss_tone(self, v3_xlsx, default_options):
        channels = list(SpreadsheetParser(default_options).parse(v3_xlsx))
        vhf = [c for c in channels if c.source_sheet == "VHF"]
        toned = [c for c in vhf if c.tx_tone.mode == "Tone"]
        assert len(toned) > 0

    def test_dmr_sheet_narrow(self, v3_xlsx, default_options):
        channels = list(SpreadsheetParser(default_options).parse(v3_xlsx))
        dmr = [c for c in channels if c.source_sheet == "DMR"]
        assert len(dmr) >= 5
        assert all(c.narrow for c in dmr)

    def test_dmr_tone_in_comment(self, v3_xlsx, default_options):
        channels = list(SpreadsheetParser(default_options).parse(v3_xlsx))
        dmr = [c for c in channels if c.source_sheet == "DMR"]
        # DMR channels should have CC/TS info stored in raw
        dmr_toned = [c for c in dmr if c.tx_tone.raw]
        assert len(dmr_toned) > 0

    def test_sequential_locations(self, v3_xlsx, default_options):
        channels = list(SpreadsheetParser(default_options).parse(v3_xlsx))
        locs = [c.location for c in channels]
        assert locs == list(range(len(channels)))

    def test_source_file_set(self, v3_xlsx, default_options):
        channels = list(SpreadsheetParser(default_options).parse(v3_xlsx))
        assert all(c.source_file == v3_xlsx.name for c in channels)


class TestR10D1Xlsx:
    def test_parses_channels(self, r10d1_xlsx, default_options):
        channels = list(SpreadsheetParser(default_options).parse(r10d1_xlsx))
        assert len(channels) >= 5

    def test_frequencies_valid(self, r10d1_xlsx, default_options):
        channels = list(SpreadsheetParser(default_options).parse(r10d1_xlsx))
        for ch in channels:
            assert ch.rx_freq > 0, f"Non-positive freq {ch.rx_freq}"
            assert ch.rx_freq < 10000, f"Implausible freq {ch.rx_freq}"


class TestConsolidatedXlsx:
    def test_parses_channels(self, consolidated_xlsx, default_options):
        channels = list(SpreadsheetParser(default_options).parse(consolidated_xlsx))
        assert len(channels) > 0


class TestR1D3Xls:
    def test_parses_channels(self, r1d3_xls, default_options):
        channels = list(SpreadsheetParser(default_options).parse(r1d3_xls))
        assert len(channels) > 0

    def test_frequencies_valid(self, r1d3_xls, default_options):
        channels = list(SpreadsheetParser(default_options).parse(r1d3_xls))
        for ch in channels:
            assert ch.rx_freq > 0


class TestChirpRoundTrip:
    def test_review_csv_roundtrip(self, v3_xlsx, default_options, tmp_path):
        from ics217a_codeplug.writers.review_writer import ReviewWriter

        original = list(SpreadsheetParser(default_options).parse(v3_xlsx))
        assert original

        review_path = tmp_path / "review.csv"
        ReviewWriter(default_options).write(original, review_path)

        reimported = list(SpreadsheetParser(default_options).parse(review_path))
        assert len(reimported) == len(original)
        for orig, re in zip(original, reimported):
            assert re.rx_freq == pytest.approx(orig.rx_freq)
            assert re.tx_freq == pytest.approx(orig.tx_freq)
            assert re.narrow == orig.narrow

    def test_duplex_reconstruction(self, tmp_path, default_options):
        """CHIRP CSV Duplex +/- correctly reconstructs tx_freq."""
        from ics217a_codeplug.writers.chirp_writer import ChirpWriter
        import csv

        chirp_rows = (
            "Location,Name,Frequency,Duplex,Offset,Tone,rToneFreq,cToneFreq,"
            "DtcsCode,DtcsPolarity,Mode,TStep,Skip,Comment,URCALL,RPT1CALL,RPT2CALL,DVCODE\r\n"
            "0,RPT1,146.940000,-,0.600000,Tone,103.5,88.5,023,NN,FM,5.00,,,,,,\r\n"
            "1,SIMP,146.520000,,0.000000,,88.5,88.5,023,NN,FM,5.00,,,,,,\r\n"
            "2,UHF,449.000000,+,5.000000,,88.5,88.5,023,NN,FM,5.00,,,,,,\r\n"
        )
        csv_path = tmp_path / "chirp.csv"
        csv_path.write_text(chirp_rows, encoding="utf-8")

        channels = list(SpreadsheetParser(default_options).parse(csv_path))
        assert len(channels) == 3
        assert channels[0].tx_freq == pytest.approx(146.340)
        assert channels[1].tx_freq == pytest.approx(146.520)
        assert channels[2].tx_freq == pytest.approx(454.0)
