from __future__ import annotations

from typing import Generator

from Common.Routines import _AbstractLocalDatabaseClass
from Interfaces.LogInterface import LogInterface
from Modules.Firefox.Mixins.PathMixin import PathMixin
from collections import namedtuple

class HistoryReader(PathMixin):

    def __init__(self, logInterface: LogInterface, dbInterface: _AbstractLocalDatabaseClass) -> None:
        self.logInterface = logInterface
        self.dbInterface = dbInterface
        super().__init__()

    def getHistory(self) -> Generator['History', None, None]:
        History = namedtuple(
            'History',
            'id url title visit_count typed last_visit_date'
        )
        cursor = self.dbInterface._cursor.execute(
            '''SELECT id, url, title, visit_count, typed, last_visit_date FROM moz_places'''

        )
        def generateRecords():
            while True:
                batch = cursor.fetchmany(500)
                if not batch:
                    break
                yield [History(*row) for row in batch]
        return generateRecords()