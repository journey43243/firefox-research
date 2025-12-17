"""
Тесты для DownloadsStrategy.
"""

import pytest
import sqlite3
from unittest.mock import Mock, patch
from collections import namedtuple

# Имитируем структуры, если импорт не работает
try:
    from Modules.Firefox.Downloads.Strategy import DownloadsStrategy, Download
    from Modules.Firefox.interfaces.Strategy import Metadata
except ImportError:
    # Заглушки для тестирования структуры
    Download = namedtuple('Download', 'id place_id anno_attribute_id content profile_id')

    class DownloadsStrategy:
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
    strategy = DownloadsStrategy.__new__(DownloadsStrategy)
    strategy._logInterface = mock_log
    strategy._dbWriteInterface = mock_db_write

    # Act
    strategy.createDataTable()

    # Assert
    # Проверяем количество вызовов ExecCommit
    assert mock_db_write.ExecCommit.call_count == 2

    # Проверяем сохранение БД
    mock_db_write.SaveSQLiteDatabaseFromRamToFile.assert_called_once()


# =================== ТЕСТЫ ДЛЯ МЕТОДА READ ===================

@patch('sqlite3.connect')
def test_read_method_with_data(mock_sqlite_connect):
    """Тест метода read с тестовыми данными."""
    # Arrange
    mock_log = Mock()
    mock_cursor = Mock()
    mock_connection = Mock()

    # Тестовые данные
    test_batch_1 = [
        (1, 100, 2, '{"size": 1024, "state": 1}'),
        (2, 101, 2, '{"size": 2048, "state": 2}'),
    ]
    test_batch_2 = [
        (3, 102, 2, '{"size": 512, "state": 3}'),
    ]

    # Настраиваем поведение курсора
    mock_cursor.fetchmany.side_effect = [test_batch_1, test_batch_2, []]
    mock_cursor.execute.return_value = mock_cursor

    mock_db_read = Mock()
    mock_db_read._cursor = mock_cursor

    strategy = DownloadsStrategy.__new__(DownloadsStrategy)
    strategy._logInterface = mock_log
    strategy._dbReadInterface = mock_db_read
    strategy._profile_id = 7

    # Act
    result = list(strategy.read())

    # Assert
    assert len(result) == 2  # Два батча
    assert len(result[0]) == 2  # Первый батч: 2 записи
    assert len(result[1]) == 1  # Второй батч: 1 запись

    # Проверяем первую запись
    first_record = result[0][0]
    assert first_record.id == 1
    assert first_record.place_id == 100
    assert first_record.profile_id == 7  # Добавлен profile_id
    assert '1024' in first_record.content


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
        Download(id=1, place_id=100, anno_attribute_id=2,
                content='{"size": 1024}', profile_id=1),
        Download(id=2, place_id=101, anno_attribute_id=2,
                content='{"size": 2048}', profile_id=1),
    ]

    strategy = DownloadsStrategy.__new__(DownloadsStrategy)
    strategy._logInterface = mock_log
    strategy._dbWriteInterface = mock_db_write

    # Act
    strategy.write(test_batch)

    # Проверяем переданные данные
    data = mock_cursor.executemany.call_args[0][1]
    assert len(data) == 2
    assert data[0] == (1, 100, 2, '{"size": 1024}', 1)


# =================== ТЕСТЫ ДЛЯ МЕТОДА EXECUTE ===================

@patch.object(DownloadsStrategy, 'createDataTable')
@patch.object(DownloadsStrategy, 'read')
def test_execute_method(mock_read, mock_create_table):
    """Тест метода execute."""
    # Arrange
    mock_log = Mock()
    mock_db_write = Mock()
    mock_db_write.SaveSQLiteDatabaseFromRamToFile = Mock()

    # Настраиваем read для возврата батчей
    test_batch_1 = [
        Download(id=1, place_id=100, anno_attribute_id=2,
                 content='{"size": 1024}', profile_id=1),
    ]
    test_batch_2 = [
        Download(id=2, place_id=101, anno_attribute_id=2,
                 content='{"size": 2048}', profile_id=1),
    ]
    mock_read.return_value = [test_batch_1, test_batch_2]

    mock_executor = Mock()
    mock_executor.submit = Mock()

    strategy = DownloadsStrategy.__new__(DownloadsStrategy)
    strategy._logInterface = mock_log
    strategy._dbWriteInterface = mock_db_write

    # Act
    strategy.execute(mock_executor)


    # Проверяем, что submit вызывался для каждого батча
    assert mock_executor.submit.call_count == 2  # Два батча

    # Проверяем, что submit вызывался с правильными аргументами
    # Первый вызов: submit(strategy.write, test_batch_1)
    submit_call_1 = mock_executor.submit.call_args_list[0]
    assert submit_call_1[0][0] == strategy.write  # Функция write
    assert submit_call_1[0][1] == test_batch_1  # Первый батч

    # Второй вызов
    submit_call_2 = mock_executor.submit.call_args_list[1]
    assert submit_call_2[0][0] == strategy.write
    assert submit_call_2[0][1] == test_batch_2

    # Проверяем сохранение БД
    mock_db_write.SaveSQLiteDatabaseFromRamToFile.assert_called_once()




if __name__ == '__main__':
    pytest.main(['-v', __file__])