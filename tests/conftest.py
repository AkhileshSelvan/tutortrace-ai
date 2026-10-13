import pytest

from scripts.create_demo_assets import make_pdf, make_pptx
from tutortrace.persistence import Store


@pytest.fixture
def store(tmp_path):
    return Store(tmp_path / "library.sqlite3")


@pytest.fixture
def pdf_bytes():
    return make_pdf(("Kinetic energy is the energy of motion.", "", "Gravity changes potential energy."))


@pytest.fixture
def pptx_bytes():
    return make_pptx(("Photosynthesis converts light into chemical energy.", "", "Chlorophyll absorbs sunlight."))
