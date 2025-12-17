"""
Тесты для BookmarksStrategy.
"""

import pytest
import sqlite3
from unittest.mock import Mock, patch
from collections import namedtuple

# Имитируем структуры, если импорт не работает
try:
    from Modules.Firefox.Bookmarks.Strategy import BookmarksStrategy, Bookmark
    from Modules.Firefox.interfaces.Strategy import Metadata
except ImportError:
    # Заглушки для тестирования структуры
    Bookmark = namedtuple('Bookmark', 'id type fk parent position title date_added last_modified profile_id')


    class BookmarksStrategy:
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
    strategy = BookmarksStrategy.__new__(BookmarksStrategy)
    strategy._logInterface = mock_log
    strategy._dbWriteInterface = mock_db_write

    # Act
    strategy.createDataTable()

    # Assert
    # Проверяем количество вызовов ExecCommit
    assert mock_db_write.ExecCommit.call_count == 1

    # SaveSQLiteDatabaseFromRamToFile не вызывается в createDataTable
    mock_db_write.SaveSQLiteDatabaseFromRamToFile.assert_not_called()


# =================== ТЕСТЫ ДЛЯ МЕТОДА READ ===================

@patch('sqlite3.connect')
def test_read_method_with_data(mock_sqlite_connect):
    """Тест метода read с тестовыми данными."""
    # Arrange
    mock_log = Mock()
    mock_cursor = Mock()
    mock_connection = Mock()

    # Тестовые данные (только type=1 закладки)
    test_batch_1 = [
        (1, 1, 100, 0, 0, 'Bookmark 1', '2023-12-27 10:00:00', '2023-12-27 10:00:00'),
        (2, 1, 101, 0, 1, 'Bookmark 2', '2023-12-27 11:00:00', '2023-12-27 11:00:00'),
    ]
    test_batch_2 = [
        (3, 1, 102, 0, 2, 'Bookmark 3', '2023-12-27 12:00:00', '2023-12-27 12:00:00'),
    ]

    # Настраиваем поведение курсора
    mock_cursor.fetchmany.side_effect = [test_batch_1, test_batch_2, []]
    mock_cursor.execute.return_value = mock_cursor

    mock_db_read = Mock()
    mock_db_read._cursor = mock_cursor

    strategy = BookmarksStrategy.__new__(BookmarksStrategy)
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
    assert first_record.type == 1
    assert first_record.fk == 100
    assert first_record.title == 'Bookmark 1'
    assert first_record.profile_id == 7  # Добавлен profile_id

    # Проверяем вторую запись
    second_record = result[0][1]
    assert second_record.id == 2
    assert second_record.position == 1

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
        Bookmark(id=1, type=1, fk=100, parent=0, position=0,
                 title='Test 1', date_added='2023-12-27 10:00:00',
                 last_modified='2023-12-27 10:00:00', profile_id=1),
        Bookmark(id=2, type=1, fk=101, parent=0, position=1,
                 title='Test 2', date_added='2023-12-27 11:00:00',
                 last_modified='2023-12-27 11:00:00', profile_id=1),
    ]

    strategy = BookmarksStrategy.__new__(BookmarksStrategy)
    strategy._logInterface = mock_log
    strategy._dbWriteInterface = mock_db_write

    # Act
    strategy.write(test_batch)

    # Assert
    # Проверяем вызов executemany
    mock_cursor.executemany.assert_called_once()

    # Проверяем SQL запрос
    sql_query = mock_cursor.executemany.call_args[0][0]
    assert 'INSERT OR REPLACE INTO bookmarks' in sql_query
    assert 'VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)' in sql_query

    # Проверяем переданные данные
    data = mock_cursor.executemany.call_args[0][1]
    assert len(data) == 2
    assert data[0] == (1, 1, 100, 0, 0, 'Test 1', '2023-12-27 10:00:00', '2023-12-27 10:00:00', 1)


# =================== ТЕСТЫ ДЛЯ МЕТОДА EXECUTE ===================

@patch.object(BookmarksStrategy, 'createDataTable')
@patch.object(BookmarksStrategy, 'read')
@patch.object(BookmarksStrategy, 'write')
def test_execute_method(mock_write, mock_read, mock_create_table):
    """Тест метода execute."""
    # Arrange
    mock_log = Mock()
    mock_db_write = Mock()
    mock_db_write.SaveSQLiteDatabaseFromRamToFile = Mock()

    # Настраиваем read для возврата батчей
    test_batch_1 = [
        Bookmark(id=1, type=1, fk=100, parent=0, position=0,
                 title='Bookmark 1', date_added='date1',
                 last_modified='date1', profile_id=1),
    ]
    test_batch_2 = [
        Bookmark(id=2, type=1, fk=101, parent=0, position=1,
                 title='Bookmark 2', date_added='date2',
                 last_modified='date2', profile_id=1),
    ]
    mock_read.return_value = [test_batch_1, test_batch_2]

    mock_executor = Mock()
    mock_executor.submit = Mock()

    strategy = BookmarksStrategy.__new__(BookmarksStrategy)
    strategy._logInterface = mock_log
    strategy._dbWriteInterface = mock_db_write

    # Act
    strategy.execute(mock_executor)

    # Проверяем, что submit вызывался для каждого батча
    assert mock_executor.submit.call_count == 2  # Два батча

    # Проверяем, что submit вызывался с правильными аргументами
    submit_call_1 = mock_executor.submit.call_args_list[0]
    assert submit_call_1[0][0] == strategy.write  # Функция write
    assert submit_call_1[0][1] == test_batch_1  # Первый батч

    submit_call_2 = mock_executor.submit.call_args_list[1]
    assert submit_call_2[0][0] == strategy.write
    assert submit_call_2[0][1] == test_batch_2

    # Проверяем сохранение БД
    mock_db_write.SaveSQLiteDatabaseFromRamToFile.assert_called_once()




if __name__ == '__main__':
    pytest.main(['-v', __file__])