import os
from pathlib import Path


TEST_DB_PATH = Path(
    os.environ.get(
        "RPA_MCP_SYNC_DB_PATH",
        Path(__file__).resolve().parents[1] / "runtime" / "pytest-tasks.db",
    )
)
os.environ["RPA_MCP_SYNC_DB_PATH"] = str(TEST_DB_PATH)


def pytest_sessionstart(session):
    if TEST_DB_PATH.exists():
        TEST_DB_PATH.unlink()
