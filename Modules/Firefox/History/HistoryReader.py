from __future__ import annotations

import sqlite3
from typing import Generator

from Common.Routines import SQLiteDatabaseInterface
from Interfaces.LogInterface import LogInterface
from Modules.Firefox.Mixins.PathMixin import PathMixin
from collections import namedtuple
from Modules.Firefox.interfaces.ReaderInterface import ReaderABC
History = namedtuple(
    'History',
    'url title visit_count typed last_visit_date profile_id'
)

class HistoryReader(ReaderABC, PathMixin):

    def __init__(self, logInterface: LogInterface, dbInterface: SQLiteDatabaseInterface, profile_id) -> None:
        self.logInterface = logInterface
        self.dbInterface = dbInterface
        self.profile_id = profile_id
        super().__init__()

    def read(self) -> Generator[list[History], None, None]:
        try:
            cursor = self.dbInterface._cursor.execute(
                '''SELECT url, title, visit_count, typed, last_visit_date FROM moz_places'''

            )
            while True:
                batch = self.dbInterface._cursor.fetchmany(500)
                if not batch:
                    break
                yield [History(*row, profile_id=self.profile_id) for row in batch]
        except sqlite3.OperationalError:
            self.logInterface.Warn(type(self), f'{self.profile_id} не может быт считан (не активен)')