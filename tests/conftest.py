# Fixtures. Tests run against the real compose database, not mocks.
import pytest
from fastapi.testclient import TestClient

from app.db import get_connection
from app.main import app


@pytest.fixture(autouse=True)
def conn():
    with get_connection() as conn:
        conn.autocommit = True
        conn.execute("TRUNCATE events, charger_state")
        yield conn


@pytest.fixture
def client():
    return TestClient(app)
