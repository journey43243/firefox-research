"""
Тесты для PasswordStrategy.
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from collections import namedtuple
import asyncio

# Имитируем структуры, если импорт не работает
try:
    from Modules.Firefox.Passwords.Strategy import PasswordStrategy, Password
    from Modules.Firefox.interfaces.Strategy import Metadata
    from Modules.Firefox.Passwords.PasswordService import PasswordService
except ImportError:
    # Заглушки для тестирования структуры
    Password = namedtuple('Password', 'url user password profile_id')

    class PasswordStrategy:
        pass

    class Metadata:
        pass

    class PasswordService:
        pass


# =================== ТЕСТЫ ДЛЯ ДАННЫХ ===================

def test_password_namedtuple_structure():
    """Тест структуры именованного кортежа Password."""
    # Создаем тестовую запись пароля
    password_record = Password(
        url='https://example.com',
        user='testuser@example.com',
        password='secret123',
        profile_id=1
    )

    # Проверяем поля
    assert password_record.url == 'https://example.com'
    assert password_record.user == 'testuser@example.com'
    assert password_record.password == 'secret123'
    assert password_record.profile_id == 1

    # Проверяем, что это кортеж
    assert isinstance(password_record, tuple)

    # Проверяем доступ по индексу
    assert password_record[0] == 'https://example.com'
    assert password_record[-1] == 1  # profile_id


# =================== ТЕСТЫ ДЛЯ ИНИЦИАЛИЗАЦИИ ===================

def test_passwords_strategy_initialization():
    """Тест инициализации PasswordStrategy."""
    # Arrange - подготавливаем моки
    mock_log = Mock()
    mock_db_read = Mock()
    mock_db_write = Mock()
    mock_password_service = Mock()

    # Создаем метаданные
    metadata = Metadata(
        logInterface=mock_log,
        dbReadInterface=mock_db_read,
        caseFolder='/test/case',
        profileId=42,
        profilePath='/test/profile'
    )

    # Act - создаем стратегию с патчами
    with patch.object(PasswordStrategy, '_writeInterface', return_value=mock_db_write), \
         patch('Modules.Firefox.Passwords.Strategy.PasswordService', return_value=mock_password_service):

        strategy = PasswordStrategy(metadata)

    # Assert - проверяем
    assert strategy._logInterface == mock_log
    assert strategy._dbReadInterface == mock_db_read
    assert strategy._dbWriteInterface == mock_db_write
    assert strategy._profile_id == 42
    assert strategy._profile_path == '/test/profile'
    assert strategy._service == mock_password_service


@pytest.mark.parametrize('profile_id', [1, 5, 10, 100])
def test_different_profile_ids(profile_id):
    """Параметризованный тест для разных ID профилей."""
    mock_log = Mock()
    mock_db_read = Mock()
    mock_db_write = Mock()
    mock_password_service = Mock()

    metadata = Metadata(
        logInterface=mock_log,
        dbReadInterface=mock_db_read,
        caseFolder='/test/case',
        profileId=profile_id,
        profilePath=f'/test/profile{profile_id}'
    )

    with patch.object(PasswordStrategy, '_writeInterface', return_value=mock_db_write), \
         patch('Modules.Firefox.Passwords.Strategy.PasswordService', return_value=mock_password_service):

        strategy = PasswordStrategy(metadata)

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
    strategy = PasswordStrategy.__new__(PasswordStrategy)
    strategy._logInterface = mock_log
    strategy._dbWriteInterface = mock_db_write

    # Act
    strategy.createDataTable()

    # Assert
    # Проверяем количество вызовов ExecCommit
    assert mock_db_write.ExecCommit.call_count == 2

    # Проверяем SQL запросы
    first_call_args = mock_db_write.ExecCommit.call_args_list[0][0][0]
    assert 'CREATE TABLE IF NOT EXISTS passwords' in first_call_args
    assert 'url TEXT' in first_call_args
    assert 'user TEXT' in first_call_args
    assert 'profile_id INTEGER' in first_call_args
    assert 'UNIQUE(url, user, password)' in first_call_args

    second_call_args = mock_db_write.ExecCommit.call_args_list[1][0][0]
    assert 'CREATE INDEX idx_url_profile_id ON passwords' in second_call_args

    # Проверяем логирование
    mock_log.Info.assert_called_once()
    info_message = mock_log.Info.call_args[0][1]
    assert 'Таблица с паролями успешно создана' in info_message

    # Проверяем сохранение БД
    mock_db_write.SaveSQLiteDatabaseFromRamToFile.assert_called_once()


# =================== ТЕСТЫ ДЛЯ МЕТОДА READ ===================

def test_read_method_with_data():
    """Тест метода read с тестовыми данными."""
    # Arrange
    mock_log = Mock()
    mock_password_service = Mock()

    # Тестовые данные паролей
    test_passwords = [
        {'url': 'https://site1.com', 'user': 'user1@site1.com', 'password': 'pass1'},
        {'url': 'https://site2.com', 'user': 'user2@site2.com', 'password': 'pass2'},
        {'url': 'https://site3.com', 'user': 'user3@site3.com', 'password': 'pass3'},
    ]

    mock_password_service.get_passwords.return_value = test_passwords

    strategy = PasswordStrategy.__new__(PasswordStrategy)
    strategy._logInterface = mock_log
    strategy._service = mock_password_service
    strategy._profile_id = 7

    # Act
    result = list(strategy.read())

    # Assert
    # Должно быть 1 батч (batch_size=500, у нас 3 записи)
    assert len(result) == 1
    assert len(result[0]) == 3

    # Проверяем первую запись
    first_record = result[0][0]
    assert first_record == ('https://site1.com', 'user1@site1.com', 'pass1', 7)

    # Проверяем вторую запись
    second_record = result[0][1]
    assert second_record[0] == 'https://site2.com'
    assert second_record[3] == 7  # profile_id

    # Проверяем логирование
    mock_log.Info.assert_called_once()
    info_message = mock_log.Info.call_args[0][1]
    assert f'Найдено {len(test_passwords)} паролей' in info_message


def test_read_method_multiple_batches():
    """Тест метода read с несколькими батчами (batch_size=500)."""
    # Arrange
    mock_log = Mock()
    mock_password_service = Mock()

    # Создаем 1500 тестовых паролей (3 батча по 500)
    test_passwords = [
        {'url': f'https://site{i}.com', 'user': f'user{i}', 'password': f'pass{i}'}
        for i in range(1500)
    ]

    mock_password_service.get_passwords.return_value = test_passwords

    strategy = PasswordStrategy.__new__(PasswordStrategy)
    strategy._logInterface = mock_log
    strategy._service = mock_password_service
    strategy._profile_id = 1

    # Act
    result = list(strategy.read())

    # Assert
    assert len(result) == 3  # 1500 / 500 = 3 батча
    assert len(result[0]) == 500  # Первый батч полный
    assert len(result[1]) == 500  # Второй батч полный
    assert len(result[2]) == 500  # Третий батч полный

    # Проверяем последний элемент последнего батча
    last_record = result[2][-1]
    assert last_record[0] == 'https://site1499.com'
    assert last_record[3] == 1  # profile_id


def test_read_method_no_passwords():
    """Тест метода read, когда пароли не найдены."""
    # Arrange
    mock_log = Mock()
    mock_password_service = Mock()

    mock_password_service.get_passwords.return_value = []  # Пустой список

    strategy = PasswordStrategy.__new__(PasswordStrategy)
    strategy._logInterface = mock_log
    strategy._service = mock_password_service
    strategy._profile_id = 1

    # Act
    result = list(strategy.read())

    # Assert
    assert result == []  # Должен вернуть пустой список

    # Проверяем логирование
    mock_log.Warn.assert_called_once()
    warn_message = mock_log.Warn.call_args[0][1]
    assert 'Пароли не найдены' in warn_message


def test_read_method_service_exception():
    """Тест обработки исключений в методе read."""
    # Arrange
    mock_log = Mock()
    mock_password_service = Mock()

    # Имитируем ошибку в сервисе
    mock_password_service.get_passwords.side_effect = Exception('Service error')

    strategy = PasswordStrategy.__new__(PasswordStrategy)
    strategy._logInterface = mock_log
    strategy._service = mock_password_service
    strategy._profile_id = 1

    # Act
    result = list(strategy.read())

    # Assert
    assert result == []  # Должен вернуть пустой список

    # Проверяем логирование
    mock_log.Warn.assert_called_once()
    warn_message = mock_log.Warn.call_args[0][1]
    assert 'Ошибка при чтении паролей' in warn_message


# =================== ТЕСТЫ ДЛЯ МЕТОДА WRITE ===================

def test_write_method():
    """Тест метода write с данными."""
    # Arrange
    mock_log = Mock()
    mock_cursor = Mock()
    mock_connection = Mock()
    mock_connection.execute = Mock()  # Для BEGIN
    mock_connection.commit = Mock()

    mock_db_write = Mock()
    mock_db_write._cursor = mock_cursor
    mock_db_write._connection = mock_connection

    # Тестовые данные
    test_batch = [
        ('https://site1.com', 'user1', 'pass1', 1),
        ('https://site2.com', 'user2', 'pass2', 1),
    ]

    strategy = PasswordStrategy.__new__(PasswordStrategy)
    strategy._logInterface = mock_log
    strategy._dbWriteInterface = mock_db_write

    # Act
    strategy.write(test_batch)

    # Assert
    # Проверяем BEGIN транзакции
    mock_connection.execute.assert_called_with("BEGIN")

    # Проверяем вызов executemany
    mock_cursor.executemany.assert_called_once()

    # Проверяем SQL запрос
    sql_query = mock_cursor.executemany.call_args[0][0]
    assert 'INSERT OR IGNORE INTO passwords' in sql_query
    assert 'VALUES (?, ?, ?, ?)' in sql_query

    # Проверяем переданные данные
    data = mock_cursor.executemany.call_args[0][1]
    assert len(data) == 2
    assert data[0] == ('https://site1.com', 'user1', 'pass1', 1)

    # Проверяем коммит
    mock_connection.commit.assert_called_once()

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
    mock_connection.execute = Mock()  # Для BEGIN
    mock_connection.commit = Mock()
    mock_connection.rollback = Mock()

    mock_db_write = Mock()
    mock_db_write._cursor = mock_cursor
    mock_db_write._connection = mock_connection

    strategy = PasswordStrategy.__new__(PasswordStrategy)
    strategy._logInterface = mock_log
    strategy._dbWriteInterface = mock_db_write

    # Act - пустой батч
    strategy.write([])

    # Assert - BEGIN вызывается, executemany вызывается с пустым списком
    mock_connection.execute.assert_called_with("BEGIN")
    mock_cursor.executemany.assert_called_once()

    # Проверяем данные - должен быть пустой список
    data_call = mock_cursor.executemany.call_args[0][1]
    assert data_call == []  # Пустой список данных

    # Проверяем коммит
    mock_connection.commit.assert_called_once()

    # Rollback не должен вызываться
    mock_connection.rollback.assert_not_called()

    # Проверяем логирование
    mock_log.Info.assert_called_once()


def test_write_method_handles_exception():
    """Тест обработки исключений в методе write."""
    # Arrange
    mock_log = Mock()
    mock_cursor = Mock()
    mock_connection = Mock()
    mock_connection.execute = Mock()  # Для BEGIN
    mock_connection.rollback = Mock()

    mock_db_write = Mock()
    mock_db_write._cursor = mock_cursor
    mock_db_write._connection = mock_connection

    # Имитируем ошибку при executemany
    mock_cursor.executemany.side_effect = Exception('DB Error')

    strategy = PasswordStrategy.__new__(PasswordStrategy)
    strategy._logInterface = mock_log
    strategy._dbWriteInterface = mock_db_write

    # Тестовые данные
    test_batch = [
        ('https://site1.com', 'user1', 'pass1', 1),
    ]

    # Act
    strategy.write(test_batch)

    # Assert
    # Проверяем BEGIN транзакции
    mock_connection.execute.assert_called_with("BEGIN")

    # Проверяем, что executemany был вызван (и упал с ошибкой)
    mock_cursor.executemany.assert_called_once()

    # Проверяем, что был rollback
    mock_connection.rollback.assert_called_once()

    # Проверяем логирование ошибки
    mock_log.Error.assert_called_once()
    error_message = mock_log.Error.call_args[0][1]
    assert 'Ошибка записи батча' in error_message


# =================== ТЕСТЫ ДЛЯ МЕТОДА EXECUTE ===================

@pytest.mark.asyncio
async def test_execute_method():
    """Асинхронный тест метода execute."""
    # Arrange
    mock_log = Mock()
    mock_db_write = Mock()
    mock_db_write.SaveSQLiteDatabaseFromRamToFile = Mock()

    # Настраиваем стратегию с моками
    strategy = PasswordStrategy.__new__(PasswordStrategy)
    strategy._logInterface = mock_log
    strategy._dbWriteInterface = mock_db_write
    strategy._profile_id = 1

    # Патчим методы
    with patch.object(PasswordStrategy, 'createDataTable') as mock_create_table, \
            patch.object(PasswordStrategy, 'read') as mock_read, \
            patch.object(PasswordStrategy, 'write', new_callable=AsyncMock) as mock_write:
        # Настраиваем read для возврата батчей
        test_batch_1 = [('url1', 'user1', 'pass1', 1)]
        test_batch_2 = [('url2', 'user2', 'pass2', 1)]
        mock_read.return_value = [test_batch_1, test_batch_2]

        # Список задач
        tasks = []

        # Act
        strategy.execute(tasks)

        # Даем время на выполнение асинхронных задач
        await asyncio.sleep(0.01)

        # Assert
        mock_create_table.assert_called_once()
        mock_read.assert_called_once()

        # Проверяем, что задачи были созданы
        assert len(tasks) == 2
        assert all(isinstance(task, asyncio.Task) for task in tasks)

        # Проверяем, что write вызывался с правильными аргументами
        assert mock_write.call_count == 2
        assert mock_write.call_args_list[0][0][0] == test_batch_1
        assert mock_write.call_args_list[1][0][0] == test_batch_2

        # Проверяем сохранение БД
        mock_db_write.SaveSQLiteDatabaseFromRamToFile.assert_not_called()

def test_execute_method_no_batches():
    """Тест метода execute без батчей."""
    # Arrange
    mock_log = Mock()
    mock_db_write = Mock()
    mock_db_write.SaveSQLiteDatabaseFromRamToFile = Mock()

    strategy = PasswordStrategy.__new__(PasswordStrategy)
    strategy._logInterface = mock_log
    strategy._dbWriteInterface = mock_db_write

    with patch.object(PasswordStrategy, 'createDataTable') as mock_create_table, \
         patch.object(PasswordStrategy, 'read') as mock_read:

        # Пустой read
        mock_read.return_value = []

        tasks = []

        # Act
        strategy.execute(tasks)

        # Assert
        mock_create_table.assert_called_once()
        mock_read.assert_called_once()
        assert len(tasks) == 0


# =================== ФИКСТУРЫ ДЛЯ УДОБСТВА ===================

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


def test_with_fixture(mock_passwords_strategy):
    """Тест с использованием фикстуры."""
    assert mock_passwords_strategy._profile_id == 1
    assert mock_passwords_strategy._profile_path == '/test/profile'
    assert mock_passwords_strategy._logInterface is not None
    assert mock_passwords_strategy._service is not None

    # Проверяем, что можем вызывать методы
    mock_passwords_strategy._dbWriteInterface.ExecCommit('TEST SQL')
    mock_passwords_strategy._dbWriteInterface.ExecCommit.assert_called_with('TEST SQL')


# =================== ПАРАМЕТРИЗОВАННЫЕ ТЕСТЫ ===================

@pytest.mark.parametrize('password_count,expected_batches', [
    (0, 0),      # Нет паролей
    (1, 1),      # 1 пароль - 1 батч
    (499, 1),    # 499 паролей - 1 батч
    (500, 1),    # 500 паролей - 1 батч
    (501, 2),    # 501 пароль - 2 батча
    (1000, 2),   # 1000 паролей - 2 батча
    (1500, 3),   # 1500 паролей - 3 батча
])
def test_batch_splitting_logic(password_count, expected_batches):
    """Тест логики разбиения на батчи (batch_size=500)."""
    # Arrange
    mock_log = Mock()
    mock_password_service = Mock()

    # Создаем тестовые пароли
    test_passwords = [
        {'url': f'https://site{i}.com', 'user': f'user{i}', 'password': f'pass{i}'}
        for i in range(password_count)
    ]

    mock_password_service.get_passwords.return_value = test_passwords

    strategy = PasswordStrategy.__new__(PasswordStrategy)
    strategy._logInterface = mock_log
    strategy._service = mock_password_service
    strategy._profile_id = 1

    # Act
    result = list(strategy.read())

    # Assert
    if password_count == 0:
        assert result == []
    else:
        assert len(result) == expected_batches

        # Проверяем размеры батчей
        total_in_batches = sum(len(batch) for batch in result)
        assert total_in_batches == password_count

        # Проверяем, что последний батч не превышает batch_size
        if result:
            assert len(result[-1]) <= 500


# =================== ТЕСТЫ ДЛЯ УНИКАЛЬНОСТИ ДАННЫХ ===================

def test_unique_constraint_handling():
    """Тест обработки уникальных ограничений в БД."""
    # Этот тест проверяет, что SQL запрос использует INSERT OR IGNORE
    # для обработки дубликатов

    mock_log = Mock()
    mock_cursor = Mock()
    mock_connection = Mock()
    mock_connection.execute = Mock()
    mock_connection.commit = Mock()

    mock_db_write = Mock()
    mock_db_write._cursor = mock_cursor
    mock_db_write._connection = mock_connection

    strategy = PasswordStrategy.__new__(PasswordStrategy)
    strategy._logInterface = mock_log
    strategy._dbWriteInterface = mock_db_write

    # Act
    strategy.write([('url', 'user', 'pass', 1)])

    # Assert
    sql_query = mock_cursor.executemany.call_args[0][0]
    assert 'INSERT OR IGNORE INTO passwords' in sql_query

    # Это гарантирует, что дубликаты (url, user, password) будут проигнорированы





if __name__ == '__main__':
    pytest.main(['-v', __file__])