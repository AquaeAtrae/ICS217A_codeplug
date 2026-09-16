import pytest
from ics217a_codeplug.utils import (
    classify_band,
    infer_protocol,
    parse_frequency,
    parse_talkgroup,
    parse_tone,
    resolve_tone_mode,
    FrequencyParseError,
)
from ics217a_codeplug.models import ToneInfo, Channel


# ---------------------------------------------------------------------------
# classify_band
# ---------------------------------------------------------------------------

class TestClassifyBand:
    # HF amateur bands
    def test_160m(self): assert classify_band(1.900) == "160m"
    def test_80m(self): assert classify_band(3.985) == "80m"
    def test_60m_low(self): assert classify_band(5.3305) == "60m"
    def test_60m_high(self): assert classify_band(5.4035) == "60m"
    def test_40m(self): assert classify_band(7.200) == "40m"
    def test_30m(self): assert classify_band(10.125) == "30m"
    def test_20m(self): assert classify_band(14.225) == "20m"
    def test_17m(self): assert classify_band(18.100) == "17m"
    def test_15m(self): assert classify_band(21.300) == "15m"
    def test_12m(self): assert classify_band(24.940) == "12m"
    def test_10m(self): assert classify_band(28.400) == "10m"

    # HF inter-band catch-all (MARS/SHARES territory)
    def test_hf_between_160_80(self): assert classify_band(2.5) == "HF"    # WWV
    def test_hf_between_80_60(self): assert classify_band(4.5) == "HF"
    def test_hf_between_60_40(self): assert classify_band(6.0) == "HF"
    def test_hf_between_40_30(self): assert classify_band(9.0) == "HF"
    def test_hf_between_20_17(self): assert classify_band(15.0) == "HF"    # WWV

    # MARS near 40m edge stays in 40m
    def test_mars_near_40m(self): assert classify_band(7.291) == "40m"

    # Service bands
    def test_cb_low(self): assert classify_band(26.965) == "CB"
    def test_cb_mid(self): assert classify_band(27.185) == "CB"   # ch 19
    def test_cb_high(self): assert classify_band(27.405) == "CB"
    def test_cb_above(self): assert classify_band(27.500) == "HF"

    def test_air_low(self): assert classify_band(108.0) == "Air"
    def test_air_mid(self): assert classify_band(122.8) == "Air"  # UNICOM
    def test_air_emergency(self): assert classify_band(121.5) == "Air"
    def test_air_high(self): assert classify_band(135.9) == "Air"

    def test_murs_ch1(self): assert classify_band(151.820) == "MURS"
    def test_murs_ch3(self): assert classify_band(151.940) == "MURS"
    def test_murs_ch4(self): assert classify_band(154.570) == "MURS"
    def test_murs_ch5(self): assert classify_band(154.600) == "MURS"
    def test_murs_gap_is_vhf(self): assert classify_band(152.0) == "VHF"

    def test_marine_ch16(self): assert classify_band(156.800) == "Marine"
    def test_marine_ch6(self): assert classify_band(156.300) == "Marine"

    def test_noaa_wx_low(self): assert classify_band(162.400) == "NOAA-WX"
    def test_noaa_wx_high(self): assert classify_band(162.550) == "NOAA-WX"

    def test_gmrs_frs_ch1(self): assert classify_band(462.5625) == "GMRS/FRS"
    def test_gmrs_frs_ch14(self): assert classify_band(467.7125) == "GMRS/FRS"
    def test_gmrs_frs_output(self): assert classify_band(462.550) == "GMRS/FRS"

    # Broad catch-alls
    def test_vhf_lo_6m(self): assert classify_band(52.525) == "VHF-Lo"
    def test_vhf_2m(self): assert classify_band(146.52) == "VHF"
    def test_vhf_noaa_rx(self): assert classify_band(162.55) in ("NOAA-WX", "VHF")
    def test_220(self): assert classify_band(223.5) == "220"
    def test_uhf_70cm(self): assert classify_band(446.0) == "UHF"
    def test_uhf_public_safety(self): assert classify_band(460.0) == "UHF"
    def test_700(self): assert classify_band(769.0) == "700"
    def test_800(self): assert classify_band(851.0) == "800"
    def test_900(self): assert classify_band(900.0) == "900"
    def test_unknown(self): assert classify_band(1200.0) == "Unknown"


# ---------------------------------------------------------------------------
# parse_frequency
# ---------------------------------------------------------------------------

class TestParseFrequency:
    def test_plain(self):
        f, n, notes = parse_frequency("146.94")
        assert f == pytest.approx(146.94)
        assert n is None

    def test_narrow_suffix(self):
        f, n, _ = parse_frequency("441.9375 N")
        assert f == pytest.approx(441.9375)
        assert n is True

    def test_wide_suffix(self):
        f, n, _ = parse_frequency("146.940 W")
        assert f == pytest.approx(146.940)
        assert n is False

    def test_strips_plus(self):
        f, n, _ = parse_frequency("147.195+")
        assert f == pytest.approx(147.195)

    def test_ieee_rounding(self):
        # Python float() already collapses 147.44999999999999 → 147.45 at parse time;
        # round(147.45, 6) == 147.45 so no rounding note is expected here.
        f, _, notes = parse_frequency("147.44999999999999")
        assert f == pytest.approx(147.45)

    def test_empty_raises(self):
        with pytest.raises(FrequencyParseError):
            parse_frequency("")

    def test_malformed_double_dot(self):
        with pytest.raises(FrequencyParseError):
            parse_frequency("5.330.5")

    def test_non_numeric_raises(self):
        with pytest.raises(FrequencyParseError):
            parse_frequency("N/A")

    def test_khz_detection(self):
        f, _, notes = parse_frequency("7103.000")
        assert f == pytest.approx(7.103)
        assert any("kHz" in n for n in notes)

    def test_khz_detection_80m(self):
        f, _, _ = parse_frequency("3947.000")
        assert f == pytest.approx(3.947)

    def test_khz_detection_with_mode_suffix(self):
        # "7103.000 USB Dial" → strip mode → "7103.000" → kHz → 7.103 MHz
        f, _, notes = parse_frequency("7103.000 USB Dial")
        assert f == pytest.approx(7.103)
        assert any("kHz" in n for n in notes)

    def test_vhf_not_khz(self):
        # 146.940 is in MHz range (< 1000), should not be converted
        f, _, notes = parse_frequency("146.940")
        assert f == pytest.approx(146.940)
        assert not any("kHz" in n for n in notes)


# ---------------------------------------------------------------------------
# parse_tone
# ---------------------------------------------------------------------------

class TestParseTone:
    def test_csq(self):
        ti, notes = parse_tone("CSQ")
        assert ti.mode == ""
        assert not notes

    def test_empty(self):
        ti, _ = parse_tone("")
        assert ti.mode == ""

    def test_ctcss(self):
        ti, notes = parse_tone("103.5")
        assert ti.mode == "Tone"
        assert ti.ctcss_freq == pytest.approx(103.5)
        assert not notes

    def test_ctcss_integer(self):
        ti, _ = parse_tone("100")
        assert ti.mode == "Tone"
        assert ti.ctcss_freq == pytest.approx(100.0)

    def test_dcs(self):
        ti, _ = parse_tone("D023")
        assert ti.mode == "DTCS"
        assert ti.dcs_code == 23

    def test_dmr_parsed_structurally(self):
        ti, notes = parse_tone("CC1/TS 2")
        assert ti.mode == "DMR"
        assert ti.color_code == 1
        assert ti.timeslot == 2
        assert ti.raw == "CC1/TS 2"
        assert not notes  # no note needed; data is in structured fields

    def test_dmr_double_digit_cc(self):
        ti, _ = parse_tone("CC15/TS1")
        assert ti.color_code == 15
        assert ti.timeslot == 1

    def test_unrecognized_stored_in_comment(self):
        ti, notes = parse_tone("AllCall*")
        assert ti.mode == ""
        assert any("not recognized" in n for n in notes)


# ---------------------------------------------------------------------------
# resolve_tone_mode
# ---------------------------------------------------------------------------

class TestResolveToneMode:
    def test_both_empty(self):
        chirp, rt, ct, dtcs, pol = resolve_tone_mode(ToneInfo(), ToneInfo())
        assert chirp == ""

    def test_tx_ctcss_only(self):
        tx = ToneInfo(mode="Tone", ctcss_freq=103.5)
        chirp, rt, ct, _, _ = resolve_tone_mode(tx, ToneInfo())
        assert chirp == "Tone"
        assert rt == pytest.approx(103.5)

    def test_both_ctcss(self):
        tx = ToneInfo(mode="Tone", ctcss_freq=103.5)
        rx = ToneInfo(mode="Tone", ctcss_freq=103.5)
        chirp, rt, ct, _, _ = resolve_tone_mode(tx, rx)
        assert chirp == "TSQL"
        assert rt == pytest.approx(103.5)
        assert ct == pytest.approx(103.5)

    def test_dtcs(self):
        tx = ToneInfo(mode="DTCS", dcs_code=23, dcs_polarity="NN")
        chirp, _, _, dtcs, pol = resolve_tone_mode(tx, ToneInfo())
        assert chirp == "DTCS"
        assert dtcs == 23


# ---------------------------------------------------------------------------
# Channel properties
# ---------------------------------------------------------------------------

class TestChannelProperties:
    def _ch(self, rx, tx):
        return Channel(location=0, source_name="Test", rx_freq=rx, tx_freq=tx)

    def test_duplex_negative(self):
        ch = self._ch(146.94, 146.34)
        assert ch.duplex == "-"
        assert ch.offset == pytest.approx(0.6)

    def test_duplex_positive(self):
        ch = self._ch(444.0, 449.0)
        assert ch.duplex == "+"
        assert ch.offset == pytest.approx(5.0)

    def test_duplex_simplex(self):
        ch = self._ch(146.52, 146.52)
        assert ch.duplex == ""
        assert ch.offset == pytest.approx(0.0)

    def test_name_truncation(self):
        ch = Channel(location=0, source_name="16V01 Primary VHF", rx_freq=146.94, tx_freq=146.34)
        assert ch.name(8) == "16V01 Pr"
        assert ch.name(16) == "16V01 Primary VH"  # "16V01 Primary VHF" is 17 chars; [:16]
        assert ch.name(17) == "16V01 Primary VHF"

    def test_name_strips_whitespace(self):
        ch = Channel(location=0, source_name="  16V1  ", rx_freq=146.94, tx_freq=146.34)
        assert ch.name(8) == "16V1"

    def test_band_vhf(self):
        ch = Channel(location=0, source_name="X", rx_freq=146.94, tx_freq=146.34)
        assert ch.band == "VHF"

    def test_band_uhf(self):
        ch = Channel(location=0, source_name="X", rx_freq=446.0, tx_freq=446.0)
        assert ch.band == "UHF"  # 446 MHz is UHF; GMRS/FRS starts at 462.55


# ---------------------------------------------------------------------------
# infer_protocol
# ---------------------------------------------------------------------------

def _proto(*, mode="A", narrow=False, tx_raw="", rx_raw="", band="VHF",
           sheet="VHF", name="", remarks="", comment=""):
    return infer_protocol(
        mode=mode, narrow=narrow, tx_tone_raw=tx_raw, rx_tone_raw=rx_raw,
        band=band, source_sheet=sheet, source_name=name,
        remarks=remarks, comment=comment,
    )


class TestParseTalkgroup:
    def test_direct_number(self):
        assert parse_talkgroup("C0l0rad0 Wide DMR TG 3108") == 3108

    def test_callsign_before_number(self):
        assert parse_talkgroup("KB0VGD BM TG K0IMT 1108410") == 1108410

    def test_short_tg(self):
        assert parse_talkgroup('B0ulder "RM Wide" DMR TG 700') == 700

    def test_allcall_returns_none(self):
        assert parse_talkgroup("simplex DMR | TX:AllCall*") is None

    def test_no_tg_returns_none(self):
        assert parse_talkgroup("R1D6 Primary VHF") is None

    def test_channel_talkgroup_property(self):
        from ics217a_codeplug.models import Channel, ToneInfo
        ch = Channel(
            location=0, source_name="16D01", rx_freq=446.975, tx_freq=441.975,
            remarks="C0l0rad0 Wide DMR TG 3108",
            tx_tone=ToneInfo(mode="DMR", raw="CC1/TS 1", color_code=1, timeslot=1, talkgroup=3108),
        )
        assert ch.talkgroup == 3108


class TestInferProtocol:
    def test_fm_wide(self):
        assert _proto(narrow=False, band="VHF") == "FM"

    def test_nfm_narrow(self):
        assert _proto(narrow=True, band="VHF") == "NFM"

    def test_dmr_from_cc_ts_raw(self):
        assert _proto(tx_raw="CC1/TS 2", band="UHF", narrow=True) == "DMR"

    def test_dmr_from_comment(self):
        assert _proto(comment="KB0VGD BM TG 3108 | TX:CC7/TS 2", band="UHF") == "DMR"

    def test_dmr_from_sheet(self):
        assert _proto(sheet="DMR", band="UHF", narrow=True) == "DMR"

    def test_p25_from_name(self):
        assert _proto(name="P25 Trunked", band="UHF") == "P25"

    def test_p25_from_nac(self):
        assert _proto(tx_raw="NAC 293", band="UHF") == "P25"

    def test_dstar(self):
        assert _proto(name="D-STAR Gateway", band="UHF") == "D-STAR"

    def test_fusion(self):
        assert _proto(name="YSF Node", band="VHF") == "Fusion"

    def test_vara_fm(self):
        assert _proto(name="VARA FM Node", band="VHF") == "VARA FM"

    def test_vara_hf(self):
        assert _proto(name="SLC K7DAV VARA HF", band="40m") == "VARA"

    def test_vara_in_comment(self):
        assert _proto(comment="VARA HF Winlink", band="40m") == "VARA"

    def test_packet_from_sheet(self):
        assert _proto(sheet="PACKET", band="VHF") == "Packet"

    def test_packet_from_name(self):
        assert _proto(name="APRS 144.390", band="VHF") == "Packet"

    def test_packet_baud(self):
        assert _proto(name="1200 Baud Packet", band="VHF") == "Packet"

    def test_hf_ssb_default(self):
        assert _proto(band="40m") == "SSB"

    def test_hf_cw(self):
        assert _proto(band="40m", name="CW Net") == "CW"

    def test_hf_am(self):
        assert _proto(band="HF", remarks="AM broadcast monitoring") == "AM"

    def test_channel_protocol_property_dmr(self):
        ch = Channel(
            location=0, source_name="16D01", rx_freq=446.975, tx_freq=441.975,
            narrow=True, source_sheet="DMR",
            tx_tone=ToneInfo(mode="", raw="CC7/TS 2"),
            rx_tone=ToneInfo(mode="", raw="CC7/TS 2"),
        )
        assert ch.protocol == "DMR"

    def test_channel_protocol_property_fm(self):
        ch = Channel(
            location=0, source_name="16V1", rx_freq=146.94, tx_freq=146.34,
            narrow=False, source_sheet="VHF",
            tx_tone=ToneInfo(mode="Tone", ctcss_freq=103.5),
        )
        assert ch.protocol == "FM"
