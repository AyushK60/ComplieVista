import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))


def pytest_configure(config):
    config.addinivalue_line("markers", "network: test requires internet access")


import pytest  # noqa: E402
from app.store.db import Store  # noqa: E402


@pytest.fixture()
def store(tmp_path):
    return Store(data_dir=tmp_path / "data")
