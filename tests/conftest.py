"""Shared test fixtures."""

from pathlib import Path

import pytest

from src.database import Database
from src.repository import Repository


@pytest.fixture
def database(tmp_path: Path) -> Database:
    value = Database(tmp_path / "lucarne.db")
    value.initialize()
    return value


@pytest.fixture
def repository(database: Database) -> Repository:
    return Repository(database)
