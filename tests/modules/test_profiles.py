"""
Тесты для ProfilesStrategy.
"""

import pytest
import os
from unittest.mock import Mock, patch, MagicMock, PropertyMock
from collections import namedtuple

# Имитируем структуры, если импорт не работает
try:
    from Modules.Firefox.Profiles.Strategy import ProfilesStrategy, PathMixin
    from Common.Routines import FileContentReader
except ImportError:
    # Заглушки для тестирования структуры

    class ProfilesStrategy:
        pass


    class PathMixin:
        pass


    class FileContentReader:
        pass


# =================== ТЕСТЫ ДЛЯ PathMixin ===================

def test_path_mixin_firefox_path():
    """Тест пути к Firefox через PathMixin."""

    # Создаем экземпляр миксина
    class TestPathMixin(PathMixin):
        pass

    mixin = TestPathMixin()

    # Проверяем, что путь содержит Firefox
    path = mixin.folderPath
    assert isinstance(path, str)
    assert 'Mozilla' in path
    assert 'Firefox' in path

    # Проверяем, что используется APPDATA
    appdata = os.getenv('APPDATA')
    if appdata:
        assert appdata in path


# =================== ТЕСТЫ ДЛЯ ИНИЦИАЛИЗАЦИИ ===================

def test_profiles_strategy_initialization():
    """Тест инициализации ProfilesStrategy."""
    # Arrange
    mock_log = Mock()
    mock_case_folder = '/test/case'

    # Act - создаем стратегию с патчем для _writeInterface
    with patch.object(ProfilesStrategy, '_writeInterface') as mock_write_interface:
        mock_write_interface.return_value = Mock()
        strategy = ProfilesStrategy(mock_log, mock_case_folder)

    # Assert
    assert strategy._logInterface == mock_log
    assert isinstance(strategy._fileReader, FileContentReader)
    assert strategy._dbWriteInterface is not None


# =================== ТЕСТЫ ДЛЯ СОЗДАНИЯ ТАБЛИЦЫ ===================

def test_create_data_table():
    """Тест метода createDataTable."""
    # Arrange
    mock_log = Mock()
    mock_db_write = Mock()
    mock_db_write.ExecCommit = Mock()
    mock_db_write.SaveSQLiteDatabaseFromRamToFile = Mock()

    # Создаем стратегию с моками
    strategy = ProfilesStrategy.__new__(ProfilesStrategy)
    strategy._logInterface = mock_log
    strategy._dbWriteInterface = mock_db_write

    # Act
    strategy.createDataTable()

    # Assert
    # Проверяем количество вызовов ExecCommit
    assert mock_db_write.ExecCommit.call_count == 2

    # Проверяем первый вызов (создание таблицы)
    first_call_args = mock_db_write.ExecCommit.call_args_list[0][0][0]
    assert 'CREATE TABLE profiles' in first_call_args
    assert 'id INTEGER PRIMARY KEY AUTOINCREMENT' in first_call_args
    assert 'path TEXT' in first_call_args

    # Проверяем второй вызов (создание индекса)
    second_call_args = mock_db_write.ExecCommit.call_args_list[1][0][0]
    assert 'CREATE INDEX idx_profiles_path' in second_call_args
    assert 'on profiles (path)' in second_call_args

    # Проверяем логирование
    mock_log.Info.assert_called_once()
    info_message = mock_log.Info.call_args[0][1]
    assert 'Таблица с профилями создана' in info_message

    # SaveSQLiteDatabaseFromRamToFile не вызывается в createDataTable
    mock_db_write.SaveSQLiteDatabaseFromRamToFile.assert_not_called()


# =================== ТЕСТЫ ДЛЯ СВОЙСТВА fileName ===================

def test_file_name_property():
    """Тест свойства fileName."""
    # Arrange
    strategy = ProfilesStrategy.__new__(ProfilesStrategy)

    # Act & Assert
    assert strategy.fileName == 'profiles.ini'


# =================== ТЕСТЫ ДЛЯ МЕТОДА READ ===================

def test_read_method_with_profiles():
    """Тест метода read с тестовыми профилями."""
    # Arrange
    mock_log = Mock()
    mock_file_reader = Mock()

    # Тестовое содержимое profiles.ini
    test_content = {
        0: '[Profile0]\n',
        1: 'Name=default-release\n',
        2: 'IsRelative=1\n',
        3: 'Path=Profiles/g579o6f5.default-release\n',
        4: '\n',
        5: '[Profile1]\n',
        6: 'Name=default\n',
        7: 'IsRelative=1\n',
        8: 'Path=Profiles/fcy693hd.default\n',
        9: 'Default=1\n',
    }

    mock_file_reader.GetTextFileContent.return_value = (None, None, test_content)

    mock_folder_path = r'C:\Users\test\AppData\Roaming\Mozilla\Firefox'

    strategy = ProfilesStrategy.__new__(ProfilesStrategy)
    strategy._logInterface = mock_log
    strategy._fileReader = mock_file_reader

    # Патчим свойство folderPath вместо установки атрибута
    with patch.object(ProfilesStrategy, 'folderPath', new_callable=PropertyMock) as mock_folder:
        mock_folder.return_value = mock_folder_path

        # Act
        result = list(strategy.read())

    # Assert
    assert len(result) == 2

    # Проверяем первый профиль
    assert 'g579o6f5.default-release' in result[0]
    assert mock_folder_path in result[0]
    assert '\\' in result[0]  # Слеши заменены на обратные

    # Проверяем второй профиль
    assert 'fcy693hd.default' in result[1]

    # Проверяем вызов GetTextFileContent
    mock_file_reader.GetTextFileContent.assert_called_once_with(
        mock_folder_path, 'profiles.ini', includeTimestamps=False
    )

    # Проверяем логирование
    mock_log.Info.assert_called_once()
    info_message = mock_log.Info.call_args[0][1]
    assert 'Считано 2 профилей' in info_message


def test_read_method_no_profiles():
    """Тест метода read без профилей."""
    # Arrange
    mock_log = Mock()
    mock_file_reader = Mock()

    # Пустое содержимое или без Path
    test_content = {
        0: '[General]\n',
        1: 'StartWithLastProfile=1\n',
        2: 'Version=2\n',
    }

    mock_file_reader.GetTextFileContent.return_value = (None, None, test_content)

    strategy = ProfilesStrategy.__new__(ProfilesStrategy)
    strategy._logInterface = mock_log
    strategy._fileReader = mock_file_reader

    # Патчим folderPath
    with patch.object(ProfilesStrategy, 'folderPath', new_callable=PropertyMock) as mock_folder:
        mock_folder.return_value = '/test/path'

        # Act
        result = list(strategy.read())

    # Assert
    assert result == []  # Должен вернуть пустой список

    # Проверяем логирование
    mock_log.Info.assert_called_once()
    info_message = mock_log.Info.call_args[0][1]
    assert 'Считано 0 профилей' in info_message


def test_read_method_path_normalization():
    """Тест нормализации путей в методе read."""
    # Arrange
    mock_log = Mock()
    mock_file_reader = Mock()

    # Тестовое содержимое с разными форматами путей
    test_content = {
        0: 'Path=Profiles/test1.default\n',  # Unix-стиль
        1: 'Path=Profiles\\test2.default\n',  # Windows-стиль
        2: 'Path=Profiles/test3.default-release\n',  # С дефисом
    }

    mock_file_reader.GetTextFileContent.return_value = (None, None, test_content)

    mock_folder_path = r'C:\Users\test\AppData\Roaming\Mozilla\Firefox'

    strategy = ProfilesStrategy.__new__(ProfilesStrategy)
    strategy._logInterface = mock_log
    strategy._fileReader = mock_file_reader

    # Патчим folderPath
    with patch.object(ProfilesStrategy, 'folderPath', new_callable=PropertyMock) as mock_folder:
        mock_folder.return_value = mock_folder_path

        # Act
        result = list(strategy.read())

    # Assert
    assert len(result) == 3

    # Проверяем, что все пути имеют правильный формат
    for path in result:
        assert mock_folder_path in path
        assert '\\' in path  # Все слеши должны быть обратными
        assert '//' not in path  # Не должно быть двойных слешей
        assert '/' not in path  # Не должно быть Unix-слешей


@patch.dict('os.environ', {'APPDATA': r'C:\Users\test\AppData\Roaming'})
def test_folder_path_from_env():
    """Тест получения пути Firefox из переменной окружения."""
    # Arrange
    # Создаем реальный экземпляр через патчирование класса PathMixin
    with patch.object(PathMixin, '_PathMixin__folderPath',
                     f"{r'C:\Users\test\AppData\Roaming'}\\Mozilla\\Firefox"):

        # Создаем стратегию
        strategy = ProfilesStrategy.__new__(ProfilesStrategy)

        # Act & Assert через наследование от PathMixin
        assert hasattr(strategy, 'folderPath')

        # Путь должен содержать APPDATA и Firefox
        path = strategy.folderPath
        assert r'C:\Users\test\AppData\Roaming' in path
        assert 'Mozilla' in path
        assert 'Firefox' in path


# =================== ТЕСТЫ ДЛЯ МЕТОДА WRITE ===================

def test_write_method():
    """Тест метода write с данными."""
    # Arrange
    mock_log = Mock()
    mock_db_write = Mock()
    mock_db_write.ExecCommit = Mock()

    # Тестовые данные
    test_profiles = [
        r'C:\Users\test\AppData\Roaming\Mozilla\Firefox\Profiles\profile1.default',
        r'C:\Users\test\AppData\Roaming\Mozilla\Firefox\Profiles\profile2.default-release',
    ]

    strategy = ProfilesStrategy.__new__(ProfilesStrategy)
    strategy._logInterface = mock_log
    strategy._dbWriteInterface = mock_db_write

    # Act
    strategy.write(test_profiles)

    # Assert
    # Проверяем количество вызовов ExecCommit
    assert mock_db_write.ExecCommit.call_count == len(test_profiles)

    # Проверяем первый вызов
    first_call = mock_db_write.ExecCommit.call_args_list[0]
    assert first_call[0][0] == 'INSERT INTO profiles (path) VALUES (?)'
    assert first_call[0][1] == (test_profiles[0],)

    # Проверяем второй вызов
    second_call = mock_db_write.ExecCommit.call_args_list[1]
    assert second_call[0][0] == 'INSERT INTO profiles (path) VALUES (?)'
    assert second_call[0][1] == (test_profiles[1],)

    # Проверяем логирование
    mock_log.Info.assert_called_once()
    info_message = mock_log.Info.call_args[0][1]
    assert 'Все профили загружены в таблицу' in info_message


def test_write_empty_list():
    """Тест метода write с пустым списком."""
    # Arrange
    mock_log = Mock()
    mock_db_write = Mock()
    mock_db_write.ExecCommit = Mock()

    strategy = ProfilesStrategy.__new__(ProfilesStrategy)
    strategy._logInterface = mock_log
    strategy._dbWriteInterface = mock_db_write

    # Act
    strategy.write([])

    # Assert
    # Не должно быть вызовов ExecCommit
    mock_db_write.ExecCommit.assert_not_called()

    # Но логирование должно быть
    mock_log.Info.assert_called_once()
    info_message = mock_log.Info.call_args[0][1]
    assert 'Все профили загружены в таблицу' in info_message


# =================== ТЕСТЫ ДЛЯ МЕТОДА EXECUTE ===================

def test_execute_method():
    """Тест метода execute."""
    # Arrange
    mock_log = Mock()
    mock_db_write = Mock()
    mock_db_write.SaveSQLiteDatabaseFromRamToFile = Mock()

    # Мок для read
    test_profiles = [
        r'C:\Users\test\AppData\Roaming\Mozilla\Firefox\Profiles\test1.default',
        r'C:\Users\test\AppData\Roaming\Mozilla\Firefox\Profiles\test2.default-release',
    ]

    strategy = ProfilesStrategy.__new__(ProfilesStrategy)
    strategy._logInterface = mock_log
    strategy._dbWriteInterface = mock_db_write

    # Патчим методы
    with patch.object(ProfilesStrategy, 'read') as mock_read, \
            patch.object(ProfilesStrategy, 'write') as mock_write:
        mock_read.return_value = test_profiles
        mock_executor = Mock()

        # Act
        strategy.execute(mock_executor)

        # Assert
        mock_read.assert_called_once()
        mock_write.assert_called_once_with(test_profiles)

        # Проверяем сохранение БД
        mock_db_write.SaveSQLiteDatabaseFromRamToFile.assert_called_once()


def test_execute_method_with_empty_profiles():
    """Тест метода execute без профилей."""
    # Arrange
    mock_log = Mock()
    mock_db_write = Mock()
    mock_db_write.SaveSQLiteDatabaseFromRamToFile = Mock()

    strategy = ProfilesStrategy.__new__(ProfilesStrategy)
    strategy._logInterface = mock_log
    strategy._dbWriteInterface = mock_db_write

    # Патчим методы
    with patch.object(ProfilesStrategy, 'read') as mock_read, \
            patch.object(ProfilesStrategy, 'write') as mock_write:
        mock_read.return_value = []  # Пустые профили
        mock_executor = Mock()

        # Act
        strategy.execute(mock_executor)

        # Assert
        mock_read.assert_called_once()
        mock_write.assert_called_once_with([])  # write вызывается с пустым списком

        # Проверяем сохранение БД
        mock_db_write.SaveSQLiteDatabaseFromRamToFile.assert_called_once()


# =================== ИНТЕГРАЦИОННЫЕ ТЕСТЫ ===================

def test_full_flow_integration():
    """Интеграционный тест полного потока работы."""
    # Arrange
    mock_log = Mock()
    mock_file_reader = Mock()
    mock_db_write = Mock()
    mock_db_write.ExecCommit = Mock()
    mock_db_write.SaveSQLiteDatabaseFromRamToFile = Mock()

    # Тестовые данные
    test_ini_content = {
        0: '[Profile0]\n',
        1: 'Name=default\n',
        2: 'Path=Profiles/testprofile.default\n',
        3: '\n',
        4: '[Profile1]\n',
        5: 'Name=work\n',
        6: 'Path=Profiles/workprofile.default-release\n',
    }

    mock_file_reader.GetTextFileContent.return_value = (None, None, test_ini_content)

    mock_folder_path = r'C:\FirefoxData'

    strategy = ProfilesStrategy.__new__(ProfilesStrategy)
    strategy._logInterface = mock_log
    strategy._fileReader = mock_file_reader
    strategy._dbWriteInterface = mock_db_write

    # Патчим folderPath
    with patch.object(ProfilesStrategy, 'folderPath',
                     new_callable=PropertyMock) as mock_folder:
        mock_folder.return_value = mock_folder_path

        # Act - полный цикл
        strategy.createDataTable()
        profiles = list(strategy.read())
        strategy.write(profiles)

        # Assert
        # Проверяем createDataTable
        assert mock_db_write.ExecCommit.call_count >= 2

        # Проверяем read
        assert len(profiles) == 2
        assert all(mock_folder_path in p for p in profiles)
        assert 'testprofile.default' in profiles[0]
        assert 'workprofile.default-release' in profiles[1]

        # Проверяем write (вызывался ExecCommit для каждого профиля + для таблицы)
        total_calls = mock_db_write.ExecCommit.call_count
        assert total_calls >= 4  # 2 для таблицы + 2 для профилей


if __name__ == '__main__':
    pytest.main(['-v', __file__])