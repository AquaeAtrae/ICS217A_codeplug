import csv
import io
import pytest
from ics217a_codeplug.models import Channel, ToneInfo, CodeplugOptions
from ics217a_codeplug.writers.chirp_writer import ChirpWriter, CHIRP_COLUMNS
from ics217a_codeplug.writers.review_writer import ReviewWriter


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
    )
    defaults.update(kwargs)
    return Channel(**defaults)


def _parse(output: str) -> list[dict]:
    return list(csv.DictReader(io.StringIO(output)))


class TestChirpWriterColumns:
    def test_exactly_18_columns(self):
        ch = _make_channel()
        output = ChirpWriter(CodeplugOptions()).write([ch], None)
        reader = csv.DictReader(io.StringIO(output))
        assert list(reader.fieldnames) == CHIRP_COLUMNS

    def test_no_meta_columns(self):
        ch = _make_channel()
        output = ChirpWriter(CodeplugOptions()).write([ch], None)
        reader = csv.DictReader(io.StringIO(output))
        for meta in ("_Band", "_Protocol", "_SourceFile", "_SourceName", "_Notes", "Name_8"):
            assert meta not in (reader.fieldnames or [])


class TestChirpWriterValues:
    def test_frequency_format(self):
        ch = _make_channel(rx_freq=146.94)
        row = _parse(ChirpWriter(CodeplugOptions()).write([ch], None))[0]
        assert row["Frequency"] == "146.940000"

    def test_duplex_and_offset(self):
        ch = _make_channel(rx_freq=146.94, tx_freq=146.34)
        row = _parse(ChirpWriter(CodeplugOptions()).write([ch], None))[0]
        assert row["Duplex"] == "-"
        assert row["Offset"] == "0.600000"

    def test_simplex(self):
        ch = _make_channel(rx_freq=146.52, tx_freq=146.52)
        row = _parse(ChirpWriter(CodeplugOptions()).write([ch], None))[0]
        assert row["Duplex"] == ""
        assert row["Offset"] == "0.000000"

    def test_name_len_8(self):
        ch = _make_channel()
        row = _parse(ChirpWriter(CodeplugOptions(name_len=8)).write([ch], None))[0]
        assert len(row["Name"]) <= 8
        assert row["Name"] == "16V01 Pr"

    def test_name_len_16(self):
        ch = _make_channel()
        row = _parse(ChirpWriter(CodeplugOptions(name_len=16)).write([ch], None))[0]
        assert row["Name"] == "16V01 Primary VH"  # source_name[:16]

    def test_ctcss_tone(self):
        ch = _make_channel()
        row = _parse(ChirpWriter(CodeplugOptions()).write([ch], None))[0]
        assert row["Tone"] == "Tone"
        assert row["rToneFreq"] == "103.5"

    def test_mode_fm(self):
        ch = _make_channel(narrow=False)
        row = _parse(ChirpWriter(CodeplugOptions()).write([ch], None))[0]
        assert row["Mode"] == "FM"

    def test_mode_nfm(self):
        ch = _make_channel(narrow=True)
        row = _parse(ChirpWriter(CodeplugOptions()).write([ch], None))[0]
        assert row["Mode"] == "NFM"

    def test_dmr_dedicated_columns(self):
        ch = _make_channel(
            narrow=True,
            tx_tone=ToneInfo(mode="DMR", raw="CC1/TS 1", color_code=1, timeslot=1),
            rx_tone=ToneInfo(mode="DMR", raw="CC1/TS 1", color_code=1, timeslot=1),
            remarks="BrandMeister TG 31082",
        )
        row = _parse(ChirpWriter(CodeplugOptions()).write([ch], None))[0]
        # CC/TS no longer in Comment
        assert "CC1" not in row["Comment"]
        assert row["Tone"] == ""
        assert row["ColorCode"] == "1"
        assert row["TimeSlot"] == "1"
        # Remarks still in comment
        assert "BrandMeister" in row["Comment"]


class TestFinalizeFromReview:
    def test_name_len_selected(self, tmp_path):
        ch = _make_channel()
        review_path = tmp_path / "review.csv"
        ReviewWriter(CodeplugOptions()).write([ch], review_path)

        for name_len in (8, 10, 12, 16):
            opts = CodeplugOptions(name_len=name_len)
            out = ChirpWriter(opts).finalize_from_review(review_path, None)
            row = _parse(out)[0]
            assert row["Name"] == ch.name(name_len), f"name_len={name_len}"

    def test_output_has_chirp_columns(self, tmp_path):
        ch = _make_channel()
        review_path = tmp_path / "review.csv"
        ReviewWriter(CodeplugOptions()).write([ch], review_path)

        out = ChirpWriter(CodeplugOptions()).finalize_from_review(review_path, None)
        reader = csv.DictReader(io.StringIO(out))
        assert list(reader.fieldnames) == CHIRP_COLUMNS

    def test_user_edits_preserved(self, tmp_path):
        ch = _make_channel()
        review_path = tmp_path / "review.csv"
        ReviewWriter(CodeplugOptions()).write([ch], review_path)

        # Simulate user editing Frequency in the review file
        content = review_path.read_text(encoding="utf-8")
        content = content.replace("146.940000", "147.000000")
        review_path.write_text(content, encoding="utf-8")

        out = ChirpWriter(CodeplugOptions()).finalize_from_review(review_path, None)
        row = _parse(out)[0]
        assert row["Frequency"] == "147.000000"

    def test_writes_to_file(self, tmp_path):
        ch = _make_channel()
        review_path = tmp_path / "review.csv"
        out_path = tmp_path / "chirp.csv"
        ReviewWriter(CodeplugOptions()).write([ch], review_path)
        result = ChirpWriter(CodeplugOptions()).finalize_from_review(review_path, out_path)
        assert result == ""
        assert out_path.exists()
