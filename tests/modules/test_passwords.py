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

    # Проверяем переданные данные
    data = mock_cursor.executemany.call_args[0][1]
    assert len(data) == 2
    assert data[0] == ('https://site1.com', 'user1', 'pass1', 1)



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
    strategy.timestamp = "test_timestamp"

    # Патчим методы
    with patch.object(PasswordStrategy, 'createDataTable') as mock_create_table, \
            patch.object(PasswordStrategy, 'read') as mock_read, \
            patch.object(PasswordStrategy, 'write') as mock_write:
        # Настраиваем read для возврата батчей
        test_batch_1 = [('url1', 'user1', 'pass1', 1)]
        test_batch_2 = [('url2', 'user2', 'pass2', 1)]
        mock_read.return_value = [test_batch_1, test_batch_2]

        # Act
        strategy.execute()

        # Assert
        # Проверяем, что методы были вызваны
        mock_create_table.assert_called_once()
        mock_read.assert_called_once()

        # Проверяем, что write вызывался для каждого батча
        assert mock_write.call_count == 2  # <-- Два батча

        # Проверяем аргументы вызовов write
        write_calls = mock_write.call_args_list
        assert write_calls[0][0][0] == test_batch_1
        assert write_calls[1][0][0] == test_batch_2

        # Проверяем сохранение БД
        mock_db_write.SaveSQLiteDatabaseFromRamToFile.assert_called_once()

if __name__ == '__main__':
    pytest.main(['-v', __file__])