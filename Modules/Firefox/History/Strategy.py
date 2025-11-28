"""
Модуль стратегии извлечения истории посещений Firefox

Этот модуль реализует стратегию для чтения истории посещений сайтов
из файла places.sqlite каждого профиля Firefox.

Таблица: moz_places
Содержит информацию о каждом посещённом URL с данными:
- URL страницы
- Название страницы
- Количество посещений
- Был ли URL введён вручную
- Время последнего посещения
"""

import asyncio
import sqlite3
from asyncio import Task
from collections import namedtuple
from typing import Iterable

from Modules.Firefox.interfaces.Strategy import StrategyABC, Generator, Metadata

# Именованный кортеж для удобства маппинга полей истории
History = namedtuple(
    'History',
    'url title visit_count typed last_visit_date profile_id'
)

class HistoryStrategy(StrategyABC):
    """
    Стратегия для извлечения истории посещений из Firefox.
    
    Читает таблицу moz_places из places.sqlite и извлекает информацию
    о посещённых сайтах, включая URL, названия страниц, количество
    посещений и время последнего посещения.
    
    Данные читаются батчами по 500 записей для оптимизации памяти.
    """

    def __init__(self, metadata: Metadata) -> None:
        """
        Инициализирует стратегию истории.
        
        Args:
            metadata: Именованный кортеж с метаинформацией:
                - logInterface: Интерфейс логирования
                - dbReadInterface: Интерфейс подключения к places.sqlite
                - dbWriteInterface: Интерфейс для записи в выходную БД
                - profileId: ID профиля в таблице profiles
                - profilePath: Путь к папке профиля
        """
        self._logInterface = metadata.logInterface
        self._dbReadInterface = metadata.dbReadInterface
        self._dbWriteInterface = metadata.dbWriteInterface
        self._profile_id = metadata.profileId

    def read(self) -> Generator[list[History], None, None]:
        """
        Читает историю посещений из places.sqlite.
        
        Конвертирует временные метки Firefox (микросекунды с 1970)
        в стандартный datetime формат (YYYY-MM-DD HH:MM:SS).
        
        Yields:
            Батчи по 500 записей истории
        
        Raises:
            sqlite3.OperationalError: Если таблица не доступна (профиль не активен)
        """
        try:
            cursor = self._dbReadInterface._cursor.execute(
                '''SELECT url, title, visit_count, typed, datetime(last_visit_date / 1000000, 'unixepoch') as last_visit_date FROM moz_places'''
            )
            while True:
                batch = cursor.fetchmany(500)
                if not batch:
                    break
                yield [History(*row, profile_id=self._profile_id) for row in batch]
        except sqlite3.OperationalError:
            self._logInterface.Warn(type(self), f'{self._profile_id} не может быт считан (не активен)')

    async def write(self, butch: Iterable[tuple]) -> None:
        """
        Записывает батч записей истории в таблицу history.
        
        Args:
            butch: Итерируемая коллекция записей для записи
        """
        self._dbWriteInterface._cursor.executemany(
            '''INSERT INTO history (url, title, visit_count,
            typed, last_visit_date, profile_id) VALUES (?, ?, ?, ?, ?, ?)''',
            butch
        )
        self._dbWriteInterface.Commit()
        self._logInterface.Info(type(self), 'Группа записей успешно загружена')

    async def execute(self, tasks: list[Task]) -> None:
        """
        Главный метод выполнения стратегии.
        
        Читает все батчи истории и запускает асинхронную запись каждого батча.
        
        Args:
            tasks: Список асинхронных задач для добавления новых задач
        """
        for batch in self.read():
            task = asyncio.create_task(self.write(batch))
            tasks.append(task)