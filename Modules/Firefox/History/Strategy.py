import asyncio
import sqlite3
from asyncio import Task
from collections import namedtuple
from typing import Iterable

from Modules.Firefox.interfaces.Strategy import StrategyABC, Generator

History = namedtuple(
    'History',
    'url title visit_count typed last_visit_date profile_id'
)

class HistoryStrategy(StrategyABC):

    def __init__(self, logInterface, dbReadInterface, dbWriteInterface, profile_id) -> None:
        self._logInterface = logInterface
        self._dbReadInterface = dbReadInterface
        self._dbWriteInterface = dbWriteInterface
        self._profile_id = profile_id

    def read(self) -> Generator[list[History], None, None]:
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
        self._dbWriteInterface._cursor.executemany(
            '''INSERT INTO history (url, title, visit_count,
            typed, last_visit_date, profile_id) VALUES (?, ?, ?, ?, ?, ?)''',
            butch
        )
        self._dbWriteInterface.Commit()
        self._logInterface.Info(type(self), 'Группа записей успешно загружена')

    async def execute(self, tasks:list[Task]) -> None:
        for batch in self.read():
            task = asyncio.create_task(self.write(batch))
            tasks.append(task)