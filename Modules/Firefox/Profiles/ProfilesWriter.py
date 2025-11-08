from typing import Iterable

from Common.Routines import SQLiteDatabaseInterface
from Interfaces.LogInterface import LogInterface

class ProfilesWriter:

    def __init__(self, logInterface: LogInterface, dbInterface: SQLiteDatabaseInterface) -> None:
        self.logInterface = logInterface
        self.dbInterface = dbInterface

    def insertProfiles(self, profiles: Iterable[str]) -> None:
        for record in profiles:
            self.dbInterface.ExecCommit(
                '''INSERT INTO profiles (path) VALUES (?)''', (record, )
            )
        self.logInterface.Info(type(self),'Все профили загружены в таблицу')