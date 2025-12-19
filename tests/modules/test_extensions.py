"""
Тесты для ExtensionsStrategy.
"""

import pytest
import json
import os
from unittest.mock import Mock, patch, mock_open
from collections import namedtuple

# Имитируем структуры, если импорт не работает
try:
    from Modules.Firefox.Extensions.Strategy import ExtensionsStrategy, Extension
    from Modules.Firefox.interfaces.Strategy import Metadata
except ImportError:
    # Заглушки для тестирования структуры
    Extension = namedtuple('Extension',
                           'id name version description type active user_disabled install_date '
                           'update_date path source_url permissions location profile_id')


    class ExtensionsStrategy:
        pass


    class Metadata:
        pass


# =================== ТЕСТЫ ДЛЯ СОЗДАНИЯ ТАБЛИЦЫ ===================

def test_create_data_table():
    """Тест метода createDataTable."""
    # Arrange
    mock_log = Mock()
    mock_db_write = Mock()
    mock_db_write.ExecCommit = Mock()
    mock_db_write.SaveSQLiteDatabaseFromRamToFile = Mock()

    # Создаем стратегию с моками
    strategy = ExtensionsStrategy.__new__(ExtensionsStrategy)
    strategy._logInterface = mock_log
    strategy._dbWriteInterface = mock_db_write

    # Act
    strategy.createDataTable()

    # Assert
    # Проверяем количество вызовов ExecCommit
    assert mock_db_write.ExecCommit.call_count == 3

    # Проверяем SQL запросы
    first_call_args = mock_db_write.ExecCommit.call_args_list[0][0][0]
    assert 'CREATE TABLE IF NOT EXISTS extensions' in first_call_args
    assert 'id TEXT PRIMARY KEY' in first_call_args
    assert 'profile_id INTEGER' in first_call_args

    second_call_args = mock_db_write.ExecCommit.call_args_list[1][0][0]
    assert 'CREATE INDEX IF NOT EXISTS idx_extensions_id' in second_call_args

    third_call_args = mock_db_write.ExecCommit.call_args_list[2][0][0]
    assert 'CREATE INDEX IF NOT EXISTS idx_extensions_profile_id' in third_call_args



# =================== ТЕСТЫ ДЛЯ МЕТОДА READ ===================

def test_read_method_with_data():
    """Тест метода read с тестовыми данными."""
    # Arrange
    mock_log = Mock()
    mock_path_exists = Mock(return_value=True)

    # Тестовые данные JSON
    test_json_data = {
        "schemaVersion": 1,
        "addons": [
            {
                "id": "test1@extension.com",
                "type": "extension",
                "defaultLocale": {
                    "name": "Test Extension 1",
                    "description": "Test description 1"
                },
                "version": "1.0.0",
                "active": True,
                "userDisabled": False,
                "installDate": 1704067200000,
                "updateDate": 1704153600000,
                "path": "/path/to/extension1.xpi",
                "sourceURI": "https://addons.mozilla.org/1",
                "userPermissions": {"permissions": ["storage", "tabs"]},
                "location": "app-profile"
            },
            {
                "id": "test2@extension.com",
                "type": "extension",
                "defaultLocale": {
                    "name": "Test Extension 2",
                    "description": "Test description 2"
                },
                "version": "2.0.0",
                "active": False,
                "userDisabled": True,
                "installDate": 1704240000000,
                "updateDate": 1704326400000,
                "path": "/path/to/extension2.xpi",
                "sourceURI": "https://addons.mozilla.org/2",
                "userPermissions": {},
                "location": "user"
            },
            {
                "id": "theme@theme.com",
                "type": "theme",  # Не extension - должно быть пропущено
                "defaultLocale": {"name": "Theme"},
                "version": "1.0.0",
                "active": True
            }
        ]
    }

    strategy = ExtensionsStrategy.__new__(ExtensionsStrategy)
    strategy._logInterface = mock_log
    strategy._profile_id = 7
    strategy._profile_path = '/test/profile'

    # Патчим os.path.exists и open
    with patch('os.path.exists', mock_path_exists), \
            patch('builtins.open', mock_open(read_data=json.dumps(test_json_data))):
        # Act
        result = list(strategy.read())

    # Assert
    assert len(result) == 1  # Один батч
    assert len(result[0]) == 2  # Два расширения (тема пропущена)

    # Проверяем первую запись
    first_extension = result[0][0]
    assert first_extension.id == 'test1@extension.com'
    assert first_extension.name == 'Test Extension 1'
    assert first_extension.version == '1.0.0'
    assert first_extension.type == 'extension'
    assert first_extension.active == 1
    assert first_extension.user_disabled == 0
    assert first_extension.profile_id == 7
    assert 'storage' in first_extension.permissions

    # Проверяем вторую запись
    second_extension = result[0][1]
    assert second_extension.id == 'test2@extension.com'
    assert second_extension.active == 0  # False -> 0
    assert second_extension.user_disabled == 1  # True -> 1

# =================== ТЕСТЫ ДЛЯ МЕТОДА WRITE ===================

def test_write_method():
    """Тест метода write с данными."""
    # Arrange
    mock_log = Mock()
    mock_cursor = Mock()
    mock_connection = Mock()

    mock_db_write = Mock()
    mock_db_write._cursor = mock_cursor
    mock_db_write._connection = mock_connection
    mock_db_write.Commit = Mock()

    # Тестовые данные
    test_batch = [
        Extension(
            id='ext1@test.com', name='Ext 1', version='1.0.0',
            description='Desc 1', type='extension', active=1,
            user_disabled=0, install_date=1704067200000,
            update_date=1704153600000, path='/path1.xpi',
            source_url='https://addons.mozilla.org/1',
            permissions='{"perm": ["storage"]}', location='app-profile',
            profile_id=1
        ),
        Extension(
            id='ext2@test.com', name='Ext 2', version='2.0.0',
            description='Desc 2', type='extension', active=0,
            user_disabled=1, install_date=1704240000000,
            update_date=1704326400000, path='/path2.xpi',
            source_url='https://addons.mozilla.org/2',
            permissions='', location='user',
            profile_id=1
        ),
    ]

    strategy = ExtensionsStrategy.__new__(ExtensionsStrategy)
    strategy._logInterface = mock_log
    strategy._dbWriteInterface = mock_db_write

    # Act
    strategy.write(test_batch)

    # Assert
    # Проверяем вызов executemany
    mock_cursor.executemany.assert_called_once()

    # Проверяем SQL запрос
    sql_query = mock_cursor.executemany.call_args[0][0]
    assert 'INSERT OR IGNORE INTO extensions' in sql_query
    assert 'VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)' in sql_query

    # Проверяем переданные данные
    data = mock_cursor.executemany.call_args[0][1]
    assert len(data) == 2
    assert data[0][0] == 'ext1@test.com'  # id
    assert data[0][5] == 1  # active
    assert data[0][6] == 0  # user_disabled
    assert data[0][13] == 1  # profile_id

# =================== ТЕСТЫ ДЛЯ МЕТОДА EXECUTE ===================

@patch.object(ExtensionsStrategy, 'createDataTable')
@patch.object(ExtensionsStrategy, 'read')
@patch.object(ExtensionsStrategy, 'write')
def test_execute_method(mock_write, mock_read, mock_create_table):
    """Тест метода execute."""
    # Arrange
    mock_log = Mock()
    mock_db_write = Mock()
    mock_db_write.SaveSQLiteDatabaseFromRamToFile = Mock()

    # Настраиваем read для возврата батчей
    test_batch = [
        Extension(
            id='ext1@test.com', name='Ext 1', version='1.0.0',
            description='Desc 1', type='extension', active=1,
            user_disabled=0, install_date=1704067200000,
            update_date=1704153600000, path='/path1.xpi',
            source_url='https://addons.mozilla.org/1',
            permissions='{}', location='app-profile',
            profile_id=1
        ),
    ]
    mock_read.return_value = [test_batch]

    strategy = ExtensionsStrategy.__new__(ExtensionsStrategy)
    strategy._logInterface = mock_log
    strategy._dbWriteInterface = mock_db_write
    strategy.timestamp = "test_timestamp"

    strategy.execute()

    # Assert
    # Проверяем, что методы были вызваны в правильном порядке
    mock_create_table.assert_called_once()
    mock_read.assert_called_once()
    mock_write.assert_called_once_with(test_batch)

    mock_db_write.SaveSQLiteDatabaseFromRamToFile.assert_called_once()

if __name__ == '__main__':
    pytest.main(['-v', __file__])