import asyncio
import sqlite3
from asyncio import Task
from collections import namedtuple
from typing import Iterable

from Modules.Firefox.interfaces.Strategy import StrategyABC, Generator

Bookmark = namedtuple(
    'Bookmark',
    'id type place parent position title date_added last_modified'
)


class BookmarksStrategy(StrategyABC):

    def __init__(self, logInterface, dbReadInterface, dbWriteInterface, profile_id) -> None:
        self._logInterface = logInterface
        self._dbReadInterface = dbReadInterface
        self._dbWriteInterface = dbWriteInterface
        self._profile_id = profile_id

    def read(self) -> Generator[list[Bookmark], None, None]:
        try:
            cursor = self._dbReadInterface._cursor.execute(
                '''SELECT id, type, fk, parent, position, title, 
                          datetime(dateAdded / 1000000, 'unixepoch') as date_added,
                          datetime(lastModified / 1000000, 'unixepoch') as last_modified
                   FROM moz_bookmarks 
                   WHERE type = 1'''  # type=1 - закладки (исключаем папки и разделители)
            )
            while True:
                batch = cursor.fetchmany(500)
                if not batch:
                    break
                yield [Bookmark(*row) for row in batch]
        except sqlite3.OperationalError as e:
            self._logInterface.Warn(type(self),
                                    f'Закладки для профиля {self._profile_id} не могут быть считаны (не активен или таблица отсутствует): {e}')

    async def write(self, butch: Iterable[tuple]) -> None:
        try:
            self._dbWriteInterface._cursor.executemany(
                '''INSERT INTO bookmarks (id, type, place, parent, position, 
                       title, date_added, last_modified) 
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                butch
            )
            self._dbWriteInterface.Commit()
            self._logInterface.Info(type(self), 'Группа закладок успешно загружена')
        except Exception as e:
            self._logInterface.Error(type(self), f'Ошибка при записи закладок: {e}')

    async def execute(self, tasks: list[Task]) -> None:
        bookmarks_count = 0
        for batch in self.read():
            bookmarks_count += len(batch)
            task = asyncio.create_task(self.write(batch))
            tasks.append(task)

        self._logInterface.Info(type(self),
                                f'Всего обработано {bookmarks_count} закладок для профиля {self._profile_id}')