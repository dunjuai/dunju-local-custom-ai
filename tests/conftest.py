"""Shared test setup: isolated temp database, fixed token, Source/ on sys.path."""
import os
import sys
import tempfile
from pathlib import Path

import pytest

_TMP = Path(tempfile.mkdtemp(prefix="dunju-test-"))
os.environ["DUNJU_DB_PATH"] = str(_TMP / "data" / "test.db")
os.environ["DUNJU_TOKEN"] = "test-token"
(_TMP / "data").mkdir(parents=True, exist_ok=True)

SOURCE = Path(__file__).resolve().parent.parent / "Source"
sys.path.insert(0, str(SOURCE))

TOKEN = "test-token"
AUTH = {"X-Dunju-Token": TOKEN}


@pytest.fixture(scope="session")
def client():
    from fastapi.testclient import TestClient
    import main
    with TestClient(main.app, base_url="http://127.0.0.1") as c:
        yield c
