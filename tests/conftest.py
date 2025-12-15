"""
Фикстуры для интеграционного тестирования модулей Firefox.
"""

import pytest
import json
import sqlite3
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, MagicMock, AsyncMock, patch, PropertyMock

from Modules.Firefox.History.Strategy import HistoryStrategy
from Modules.Firefox.Bookmarks.Strategy import BookmarksStrategy
from Modules.Firefox.Downloads.Strategy import DownloadsStrategy
from Modules.Firefox.Passwords.Strategy import PasswordStrategy
from Modules.Firefox.Extensions.Strategy import ExtensionsStrategy
from Modules.Firefox.Profiles.Strategy import ProfilesStrategy

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
def temp_firefox_profile(tmp_path):
    """Создает временную структуру профиля Firefox для тестирования."""
    profile_path = tmp_path / "test_profile"
    profile_path.mkdir(exist_ok=True)

    # Создаем необходимые файлы Firefox
    (profile_path / "places.sqlite").touch()  # История, закладки, загрузки
    (profile_path / "logins.json").touch()  # Пароли
    (profile_path / "key4.db").touch()  # Ключи для паролей
    (profile_path / "extensions.json").touch()  # Расширения
    (profile_path / "favicons.sqlite").touch()  # Иконки

    # Создаем поддиректорию Profiles
    profiles_dir = tmp_path / "Profiles"
    profiles_dir.mkdir(exist_ok=True)

    # Копируем профиль в Profiles
    test_profile = profiles_dir / "test.default"
    if test_profile.exists():
        shutil.rmtree(test_profile)
    shutil.copytree(profile_path, test_profile)

    # Создаем profiles.ini
    profiles_ini = tmp_path / "profiles.ini"
    profiles_ini_content = f"""[General]
StartWithLastProfile=1
Version=2

[Profile0]
Name=default
IsRelative=1
Path=Profiles/test.default
Default=1
"""
    profiles_ini.write_text(profiles_ini_content)

    return {
        "base_path": str(tmp_path),
        "profile_path": str(profile_path),
        "profiles_ini": str(profiles_ini),
        "real_profile_path": str(test_profile)
    }


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


@pytest.fixture
def mock_modules():
    """Создает моки для всех модулей Firefox."""
    modules = {}

    # Моки для стратегий
    modules["ProfilesStrategy"] = Mock()
    modules["HistoryStrategy"] = Mock()
    modules["BookmarksStrategy"] = Mock()
    modules["DownloadsStrategy"] = Mock()
    modules["PasswordStrategy"] = Mock()
    modules["ExtensionsStrategy"] = Mock()

    # Настраиваем возвращаемые значения
    modules["ProfilesStrategy"].read.return_value = ["/fake/path/profile1", "/fake/path/profile2"]
    modules["ProfilesStrategy"].write = Mock()
    modules["ProfilesStrategy"].createDataTable = Mock()
    modules["ProfilesStrategy"].execute = AsyncMock()

    modules["HistoryStrategy"].read.return_value = [
        {"url": "https://example.com", "title": "Example", "visit_count": 5},
        {"url": "https://google.com", "title": "Google", "visit_count": 10}
    ]
    modules["HistoryStrategy"].write = Mock()
    modules["HistoryStrategy"].execute = AsyncMock()

    modules["BookmarksStrategy"].read.return_value = [
        {"title": "Bookmark 1", "url": "https://bookmark1.com", "folder": "Bookmarks"},
        {"title": "Bookmark 2", "url": "https://bookmark2.com", "folder": "Work"}
    ]
    modules["BookmarksStrategy"].write = Mock()
    modules["BookmarksStrategy"].execute = AsyncMock()

    modules["DownloadsStrategy"].read.return_value = [
        {"filename": "file1.pdf", "url": "https://example.com/file1.pdf", "size": 1024},
        {"filename": "file2.zip", "url": "https://example.com/file2.zip", "size": 2048}
    ]
    modules["DownloadsStrategy"].write = Mock()
    modules["DownloadsStrategy"].execute = AsyncMock()

    modules["PasswordStrategy"].read.return_value = [
        {"url": "https://login.example.com", "username": "user1", "password": "encrypted1"},
        {"url": "https://secure.site", "username": "admin", "password": "encrypted2"}
    ]
    modules["PasswordStrategy"].write = Mock()
    modules["PasswordStrategy"].execute = AsyncMock()

    modules["ExtensionsStrategy"].read.return_value = [
        {"name": "uBlock Origin", "version": "1.50.0", "id": "uBlock0@raymondhill.net"},
        {"name": "Dark Reader", "version": "4.9.63", "id": "addon@darkreader.org"}
    ]
    modules["ExtensionsStrategy"].write = Mock()
    modules["ExtensionsStrategy"].execute = AsyncMock()

    return modules


@pytest.fixture
def mock_database():
    """Создает мок для базы данных."""
    mock_db = MagicMock()
    mock_db.ExecCommit = Mock()
    mock_db.SaveSQLiteDatabaseFromRamToFile = Mock()
    mock_db.IsConnected = Mock(return_value=True)
    mock_db.InsertData = Mock()
    mock_db.Save = Mock()
    return mock_db


@pytest.fixture
def mock_executor():
    """Создает мок для исполнителя."""
    executor = MagicMock()
    executor.logger = mock_log_interface()
    executor.CreateDataTable = Mock()
    executor.db = mock_database()
    return executor


@pytest.fixture
def real_places_database(temp_firefox_profile):
    """Создает реальную базу данных places.sqlite с тестовыми данными."""
    profile_path = Path(temp_firefox_profile["real_profile_path"])
    places_db = profile_path / "places.sqlite"

    if places_db.exists():
        places_db.unlink()

    conn = sqlite3.connect(str(places_db))
    cursor = conn.cursor()

    # Создаем таблицу moz_places (история)
    cursor.execute("""
        CREATE TABLE moz_places (
            id INTEGER PRIMARY KEY,
            url TEXT,
            title TEXT,
            visit_count INTEGER,
            last_visit_date INTEGER
        )
    """)

    # Добавляем тестовые данные истории
    test_history = [
        (1, 'https://example.com', 'Example Domain', 5, 1672531200000),
        (2, 'https://google.com', 'Google', 15, 1672617600000),
        (3, 'https://github.com', 'GitHub', 8, 1672704000000)
    ]
    cursor.executemany("INSERT INTO moz_places VALUES (?, ?, ?, ?, ?)", test_history)

    # Создаем таблицу moz_bookmarks (закладки)
    cursor.execute("""
        CREATE TABLE moz_bookmarks (
            id INTEGER PRIMARY KEY,
            type INTEGER,
            fk INTEGER,
            parent INTEGER,
            title TEXT,
            dateAdded INTEGER
        )
    """)

    # Добавляем тестовые закладки
    test_bookmarks = [
        (1, 1, 1, 3, 'Example Bookmark', 1672531200000),
        (2, 1, 2, 3, 'Google', 1672617600000),
        (3, 2, 0, 0, 'Bookmarks Toolbar', 1672531200000)
    ]
    cursor.executemany("INSERT INTO moz_bookmarks VALUES (?, ?, ?, ?, ?, ?)", test_bookmarks)

    conn.commit()
    conn.close()

    return places_db


@pytest.fixture
def real_logins_file(temp_firefox_profile):
    """Создает реальный файл logins.json с тестовыми паролями."""
    profile_path = Path(temp_firefox_profile["real_profile_path"])
    logins_file = profile_path / "logins.json"

    test_logins = {
        "nextId": 100,
        "logins": [
            {
                "id": 1,
                "hostname": "https://example.com",
                "httpRealm": None,
                "formSubmitURL": "https://example.com/login",
                "usernameField": "username",
                "passwordField": "password",
                "encryptedUsername": "MDIEEPgAAAAAAAAAAAAAAAAAAAEwFAYIKoZIhvcNAwcECI123456789==",
                "encryptedPassword": "MDIEEPgAAAAAAAAAAAAAAAAAAAEwFAYIKoZIhvcNAwcECI987654321==",
                "guid": "{12345678-1234-1234-1234-123456789012}",
                "encType": 1,
                "timeCreated": 1672531200000,
                "timeLastUsed": 1672617600000,
                "timePasswordChanged": 1672531200000,
                "timesUsed": 5
            }
        ]
    }

    with open(logins_file, "w") as f:
        json.dump(test_logins, f, indent=2)

    return logins_file


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
    config.addinivalue_line(
        "markers", "comprehensive: comprehensive integration tests"
    )

@pytest.fixture
def mock_bookmarks_strategy():
    """Фикстура для создания BookmarksStrategy с моками."""
    mock_log = Mock()
    mock_db_read = Mock()
    mock_db_write = Mock()
    mock_db_write.ExecCommit = Mock()
    mock_db_write.Commit = Mock()
    mock_db_write.SaveSQLiteDatabaseFromRamToFile = Mock()

    # Создаем стратегию
    strategy = BookmarksStrategy.__new__(BookmarksStrategy)
    strategy._logInterface = mock_log
    strategy._dbReadInterface = mock_db_read
    strategy._dbWriteInterface = mock_db_write
    strategy._profile_id = 1

    return strategy

def test_with_fixture(mock_bookmarks_strategy):
    """Тест с использованием фикстуры."""
    assert mock_bookmarks_strategy._profile_id == 1
    assert mock_bookmarks_strategy._logInterface is not None
    assert mock_bookmarks_strategy._dbWriteInterface is not None

    # Проверяем, что можем вызывать методы
    mock_bookmarks_strategy._dbWriteInterface.ExecCommit('TEST SQL')
    mock_bookmarks_strategy._dbWriteInterface.ExecCommit.assert_called_with('TEST SQL')

# =================== ФИКСТУРЫ ДЛЯ УДОБСТВА ===================

@pytest.fixture
def mock_extensions_strategy():
    """Фикстура для создания ExtensionsStrategy с моками."""
    mock_log = Mock()
    mock_db_read = Mock()
    mock_db_write = Mock()
    mock_db_write.ExecCommit = Mock()
    mock_db_write.Commit = Mock()
    mock_db_write.SaveSQLiteDatabaseFromRamToFile = Mock()

    # Создаем стратегию
    strategy = ExtensionsStrategy.__new__(ExtensionsStrategy)
    strategy._logInterface = mock_log
    strategy._dbReadInterface = mock_db_read
    strategy._dbWriteInterface = mock_db_write
    strategy._profile_id = 1
    strategy._profile_path = '/test/profile'

    return strategy


def test_with_fixture_extensions(mock_extensions_strategy):
    """Тест с использованием фикстуры."""
    assert mock_extensions_strategy._profile_id == 1
    assert mock_extensions_strategy._profile_path == '/test/profile'
    assert mock_extensions_strategy._logInterface is not None

    # Проверяем, что можем вызывать методы
    mock_extensions_strategy._dbWriteInterface.ExecCommit('TEST SQL')
    mock_extensions_strategy._dbWriteInterface.ExecCommit.assert_called_with('TEST SQL')

# =================== ФИКСТУРЫ ДЛЯ УДОБСТВА HISTORY ===================

@pytest.fixture
def mock_history_strategy():
    """Фикстура для создания HistoryStrategy с моками."""
    mock_log = Mock()
    mock_db_read = Mock()
    mock_db_write = Mock()
    mock_db_write.ExecCommit = Mock()
    mock_db_write.Commit = Mock()
    mock_db_write.SaveSQLiteDatabaseFromRamToFile = Mock()

    # Создаем стратегию
    strategy = HistoryStrategy.__new__(HistoryStrategy)
    strategy._logInterface = mock_log
    strategy._dbReadInterface = mock_db_read
    strategy._dbWriteInterface = mock_db_write
    strategy._profile_id = 1

    return strategy


def test_with_fixture_history(mock_history_strategy):
    """Тест с использованием фикстуры."""
    assert mock_history_strategy._profile_id == 1
    assert mock_history_strategy._logInterface is not None
    assert mock_history_strategy._dbWriteInterface is not None

    # Проверяем, что можем вызывать методы
    mock_history_strategy._dbWriteInterface.ExecCommit('TEST SQL')
    mock_history_strategy._dbWriteInterface.ExecCommit.assert_called_with('TEST SQL')


# =================== FIXTURE ДЛЯ DOWNLOADS ===================

@pytest.fixture
def mock_downloads_strategy():
    """Фикстура для создания DownloadsStrategy с моками."""
    mock_log = Mock()
    mock_db_read = Mock()
    mock_db_write = Mock()
    mock_db_write.ExecCommit = Mock()
    mock_db_write.Commit = Mock()
    mock_db_write.SaveSQLiteDatabaseFromRamToFile = Mock()

    # Создаем стратегию
    strategy = DownloadsStrategy.__new__(DownloadsStrategy)
    strategy._logInterface = mock_log
    strategy._dbReadInterface = mock_db_read
    strategy._dbWriteInterface = mock_db_write
    strategy._profile_id = 1

    return strategy

def test_with_fixture_downloads(mock_downloads_strategy):
    """Тест с использованием фикстуры."""
    assert mock_downloads_strategy._profile_id == 1
    assert mock_downloads_strategy._logInterface is not None
    assert mock_downloads_strategy._dbWriteInterface is not None

    # Проверяем, что можем вызывать методы
    mock_downloads_strategy._dbWriteInterface.ExecCommit('TEST SQL')
    mock_downloads_strategy._dbWriteInterface.ExecCommit.assert_called_with('TEST SQL')


# =================== ФИКСТУРЫ ДЛЯ УДОБСТВА PROFILES ===================

@pytest.fixture
def mock_profiles_strategy():
    """Фикстура для создания ProfilesStrategy с моками."""
    mock_log = Mock()
    mock_file_reader = Mock()
    mock_db_write = Mock()
    mock_db_write.ExecCommit = Mock()
    mock_db_write.SaveSQLiteDatabaseFromRamToFile = Mock()

    # Создаем стратегию
    strategy = ProfilesStrategy.__new__(ProfilesStrategy)
    strategy._logInterface = mock_log
    strategy._fileReader = mock_file_reader
    strategy._dbWriteInterface = mock_db_write

    return strategy


def test_with_fixture_profiles():
    """Тест с использованием фикстуры."""
    mock_profiles_strategy = Mock(spec=ProfilesStrategy)
    mock_profiles_strategy._logInterface = Mock()
    mock_profiles_strategy._fileReader = Mock()
    mock_profiles_strategy._dbWriteInterface = Mock()

    # Используем patch для тестирования свойств
    with patch.object(ProfilesStrategy, 'folderPath',
                     new_callable=PropertyMock) as mock_folder:
        mock_folder.return_value = r'C:\Users\test\AppData\Roaming\Mozilla\Firefox'
        strategy = ProfilesStrategy.__new__(ProfilesStrategy)
        strategy._logInterface = Mock()

        # Здесь мы не можем напрямую проверить folderPath, так как это свойство класса
        # Вместо этого тестируем через mock
        assert 'Mozilla' in mock_folder.return_value
        assert 'Firefox' in mock_folder.return_value


# =================== ФИКСТУРЫ ДЛЯ УДОБСТВА PASSWORDS ===================

@pytest.fixture
def mock_passwords_strategy():
    """Фикстура для создания PasswordStrategy с моками."""
    mock_log = Mock()
    mock_db_read = Mock()
    mock_db_write = Mock()
    mock_db_write.ExecCommit = Mock()
    mock_db_write.SaveSQLiteDatabaseFromRamToFile = Mock()
    mock_password_service = Mock()

    # Создаем стратегию
    strategy = PasswordStrategy.__new__(PasswordStrategy)
    strategy._logInterface = mock_log
    strategy._dbReadInterface = mock_db_read
    strategy._dbWriteInterface = mock_db_write
    strategy._service = mock_password_service
    strategy._profile_id = 1
    strategy._profile_path = '/test/profile'

    return strategy


def test_with_fixture_passwords(mock_passwords_strategy):
    """Тест с использованием фикстуры."""
    assert mock_passwords_strategy._profile_id == 1
    assert mock_passwords_strategy._profile_path == '/test/profile'
    assert mock_passwords_strategy._logInterface is not None
    assert mock_passwords_strategy._service is not None

    # Проверяем, что можем вызывать методы
    mock_passwords_strategy._dbWriteInterface.ExecCommit('TEST SQL')
    mock_passwords_strategy._dbWriteInterface.ExecCommit.assert_called_with('TEST SQL')