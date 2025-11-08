from Common.Routines import SQLiteDatabaseInterface
from Interfaces.LogInterface import LogInterface
from Modules.Firefox.interfaces.WriterInterface import WriterABC

class HistoryWriter(WriterABC):

    def __init__(self, logInterface: LogInterface, dbInterface: SQLiteDatabaseInterface) -> None:
        self.logInterface = logInterface
        self.dbInterface = dbInterface

    async def write(self, butch) -> None:
        self.dbInterface._cursor.executemany(
            '''INSERT INTO history (url, title, visit_count,
            typed, last_visit_date, profile_id) VALUES (?, ?, ?, ?, ?, ?)''',
            butch
        )
        self.dbInterface.Commit()
        self.logInterface.Info(type(self), 'Группа записей успешно загружена')
