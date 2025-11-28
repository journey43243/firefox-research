"""
Модуль стратегии извлечения закладок Firefox

Этот модуль реализует стратегию для чтения закладок (сохранённых ссылок)
из файла places.sqlite каждого профиля Firefox.

Таблица: moz_bookmarks (только записи с type = 1, которые представляют URL)
Содержит информацию о каждой закладке:
- ID закладки
- Тип (папка, разделитель, URL)
- Связанный URL
- Родительская папка
- Позиция в иерархии
- Название закладки
- Дата добавления
- Дата последнего изменения
"""

import asyncio
import sqlite3
from asyncio import Task
from collections import namedtuple
from typing import Iterable

from Modules.Firefox.interfaces.Strategy import StrategyABC, Generator, Metadata

# Именованный кортеж для удобства маппинга полей закладок
Bookmark = namedtuple(
    'Bookmark',
    'id type fk parent position title date_added last_modified profile_id'
)

class BookmarksStrategy(StrategyABC):
    """
    Стратегия для извлечения закладок из Firefox.
    
    Читает таблицу moz_bookmarks из places.sqlite и извлекает информацию
    о закладках пользователя, включая названия, связанные URL, даты создания
    и последнего изменения.
    
    Извлекаются только записи с type = 1 (фактические URL, не папки).
    Данные читаются батчами по 500 записей.
    """

    def __init__(self, metadata: Metadata) -> None:
        """
        Инициализирует стратегию закладок.
        
        Args:
            metadata: Именованный кортеж с метаинформацией профиля
        """
        self._logInterface = metadata.logInterface
        self._dbReadInterface = metadata.dbReadInterface
        self._dbWriteInterface = metadata.dbWriteInterface
        self._profile_id = metadata.profileId

    def read(self) -> Generator[list[Bookmark], None, None]:
        """
        Читает закладки из places.sqlite.
        
        Фильтрует по type = 1 (только URL, не папки).
        Конвертирует временные метки Firefox в datetime формат.
        
        Yields:
            Батчи по 500 записей закладок
        
        Raises:
            sqlite3.OperationalError: Если таблица не доступна
        """
        try:
            cursor = self._dbReadInterface._cursor.execute(
                '''SELECT id, type, fk, parent, position, title, 
                          datetime(dateAdded / 1000000, 'unixepoch') as date_added,
                          datetime(lastModified / 1000000, 'unixepoch') as last_modified
                   FROM moz_bookmarks 
                   WHERE type = 1'''
            )
            while True:
                batch = cursor.fetchmany(500)
                if not batch:
                    break
                yield [Bookmark(*row, profile_id=self._profile_id) for row in batch]
        except sqlite3.OperationalError as e:
            self._logInterface.Warn(type(self),
                                    f'Закладки для профиля {self._profile_id} не могут быть считаны: {e}')

    async def write(self, butch: Iterable[tuple]) -> None:
        """
        Записывает батч закладок в таблицу bookmarks.
        
        Использует INSERT OR REPLACE для обновления существующих записей.
        
        Args:
            butch: Итерируемая коллекция закладок для записи
        """
        self._dbWriteInterface._cursor.executemany(
            '''INSERT OR REPLACE INTO bookmarks 
               (id, type, place, parent, position, title, date_added, last_modified, profile_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
            butch
        )
        self._dbWriteInterface.Commit()
        self._logInterface.Info(type(self), f'Группа из {len(butch)} закладок успешно загружена')

    async def execute(self, tasks: list[Task]) -> None:
        """
        Главный метод выполнения стратегии.
        
        Читает все батчи закладок и запускает асинхронную запись.
        
        Args:
            tasks: Список асинхронных задач
        """
        for batch in self.read():
            task = asyncio.create_task(self.write(batch))
            tasks.append(task)
            await task

