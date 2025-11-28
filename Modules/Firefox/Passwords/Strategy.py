"""
Модуль стратегии извлечения паролей Firefox

Этот модуль реализует стратегию для чтения сохранённых паролей
из профиля Firefox с использованием NSS библиотеки для расшифровки.

Использует PasswordService для расшифровки зашифрованных паролей.
"""

import asyncio
from asyncio import Task
from collections import namedtuple
from typing import Iterable
from Modules.Firefox.Passwords.PasswordService import PasswordService
from Modules.Firefox.interfaces.Strategy import StrategyABC, Generator, Metadata

# Именованный кортеж для маппинга полей паролей
Password = namedtuple('Password', 'url user password profile_id')

class PasswordStrategy(StrategyABC):
    """
    Стратегия для извлечения паролей из Firefox.
    
    Использует PasswordService для расшифровки паролей, хранящихся
    в logins.json или signons.sqlite. Поддерживает батчированую
    запись в БД для оптимизации.
    
    Пароли хранятся зашифрованными с использованием NSS (Network Security Services).
    Требуется доступ к nss3.dll (на Windows) или libnss3.so (на Linux).
    """

    def __init__(self, metadata: Metadata) -> None:
        """
        Инициализирует стратегию паролей.
        
        Args:
            metadata: Именованный кортеж с метаинформацией профиля
        """
        self._logInterface = metadata.logInterface
        self._dbReadInterface = metadata.dbReadInterface
        self._dbWriteInterface = metadata.dbWriteInterface
        self._profile_id = metadata.profileId
        self._profile_path = metadata.profilePath
        self._service = PasswordService(self._profile_path, self._logInterface)

    def read(self) -> Generator[list[tuple[str, str, str, int]], None, None]:
        """
        Читает и расшифровывает пароли из профиля.
        
        Извлекает пароли из logins.json (современный формат) или
        signons.sqlite (старый формат), расшифровывает их и возвращает
        батчами по 500 записей.
        
        Yields:
            Батчи по 500 записей (url, user, password, profile_id)
        
        Warns:
            Если пароли не найдены или при ошибке чтения
        """
        try:
            all_pw = self._service.get_passwords()
            if not all_pw:
                self._logInterface.Warn(type(self), 'Пароли не найдены')
                return
            batch_size = 500
            batch: list[tuple[str, str, str, int]] = []
            for rec in all_pw:
                batch.append((rec['url'], rec['user'], rec['password'], self._profile_id))
                if len(batch) >= batch_size:
                    yield batch
                    batch = []
            if batch:
                yield batch
            self._logInterface.Info(type(self), f'Найдено {len(all_pw)} паролей')
        except Exception as e:
            self._logInterface.Warn(type(self), f'Ошибка при чтении паролей: {e}')

    async def write(self, batch: Iterable[tuple]) -> None:
        """
        Записывает батч паролей в таблицу passwords.
        
        Использует транзакцию для обеспечения целостности данных.
        INSERT OR IGNORE пропускает дубликаты (same url/user/password).
        
        Args:
            batch: Итерируемая коллекция кортежей (url, user, password, profile_id)
        """
        cursor = self._dbWriteInterface._cursor
        conn = self._dbWriteInterface._connection
        try:
            conn.execute("BEGIN")
            cursor.executemany(
                '''INSERT OR IGNORE INTO passwords (url, user, password, profile_id) VALUES (?, ?, ?, ?)''',
                batch
            )
            conn.commit()
        except Exception as e:
            conn.rollback()
            self._logInterface.Error(type(self), f"Ошибка записи батча: {e}")
        else:
            self._logInterface.Info(type(self), f'Группа записей успешно загружена')

    async def execute(self, tasks: list[Task]) -> None:
        """
        Главный метод выполнения стратегии.
        
        Читает все батчи паролей и запускает асинхронную запись каждого батча.
        
        Args:
            tasks: Список асинхронных задач для добавления новых задач
        """
        for batch in self.read():
            task = asyncio.create_task(self.write(batch))
            tasks.append(task)
