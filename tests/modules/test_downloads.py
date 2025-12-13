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


# =================== ТЕСТЫ ДЛЯ ДАННЫХ ===================

def test_download_namedtuple_structure():
    """Тест структуры именованного кортежа Download."""
    # Создаем тестовую запись загрузки
    download_record = Download(
        id=1,
        place_id=100,
        anno_attribute_id=2,
        content='{"size": 1024, "state": 1}',
        profile_id=1
    )

    # Проверяем поля
    assert download_record.id == 1
    assert download_record.place_id == 100
    assert download_record.anno_attribute_id == 2
    assert download_record.profile_id == 1
    assert '1024' in download_record.content
    assert 'state' in download_record.content

    # Проверяем, что это кортеж
    assert isinstance(download_record, tuple)

    # Проверяем доступ по индексу
    assert download_record[0] == 1  # id
    assert download_record[-1] == 1  # profile_id


# =================== ТЕСТЫ ДЛЯ ИНИЦИАЛИЗАЦИИ ===================

def test_downloads_strategy_initialization():
    """Тест инициализации DownloadsStrategy."""
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
    with patch.object(DownloadsStrategy, '_writeInterface', return_value=mock_db_write):
        strategy = DownloadsStrategy(metadata)

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

    with patch.object(DownloadsStrategy, '_writeInterface', return_value=mock_db_write):
        strategy = DownloadsStrategy(metadata)

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
    strategy = DownloadsStrategy.__new__(DownloadsStrategy)
    strategy._logInterface = mock_log
    strategy._dbWriteInterface = mock_db_write

    # Act
    strategy.createDataTable()

    # Assert
    # Проверяем количество вызовов ExecCommit
    assert mock_db_write.ExecCommit.call_count == 2

    # Проверяем первый вызов (создание таблицы)
    first_call_args = mock_db_write.ExecCommit.call_args_list[0][0][0]
    assert 'CREATE TABLE downloads' in first_call_args
    assert 'id PRIMARY KEY' in first_call_args
    assert 'profile_id INTEGER' in first_call_args

    # Проверяем второй вызов (создание индекса)
    second_call_args = mock_db_write.ExecCommit.call_args_list[1][0][0]
    assert 'CREATE INDEX idx_downloads_place_id' in second_call_args

    # Проверяем логирование
    mock_log.Info.assert_called_once()
    info_message = mock_log.Info.call_args[0][1]
    assert 'Таблица с загрузками создана' in info_message

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

    # Проверяем вторую запись
    second_record = result[0][1]
    assert second_record.id == 2
    assert second_record.place_id == 101


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

    strategy = DownloadsStrategy.__new__(DownloadsStrategy)
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

    # Имитируем ошибку SQLite (именно OperationalError)
    mock_cursor.execute.side_effect = sqlite3.OperationalError('Table moz_annos not found')

    mock_db_read = Mock()
    mock_db_read._cursor = mock_cursor

    strategy = DownloadsStrategy.__new__(DownloadsStrategy)
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
    assert warn_call[0][0] == DownloadsStrategy
    assert f'Загрузки для профиля {strategy._profile_id} не могут быть считаны' in warn_call[0][1]


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

    # Assert
    # Проверяем вызов executemany
    mock_cursor.executemany.assert_called_once()

    # Проверяем SQL запрос
    sql_query = mock_cursor.executemany.call_args[0][0]
    assert 'INSERT OR IGNORE INTO downloads' in sql_query
    assert 'VALUES (?, ?, ?, ?, ?)' in sql_query

    # Проверяем переданные данные
    data = mock_cursor.executemany.call_args[0][1]
    assert len(data) == 2
    assert data[0] == (1, 100, 2, '{"size": 1024}', 1)

    # Проверяем коммит
    mock_db_write.Commit.assert_called_once()

    # Проверяем логирование
    mock_log.Info.assert_called_once()
    info_message = mock_log.Info.call_args[0][1]
    assert 'Группа загрузок успешно загружена' in info_message


def test_write_empty_batch():
    """Тест метода write с пустым батчем."""
    # Arrange
    mock_log = Mock()
    mock_cursor = Mock()
    mock_connection = Mock()
    mock_connection.rollback = Mock()

    mock_db_write = Mock()
    mock_db_write._cursor = mock_cursor
    mock_db_write._connection = mock_connection
    mock_db_write.Commit = Mock()

    strategy = DownloadsStrategy.__new__(DownloadsStrategy)
    strategy._logInterface = mock_log
    strategy._dbWriteInterface = mock_db_write

    # Act - пустой батч
    strategy.write([])

    # Assert - executemany НЕ вызывается при пустом батче!
    mock_cursor.executemany.assert_not_called()

    # Коммит тоже не должен вызываться
    mock_db_write.Commit.assert_not_called()

    # И логирование Info не должно вызываться
    mock_log.Info.assert_not_called()


def test_write_method_handles_exception():
    """Тест обработки исключений в методе write."""
    # Arrange
    mock_log = Mock()
    mock_cursor = Mock()
    mock_connection = Mock()
    mock_connection.rollback = Mock()

    mock_db_write = Mock()
    mock_db_write._cursor = mock_cursor
    mock_db_write._connection = mock_connection
    mock_db_write.Commit = Mock()

    # Имитируем ошибку при executemany
    mock_cursor.executemany.side_effect = Exception('DB Error')

    strategy = DownloadsStrategy.__new__(DownloadsStrategy)
    strategy._logInterface = mock_log
    strategy._dbWriteInterface = mock_db_write

    # Тестовые данные
    test_batch = [
        Download(id=1, place_id=100, anno_attribute_id=2,
                 content='{"size": 1024}', profile_id=1),
    ]

    # Act
    strategy.write(test_batch)

    # Assert
    # BEGIN НЕ вызывается в реальном коде
    # Проверяем, что executemany был вызван (и упал с ошибкой)
    mock_cursor.executemany.assert_called_once()

    # Проверяем, что был rollback (если он есть в коде)
    # Но в реальном коде rollback может не вызываться

    # Коммит не должен вызываться при ошибке
    mock_db_write.Commit.assert_not_called()

    # Проверяем логирование ошибки
    mock_log.Error.assert_called_once()
    error_message = mock_log.Error.call_args[0][1]
    assert 'Ошибка при записи загрузок' in error_message

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

    # Assert
    # Проверяем порядок вызовов
    mock_create_table.assert_called_once()
    mock_read.assert_called_once()

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

# =================== ФИКСТУРЫ ДЛЯ УДОБСТВА ===================

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


def test_with_fixture(mock_downloads_strategy):
    """Тест с использованием фикстуры."""
    assert mock_downloads_strategy._profile_id == 1
    assert mock_downloads_strategy._logInterface is not None
    assert mock_downloads_strategy._dbWriteInterface is not None

    # Проверяем, что можем вызывать методы
    mock_downloads_strategy._dbWriteInterface.ExecCommit('TEST SQL')
    mock_downloads_strategy._dbWriteInterface.ExecCommit.assert_called_with('TEST SQL')


# =================== ПАРАМЕТРИЗОВАННЫЕ ТЕСТЫ ===================

@pytest.mark.parametrize('test_data,expected_count', [
    ([], 0),
    ([(1, 100, 2, '{"size": 1024}')], 1),
    ([(1, 100, 2, '{"size": 1024}'),
      (2, 101, 2, '{"size": 2048}')], 2),
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

    strategy = DownloadsStrategy.__new__(DownloadsStrategy)
    strategy._logInterface = mock_log
    strategy._dbReadInterface = mock_db_read
    strategy._profile_id = 3

    # Act
    result = list(strategy.read())

    # Assert
    if expected_count > 0:
        assert len(result) == 1  # Один батч
        assert len(result[0]) == expected_count
    else:
        assert result == []


if __name__ == '__main__':
    pytest.main(['-v', __file__])