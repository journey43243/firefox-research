import pytest
import tempfile
import sqlite3
import json
import os
from pathlib import Path
from unittest.mock import Mock, MagicMock

@pytest.fixture
def temp_profile_dir():
    """Создает временную директорию профиля Firefox."""
    with tempfile.TemporaryDirectory() as tmpdir:
        profile_path = Path(tmpdir) / "test_profile"
        profile_path.mkdir()

        # Создаем places.sqlite с тестовыми данными
        db_path = profile_path / "places.sqlite"
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()

        # Создаем таблицу moz_places
        cursor.execute('''
            CREATE TABLE moz_places (
                id INTEGER PRIMARY KEY,
                url TEXT,
                title TEXT,
                visit_count INTEGER,
                typed INTEGER,
                last_visit_date INTEGER
            )
        ''')

        # Добавляем тестовые данные
        test_data = [
            (1, 'https://example.com', 'Example', 5, 1, 1704067200000000),
            (2, 'https://test.com', 'Test Site', 3, 0, 1704153600000000),
        ]
        cursor.executemany(
            'INSERT INTO moz_places VALUES (?, ?, ?, ?, ?, ?)',
            test_data
        )
        conn.commit()
        conn.close()

        # Создаем extensions.json
        extensions_data = {
            "schemaVersion": 1,
            "addons": [
                {
                    "id": "test@extension.com",
                    "type": "extension",
                    "defaultLocale": {
                        "name": "Test Extension",
                        "description": "Test extension description"
                    },
                    "version": "1.0.0",
                    "active": True,
                    "userDisabled": False,
                    "installDate": 1704067200000,
                    "updateDate": 1704153600000,
                    "path": "/test/path.xpi",
                    "sourceURI": "https://addons.mozilla.org",
                    "location": "app-profile"
                }
            ]
        }

        with open(profile_path / "extensions.json", "w") as f:
            json.dump(extensions_data, f)

        yield profile_path

@pytest.fixture
def mock_log_interface():
    """Мок интерфейса логирования."""
    mock_log = Mock()
    mock_log.Info = Mock()
    mock_log.Warn = Mock()
    mock_log.Error = Mock()
    mock_log.Debug = Mock()
    return mock_log

@pytest.fixture
def mock_db_interface():
    """Мок интерфейса базы данных."""
    mock_db = Mock()
    mock_db._cursor = Mock()
    mock_db._connection = Mock()
    mock_db.ExecCommit = Mock()
    mock_db.Commit = Mock()
    mock_db.SaveSQLiteDatabaseFromRamToFile = Mock()
    return mock_db

@pytest.fixture
def metadata_fixture(mock_log_interface, temp_profile_dir):
    """Фикстура метаданных для стратегий."""
    class Metadata:
        def __init__(self):
            self.logInterface = mock_log_interface
            self.dbReadInterface = Mock()
            self.caseFolder = temp_profile_dir.parent
            self.profileId = 1
            self.profilePath = str(temp_profile_dir)

    return Metadata()

# Регистрация маркеров
def pytest_configure(config):
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line(
        "markers", "integration: integration tests"
    )
    config.addinivalue_line(
        "markers", "unit: unit tests"
    )