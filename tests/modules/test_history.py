"""
Тесты для HistoryStrategy.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from collections import namedtuple
import sqlite3

# Имитируем структуры, если импорт не работает
# В реальном тесте эти импорты должны работать через conftest.py
try:
    from Modules.Firefox.History.Strategy import HistoryStrategy, History
    from Modules.Firefox.interfaces.Strategy import Metadata
except ImportError:
    # Заглушки для тестирования структуры
    History = namedtuple('History', 'url title visit_count typed last_visit_date profile_id')

    class HistoryStrategy:
        pass

    class Metadata:
        pass


# =================== ТЕСТЫ ДЛЯ ДАННЫХ ===================

def test_history_namedtuple_structure():
    """Тест структуры именованного кортежа History."""
    # Создаем тестовую запись истории
    history_record = History(
        url='https://example.com',
        title='Example Website',
        visit_count=5,
        typed=1,
        last_visit_date='2023-12-27 10:30:00',
        profile_id=1
    )

    # Проверяем поля
    assert history_record.url == 'https://example.com'
    assert history_record.title == 'Example Website'
    assert history_record.visit_count == 5
    assert history_record.typed == 1
    assert history_record.profile_id == 1
    assert '2023-12-27' in history_record.last_visit_date

    # Проверяем, что это кортеж
    assert isinstance(history_record, tuple)

    # Проверяем доступ по индексу
    assert history_record[0] == 'https://example.com'
    assert history_record[-1] == 1  # profile_id

    # Проверяем именованный доступ
    assert history_record.url == history_record[0]


# =================== ТЕСТЫ ДЛЯ ИНИЦИАЛИЗАЦИИ ===================

def test_history_strategy_initialization():
    """Тест инициализации HistoryStrategy."""
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
    with patch.object(HistoryStrategy, '_writeInterface', return_value=mock_db_write):
        strategy = HistoryStrategy(metadata)

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

    with patch.object(HistoryStrategy, '_writeInterface', return_value=mock_db_write):
        strategy = HistoryStrategy(metadata)

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
    strategy = HistoryStrategy.__new__(HistoryStrategy)
    strategy._logInterface = mock_log
    strategy._dbWriteInterface = mock_db_write

    # Act
    strategy.createDataTable()

    # Assert
    # Проверяем количество вызовов ExecCommit
    assert mock_db_write.ExecCommit.call_count == 2

    # Проверяем первый вызов (создание таблицы)
    first_call_args = mock_db_write.ExecCommit.call_args_list[0][0][0]
    assert 'CREATE TABLE history' in first_call_args
    assert 'url TEXT' in first_call_args
    assert 'profile_id INTEGER' in first_call_args

    # Проверяем второй вызов (создание индекса)
    second_call_args = mock_db_write.ExecCommit.call_args_list[1][0][0]
    assert 'CREATE INDEX idx_history_url' in second_call_args

    # Проверяем логирование
    mock_log.Info.assert_called_once()
    info_message = mock_log.Info.call_args[0][1]
    assert 'Таблица с историей создана' in info_message

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
        ('https://site1.com', 'Site 1', 3, 1, '2023-12-27 10:00:00'),
        ('https://site2.com', 'Site 2', 5, 0, '2023-12-27 11:00:00'),
    ]
    test_batch_2 = [
        ('https://site3.com', 'Site 3', 1, 1, '2023-12-27 12:00:00'),
    ]

    # Настраиваем поведение курсора
    mock_cursor.fetchmany.side_effect = [test_batch_1, test_batch_2, []]
    mock_cursor.execute.return_value = mock_cursor

    mock_db_read = Mock()
    mock_db_read._cursor = mock_cursor

    strategy = HistoryStrategy.__new__(HistoryStrategy)
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
    assert first_record.url == 'https://site1.com'
    assert first_record.title == 'Site 1'
    assert first_record.visit_count == 3
    assert first_record.profile_id == 7  # Добавлен profile_id

    # Проверяем вторую запись
    second_record = result[0][1]
    assert second_record.url == 'https://site2.com'
    assert second_record.typed == 0  # Проверяем typed=0


@patch('sqlite3.connect')
def test_read_method_empty(mock_sqlite_connect):
    """Тест метода read с пустой БД."""
    # Arrange
    mock_log = Mock()
    mock_cursor = Mock()

    mock_cursor.fetchmany.return_value = []
    mock_cursor.execute.return_value = mock_cursor

    mock_db_read = Mock()
    mock_db_read._cursor = mock_cursor

    strategy = HistoryStrategy.__new__(HistoryStrategy)
    strategy._logInterface = mock_log
    strategy._dbReadInterface = mock_db_read
    strategy._profile_id = 1

    # Act
    result = list(strategy.read())

    # Assert
    assert result == []  # Должен вернуть пустой список


def test_read_method_with_sql_error():
    """Тест обработки SQL ошибок в методе read."""
    mock_log = Mock()
    mock_cursor = Mock()

    # Имитируем ошибку SQL
    mock_cursor.execute.side_effect = sqlite3.OperationalError('Table moz_places not found')

    mock_db_read = Mock()
    mock_db_read._cursor = mock_cursor

    strategy = HistoryStrategy.__new__(HistoryStrategy)
    strategy._logInterface = mock_log
    strategy._dbReadInterface = mock_db_read
    strategy._profile_id = 1

    # Act
    result = list(strategy.read())

    # Assert
    assert result == []  # При ошибке должен вернуть пустой список

    mock_log.Warn.assert_called_once()

    # Проверяем, что вызвано с правильными аргументами
    warn_call = mock_log.Warn.call_args
    assert warn_call[0][0] == HistoryStrategy  # type(self)
    assert f'{strategy._profile_id} не может быть считан' in warn_call[0][1]


# =================== ТЕСТЫ ДЛЯ МЕТОДА WRITE ===================

def test_write_method():
    """Тест метода write."""
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
        History('https://test1.com', 'Test 1', 2, 1, '2023-12-27 10:00:00', 1),
        History('https://test2.com', 'Test 2', 5, 0, '2023-12-27 11:00:00', 1),
    ]

    strategy = HistoryStrategy.__new__(HistoryStrategy)
    strategy._logInterface = mock_log
    strategy._dbWriteInterface = mock_db_write

    # Act
    strategy.write(test_batch)

    # Assert
    # Проверяем вызов executemany
    mock_cursor.executemany.assert_called_once()

    # Проверяем SQL запрос
    sql_query = mock_cursor.executemany.call_args[0][0]
    assert 'INSERT INTO history' in sql_query
    assert 'VALUES (?, ?, ?, ?, ?, ?)' in sql_query

    # Проверяем переданные данные
    data = mock_cursor.executemany.call_args[0][1]
    assert len(data) == 2
    assert data[0] == ('https://test1.com', 'Test 1', 2, 1, '2023-12-27 10:00:00', 1)

    # Проверяем коммит
    mock_db_write.Commit.assert_called_once()

    # Проверяем логирование
    mock_log.Info.assert_called_once()
    info_message = mock_log.Info.call_args[0][1]
    assert 'Группа записей успешно загружена' in info_message


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

    strategy = HistoryStrategy.__new__(HistoryStrategy)
    strategy._logInterface = mock_log
    strategy._dbWriteInterface = mock_db_write

    # Act - пустой батч
    strategy.write([])

    # Assert - executemany ВСЕГДА вызывается, даже с пустым списком
    mock_cursor.executemany.assert_called_once()

    # Проверяем SQL запрос
    sql_call = mock_cursor.executemany.call_args[0][0]
    assert "INSERT INTO history (url, title, visit_count," in sql_call
    assert "VALUES (?, ?, ?, ?, ?, ?)" in sql_call

    # Проверяем данные - должен быть пустой список
    data_call = mock_cursor.executemany.call_args[0][1]
    assert data_call == []  # Пустой список данных

    # Проверяем коммит
    mock_db_write.Commit.assert_called_once()

    # Проверяем логирование
    mock_log.Info.assert_called_once()
    info_message = mock_log.Info.call_args[0][1]
    assert "Группа записей успешно загружена" in info_message


# =================== ТЕСТЫ ДЛЯ МЕТОДА EXECUTE ===================

@patch.object(HistoryStrategy, 'createDataTable')
@patch.object(HistoryStrategy, 'read')
@patch.object(HistoryStrategy, 'write')
def test_execute_method(mock_write, mock_read, mock_create_table):
    """Тест метода execute."""
    # Arrange
    mock_log = Mock()
    mock_db_write = Mock()
    mock_db_write.SaveSQLiteDatabaseFromRamToFile = Mock()

    # Настраиваем read для возврата двух батчей
    test_batch_1 = [History('url1', 'title1', 1, 1, 'date1', 1)]
    test_batch_2 = [History('url2', 'title2', 2, 0, 'date2', 1)]
    mock_read.return_value = [test_batch_1, test_batch_2]

    mock_executor = Mock()

    strategy = HistoryStrategy.__new__(HistoryStrategy)
    strategy._logInterface = mock_log
    strategy._dbWriteInterface = mock_db_write

    # Act
    strategy.execute(mock_executor)

    # Assert
    # Проверяем порядок вызовов
    mock_create_table.assert_called_once()
    mock_read.assert_called_once()
    assert mock_write.call_count == 2  # Два батча

    # Проверяем, что write вызывался с правильными аргументами
    assert mock_write.call_args_list[0][0][0] == test_batch_1
    assert mock_write.call_args_list[1][0][0] == test_batch_2

    # Проверяем сохранение БД
    mock_db_write.SaveSQLiteDatabaseFromRamToFile.assert_called_once()


# =================== ФИКСТУРЫ ДЛЯ УДОБСТВА ===================

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


def test_with_fixture(mock_history_strategy):
    """Тест с использованием фикстуры."""
    assert mock_history_strategy._profile_id == 1
    assert mock_history_strategy._logInterface is not None
    assert mock_history_strategy._dbWriteInterface is not None

    # Проверяем, что можем вызывать методы
    mock_history_strategy._dbWriteInterface.ExecCommit('TEST SQL')
    mock_history_strategy._dbWriteInterface.ExecCommit.assert_called_with('TEST SQL')


if __name__ == '__main__':
    # Для запуска теста напрямую (опционально)
    pytest.main(['-v', __file__])