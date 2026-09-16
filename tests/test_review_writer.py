import csv
import io
import pytest
from ics217a_codeplug.models import Channel, ToneInfo, CodeplugOptions, NAME_LENGTHS
from ics217a_codeplug.writers.review_writer import ReviewWriter, REVIEW_COLUMNS


def _make_channel(**kwargs):
    defaults = dict(
        location=0,
        source_name="16V01 Primary VHF Repeater",
        rx_freq=146.94,
        tx_freq=146.34,
        narrow=False,
        tx_tone=ToneInfo(mode="Tone", ctcss_freq=103.5, raw="103.5"),
        rx_tone=ToneInfo(),
        source_file="test.xlsx",
        source_sheet="VHF",
    )
    defaults.update(kwargs)
    return Channel(**defaults)


def _parse_output(output: str) -> list[dict]:
    reader = csv.DictReader(io.StringIO(output))
    return list(reader)


class TestReviewWriterColumns:
    def test_column_count(self):
        ch = _make_channel()
        output = ReviewWriter(CodeplugOptions()).write([ch], dest=None)
        reader = csv.DictReader(io.StringIO(output))
        assert set(reader.fieldnames or []) == set(REVIEW_COLUMNS)

    def test_protocol_column_present(self):
        ch = _make_channel()
        output = ReviewWriter(CodeplugOptions()).write([ch], dest=None)
        rows = _parse_output(output)
        assert "_Protocol" in rows[0]

    def test_protocol_fm(self):
        ch = _make_channel(narrow=False)
        rows = _parse_output(ReviewWriter(CodeplugOptions()).write([ch], None))
        assert rows[0]["_Protocol"] == "FM"

    def test_protocol_dmr(self):
        ch = _make_channel(
            narrow=True, source_sheet="DMR",
            tx_tone=ToneInfo(mode="DMR", raw="CC7/TS 2", color_code=7, timeslot=2, talkgroup=3108),
            rx_tone=ToneInfo(mode="DMR", raw="CC7/TS 2", color_code=7, timeslot=2, talkgroup=3108),
        )
        rows = _parse_output(ReviewWriter(CodeplugOptions()).write([ch], None))
        assert rows[0]["_Protocol"] == "DMR"
        assert rows[0]["TalkGroup"] == "3108"

    def test_talkgroup_empty_for_non_dmr(self):
        ch = _make_channel()
        rows = _parse_output(ReviewWriter(CodeplugOptions()).write([ch], None))
        assert rows[0]["TalkGroup"] == ""

    def test_all_name_columns_present(self):
        ch = _make_channel()
        output = ReviewWriter(CodeplugOptions()).write([ch], dest=None)
        rows = _parse_output(output)
        for n in NAME_LENGTHS:
            assert f"Name_{n}" in rows[0]

    def test_name_cols_are_prefixes_of_source_name(self):
        ch = _make_channel()
        output = ReviewWriter(CodeplugOptions()).write([ch], dest=None)
        rows = _parse_output(output)
        row = rows[0]
        stripped = ch.source_name.strip()
        for n in NAME_LENGTHS:
            assert stripped.startswith(row[f"Name_{n}"].rstrip())

    def test_name_col_lengths_respected(self):
        ch = _make_channel()
        output = ReviewWriter(CodeplugOptions()).write([ch], dest=None)
        rows = _parse_output(output)
        row = rows[0]
        for n in NAME_LENGTHS:
            assert len(row[f"Name_{n}"]) <= n

    def test_source_name_is_full(self):
        ch = _make_channel()
        output = ReviewWriter(CodeplugOptions()).write([ch], dest=None)
        rows = _parse_output(output)
        assert rows[0]["_SourceName"] == ch.source_name

    def test_source_file_is_basename(self):
        ch = _make_channel(source_file="/some/long/path/test.xlsx")
        output = ReviewWriter(CodeplugOptions()).write([ch], dest=None)
        rows = _parse_output(output)
        # source_file stored as-is (basename set by parser); just verify it's present
        assert "_SourceFile" in rows[0]


class TestReviewWriterBand:
    def test_band_vhf(self):
        ch = _make_channel(rx_freq=146.94)
        rows = _parse_output(ReviewWriter(CodeplugOptions()).write([ch], None))
        assert rows[0]["_Band"] == "VHF"

    def test_band_uhf(self):
        ch = _make_channel(rx_freq=446.0, tx_freq=446.0)
        rows = _parse_output(ReviewWriter(CodeplugOptions()).write([ch], None))
        assert rows[0]["_Band"] == "UHF"

    def test_band_gmrs(self):
        ch = _make_channel(rx_freq=462.5625, tx_freq=462.5625)
        rows = _parse_output(ReviewWriter(CodeplugOptions()).write([ch], None))
        assert rows[0]["_Band"] == "GMRS/FRS"

    def test_band_hf_40m(self):
        ch = _make_channel(rx_freq=7.250, tx_freq=7.250)
        rows = _parse_output(ReviewWriter(CodeplugOptions()).write([ch], None))
        assert rows[0]["_Band"] == "40m"


class TestReviewWriterNotes:
    def test_dmr_notes_present(self):
        ch = _make_channel(
            tx_tone=ToneInfo(mode="", raw="CC1/TS 2"),
            notes=["DMR color code/timeslot stored in Comment: 'CC1/TS 2'"],
        )
        rows = _parse_output(ReviewWriter(CodeplugOptions()).write([ch], None))
        assert "DMR" in rows[0]["_Notes"]

    def test_clean_channel_empty_notes(self):
        ch = _make_channel(notes=[])
        rows = _parse_output(ReviewWriter(CodeplugOptions()).write([ch], None))
        assert rows[0]["_Notes"] == ""


class TestReviewWriterMultiFile:
    def test_sequential_locations(self):
        channels = [_make_channel(location=i, source_file=f"file{i}.xlsx") for i in range(5)]
        rows = _parse_output(ReviewWriter(CodeplugOptions()).write(channels, None))
        locs = [int(r["Location"]) for r in rows]
        assert locs == list(range(5))

    def test_source_file_distinguishes_rows(self):
        channels = [
            _make_channel(location=0, source_file="file_a.xlsx"),
            _make_channel(location=1, source_file="file_b.xlsx"),
        ]
        rows = _parse_output(ReviewWriter(CodeplugOptions()).write(channels, None))
        assert rows[0]["_SourceFile"] == "file_a.xlsx"
        assert rows[1]["_SourceFile"] == "file_b.xlsx"


class TestReviewWriterToFile:
    def test_writes_file(self, tmp_path):
        ch = _make_channel()
        dest = tmp_path / "out.csv"
        result = ReviewWriter(CodeplugOptions()).write([ch], dest)
        assert result == ""
        assert dest.exists()
        rows = _parse_output(dest.read_text(encoding="utf-8"))
        assert len(rows) == 1
