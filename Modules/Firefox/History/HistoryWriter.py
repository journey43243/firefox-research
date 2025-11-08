from Common.Routines import _AbstractLocalDatabaseClass
from Interfaces.LogInterface import LogInterface

class HistoryWriter:

    def __init__(self,logInterface: LogInterface,dbInterface: _AbstractLocalDatabaseClass) -> None:
        self.logInterface = logInterface
        self.dbInterface = dbInterface

    def writeHistory(self, butch) -> None:
        self.dbInterface._cursor.executemany(
            '''INSERT INTO history VALUES (?, ?, ?, ?, ?, ?)''',
            butch
        )
        self.dbInterface.Commit()
        self.logInterface.Info('Группа записей успешно загружена')