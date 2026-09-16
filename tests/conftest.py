from pathlib import Path
import pytest

SAMPLES = Path(__file__).parent.parent / "samples"


@pytest.fixture
def v3_xlsx():
    return SAMPLES / "20240724 - ics form 217a, R1D6 (v3) AJB.xlsx"


@pytest.fixture
def r10d1_xlsx():
    return SAMPLES / "ICS Form 217a Comm Resource Avail Worksheet Region 10 District 1.xlsx"


@pytest.fixture
def consolidated_xlsx():
    return SAMPLES / "Consolidated ICS-217.xlsx"


@pytest.fixture
def r1d3_xls():
    return SAMPLES / "R1-D3 ICS217A UPDATE 03-07-21.xls"


@pytest.fixture
def v3_docx():
    return SAMPLES / "ICS form 217a, R1D6 (V3).docx"


@pytest.fixture
def r10d1_pdf():
    return SAMPLES / "ICS Form 217a Comm Resource Avail Worksheet Region 10 District 1.pdf"


@pytest.fixture
def v3_pdf():
    return SAMPLES / "ICS form 217a, R1D6 (V3).pdf"


@pytest.fixture
def default_options():
    from ics217a_codeplug.models import CodeplugOptions
    return CodeplugOptions()
