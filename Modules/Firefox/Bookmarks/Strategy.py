import asyncio
import sqlite3
from asyncio import Task
from collections import namedtuple
from typing import Iterable

from Modules.Firefox.interfaces.Strategy import StrategyABC, Generator, Metadata

Bookmark = namedtuple(
    'Bookmark',
    'id type fk parent position title date_added last_modified profile_id'
)


class BookmarksStrategy(StrategyABC):

    def __init__(self, metadata: Metadata) -> None:
        self._logInterface = metadata.logInterface
        self._dbReadInterface = metadata.dbReadInterface
        self._dbWriteInterface = metadata.dbWriteInterface
        self._profile_id = metadata.profileId

    def read(self) -> Generator[list[Bookmark], None, None]:
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
        self._dbWriteInterface._cursor.executemany(
            '''INSERT OR REPLACE INTO bookmarks 
               (id, type, place, parent, position, title, date_added, last_modified, profile_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
            butch
        )
        self._dbWriteInterface.Commit()
        self._logInterface.Info(type(self), f'Группа из {len(butch)} закладок успешно загружена')

    async def execute(self, tasks: list[Task]) -> None:
        for batch in self.read():
            task = asyncio.create_task(self.write(batch))
            tasks.append(task)
            await task

