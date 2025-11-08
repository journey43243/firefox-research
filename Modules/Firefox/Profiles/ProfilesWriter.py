from typing import Iterable

from Common.Routines import _AbstractDatabaseClass
from Interfaces.LogInterface import LogInterface

class ProfilesWriter:

    def __init__(self, logInterface: LogInterface, dbInterface: _AbstractDatabaseClass) -> None:
        self.logInterface = logInterface
        self.dbInterface = dbInterface

    def insertProfiles(self, profiles: Iterable[str]) -> None:
        for record in profiles:
            self.dbInterface._cursor.execute(
                '''INSERT INTO profiles VALUES (?)''', (record,)
            )
        self.logInterface.Info(type(self),'Все профили загружены в таблицу')